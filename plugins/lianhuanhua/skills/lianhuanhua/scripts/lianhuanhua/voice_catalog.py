from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


CATALOG_PATH = Path(__file__).resolve().parents[2] / "assets" / "voice-catalog.json"
DEFAULT_VOICE = "温柔淑女 2.0"


@lru_cache(maxsize=1)
def load_voice_catalog() -> dict[str, Any]:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    voices = data.get("voices")
    if not isinstance(voices, list) or not voices:
        raise ValueError(f"Voice catalog is empty or invalid: {CATALOG_PATH}")
    if int(data.get("count", -1)) != len(voices):
        raise ValueError("Voice catalog count does not match its voice entries")
    return data


def _normalize(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.casefold())


def search_voices(query: str = "", *, limit: int = 10) -> list[dict[str, Any]]:
    voices = load_voice_catalog()["voices"]
    query = query.strip()
    if not query:
        return voices[:limit]

    normalized_query = _normalize(query)
    tokens = [_normalize(token) for token in re.split(r"[\s,，、;/]+", query) if len(_normalize(token)) >= 2]
    wants_female = any(word in query.casefold() for word in ("女声", "女性", "female", "姐姐", "少女"))
    wants_male = any(word in query.casefold() for word in ("男声", "男性", "male", "青年", "叔"))
    scored: list[tuple[int, dict[str, Any]]] = []

    for voice in voices:
        name = str(voice.get("name", ""))
        voice_id = str(voice.get("id", ""))
        searchable = _normalize(
            " ".join(
                str(voice.get(field, ""))
                for field in ("name", "id", "scene", "language", "capabilities", "tags")
            )
        )
        score = 0
        if normalized_query == _normalize(name) or normalized_query == _normalize(voice_id):
            score += 1000
        elif normalized_query and normalized_query in searchable:
            score += 200
        score += sum(25 + min(len(token), 10) for token in tokens if token in searchable)
        if wants_female and "female" in voice_id:
            score += 30
        if wants_male and "male" in voice_id:
            score += 30
        if score:
            scored.append((score, voice))

    scored.sort(key=lambda item: (-item[0], str(item[1].get("name", ""))))
    return [voice for _, voice in scored[:limit]]


def resolve_catalog_voice(query: str | None) -> dict[str, Any]:
    requested = (query or DEFAULT_VOICE).strip()
    matches = search_voices(requested, limit=5)
    if not matches:
        raise ValueError(
            f"No built-in Doubao TTS 2.0 voice matched {requested!r}. "
            "Run `lianhuanhua voices --query <description>` or copy an ID from "
            "https://console.volcengine.com/speech/app"
        )
    return matches[0]
