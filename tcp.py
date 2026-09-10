"""Sigma TCP matchmaking service built on the recovered packet contract."""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import os
import socketserver
import threading
import time
from pathlib import Path
from typing import Callable

from packet_mapping import (
    Frame,
    MM_CANCEL,
    MM_START,
    PROTO_MATCHMAKING,
    decode_frame,
    make_frame,
    matchmaking_start_notification,
    matchmaking_stop_notification,
    matchmaking_success_notification,
    read_varint,
    read_bytes,
)


@dataclass
class WaitingPlayer:
    connection: object
    region: int
    joined_at: float
    game_mode: int = 0
    difficulty: int = 0
    match_mode: int = 0
    map_id: int = 0


class MatchmakingQueue:
    """Thread-safe private-server queue.

    The default policy creates a one-player compatibility match immediately.
    Set `min_players` above one only when a real multi-player game node is
    available; the current client contract does not provide gameplay sync.
    """

    def __init__(self, advertised_addr: str, min_players: int = 1, log: Callable[..., None] | None = None):
        self.advertised_addr = advertised_addr
        self.min_players = max(1, min_players)
        self.log = log or (lambda *_args, **_kwargs: None)
        self._waiting: list[WaitingPlayer] = []
        self._lock = threading.Lock()
        self._next_match_id = int(time.time() * 1000)

    def enqueue(self, player: WaitingPlayer) -> None:
        with self._lock:
            self._waiting.append(player)
            self.log("queue_join", queue_size=len(self._waiting), region=player.region)
            if len(self._waiting) < self.min_players:
                return
            group = self._waiting[: self.min_players]
            del self._waiting[: self.min_players]
        self._create_match(group)

    def cancel(self, connection: object) -> None:
        with self._lock:
            before = len(self._waiting)
            self._waiting = [player for player in self._waiting if player.connection is not connection]
            if before != len(self._waiting):
                self.log("queue_cancel", queue_size=len(self._waiting))

    def _create_match(self, players: list[WaitingPlayer]) -> None:
        with self._lock:
            self._next_match_id += 1
            match_id = self._next_match_id
        for player in players:
            try:
                writer = player.connection
                writer.sendall(make_frame(PROTO_MATCHMAKING, player.region, matchmaking_start_notification(player.game_mode, player.difficulty, player.match_mode)))
                time.sleep(0.15)
                writer.sendall(make_frame(PROTO_MATCHMAKING, player.region, matchmaking_success_notification(self.advertised_addr, match_id, player.game_mode, player.match_mode, player.map_id)))
                self.log("match_success", match_id=match_id, server_addr=self.advertised_addr)
            except (ConnectionError, OSError) as error:
                self.log("match_send_error", match_id=match_id, error=type(error).__name__)

    def stop(self) -> None:
        with self._lock:
            waiting = self._waiting
            self._waiting = []
        for player in waiting:
            try:
                player.connection.sendall(make_frame(PROTO_MATCHMAKING, player.region, matchmaking_stop_notification()))
            except (ConnectionError, OSError):
                pass


def parse_start_request(frame: Frame) -> WaitingPlayer | None:
    if frame.protocol != PROTO_MATCHMAKING or frame.subcommand != MM_START:
        return None
    try:
        _command, offset = read_varint(frame.payload)
        _raw_content, _ = read_bytes(frame.payload, offset)
    except (ValueError, AttributeError):
        return WaitingPlayer(connection=None, region=frame.region, joined_at=time.time())  # type: ignore[arg-type]
    return WaitingPlayer(connection=None, region=frame.region, joined_at=time.time())  # type: ignore[arg-type]


class MatchmakingTCPHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        server: MatchmakingTCPServer = self.server  # type: ignore[assignment]
        peer = f"{self.client_address[0]}:{self.client_address[1]}"
        server.log("connected", peer=peer)
        self.request.settimeout(30)
        buffer = bytearray()
        try:
            while True:
                chunk = self.request.recv(4096)
                if not chunk:
                    return
                buffer.extend(chunk)
                while True:
                    frame = decode_frame(buffer)
                    if frame is None:
                        break
                    server.log("packet", peer=peer, protocol=frame.protocol, region=frame.region, subcommand=frame.subcommand)
                    if frame.protocol != PROTO_MATCHMAKING:
                        continue
                    if frame.subcommand == MM_START:
                        player = parse_start_request(frame) or WaitingPlayer(self.request, frame.region, time.time())
                        player.connection = self.request
                        server.queue.enqueue(player)
                    elif frame.subcommand == MM_CANCEL:
                        server.queue.cancel(self.request)
                        self.request.sendall(make_frame(PROTO_MATCHMAKING, frame.region, matchmaking_stop_notification()))
        except (ConnectionError, OSError, TimeoutError) as error:
            server.log("connection_error", peer=peer, error=type(error).__name__)
        finally:
            server.queue.cancel(self.request)
            server.log("disconnected", peer=peer)


class MatchmakingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, handler, queue: MatchmakingQueue, log):
        super().__init__(address, handler)
        self.queue = queue
        self.log = log


def serve(host: str = "0.0.0.0", port: int = 10101, advertised_addr: str = "127.0.0.1:10101", log: Callable[..., None] | None = None) -> None:
    log = log or (lambda event, **fields: print(event, fields, flush=True))
    queue = MatchmakingQueue(advertised_addr, log=log)
    with MatchmakingTCPServer((host, port), MatchmakingTCPHandler, queue, log) as server:
        log("started", host=host, port=port, advertised_addr=advertised_addr)
        try:
            server.serve_forever()
        finally:
            queue.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sigma TCP matchmaking service")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=10101, type=int)
    parser.add_argument("--advertised-addr", default=os.getenv("SIGMA_GAME_SERVER_ADDR", "127.0.0.1:10101"))
    args = parser.parse_args()
    serve(args.host, args.port, args.advertised_addr)


if __name__ == "__main__":
    main()
