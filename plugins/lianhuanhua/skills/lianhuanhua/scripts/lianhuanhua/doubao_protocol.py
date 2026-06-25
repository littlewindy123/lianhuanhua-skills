from __future__ import annotations

import gzip
import json
import struct
from dataclasses import dataclass
from typing import Any

MESSAGE_FULL_CLIENT_REQUEST = 0x1
MESSAGE_AUDIO_ONLY_REQUEST = 0x2
MESSAGE_FULL_SERVER_RESPONSE = 0x9
MESSAGE_AUDIO_ONLY_RESPONSE = 0xB
MESSAGE_ERROR = 0xF

FLAG_WITH_EVENT = 0x4
SERIALIZATION_RAW = 0x0
SERIALIZATION_JSON = 0x1
COMPRESSION_NONE = 0x0
COMPRESSION_GZIP = 0x1

CONNECTION_EVENTS = {1, 2, 50, 51, 52}


@dataclass
class Frame:
    message_type: int
    flags: int
    serialization: int
    compression: int
    event: int | None
    connection_id: str | None
    session_id: str | None
    payload: bytes
    error_code: int | None = None

    @property
    def json_payload(self) -> Any | None:
        if self.serialization != SERIALIZATION_JSON or not self.payload:
            return None
        try:
            return json.loads(self.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None


def _header(message_type: int, flags: int, serialization: int, compression: int) -> bytes:
    # protocol v1, 4-byte header
    return bytes(
        [
            0x11,
            ((message_type & 0xF) << 4) | (flags & 0xF),
            ((serialization & 0xF) << 4) | (compression & 0xF),
            0x00,
        ]
    )


def encode_json_event(event: int, payload: dict[str, Any], session_id: str | None = None) -> bytes:
    payload_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    chunks = [
        _header(MESSAGE_FULL_CLIENT_REQUEST, FLAG_WITH_EVENT, SERIALIZATION_JSON, COMPRESSION_NONE),
        struct.pack(">i", event),
    ]
    if session_id is not None:
        encoded_session = session_id.encode("utf-8")
        chunks.extend([struct.pack(">I", len(encoded_session)), encoded_session])
    chunks.extend([struct.pack(">I", len(payload_bytes)), payload_bytes])
    return b"".join(chunks)


def _read_u32(data: bytes, offset: int) -> tuple[int, int]:
    if offset + 4 > len(data):
        raise ValueError("Unexpected end of frame while reading uint32")
    return struct.unpack_from(">I", data, offset)[0], offset + 4


def _read_i32(data: bytes, offset: int) -> tuple[int, int]:
    if offset + 4 > len(data):
        raise ValueError("Unexpected end of frame while reading int32")
    return struct.unpack_from(">i", data, offset)[0], offset + 4


def _read_blob(data: bytes, offset: int) -> tuple[bytes, int]:
    size, offset = _read_u32(data, offset)
    end = offset + size
    if end > len(data):
        raise ValueError(f"Frame blob declares {size} bytes but only {len(data)-offset} remain")
    return data[offset:end], end


def decode_frame(data: bytes) -> Frame:
    if len(data) < 4:
        raise ValueError("WebSocket binary frame is shorter than the protocol header")

    version = data[0] >> 4
    header_words = data[0] & 0x0F
    if version != 1:
        raise ValueError(f"Unsupported protocol version: {version}")
    header_size = header_words * 4
    if header_size < 4 or header_size > len(data):
        raise ValueError(f"Invalid header size: {header_size}")

    message_type = data[1] >> 4
    flags = data[1] & 0x0F
    serialization = data[2] >> 4
    compression = data[2] & 0x0F
    offset = header_size
    event: int | None = None
    connection_id: str | None = None
    session_id: str | None = None
    error_code: int | None = None

    if message_type == MESSAGE_ERROR:
        error_code, offset = _read_i32(data, offset)
        payload, _ = _read_blob(data, offset)
        if compression == COMPRESSION_GZIP:
            payload = gzip.decompress(payload)
        return Frame(
            message_type,
            flags,
            serialization,
            compression,
            None,
            None,
            None,
            payload,
            error_code,
        )

    if flags & FLAG_WITH_EVENT:
        event, offset = _read_i32(data, offset)

    if event is not None:
        # Connection-class responses may carry a connection id. Session/data-class
        # responses carry a session id. Client connection requests do not carry an id.
        if event in {50, 51, 52}:
            blob, offset = _read_blob(data, offset)
            connection_id = blob.decode("utf-8", errors="replace")
        elif event >= 100:
            blob, offset = _read_blob(data, offset)
            session_id = blob.decode("utf-8", errors="replace")

    payload, _ = _read_blob(data, offset)
    if compression == COMPRESSION_GZIP:
        payload = gzip.decompress(payload)

    return Frame(
        message_type=message_type,
        flags=flags,
        serialization=serialization,
        compression=compression,
        event=event,
        connection_id=connection_id,
        session_id=session_id,
        payload=payload,
        error_code=error_code,
    )


def frame_to_log(frame: Frame) -> dict[str, Any]:
    record: dict[str, Any] = {
        "message_type": frame.message_type,
        "flags": frame.flags,
        "serialization": frame.serialization,
        "compression": frame.compression,
        "event": frame.event,
        "connection_id": frame.connection_id,
        "session_id": frame.session_id,
        "payload_size": len(frame.payload),
        "error_code": frame.error_code,
    }
    parsed = frame.json_payload
    if parsed is not None:
        record["json"] = parsed
    elif frame.message_type != MESSAGE_AUDIO_ONLY_RESPONSE:
        record["payload_text"] = frame.payload.decode("utf-8", errors="replace")
    return record
