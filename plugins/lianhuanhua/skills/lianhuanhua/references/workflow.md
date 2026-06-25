# Workflow

## Stages and gates

| Stage | Main artifact | Gate before continuing |
|---|---|---|
| Input | `project.json` | Files readable, mode known |
| Audio | `narration.*` | Audio decodes and duration is valid |
| Timeline | `timeline.json` | Segments sorted, no negative times |
| Identity | `character_bible.json` | Defining traits are explicit |
| Style | `style_bible.json` | Palette and rendering rules are fixed |
| Character sheet | `character_sheet.png` | Visually matches original reference |
| Storyboard | `storyboard.json` | Covers full timeline without accidental gaps |
| Panels | `panels/*.png` | Every panel passes review |
| Silent render | `silent_video.mp4` | Correct duration/resolution/video stream |
| Final render | `final_video.mp4` | Video and audio streams decode |

Do not collapse all stages into one prompt. Persist each decision so a later run can resume without restarting.
