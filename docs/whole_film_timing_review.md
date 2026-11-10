# Continuous-film timing and review

The continuous-film branch now reviews the master timeline before compiling its
render windows. A delivered JSON object is not evidence that the plot follows
the user's timed brief.

The author retains explicit story windows and scene-specific vocal duties,
expands montage into actual timed views, and separates present state from new
visible action. It chooses shot density creatively; no shot quota or genre-specific
story rule is imposed. The window compiler still only selects beats and converts
global milliseconds to local time. It now labels new action separately from state.

The review uses the complete source brief, supplied SRT (if present), roles and
indexed master beats. Conservative lyric checks apply only to explicit sung
claims. Missing SRT, missing performance coverage and ordinary repeated actions
are not errors. No lyrics or source media are changed.

Local issues trigger replacement of only the flagged contiguous beat ranges;
unchanged neighbors are retained. Repairs may add, remove or retime beats inside
that range, followed by a fresh global review. Up to two repair rounds and two
review-format retries are permitted. Invalid responses preserve the usable draft
and leave failed-open/warning status instead of a false pass or a rendering gate.
Existing JSON review helpers are reused; no dependencies or frameworks are added.

Records: screenplay_review.json at the task root; film_review_* and film_repair_*
raw deliveries under preproduction. A changed master also saves its pre-review
copy. Matching saved reviews are reused on resume. Existing ready projects retain
their cached prompts; create a NEW recipe task to evaluate the revised author.

For Windows, stop Banana MV before pulling this branch and restart afterward.
CU130 ComfyUI can remain running. The desktop launcher can pull the current branch
with --ff-only when the checkout is clean. If the separate local Story Fix ZIP was
already applied, restore it before pulling; do not reset unrelated local changes.
This commit changes neither the notebook nor ComfyUI/Torch/model installation.

Validation: 45 focused tests passed. Full local discovery ran 336 tests: 335
passed; one runtime/widget test could not import IPython in the development
runtime. CI installs IPython. Apply/restore of the separate local patch was also
tested. Real Qwen 9B story quality and H3 rendering require a subsequent user test;
unit tests and a self-review are not proof of creative correctness.

The regression fixture reproduces an early defeat at 35 s and an explicit final
vocal claim at 41 s against a supplied 54.5 s lyric. Its numbers and boxing premise
are test data only, not production rules.

Research analogy: [Self-Refine](https://arxiv.org/abs/2303.17651) describes iterative
feedback/refinement. It was not evaluated on this checkpoint or this MV task;
this implementation uses bounded local edits and existing project utilities.

## Clock and repair-scope correction

Review inputs now include program-calculated start/end/span seconds alongside the
unchanged integer millisecond clock and source duration. A beat at 8000 ms begins
at 8 seconds; if it is the last beat in a 58.5-second song, it continues for
50.5 seconds. The reviewer must not interpret this as an 80-second timeline.
No heuristic timestamp scaling is performed.

The existing issues JSON schema now permits index -1 as an explicit whole-film
issue. Global clock/story allocation or a lost parallel strand can then replace
the complete timeline within the same repair-round limit. Local issues retain
neighbor-preserving edits. All repaired films receive another complete review.
Malformed repairs preserve the original film and leave warnings. Review audit
version is 2, so prior version-1 reviews do not claim this check was performed.

No SRT is required. Explicit timing in the original brief remains authoritative
without lyrics or subtitles; no precise sung timing is invented from plain lyrics.
The regression fixture contains no SRT and reproduces all story beats crowded
into 0–8 seconds with the terminal state repeated in later technical windows.

Review output is capped at 4096 tokens for the compact issues JSON. Full-script
repair retains the full author budget (at least 16384); the movie itself is not
shortened. Format retries and repair rounds remain bounded.

Validation for this correction: all 340 offline tests passed (including the
previously unavailable IPython widget test). 49 focused tests passed, including
explicit no-SRT whole-film repair,
local neighbor preservation, malformed global repair, millisecond/second display,
and unchanged original timestamps. Real 9B behavior still needs a fresh recipe
task; existing ready tasks deliberately keep their saved prompts.
