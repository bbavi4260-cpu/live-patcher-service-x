"""Sigma realtime game-node and conservative single-player matchmaker.

The decompiled client exposes a TCPMsgPacket envelope with a one-byte protocol
command, one-byte region, four-byte little-endian payload length, and a
ProtoReq-style payload containing a varint sub-command plus byte data. This
module keeps the old metadata listener behavior and, when enabled, answers the
recovered MATCHMAKING START command with a START_NTF followed by a
MATCHMAKINGSUSS_NTF. It does not decrypt traffic or pretend to implement the
actual gameplay server.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import socketserver
import struct
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from packet_mapping import message_notify

LOG_LOCK = threading.Lock()
MAX_FRAME_BYTES = 65536
TCP_HEADER_SIZE = 6  # command byte + region byte + little-endian uint32 length
MATCHMAKING_PROTOCOL = 3
MATCH_START = 1
MATCH_SUCCESS_NTF = 5
MATCH_START_NTF = 12
MATCH_STOP_NTF = 15


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def write_event(log_path: Path, event: str, **fields: object) -> None:
    row = {"timestamp": utc_now(), "event": event, **fields}
    with LOG_LOCK:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    safe = " ".join(f"{key}={value}" for key, value in fields.items())
    print(f"{row['timestamp']} [GAME_NODE] {event} {safe}".rstrip(), flush=True)


def put_varint(value: int) -> bytes:
    value = int(value)
    if value < 0:
        raise ValueError("varint values must be non-negative")
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def get_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data) and shift <= 63:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return value, offset
        shift += 7
    raise ValueError("invalid or incomplete varint")


def put_bytes(data: bytes) -> bytes:
    return put_varint(len(data)) + data


def put_string(value: str) -> bytes:
    return put_bytes(value.encode("utf-8"))


def packet(protocol: int, region: int, payload: bytes) -> bytes:
    if len(payload) > MAX_FRAME_BYTES:
        raise ValueError("payload too large")
    return bytes((protocol & 0xFF, region & 0xFF)) + struct.pack("<I", len(payload)) + payload


def proto_req(subcommand: int, content: bytes = b"") -> bytes:
    # tcp.ProtoReq has uint cmd followed by byte[] data. FastBinaryWriter uses
    # varints for the normal uint and a length-prefixed byte array.
    return put_varint(subcommand) + put_bytes(content)


def start_notification(game_mode: int = 0, difficulty: int = 0, match_mode: int = 0) -> bytes:
    # tcp.MatchmakingStartNtf field order from Assembly-CSharp decompilation.
    body = b"".join(put_varint(x) for x in (game_mode, difficulty, match_mode, 1))
    return message_notify(MATCHMAKING_PROTOCOL, MATCH_START_NTF, body)


def success_notification(addr: str, match_id: int, game_mode: int = 0, match_mode: int = 0) -> bytes:
    # tcp.MatchmakingSussNtf field order from the recovered class. Empty secret
    # and prepare token are intentional for the local compatibility server.
    body = b"".join(
        (
            put_varint(match_id),
            put_string(addr),
            put_string(secrets.token_hex(16)),
            put_string(secrets.token_hex(8)),
            put_varint(0),      # sleep_ms
            put_varint(0),      # map_id; client-selected/default map
            put_varint(game_mode),
            put_varint(match_mode),
            b"\x00",           # use_cache
            put_varint(0),      # level_visual_style normal
            put_varint(0),      # difficulty
            b"\x01",           # first_login
            b"\x00",           # is_in_special_pool
            put_string(""),
            put_string(""),
            b"\x00",           # is_in_emulator_pool
        )
    )
    return message_notify(MATCHMAKING_PROTOCOL, MATCH_SUCCESS_NTF, body)


class GameNodeHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        server = self.server  # type: ignore[assignment]
        log_path: Path = server.game_log  # type: ignore[attr-defined]
        matchmaker: bool = server.matchmaker  # type: ignore[attr-defined]
        advertised_addr: str = server.advertised_addr  # type: ignore[attr-defined]
        peer = f"{self.client_address[0]}:{self.client_address[1]}"
        write_event(log_path, "connected", peer=peer, matchmaker=matchmaker)
        self.request.settimeout(30)
        buffer = bytearray()
        total = 0
        matched = False
        try:
            while True:
                chunk = self.request.recv(4096)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_FRAME_BYTES:
                    write_event(log_path, "closed_oversize_input", peer=peer, bytes=total)
                    return
                buffer.extend(chunk)
                write_event(log_path, "frame_bytes_received", peer=peer, bytes=len(chunk))
                while True:
                    if len(buffer) < TCP_HEADER_SIZE:
                        break
                    protocol = buffer[0]
                    region = buffer[1]
                    length = struct.unpack_from("<I", buffer, 2)[0]
                    if length > MAX_FRAME_BYTES:
                        write_event(log_path, "closed_oversize_frame", peer=peer, length=length)
                        return
                    if len(buffer) < TCP_HEADER_SIZE + length:
                        break
                    payload = bytes(buffer[TCP_HEADER_SIZE : TCP_HEADER_SIZE + length])
                    del buffer[: TCP_HEADER_SIZE + length]
                    subcommand = None
                    try:
                        subcommand, inner_offset = get_varint(payload)
                    except ValueError:
                        inner_offset = 0
                    write_event(
                        log_path,
                        "packet_received",
                        peer=peer,
                        protocol=protocol,
                        region=region,
                        length=length,
                        subcommand=subcommand,
                    )
                    if matchmaker and protocol == MATCHMAKING_PROTOCOL and subcommand == MATCH_START:
                        # A private-server compatibility match is created for
                        # the requesting player. No fabricated multi-player
                        # roster is sent; the client receives the real success
                        # contract with a generated local match ID.
                        self.request.sendall(packet(protocol, region, start_notification()))
                        write_event(log_path, "matchmaking_start_sent", peer=peer, subcommand=MATCH_START)
                        time.sleep(0.15)
                        match_id = int(time.time() * 1000) & 0x7FFFFFFFFFFFFFFF
                        self.request.sendall(packet(protocol, region, success_notification(advertised_addr, match_id)))
                        matched = True
                        write_event(
                            log_path,
                            "matchmaking_success_sent",
                            peer=peer,
                            match_id=match_id,
                            server_addr=advertised_addr,
                        )
                    elif protocol == MATCHMAKING_PROTOCOL and subcommand is not None:
                        write_event(log_path, "matchmaking_subcommand_ignored", peer=peer, subcommand=subcommand)
                    else:
                        write_event(log_path, "opaque_packet_received", peer=peer, protocol=protocol, length=length)
        except (ConnectionError, OSError, socket.timeout) as error:
            write_event(log_path, "connection_error", peer=peer, error=type(error).__name__)
        finally:
            write_event(log_path, "disconnected", peer=peer, bytes=total, matched=matched)


class ThreadingGameNodeServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    parser = argparse.ArgumentParser(description="Sigma realtime game-node and compatibility matchmaker")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=10101, type=int)
    parser.add_argument("--log-dir", required=True)
    parser.add_argument("--matchmaker", action="store_true", help="answer recovered MATCHMAKING START packets")
    parser.add_argument("--advertised-addr", default=None, help="address:port sent in MatchmakingSussNtf")
    args = parser.parse_args()
    log_dir = Path(args.log_dir).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    advertised_addr = args.advertised_addr or os.getenv("SIGMA_GAME_SERVER_ADDR") or f"127.0.0.1:{args.port}"
    with ThreadingGameNodeServer((args.host, args.port), GameNodeHandler) as server:
        server.game_log = log_dir / "game_node.jsonl"  # type: ignore[attr-defined]
        server.matchmaker = bool(args.matchmaker)  # type: ignore[attr-defined]
        server.advertised_addr = advertised_addr  # type: ignore[attr-defined]
        mode = "single_player_compat_matchmaker" if args.matchmaker else "opaque_metadata_only"
        write_event(server.game_log, "started", host=args.host, port=args.port, mode=mode, advertised_addr=advertised_addr)
        server.serve_forever()


if __name__ == "__main__":
    main()
