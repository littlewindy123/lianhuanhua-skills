from __future__ import annotations

import json
import struct
from types import SimpleNamespace

import pytest
from websockets.datastructures import Headers

from lianhuanhua.doubao_protocol import (
    MESSAGE_AUDIO_ONLY_RESPONSE,
    MESSAGE_FULL_SERVER_RESPONSE,
    SERIALIZATION_JSON,
    decode_frame,
    encode_json_event,
)
from lianhuanhua.doubao_tts import DoubaoError, _handshake_error_message, resolve_speaker
from lianhuanhua.voice_catalog import load_voice_catalog, search_voices


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


def test_voice_catalog_contains_all_official_tts_2_voices() -> None:
    catalog = load_voice_catalog()
    assert catalog["count"] == 442
    assert len(catalog["voices"]) == 442
    assert len({voice["id"] for voice in catalog["voices"]}) == 442


def test_search_voice_catalog_by_natural_language() -> None:
    matches = search_voices("温柔淑女 2.0", limit=3)
    assert matches[0]["id"] == "zh_female_wenroushunv_uranus_bigtts"


def test_resolve_speaker_from_catalog_preference(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOUBAO_SPEAKER", raising=False)
    speaker, source = resolve_speaker({"voice_preference": "温柔淑女 2.0"})
    assert speaker == "zh_female_wenroushunv_uranus_bigtts"
    assert source == "温柔淑女 2.0"


def test_explicit_speaker_overrides_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOUBAO_SPEAKER", "S_custom_voice")
    speaker, source = resolve_speaker({"voice_preference": "温柔淑女 2.0"})
    assert speaker == "S_custom_voice"
    assert source == "explicit"


def test_unknown_voice_profile_has_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOUBAO_SPEAKER", raising=False)
    with pytest.raises(DoubaoError, match="console.volcengine.com/speech/app"):
        resolve_speaker({"voice_preference": "不存在的火星机器人音色"})


def test_handshake_401_explains_api_key_source() -> None:
    response = SimpleNamespace(
        status_code=401,
        body=bytearray(b'{"error":"Invalid X-Api-Key"}'),
        headers=Headers({"X-Tt-Logid": "test-log-id"}),
    )
    error = SimpleNamespace(response=response)
    message = _handshake_error_message(error)
    assert "Invalid X-Api-Key" in message
    assert "test-log-id" in message
    assert "API Key Management" in message
    assert "APP ID" in message


def test_handshake_403_explains_resource_grant() -> None:
    response = SimpleNamespace(
        status_code=403,
        body=bytearray(
            b'{"error":"[resource_id=volc.seedtts.default] requested resource not granted"}'
        ),
        headers=Headers({"X-Tt-Logid": "test-resource-log-id"}),
    )
    error = SimpleNamespace(response=response)
    message = _handshake_error_message(error)
    assert "resource not granted" in message
    assert "seed-tts-2.0" in message
    assert "console.volcengine.com/speech/app" in message
    assert "resource pack" in message
