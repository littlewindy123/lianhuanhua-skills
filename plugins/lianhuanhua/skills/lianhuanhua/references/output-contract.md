# Output contract

A successful project contains:

- decodable narration audio,
- normalized timeline JSON,
- subtitles SRT,
- character and style bibles,
- storyboard JSON,
- all approved panel images,
- silent H.264 MP4,
- final MP4 with video and audio,
- raw TTS events or transcription metadata,
- logs containing FFmpeg commands and errors.

Validation must check:

- final file exists and is non-empty,
- video stream exists,
- audio stream exists in final video,
- resolution matches project settings,
- duration difference from narration is within tolerance,
- every storyboard panel file exists,
- JSON files pass schemas.
