# FFmpeg rendering

## Visual output

Default:

- 1080x1920,
- 30 fps,
- H.264,
- yuv420p,
- AAC audio.

## Image fit

Never stretch source art. Scale and crop to cover the canvas. When a crop would remove the subject, use a blurred/background-filled layout or revise the composition before rendering.

## Motion

The renderer supports restrained Ken Burns effects. Motion should be subtle enough that line art does not shimmer or reveal empty crop edges.

## Transitions

Crossfades consume overlap time. The renderer extends source clips internally so the final duration remains aligned to the absolute storyboard duration.

## Subtitles

Always export SRT. Burning subtitles is optional because font availability differs by operating system. When burning Chinese subtitles, configure an installed CJK font such as Microsoft YaHei or Noto Sans CJK SC.

## Audio

Narration is the source of truth for duration. Final muxing should trim or pad video only when necessary and must not stretch narration by default.
