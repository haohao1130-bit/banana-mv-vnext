# V2 review implementation and verification

## Confirmed from code and the latest supplied job

- `screenplay_review.json` reports `review_failed_open`, rounds zero, JSON delimiter failure at char 834. The old code invoked `json.loads` once inside the whole-loop exception handler. It neither retried formatting nor retained the malformed review response. The exact missing character cannot now be established.
- Native prompts contain ring actions after an explicit stage cut and singing in ring shots despite scene-specific user roles. This is present in the written prompts, before rendering.
- The global review previously had no explicit optional-SRT policy or timing comparison instruction. Current local SRT already carries both global source bounds and clip-relative bounds; reuse it.
- The 30–45-second commission refers to an earlier lyric phrase; the final camera sequence schedules the final lyric in a shot starting before its SRT onset. Exact onset inside a multi-second shot remains ambiguous; do not treat every earlier shot start as proof of an error.
- Same-image dual roles are a plausible contributor, not a proven sole cause. Shared setup also mixes world/plot prose; scene mapping must obey the original brief over generated settings.

## Sources and applicability

| Source | Verified method | Applied here |
|---|---|---|
| [llama.cpp grammars](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md) | Backend-supported grammar constrains a subset of JSON Schema | Analogy only: current ComfyUI TextGenerate inputs expose no verified grammar/schema option. Do not claim constrained decoding or change runtime. Embed schema and strictly validate the review result. |
| [json_repair](https://github.com/mangiucugna/json_repair) | Strict JSON first; fallback repair; cautions about changed values and ambiguity | Use stdlib only and a narrower string-aware trailing-comma repair. Never close truncated arrays, infer missing issues or turn failure into an empty pass. Invalid escaping triggers a fresh bounded review. No new dependency. |
| [Self-Refine paper](https://arxiv.org/abs/2303.17651) | Iterative feedback, refinement and re-evaluation with the same LLM | Borrow bounded full-script feedback / local replacement / full updated-script review. Paper results on other models/tasks do not prove this quantized 9B's QA accuracy. |
| [H3 Ref2VA guide](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/ref-en.txt) | Subject is a content unit; one asset may supply multiple subjects; speaker ID differs from subject ID | Prefer B initially: scene-role instances with separate Subject definitions referencing the same original Picture. No new image input, no silent numbering changes. Actual multi-instance visual reliability remains untested. |
| [pysubs2 API](https://pysubs2.readthedocs.io/en/latest/api-reference.html) | Subtitle events represent timed text intervals | Retain existing parser/excerpt; no new subtitle library. Declare global source vs local shot clocks. Use interval overlap with a 0.75s margin for conservative exact-phrase checks, not cut scheduling. Margin is an engineering choice, not an H3 guarantee. |

## Implementation

`review_output.py` provides a schema-shaped contract, strict structure/types/index validation, duplicate-key rejection, fenced/thinking wrapper handling, narrow comma repair, and at most two format retries. Each attempt saves its response and parse status. It is not token-constrained output.

Global review preserves full-script context, issues, retries, raw repair drafts and before/after hashes. Only flagged clip bodies change. After edits the reviewer sees the whole updated script and immediate neighbors. Existing rejection of unusable repair bodies is preserved; service/format failures are warnings rather than rendering gates.

`filming_review.py` reviews the actual native prompt against its local commission and scene-role directives. It checks explicit location/activity contradictions, vocal permissions, state replay, ending scope and conditional SRT evidence. Only this clip may be rewritten; all valid coverage should be preserved. Format failure retains the last renderable prompt. A full SRT is visible to the reviewer for comparison, never forwarded to the local creative repair writer as a whole-song plan.

No SRT is valid. No singing shot is valid. Missing lyric coverage is valid. Explicit sung text scheduled in a demonstrably non-overlapping interval is a candidate issue. A quoted theme is not a singing event. Deterministic checks match substantial exact normalized phrases; translations, paraphrases, unknown lyrics and subtle scene semantics are left to the model reviewer and remain fallible. Source time is explicit in each clip; shot clocks remain local.

All quality failures appear in status preview/UI with a warning; the existing approve/open controls remain available. A warning means review before rendering, never verified safe output. Global screenplay repair limit is two rounds; local filming repair limit one; each review's format retries cap at two. More 9B calls are expected, bounded and logged. No H3/GPU run was performed during engineering.

## A vs B

A (three input images) remains an explicit user-input option, not an automatic conversion: upload stage and ring references separately and bind each by its provided number. It consumes an additional existing image slot and can alter continuity numbering, so it is not enabled by silently duplicating images. B uses documented multi-Subject referencing and preserves existing media slots. No automatic global Subject-ID renumberer is introduced; adherence is prompted and reviewed, not guaranteed by text rewriting.

## Regression scope

Tests use sanitized structural fixtures, not private assets or the user's full screenplay. Cover malformed quotes/trailing commas/truncation, schema and index errors, bounded retries, failure warnings, local replacement then full review, optional SRT, no vocal coverage, wrong-interval lyrics, local shot timing, scene confusion repair, keeping full SRT out of local rewriting, existing replay/HARD STOP checks and the current short-tail threshold. Offline substitutes cannot verify actual creative quality, model obedience or lip sync.

Existing short-tail semantics (at most 3 residual seconds with a preceding segment), original source audio/SRT, H3 graph, image numbering, retakes and assembly are preserved. Existing ready productions are not rewritten. Use a fresh task for real 9B draft testing, then opt into a short L4/H3 validation after inspecting warnings and prompts.
