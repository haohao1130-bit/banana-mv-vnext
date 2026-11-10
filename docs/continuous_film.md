# Continuous whole-film preparation (experimental branch)

A single 9B creative request expands the source brief into one global shooting
script. Render intervals are selected afterward; they are not supplied as CLIP
commissions or sent to a second camera writer. Beat lengths and cuts are creative
choices, independent of 10/15-second technical windows.

Each authored beat has a global millisecond onset, stable shot ID, camera prose,
present state, new action, ongoing activity and its ongoing state/camera view. An ongoing
phase is written in the original whole-film call, not invented at the boundary.
A window receives its active snapshot and only actions whose onsets occur in it.
If it begins inside an existing beat, it receives that beat's authored ongoing
phase, without its already completed initiation. A new beat with the same shot ID
continues the same view; it does not become an editorial cut.

Example: a global 20,000 ms cut becomes local 5,000 ms in a window beginning at
15,000 ms. The compiler does not rewrite its action or camera instructions.
Previous/future action paragraphs are excluded. Identity/scene/vocal definitions
are shared; mutable appearance belongs to the active state, which overrides the
initial reference wardrobe. Snapshots are planned prose, not observations of H3.

## Integration and compatibility

New tasks on this branch persist `whole_film_version=1`. Old requests without this
field continue using their existing preparation and review code. The UI, source
song, H3 sampler, LoRAs, reference slots and renderer are reused. Chain mode still
injects the actual previous last frame and shifts original Picture indices once.
Preparation marks ready only after the worker has saved the derived local plans.
Resume recompiles a saved master without another creative call.

The full-film call reserves at least 16,384 generated tokens in a copied writer
configuration. It does not change every model call's default. This is an
experimental budget, not proof of five-minute model capacity. Generation elapsed
time, character count and configured token ceiling are recorded; the backend does
not expose actual token usage or a reliable finish reason. Raw responses survive
bounded delivery retries. JSON parsing/timestamps/required data are execution
checks; no semantic vetoes or cut quotas are introduced.

## Scope and remaining validation

Existing clip screenplay/filming repair prompts are deliberately not applied to
this new representation: they would re-author isolated commissions. A visible
`not_run_whole_film` quality warning records this, rather than claiming review
passed. Legacy tasks retain their existing bounded review/repair path. A future
whole-film review needs to preserve this single authoring unit; it is not part of
this initial prototype.

Offline tests verify 10- and 15-second slicing of a synthetic five-minute script,
no duplicated event onsets, no prior/future action leakage, same-shot continuation,
chain numbering, missing SRT, bounded format retry, and the real worker's
prepare-before-render and interrupted resume with mocked model/GPU calls.
They do not measure actual 9B performance, artistic quality, exact physics inside
a long beat, or H3 reproduction. First live test should use “prepare recipe” only
and inspect `preproduction/whole_film.json`, `whole_film_generation.json` and all
compiled prompts. No GPU inference was launched during implementation.

## References

- ComfyUI TextGenerate output-token control:
  https://github.com/Comfy-Org/docs/blob/main/built-in-nodes/TextGenerate.mdx
- H3 reference and shot conventions:
  https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/ref-en.txt
- Context selection rationale, not a video-quality benchmark:
  https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

The branch notebook explicitly clones `feature/continuous-film`; use a fresh
Colab runtime because the existing bootstrap intentionally reuses an installed
checkout. Main remains on the prior implementation until live evaluation.

## First live delivery failure: task 73c4d5f974bb

All four raw attempts supplied subject_definitions as an array of identity records,
while the initial parser accepted only a string and incorrectly reported missing
identity. Two attempts are complete JSON (16 and 5 beats); two exhibit repetition
and end inside a string. Accept nonempty string/list/object identity definitions,
rendering structured tables losslessly without guessing Picture mappings or
renumbering identities. On resume, inspect this immutable job's saved raw attempts
in creation order and recover the first structurally valid complete timeline before
calling 9B. Keep every raw file and log accepted/rejected candidates. Never close
truncated JSON to manufacture a complete film. The actual two complete deliveries
compiled into all four windows offline; this says nothing about their story quality.

Model repetition/truncation remains a separate observed generation limitation.
This fix does not claim to solve it or silently accept a partial timeline.
