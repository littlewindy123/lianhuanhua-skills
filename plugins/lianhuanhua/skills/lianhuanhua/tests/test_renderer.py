from __future__ import annotations

import json
import shutil
import subprocess

import pytest
from PIL import Image

from lianhuanhua.renderer import mux_final_video, render_silent_video
from lianhuanhua.workspace import initialize_workspace


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
def test_render_smoke(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "render")
    for index in (1, 2):
        Image.new("RGB", (360, 640), (230 - index * 10, 220, 200 + index * 10)).save(
            ws.panels_dir / f"panel_{index:03d}.png"
        )

    timeline = {
        "version": "0.1",
        "source": "test",
        "audio_file": str(ws.audio_dir / "narration.mp3"),
        "duration": 1.0,
        "segments": [
            {"id": "seg_001", "text": "测试", "start": 0.0, "end": 1.0, "emotion": "", "words": []}
        ],
    }
    storyboard = {
        "version": "0.1",
        "video": {"width": 360, "height": 640, "fps": 15, "duration": 1.0},
        "shots": [
            {
                "id": "shot_001", "segment_id": "seg_001", "scene_id": "s", "start": 0.0, "end": 0.5,
                "image": "work/panels/panel_001.png", "is_anchor": True, "visual_action": "a",
                "character_state": "a", "scene_state": "a", "composition": "a", "previous_panel_summary": "",
                "motion": {"type": "slow_zoom_in", "strength": 0.2, "focus_x": 0.5, "focus_y": 0.5},
                "transition_out": {"type": "dissolve", "duration": 0.1}
            },
            {
                "id": "shot_002", "segment_id": "seg_001", "scene_id": "s", "start": 0.5, "end": 1.0,
                "image": "work/panels/panel_002.png", "is_anchor": False, "visual_action": "b",
                "character_state": "b", "scene_state": "b", "composition": "b", "previous_panel_summary": "a",
                "motion": {"type": "slow_zoom_out", "strength": 0.2, "focus_x": 0.5, "focus_y": 0.5},
                "transition_out": {"type": "cut", "duration": 0.0}
            },
        ],
    }
    ws.timeline.write_text(json.dumps(timeline), encoding="utf-8")
    ws.storyboard.write_text(json.dumps(storyboard), encoding="utf-8")
    (ws.work / "subtitles.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\n测试\n", encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "libmp3lame", str(ws.audio_dir / "narration.mp3")],
        check=True,
        capture_output=True,
    )
    assert render_silent_video(ws.root).exists()
    assert mux_final_video(ws.root).exists()
