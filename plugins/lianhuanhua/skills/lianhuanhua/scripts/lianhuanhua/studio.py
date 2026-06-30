from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .doubao_tts import config_from_project, synthesize_plan
from .exporter import export_project
from .prompts import build_panel_prompts
from .renderer import mux_final_video, render_silent_video
from .schema_validation import validate_data
from .storyboard import build_storyboard_workspace, normalize_variation_strength
from .utils import ensure_dir, read_json, write_json
from .validation import validate_manual_panels, validate_output, validate_workspace
from .voice_catalog import load_voice_catalog
from .workspace import initialize_workspace, skill_root


PANEL_RE = re.compile(r"^panel_[0-9]{3}\.png$")
PANEL_ID_RE = re.compile(r"^panel_[0-9]{3}$")
MOTION_TYPES = {"hold", "slow_zoom_in", "slow_zoom_out", "pan_left", "pan_right", "float_up_down"}


def static_dir() -> Path:
    return skill_root() / "studio_static"


def ensure_studio_workspace(workspace: Path) -> None:
    if not (workspace / "project.json").exists():
        initialize_workspace(workspace)
    ensure_dir(workspace / "work")
    ensure_dir(workspace / "work" / "panels")
    ensure_dir(workspace / "input" / "character")
    state = workspace / "work" / "studio_state.json"
    if not state.exists():
        write_json(
            state,
            {
                "stage": "create",
                "action": "generate_full_project",
                "node_status": {
                    "voice": "pending",
                    "storyboard": "pending",
                    "images": "pending",
                    "video": "pending",
                },
            },
        )


def _ratio_size(value: str, fallback: tuple[int, int]) -> tuple[int, int]:
    if value == "16:9":
        return 1920, 1080
    if value == "1:1":
        return 1080, 1080
    if value == "4:5":
        return 1080, 1350
    if value == "9:16":
        return 1080, 1920
    return fallback


def _load_secrets(workspace: Path) -> dict[str, Any]:
    path = workspace / "work" / ".secrets.json"
    if not path.exists():
        return {}
    return read_json(path)


def _save_secret_api_key(workspace: Path, api_key: str | None) -> None:
    if api_key is None:
        return
    api_key = api_key.strip()
    secrets = _load_secrets(workspace)
    if api_key:
        secrets["DOUBAO_API_KEY"] = api_key
    elif "DOUBAO_API_KEY" in secrets:
        secrets.pop("DOUBAO_API_KEY")
    write_json(workspace / "work" / ".secrets.json", secrets)


def _apply_secrets_to_env(workspace: Path) -> None:
    api_key = str(_load_secrets(workspace).get("DOUBAO_API_KEY", "")).strip()
    if api_key:
        os.environ["DOUBAO_API_KEY"] = api_key


def _safe_name(name: str) -> str:
    return Path(name).name.replace("\\", "")


def _workspace_relative_path(workspace: Path, value: str) -> Path:
    value = value.replace("\\", "/")
    path = Path(value)
    return path if path.is_absolute() else workspace / path


def _decode_file(payload: dict[str, Any]) -> bytes:
    data = str(payload.get("content_base64") or "")
    if "," in data and data.split(",", 1)[0].startswith("data:"):
        data = data.split(",", 1)[1]
    return base64.b64decode(data, validate=True)


def _storyboard_panel_target(workspace: Path, panel_id: str) -> Path:
    storyboard_path = workspace / "work" / "storyboard.json"
    if storyboard_path.exists():
        storyboard = read_json(storyboard_path)
        for index, shot in enumerate(storyboard.get("shots", []), start=1):
            image = Path(str(shot.get("image", "")))
            shot_panel_id = image.stem if image.stem.startswith("panel_") else f"panel_{index:03d}"
            if shot_panel_id == panel_id:
                return workspace / image if not image.is_absolute() else image
    return workspace / "work" / "panels" / f"{panel_id}.png"


def _panel_records(workspace: Path) -> list[dict[str, Any]]:
    storyboard_path = workspace / "work" / "storyboard.json"
    if not storyboard_path.exists():
        return []
    storyboard = read_json(storyboard_path)
    records: list[dict[str, Any]] = []
    for index, shot in enumerate(storyboard.get("shots", []), start=1):
        image = Path(str(shot.get("image", "")))
        panel_id = image.stem if image.stem.startswith("panel_") else f"panel_{index:03d}"
        image_path = workspace / image if not image.is_absolute() else image
        records.append(
            {
                "panel_id": panel_id,
                "filename": f"{panel_id}.png",
                "shot_id": shot.get("id"),
                "start": shot.get("start"),
                "end": shot.get("end"),
                "narration": _shot_narration(workspace, shot),
                "image_description": shot.get("visual_action", ""),
                "prompt": _read_panel_prompt(workspace, str(shot.get("id", ""))),
                "motion": shot.get("motion", {}),
                "exists": image_path.exists(),
                "url": f"/api/panel/{panel_id}.png",
            }
        )
    return records


def _shot_narration(workspace: Path, shot: dict[str, Any]) -> str:
    timeline_path = workspace / "work" / "timeline.json"
    if not timeline_path.exists():
        return ""
    timeline = read_json(timeline_path)
    shot_start = float(shot.get("start", 0))
    shot_end = float(shot.get("end", 0))
    texts: list[str] = []
    for segment in timeline.get("segments", []):
        start = float(segment.get("start", 0))
        end = float(segment.get("end", 0))
        if start >= shot_start - 0.05 and end <= shot_end + 0.05:
            texts.append(str(segment.get("text", "")))
    if texts:
        return "".join(texts)
    segments = {segment.get("id"): segment for segment in timeline.get("segments", [])}
    return str(segments.get(shot.get("segment_id"), {}).get("text", ""))


def _read_panel_prompt(workspace: Path, shot_id: str) -> str:
    path = workspace / "work" / "prompts" / f"{shot_id}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _audio_record(workspace: Path) -> dict[str, Any]:
    candidates = [
        workspace / "work" / "audio" / "narration.mp3",
        workspace / "work" / "audio" / "narration.wav",
        workspace / "work" / "audio" / "extracted.wav",
    ]
    audio = next((path for path in candidates if path.exists() and path.stat().st_size > 0), None)
    if audio is None:
        return {"exists": False, "url": None, "path": None}
    return {
        "exists": True,
        "url": f"/api/audio/{audio.name}",
        "path": str(audio),
        "filename": audio.name,
    }


def _character_records(workspace: Path, project: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for value in project.get("paths", {}).get("character_images", []):
        path = _workspace_relative_path(workspace, str(value))
        if not path.exists():
            continue
        name = path.name
        records.append(
            {
                "filename": name,
                "path": str(path),
                "url": f"/api/character/{name}",
                "exists": True,
            }
        )
    return records


def _default_node_status(workspace: Path) -> dict[str, str]:
    status = {
        "voice": "pending",
        "storyboard": "pending",
        "images": "pending",
        "video": "pending",
    }
    if _audio_record(workspace)["exists"] and (workspace / "work" / "timeline.json").exists():
        status["voice"] = "ready"
    if (workspace / "output" / "prompts-package.zip").exists():
        status["storyboard"] = "ready"
    panels = _panel_records(workspace)
    if panels and all(panel.get("exists") for panel in panels):
        status["images"] = "ready"
    if (workspace / "output" / "final_video.mp4").exists():
        status["video"] = "ready"
    state_path = workspace / "work" / "studio_state.json"
    if state_path.exists():
        saved = read_json(state_path).get("node_status", {})
        if isinstance(saved, dict):
            status.update({key: str(value) for key, value in saved.items() if key in status})
    return status


def save_project_settings(workspace: Path, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_studio_workspace(workspace)
    project_path = workspace / "project.json"
    project = read_json(project_path)

    story = payload.get("story")
    if isinstance(story, str):
        story_path = workspace / str(project.get("paths", {}).get("story") or "input/story.txt")
        ensure_dir(story_path.parent)
        story_path.write_text(story.strip() + "\n", encoding="utf-8")
        plan_path = workspace / "work" / "narration_plan.json"
        plan = read_json(plan_path)
        plan["chunks"] = [{"id": "narration_001", "text": story.strip(), "instruction": "", "pause_after_ms": 0}]
        write_json(plan_path, plan)

    ratio = payload.get("ratio")
    width = int(payload.get("width") or project["video"].get("width", 1080))
    height = int(payload.get("height") or project["video"].get("height", 1920))
    if isinstance(ratio, str):
        width, height = _ratio_size(ratio, (width, height))
    project["video"]["width"] = width
    project["video"]["height"] = height
    if "burn_subtitles" in payload:
        project["video"]["burn_subtitles"] = bool(payload["burn_subtitles"])

    if isinstance(payload.get("mood"), str):
        project["mood"] = payload["mood"]
    if isinstance(payload.get("style_prompt"), str):
        project.setdefault("visual", {})["style_prompt"] = payload["style_prompt"]
        project.setdefault("visual", {})["reference_mode"] = "image_or_style"
    if isinstance(payload.get("character_identity_hint"), str):
        project.setdefault("visual", {})["character_identity_hint"] = payload["character_identity_hint"].strip()
    if isinstance(payload.get("image_density"), str):
        project.setdefault("storyboard", {})["image_density"] = payload["image_density"]
    if isinstance(payload.get("variation_strength"), str):
        project.setdefault("storyboard", {})["variation_strength"] = normalize_variation_strength(
            payload["variation_strength"]
        )
    if isinstance(payload.get("voice_preference"), str):
        project.setdefault("tts", {})["voice_preference"] = payload["voice_preference"]
    if isinstance(payload.get("speaker"), str):
        project.setdefault("tts", {})["speaker"] = payload["speaker"]
    if payload.get("speech_rate") is not None:
        project.setdefault("tts", {})["speech_rate"] = float(payload["speech_rate"])
    if isinstance(payload.get("image_provider"), str):
        mode = "external" if payload["image_provider"] == "external" else "codex"
        project.setdefault("image_workflow", {})["mode"] = mode
    else:
        project.setdefault("image_workflow", {})["mode"] = "codex"

    character_uploads = payload.get("character_images")
    if isinstance(character_uploads, list) and character_uploads:
        saved: list[str] = []
        for index, item in enumerate(character_uploads, start=1):
            name = _safe_name(str(item.get("name") or f"reference_{index:03d}.png"))
            suffix = Path(name).suffix.lower() if Path(name).suffix else ".png"
            if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                raise ValueError(f"Unsupported character image type: {name}")
            target = workspace / "input" / "character" / f"reference_{index:03d}{suffix}"
            ensure_dir(target.parent)
            target.write_bytes(_decode_file(item))
            saved.append(str(target.relative_to(workspace)))
        project.setdefault("paths", {})["character_images"] = saved

    _save_secret_api_key(workspace, payload.get("api_key"))
    write_json(project_path, project)
    return project


def studio_snapshot(workspace: Path) -> dict[str, Any]:
    ensure_studio_workspace(workspace)
    project = read_json(workspace / "project.json")
    story_path = workspace / str(project.get("paths", {}).get("story") or "input/story.txt")
    state_path = workspace / "work" / "studio_state.json"
    return {
        "project": project,
        "story": story_path.read_text(encoding="utf-8") if story_path.exists() else "",
        "timeline": read_json(workspace / "work" / "timeline.json") if (workspace / "work" / "timeline.json").exists() else None,
        "storyboard": read_json(workspace / "work" / "storyboard.json") if (workspace / "work" / "storyboard.json").exists() else None,
        "studio_state": read_json(state_path) if state_path.exists() else None,
        "node_status": _default_node_status(workspace),
        "audio": _audio_record(workspace),
        "character_images": _character_records(workspace, project),
        "panels": _panel_records(workspace),
        "prompt_package": {
            "exists": (workspace / "output" / "prompts-package.zip").exists(),
            "url": "/api/download/prompts-package.zip",
        },
        "outputs": {
            "silent_video": str(workspace / "output" / "silent_video.mp4"),
            "final_video": str(workspace / "output" / "final_video.mp4"),
        },
        "has_doubao_key": bool(_load_secrets(workspace).get("DOUBAO_API_KEY") or os.getenv("DOUBAO_API_KEY")),
    }


def write_studio_action(workspace: Path, payload: dict[str, Any]) -> dict[str, Any]:
    errors = validate_data(payload, "studio_state.schema.json")
    if errors:
        raise ValueError("; ".join(errors))
    write_json(workspace / "work" / "studio_state.json", payload)
    return payload


def generate_voice(workspace: Path, payload: dict[str, Any]) -> dict[str, Any]:
    project = save_project_settings(workspace, payload)
    _apply_secrets_to_env(workspace)
    plan = read_json(workspace / "work" / "narration_plan.json")
    output_audio, timeline = synthesize_plan(
        plan=plan,
        output_dir=workspace / "work" / "audio",
        config=config_from_project(project),
        log_dir=workspace / "logs",
    )
    write_studio_action(
        workspace,
        {
            "stage": "voice",
            "action": "confirm_voice",
            "node_status": {
                "voice": "ready",
                "storyboard": "pending",
                "images": "pending",
                "video": "pending",
            },
        },
    )
    return {"audio": str(output_audio), "timeline": timeline}


def generate_storyboard(workspace: Path, payload: dict[str, Any]) -> dict[str, Any]:
    save_project_settings(workspace, payload)
    result = build_storyboard_workspace(workspace)
    write_studio_action(
        workspace,
        {
            "stage": "storyboard",
            "action": "confirm_storyboard",
            "node_status": {
                "voice": "confirmed",
                "storyboard": "ready",
                "images": "pending",
                "video": "pending",
            },
        },
    )
    return result


def timeline_preview(workspace: Path) -> dict[str, Any]:
    snapshot = studio_snapshot(workspace)
    return {
        "audio": snapshot["audio"],
        "timeline": snapshot["timeline"],
        "storyboard": snapshot["storyboard"],
        "panels": snapshot["panels"],
    }


def update_storyboard_timeline(workspace: Path, payload: dict[str, Any]) -> dict[str, Any]:
    storyboard_path = workspace / "work" / "storyboard.json"
    if not storyboard_path.exists():
        raise ValueError("storyboard.json does not exist")
    storyboard = read_json(storyboard_path)
    updates = payload.get("shots")
    if not isinstance(updates, list):
        raise ValueError("shots must be a list")
    updates_by_id = {str(item.get("id")): item for item in updates if isinstance(item, dict) and item.get("id")}
    for shot in storyboard.get("shots", []):
        update = updates_by_id.get(str(shot.get("id")))
        if not update:
            continue
        if "start" in update:
            shot["start"] = float(update["start"])
        if "end" in update:
            shot["end"] = float(update["end"])
        if float(shot["end"]) <= float(shot["start"]):
            raise ValueError(f"Shot {shot.get('id')} has non-positive duration")
        if isinstance(update.get("motion"), dict):
            motion = dict(shot.get("motion", {}))
            motion.update(update["motion"])
            if motion.get("type") not in MOTION_TYPES:
                raise ValueError(f"Invalid motion type for {shot.get('id')}: {motion.get('type')}")
            shot["motion"] = motion

    ordered = sorted(storyboard.get("shots", []), key=lambda item: float(item.get("start", 0)))
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if float(current["start"]) < float(previous["end"]) - 0.001:
            raise ValueError(f"Timeline overlap: {previous.get('id')} and {current.get('id')}")
    storyboard["shots"] = ordered
    if ordered:
        storyboard.setdefault("video", {})["duration"] = max(float(shot["end"]) for shot in ordered)
    write_json(storyboard_path, storyboard)
    build_panel_prompts(workspace)
    return timeline_preview(workspace)


def save_uploaded_panels(workspace: Path, files: list[dict[str, Any]]) -> dict[str, Any]:
    names: list[str] = []
    for item in files:
        name = _safe_name(str(item.get("name") or ""))
        names.append(name)
        if not PANEL_RE.match(name):
            continue
        content = _decode_file(item)
        target = workspace / "work" / "panels" / name
        ensure_dir(target.parent)
        target.write_bytes(content)
    return validate_manual_panels(workspace, filenames=names)


def replace_panel(workspace: Path, payload: dict[str, Any]) -> dict[str, Any]:
    panel_id = str(payload.get("panel_id") or "")
    if not PANEL_ID_RE.match(panel_id):
        raise ValueError("panel_id must look like panel_001")
    content = _decode_file(payload)
    target = _storyboard_panel_target(workspace, panel_id)
    ensure_dir(target.parent)
    target.write_bytes(content)
    return validate_manual_panels(workspace)


def render_video(workspace: Path) -> dict[str, Any]:
    errors = validate_workspace(workspace, require_images=True)
    if errors:
        raise ValueError("; ".join(errors))
    project = read_json(workspace / "project.json")
    silent = render_silent_video(workspace)
    final = mux_final_video(workspace, burn_subtitles=bool(project.get("video", {}).get("burn_subtitles", True)))
    output_errors = validate_output(workspace)
    if output_errors:
        raise ValueError("; ".join(output_errors))
    exported = export_project(workspace)
    write_studio_action(
        workspace,
        {
            "stage": "video",
            "action": "render_video",
            "node_status": {
                "voice": "confirmed",
                "storyboard": "confirmed",
                "images": "confirmed",
                "video": "ready",
            },
        },
    )
    return {"silent_video": str(silent), "final_video": str(final), "exported": [str(path) for path in exported]}


class StudioHandler(BaseHTTPRequestHandler):
    workspace: Path

    server_version = "LianhuanhuaStudio/0.3"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        print(f"[studio] {self.address_string()} - {format % args}")

    def _json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, message: str, status: int = 400) -> None:
        self._json({"ok": False, "error": message}, status=status)

    def _body_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _send_file(self, path: Path, content_type: str | None = None) -> None:
        if not path.exists() or not path.is_file():
            self._error("Not found", status=HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        if path.name.endswith(".zip"):
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path in {"/", "/index.html"}:
            self._send_file(static_dir() / "index.html", "text/html; charset=utf-8")
            return
        if path == "/api/project":
            self._json({"ok": True, "data": studio_snapshot(self.workspace)})
            return
        if path == "/api/voices":
            self._json({"ok": True, "data": load_voice_catalog()})
            return
        if path == "/api/timeline-preview":
            self._json({"ok": True, "data": timeline_preview(self.workspace)})
            return
        if path.startswith("/api/audio/"):
            name = _safe_name(path.rsplit("/", 1)[-1])
            allowed = {"narration.mp3", "narration.wav", "extracted.wav"}
            if name not in allowed and not re.match(r"^narration_[0-9]{3}\.(mp3|wav)$", name):
                self._error("Invalid audio name", status=HTTPStatus.BAD_REQUEST)
                return
            self._send_file(self.workspace / "work" / "audio" / name)
            return
        if path.startswith("/api/character/"):
            name = _safe_name(path.rsplit("/", 1)[-1])
            if Path(name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                self._error("Invalid character image name", status=HTTPStatus.BAD_REQUEST)
                return
            self._send_file(self.workspace / "input" / "character" / name)
            return
        if path == "/api/download/prompts-package.zip":
            self._send_file(self.workspace / "output" / "prompts-package.zip", "application/zip")
            return
        if path.startswith("/api/panel/"):
            name = _safe_name(path.rsplit("/", 1)[-1])
            if not PANEL_RE.match(name):
                self._error("Invalid panel name", status=HTTPStatus.BAD_REQUEST)
                return
            self._send_file(self.workspace / "work" / "panels" / name)
            return
        self._error("Not found", status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = self._body_json()
            if parsed.path == "/api/project":
                save_project_settings(self.workspace, payload)
                self._json({"ok": True, "data": studio_snapshot(self.workspace)})
            elif parsed.path == "/api/generate-voice":
                self._json({"ok": True, "data": generate_voice(self.workspace, payload)})
            elif parsed.path == "/api/generate-storyboard":
                self._json({"ok": True, "data": generate_storyboard(self.workspace, payload)})
            elif parsed.path == "/api/write-action":
                self._json({"ok": True, "data": write_studio_action(self.workspace, payload)})
            elif parsed.path == "/api/upload-panels":
                self._json({"ok": True, "data": save_uploaded_panels(self.workspace, list(payload.get("files", [])))})
            elif parsed.path == "/api/replace-panel":
                self._json({"ok": True, "data": replace_panel(self.workspace, payload)})
            elif parsed.path == "/api/render-video":
                self._json({"ok": True, "data": render_video(self.workspace)})
            elif parsed.path == "/api/update-storyboard-timeline":
                self._json({"ok": True, "data": update_storyboard_timeline(self.workspace, payload)})
            else:
                self._error("Not found", status=HTTPStatus.NOT_FOUND)
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc), status=HTTPStatus.BAD_REQUEST)


def run_studio_server(workspace: Path, *, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> int:
    workspace = workspace.expanduser().resolve()
    ensure_studio_workspace(workspace)
    handler = type("BoundStudioHandler", (StudioHandler,), {"workspace": workspace})
    httpd = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{httpd.server_address[1]}/"
    print(f"Lianhuanhua Studio V0.3: {url}")
    print(f"Workspace: {workspace}")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Studio stopped")
    finally:
        httpd.server_close()
    return 0
