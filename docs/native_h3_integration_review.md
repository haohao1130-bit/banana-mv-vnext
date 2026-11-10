# Native H3 director integration review — 2026-11-11

Base: `fix/restore-native-h3-director` at `2e70625`.
This review preserves Macro Spine → Chained Chapters and source-song rendering.
No main/Colab notebook/environment/model changes are included.

## Confirmed from code and reproducible offline checks

- `enhance_window` passes the entire guide file into a dedicated local camera
  call. The long-guide sentinel test verifies content beyond 6,000 characters.
  Story authoring retains its compact JSON-specific commission; only the local
  native camera director receives the complete human guide.
- Initial authoring exported accepted native text, but revision `_compiled()`
  bypassed it. The author and candidate pipelines now share `direct_window()`.
  Changed windows receive the independent camera pass, unchanged windows retain
  their saved shooting text byte-for-byte. Native camera drafts/cache/inputs live
  inside the unpublished revision until explicit adoption.
- The former cache key omitted direction, SRT/music context, model parameters
  and image content. Version 2 keys hash the complete local context, final system
  (including the full guide and camera contract), rewriter settings and images.
  This applies when the author/revision pipeline is invoked; an already prepared
  old job is deliberately not auto-migrated or silently regenerated.
- Runtime/model errors formerly escaped the nonblocking fallback. They now record
  a warning and retain the valid compiler draft; transport errors do not trigger
  a format retry. Missing/unreadable guides do not run a guide-less call and label
  it restored camera output. A successful retry clears a stale warning.
- Camera warnings reached `director_plan.json` but were dropped by status preview.
  Active plan warnings now reach the existing quality-warning UI. Each segment
  also exposes native/fallback provenance, explicitly without render verification.
- Safe format normalization handles a whole Markdown fence, decimal zero-padding,
  `at` capitalization and an explicit first-shot zero clock. It never moves or
  rounds a cut, repairs a missing scene, or changes a required time. Missing/shifted
  locked cuts still warn/fallback after the bounded format retry.

## Evidence artifacts

For each local window in `preproduction/`:

- `NN_native_h3_input.json`: actual full system, local commission, guide path and
  character count, model parameters and cache identity.
- `NN_native_h3_raw_*.txt`: actual model deliveries.
- `NN_native_h3.json`: accepted unshifted native output and cache identity.
- `NN_native_h3_warning.json`: fallback reason, attempts and error records.
- `NN_native_h3_delivery.json`: `native` or `fallback` and the digest of the actual
  final, chain-adjusted prompt. These statuses describe delivery/format, not
  semantic screenplay acceptance or successful video rendering.
- `NN_prompt.txt`: exact prepared H3 prompt. Original reference slots are shifted
  once for chain windows after camera authoring, reserving Picture 1 for continuity.

Candidate camera artifacts remain under `preproduction/recipe_revisions/<id>/`.
Adoption publishes the corresponding native cache/delivery/warning together with
story and prompts, using the existing backups and rollback. A camera fallback is
visible in the candidate plan; explicit adoption still belongs to the user.

## Source comparison

- Official full-reference guide:
  https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md
  It requires six sections and detailed shot composition, positions, action/state
  changes, lighting and camera movement, rather than synopsis prose.
- Earlier working per-window implementation, `write_shoot_prompt()`:
  https://github.com/haohao1130-bit/banana-mv-public/blob/main/banana_mv/shoot_plan.py
  It loads the full guide, supplies current-script/local timing evidence and asks
  the model to choose cinematography. This change restores that role after a
  locked timeline, rather than transplanting its entire author/render architecture.

## Verification and limits

- Baseline: 411 Python tests passed.
- Updated: 421 Python tests passed; Node UI/asset-reuse checks passed.
- New checks cover runtime/guide fail-open, contextual cache invalidation, safe
  format-only correction, chain reference shift and output digest, local revision
  camera adoption/unaffected-window preservation, failed candidate isolation and
  warning/provenance visibility. All model outputs in these tests are mocks.
- Existing Windows launcher and notebook files are unchanged. Windows parsing is
  delegated to the existing GitHub Actions check; no local PowerShell is available.
- Latest inspected Drive task `88dcf71e527a` has no `native_camera_version` and no
  native-camera artifacts. It is an old-path example, not an acceptance run.
- No RTX 5070 9B job or H3 rendering was run from this workspace. Fine-grained
  blocking, meaningful intercuts, singing permissions, untouched finale timing
  and fallback frequency remain real-model acceptance items. Deterministic cut
  checks alone cannot establish those semantic properties.

## Next local acceptance

1. Fetch/switch/pull this repair branch and restart Banana with the existing CU130
   setup. Keep main and the Comfy/PyTorch/model environment unchanged.
2. Create a NEW recipe using the same ~58.5-second song, reference images, original
   brief and optional SRT. Do not regenerate a saved old recipe implicitly.
3. Check `native_camera_version=1`, all window delivery statuses and any warning.
   Confirm prompt provenance matches the actual prepared `NN_prompt.txt` files.
4. Read the full per-window shooting prose: concrete movement/contact/reaction,
   camera paths, separate locations, assigned vocal roles and correct finale.
5. If requesting a local revision, inspect candidate native camera artifacts;
   compare with original, then explicitly adopt/keep. No H3 render is needed to
   assess this text-only stage. Actual video cuts require a separate H3 render.

## Additional actual-run finding: four Macro calls

Task `88dcf71e527a` saved four Macro deliveries (initial + three configured retries).
This was upstream of the restored native camera stage; its request has no
`native_camera_version`. Two deliveries (`33ba4dd2`, `aa359658`) contain complete
chapter arrays after a prematurely closed root JSON object. The decoder read only
the prefix and validation reported missing chapters. The next delivery (`bed0e745`)
is truncated inside a repeated appearance string. The final `c56ed879` is valid.
Chapter 1 separately needed one retry for a missing `continuation_state`.

A narrowly scoped `_spine_delivery` format recovery now joins only an exact
complete `"chapters": [...]` suffix after that early root close and requires strict
JSON parsing. No story values, times or missing text are synthesized. Both saved
failure deliveries validate as four chapters after this mechanical recovery.
A regression test exercises the author pipeline and confirms one Macro call for
that complete-but-malformed shape. Truncated text still requires a bounded retry.
`whole_film_spine_attempts.json` records attempt, raw file, repair method and error,
so future retry causes no longer need to be inferred from file counts. Configured
Macro/Chapter retry limits are unchanged; native-camera format attempts remain
at most initial + one retry. No extra semantic rejection loop is introduced.
