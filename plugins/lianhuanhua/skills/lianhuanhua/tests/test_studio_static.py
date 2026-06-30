from __future__ import annotations

from pathlib import Path


def _studio_html() -> str:
    return (Path(__file__).resolve().parents[1] / "studio_static" / "index.html").read_text(
        encoding="utf-8"
    )


def test_studio_voice_loading_uses_resilient_initialization() -> None:
    html = _studio_html()

    assert "Promise.allSettled([loadVoices(),load()])" in html
    assert "音色列表加载失败，已使用当前音色" in html
    assert "loadVoices().then(load)" not in html


def test_studio_voice_select_has_project_fallback() -> None:
    html = _studio_html()

    assert "function currentProjectVoice()" in html
    assert "当前项目" in html
    assert ".filter(v=>v&&v.name&&v.id)" in html


def test_studio_v04_identity_variation_and_timeline_controls_exist() -> None:
    html = _studio_html()

    assert 'id="characterIdentityHint"' in html
    assert 'id="variationStrength"' in html
    assert 'id="clipTimeline"' in html
    assert "/api/update-storyboard-timeline" in html
