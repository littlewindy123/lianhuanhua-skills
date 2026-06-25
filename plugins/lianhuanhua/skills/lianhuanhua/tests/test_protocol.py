from __future__ import annotations

import json
import struct

from lianhuanhua.doubao_protocol import (
    MESSAGE_AUDIO_ONLY_RESPONSE,
    MESSAGE_FULL_SERVER_RESPONSE,
    SERIALIZATION_JSON,
    decode_frame,
    encode_json_event,
)


def test_encode_start_connection() -> None:
    frame = encode_json_event(1, {})
    assert frame[:4] == bytes([0x11, 0x14, 0x10, 0x00])
    assert struct.unpack(">i", frame[4:8])[0] == 1


def test_decode_audio_response() -> None:
    session = b"session-1"
    audio = b"abc123"
    raw = b"".join(
        [
            bytes([0x11, 0xB4, 0x00, 0x00]),
            struct.pack(">i", 352),
            struct.pack(">I", len(session)),
            session,
            struct.pack(">I", len(audio)),
            audio,
        ]
    )
    frame = decode_frame(raw)
    assert frame.message_type == MESSAGE_AUDIO_ONLY_RESPONSE
    assert frame.event == 352
    assert frame.session_id == "session-1"
    assert frame.payload == audio


def test_decode_subtitle_like_json_response() -> None:
    session = b"session-2"
    payload = json.dumps({"text": "你好", "words": [{"word": "你", "startTime": 0.1, "endTime": 0.2}]}).encode()
    raw = b"".join(
        [
            bytes([0x11, 0x94, 0x10, 0x00]),
            struct.pack(">i", 353),
            struct.pack(">I", len(session)),
            session,
            struct.pack(">I", len(payload)),
            payload,
        ]
    )
    frame = decode_frame(raw)
    assert frame.message_type == MESSAGE_FULL_SERVER_RESPONSE
    assert frame.serialization == SERIALIZATION_JSON
    assert frame.json_payload["text"] == "你好"
