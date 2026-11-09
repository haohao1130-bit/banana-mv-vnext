# Local filming handoff comparison — 2026-11-09

## Evidence and limits

Completed old MV task `6d77adf41128` was created on November 7 Taiwan time,
before the November 8 fixes. Its saved allocation repeats the correct-file / full
regeneration pair in intervals 13–14 and 15–16. Sampled final-video frames show
similar document/performance imagery with different coverage. This is not proof
of perfect event continuity. The last 2-second commission holds the slumped man;
the native draft adds customer dialogue, and a 201-second frame shows the customer.
Frame inspection does not verify the actual audible dialogue or lip sync.

The old request already supplied roughly 6,164 characters and 14 acts. It is not
an apples-to-apples test of automatic expansion from a rough story cue.

## Confirmed engineering difference

The legacy `write_shoot_prompt` and VNext `prepare` had separate instruction sets.
VNext omitted portions of the legacy local commissioning rules and did not pass
the existing FREE/FAITHFUL adaptation selection to its camera writer. This
instruction drift is confirmed; its causal effect on generated quality is not.

Extract the existing local commissioning prose as `LOCAL_FILMING_COMMISSION`.
Use it in both writers and local filming repairs. Retain VNext-specific state,
momentum and scene-instance instructions. Replace the legacy unconditional
singer/challenger distinction with commissioned scene-role duties, since one
identity may occupy both roles. No new model call, semantic gate, dependency,
image renumbering, render behavior or saved-production migration is introduced.

## Validation

Paired request-capture tests send the same script through both entry points for
terminal holds, action consequences and parallel-strand returns, in FREE and
FAITHFUL modes. They verify shared rules, exact local event/setup delivery,
selected adaptation, one fresh writer call and unchanged stored mock output.
These are request-contract tests, not generated-quality A/B results.
Existing worker tests cover all prompts before rendering, chain numbering,
source audio and interrupted resume. Actual 9B/H3 quality remains unverified;
compare identical source clips/materials in a future controlled model run.

## Research basis

- Official H3 reference guide: https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/ref-en.txt
  One reference asset can supply several subjects; Subject and speaker IDs have
  distinct roles. This supports the format, not proven same-face role isolation.
- Huang et al., ICLR 2024: https://arxiv.org/abs/2310.01798
  Intrinsic self-correction can fail on reasoning tasks without external feedback.
  This is an analogy supporting evidence-based reviews, not a 9B video benchmark.
