"""Recovered Sigma TCP packet and matchmaking mappings.

The decompiled Assembly-CSharp contract identifies a six-byte practical wire
header: protocol command (u8), region (u8), payload length (u32 little-endian),
followed by a ProtoReq-style varint command and length-prefixed byte payload.
"""
from __future__ import annotations

from dataclasses import dataclass
import secrets
import struct

TCP_HEADER_SIZE = 6
MAX_PACKET_SIZE = 20_480
PROTO_INIT = 1
PROTO_HEARTBEAT = 2
PROTO_MATCHMAKING = 3
PROTO_GROUP = 5
PROTO_ROOM = 14
PROTO_GAMESERVERMANAGER = 35

MM_START = 1
MM_CANCEL = 2
MM_GROUP_START = 3
MM_GROUP_CANCEL = 4
MM_SUCCESS_NTF = 5
MM_DROP_MATCH = 6
MM_GAME_OPENING_INFO = 7
MM_CHECK_INGAME_PLAYER = 8
MM_CLEAR_INGAME_PLAYER = 9
MM_START_NTF = 12
MM_MASS_GROUP_START = 13
MM_MASS_GROUP_CANCEL = 14
MM_STOP_NTF = 15
MM_RANKING_BANNED = 16
MM_TEAMMATE_RANKING_BANNED = 17


@dataclass(frozen=True)
class Frame:
    protocol: int
    region: int
    payload: bytes

    @property
    def subcommand(self) -> int | None:
        try:
            command, _ = read_varint(self.payload)
            return command
        except ValueError:
            return None


def write_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("varint cannot encode a negative value")
    output = bytearray()
    while value >= 0x80:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def read_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data) and shift <= 63:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte & 0x80 == 0:
            return value, offset
        shift += 7
    raise ValueError("incomplete or invalid varint")


def write_bytes(data: bytes) -> bytes:
    return write_varint(len(data)) + data


def write_string(value: str) -> bytes:
    return write_bytes(value.encode("utf-8"))


def read_bytes(data: bytes, offset: int) -> tuple[bytes, int]:
    size, offset = read_varint(data, offset)
    end = offset + size
    if end > len(data):
        raise ValueError("length-prefixed field exceeds payload")
    return data[offset:end], end


def make_proto_request(subcommand: int, content: bytes = b"") -> bytes:
    return write_varint(subcommand) + write_bytes(content)


def make_frame(protocol: int, region: int, proto_payload: bytes) -> bytes:
    if len(proto_payload) > MAX_PACKET_SIZE:
        raise ValueError("packet payload exceeds MAX_PACKET_SIZE")
    return bytes((protocol & 0xFF, region & 0xFF)) + struct.pack("<I", len(proto_payload)) + proto_payload


def decode_frame(buffer: bytearray) -> Frame | None:
    if len(buffer) < TCP_HEADER_SIZE:
        return None
    protocol = buffer[0]
    region = buffer[1]
    length = struct.unpack_from("<I", buffer, 2)[0]
    if length > MAX_PACKET_SIZE:
        raise ValueError("packet length exceeds MAX_PACKET_SIZE")
    if len(buffer) < TCP_HEADER_SIZE + length:
        return None
    payload = bytes(buffer[TCP_HEADER_SIZE : TCP_HEADER_SIZE + length])
    del buffer[: TCP_HEADER_SIZE + length]
    return Frame(protocol, region, payload)


def message_notify(protocol: int, command: int, content: bytes = b"", ret: int = 0, account_id: int = 0) -> bytes:
    """Encode the recovered proto.MessageNotify response envelope."""
    return b"".join((
        write_varint(account_id),
        write_varint(protocol),
        write_varint(ret),
        write_varint(command),
        write_bytes(content),
    ))


def matchmaking_start_notification(game_mode: int = 0, difficulty: int = 0, match_mode: int = 0, avg_wait: int = 1) -> bytes:
    content = b"".join(write_varint(value) for value in (game_mode, difficulty, match_mode, avg_wait))
    return message_notify(PROTO_MATCHMAKING, MM_START_NTF, content)


def matchmaking_success_notification(
    server_addr: str,
    match_id: int,
    game_mode: int = 0,
    match_mode: int = 0,
    map_id: int = 0,
) -> bytes:
    content = b"".join(
        (
            write_varint(match_id),
            write_string(server_addr),
            write_string(secrets.token_hex(16)),
            write_string(secrets.token_hex(8)),
            write_varint(0),
            write_varint(map_id),
            write_varint(game_mode),
            write_varint(match_mode),
            b"\x00",
            write_varint(0),
            write_varint(0),
            b"\x01",
            b"\x00",
            write_string(""),
            write_string(""),
            b"\x00",
        )
    )
    return message_notify(PROTO_MATCHMAKING, MM_SUCCESS_NTF, content)


def matchmaking_stop_notification(reason: int = 0) -> bytes:
    return message_notify(PROTO_MATCHMAKING, MM_STOP_NTF, write_varint(reason))
