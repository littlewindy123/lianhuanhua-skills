# AGENTS.md

## Project goal

Build and maintain a Codex-only plugin that turns a story, audio file, or video plus character references into a consistent comic-style vertical video.

## Architecture rules

- Creative decisions belong in `SKILL.md` and `references/`.
- Deterministic behavior belongs in Python and FFmpeg.
- JSON files are contracts. Update schemas and templates together.
- Never log API keys, tokens, or private user media contents unnecessarily.
- Preserve raw Doubao event logs without secrets for protocol debugging.
- Keep image generation sequential; do not optimize it into uncontrolled parallel batches.
- Do not report successful delivery unless ffprobe validates the final output.

## Commands

```bash
SKILL=plugins/lianhuanhua/skills/lianhuanhua
PYTHONPATH="$SKILL/scripts" pytest -q "$SKILL/tests"
python "$SKILL/scripts/lianhuanhua_cli.py" doctor
```

## Before committing

1. Compile all Python files.
2. Validate every JSON file.
3. Run tests.
4. Run the synthetic FFmpeg smoke test described in `CODEX_TODO.md`.
5. Check that repository files contain no credentials or generated user media.
