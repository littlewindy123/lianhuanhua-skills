# Release checklist

- [ ] Replace repository placeholders in README and plugin metadata.
- [ ] Test installation using `codex plugin marketplace add`.
- [ ] Run `doctor` on Windows, macOS, and Linux.
- [ ] Complete one text-to-video example with Doubao TTS 2.0.
- [ ] Complete one existing-video example with faster-whisper.
- [ ] Confirm `build-prompts` exports `output/image_prompt_pack.md` and `.json`.
- [ ] Confirm `$imagegen` is used only when the user chooses Codex or hybrid image generation.
- [ ] Confirm all panels pass manual identity review.
- [ ] Render 1080x1920 H.264/AAC output.
- [ ] Add a short GIF/video demo at the top of README.
- [ ] Add real benchmark numbers only after repeatable tests.
- [ ] Create a GitHub release and tag matching plugin version.
