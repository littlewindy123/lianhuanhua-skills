# Image generation with Codex

Codex includes the `$imagegen` system skill. Invoke it explicitly so image work is visible and intentional.

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

## Review record

For each panel write a review entry with scores from 0 to 1 and concrete defects. `passed` must not be based on an average alone: an immutable character trait failure always fails the panel.
