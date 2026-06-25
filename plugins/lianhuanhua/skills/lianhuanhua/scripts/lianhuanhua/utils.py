from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable


class CommandError(RuntimeError):
    pass


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False) + "\n")


def executable(name: str) -> str | None:
    return shutil.which(name)


def run_command(
    args: Iterable[str],
    *,
    log_path: Path | None = None,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    cmd = [str(a) for a in args]
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if log_path:
        ensure_dir(log_path.parent)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("$ " + " ".join(cmd) + "\n")
            if result.stdout:
                handle.write(result.stdout + ("\n" if not result.stdout.endswith("\n") else ""))
            if result.stderr:
                handle.write(result.stderr + ("\n" if not result.stderr.endswith("\n") else ""))
    if check and result.returncode != 0:
        raise CommandError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr.strip()}"
        )
    return result


def ffprobe(path: Path) -> dict[str, Any]:
    if not executable("ffprobe"):
        raise RuntimeError("ffprobe is not installed or not on PATH")
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ]
    )
    return json.loads(result.stdout)


def media_duration(path: Path) -> float:
    info = ffprobe(path)
    duration = info.get("format", {}).get("duration")
    if duration is None:
        durations = [s.get("duration") for s in info.get("streams", []) if s.get("duration")]
        if not durations:
            raise RuntimeError(f"Could not determine duration for {path}")
        duration = max(float(value) for value in durations)
    return float(duration)


def resolve_workspace_path(workspace: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else workspace / path
