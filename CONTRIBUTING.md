# Contributing

Thanks for helping improve 连环画 Skills.

## Good first contributions

- Add a new FFmpeg camera motion preset.
- Improve Windows path handling.
- Add a storyboard example.
- Improve Doubao event parsing against fresh API captures.
- Add character-consistency review fixtures.
- Add subtitle presets.

## Development

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r plugins/lianhuanhua/skills/lianhuanhua/scripts/requirements.txt
pip install -r plugins/lianhuanhua/skills/lianhuanhua/scripts/requirements-dev.txt
pytest plugins/lianhuanhua/skills/lianhuanhua/tests
```

Keep deterministic media work in Python/FFmpeg. Keep creative decisions and visual review in the Skill instructions.
