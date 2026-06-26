# Image workflow

Default to low-token operation. Do not call `$imagegen` or inspect images visually unless the user chose a workflow that needs it.

## Modes

- `external`: export prompts only. The user generates all panels in GPT or another image tool and returns files.
- `codex`: use Codex's `$imagegen` skill for generated or edited images.
- `hybrid`: use `$imagegen` only for selected anchors/key panels; export the rest.

If `project.image_workflow.mode` is `ask`, ask once before image generation and save the choice.

## Prompt structure

Every generated panel prompt is assembled from fixed and changing blocks:

1. Global style lock.
2. Character identity lock.
3. Scene continuity state.
4. Previous panel summary.
5. Current visual action.
6. Camera/composition.
7. Forbidden changes.

Do not rely on the phrase “same character” alone.

## Reference order

Attach:

1. Original character image.
2. Approved character sheet.
3. Nearest approved scene anchor.
4. Previous approved panel.

When too many references confuse the result, retain the original, character sheet, and nearest anchor.

Only attach references when using `$imagegen`. In external mode, list the references in the prompt pack instead.

## Edit vs generate

Use edit when:

- pose changes slightly,
- expression changes,
- lighting changes,
- a prop is added or removed,
- time advances in the same scene.

Use a new generation from references when:

- location changes,
- camera angle changes radically,
- the previous composition blocks the new action.

## Low-cost checks

Default `project.image_workflow.review` is `none`.

Validate only:

- image file exists,
- image can be opened,
- aspect ratio is close to the target,
- project/storyboard/timeline schemas pass,
- FFmpeg/ffprobe output is valid.

Do not judge character drift, style drift, emotional quality, or composition by default. The user can see externally generated panels directly.

## Optional strict review

Use strict visual review only when `project.image_workflow.review` is `strict` or the user explicitly asks. Then write `work/panel_reviews.json` with scores from 0 to 1 and concrete defects. `passed` must not be based on an average alone: an immutable character trait failure always fails the panel.
