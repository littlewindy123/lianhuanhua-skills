# Character consistency

Consistency is a workflow, not a single prompt sentence.

## 1. Character bible

Record immutable traits using observable facts from the reference:

- species/person type,
- silhouette and body proportions,
- face/head shape,
- eyes, ears, hair, markings,
- fixed clothes and accessories,
- line weight and material style,
- fixed colors.

Record mutable traits separately:

- pose,
- facial expression,
- camera angle,
- lighting,
- background.

Record forbidden changes explicitly.

## 2. Character sheet

Generate a neutral sheet before story panels. It should provide enough angles to reuse the design but must not invent hidden details recklessly. If the source only shows a head, do not assert an exact full-body design without labeling it as an approved extension.

## 3. Style bible

Lock:

- line style,
- palette,
- shading,
- texture,
- background density,
- lighting softness,
- aspect ratio,
- prohibited styles.

## 4. Continuity ledger

Each shot carries forward:

- location,
- time of day,
- weather,
- character position,
- facing direction,
- pose before/after,
- clothing/accessories,
- props,
- active emotion,
- visible injuries/dirt/state changes.

## 5. Anchor-first generation

Generate high-value anchors first. An anchor establishes a stable scene and character state. Later images reference the closest approved anchor.

## 6. Sequential generation

Do not generate all panels concurrently. Use this reference chain:

```text
original reference
+ approved character sheet
+ nearest scene anchor
+ previous approved panel
+ current shot prompt
```

Use previous-panel editing for incremental action. Use a fresh composition with all references only for major scene changes.

## 7. Visual review

A panel fails when any defining trait changes, style drifts, continuity breaks, or the image does not express the narration. Repair the smallest incorrect region or instruction. Avoid full regeneration unless composition is fundamentally wrong.
