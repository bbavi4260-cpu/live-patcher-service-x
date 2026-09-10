"""Sigma UDP heartbeat and lightweight match telemetry service.

This module deliberately does not implement gameplay, aim, movement, or any
anti-cheat bypass. It only provides a bounded liveness endpoint for the
private-server compatibility stack.
"""
from __future__ import annotations

import argparse
import json
import os
import socketserver
import threading
from datetime import datetime, timezone
from pathlib import Path

MAX_DATAGRAM = 4096
HEARTBEAT_MAGIC = b"SIGMA-HB"
ACK_MAGIC = b"SIGMA-ACK"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class UDPLog:
    def __init__(self, path: Path | None = None):
        self.path = path
        self.lock = threading.Lock()

    def write(self, event: str, **fields: object) -> None:
        row = {"timestamp": utc_now(), "event": event, **fields}
        text = json.dumps(row, separators=(",", ":"))
        with self.lock:
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(text + "\n")
        print(f"[UDP] {text}", flush=True)


class HeartbeatHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        data, server_socket = self.request
        server: HeartbeatServer = self.server  # type: ignore[assignment]
        if len(data) > MAX_DATAGRAM:
            server.logger.write("datagram_oversize", peer=str(self.client_address), bytes=len(data))
            return
        server.logger.write("datagram_received", peer=str(self.client_address), bytes=len(data), magic=data[:8].hex())
        # A small acknowledgement is useful for client liveness checks. Unknown
        # datagrams are logged but never interpreted as gameplay commands.
        if data.startswith(HEARTBEAT_MAGIC):
            response = ACK_MAGIC + data[len(HEARTBEAT_MAGIC) : 32]
            server_socket.sendto(response, self.client_address)
            server.logger.write("heartbeat_ack_sent", peer=str(self.client_address), bytes=len(response))


class HeartbeatServer(socketserver.ThreadingUDPServer):
    allow_reuse_address = True

    def __init__(self, address, logger: UDPLog):
        super().__init__(address, HeartbeatHandler)
        self.logger = logger


def serve(host: str = "0.0.0.0", port: int = 10102, log_path: str | None = None) -> None:
    logger = UDPLog(Path(log_path) if log_path else None)
    with HeartbeatServer((host, port), logger) as server:
        logger.write("started", host=host, port=port)
        try:
            server.serve_forever()
        finally:
            logger.write("stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sigma UDP heartbeat service")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=10102, type=int)
    parser.add_argument("--log", default=os.getenv("SIGMA_UDP_LOG", "logs/udp2.jsonl"))
    args = parser.parse_args()
    serve(args.host, args.port, args.log)


if __name__ == "__main__":
    main()
