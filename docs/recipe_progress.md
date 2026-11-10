# Recipe progress and furnace animation

Whole-film authoring reports real author attempts, review rounds, repair scope,
and compiled-window counts through an optional callback. The worker persists
planning_progress with stage and timestamps in the existing job status. Review
translation retains its existing block counts. No token stream, estimated
completion percentage, new dependency or extra model call is introduced.

The frontend's existing status polling displays a separate indeterminate recipe
bar, elapsed wall time and the actual current stage. The video-completion counter
remains reserved for rendering. Plan-ready is labelled as a finished recipe,
with no claim that any video has been generated. Older jobs lacking progress
metadata still show their existing high-level stage.

The inline SVG adds glasses, a manuscript and animated writing hand to Banana.
Authoring, proofreading, rewriting and completion use different data-phase
styles. The helper stops throwing ingredients while preparing a recipe. Once
rendering starts, audio/input preparation shows ingredient loading and sampling
shows the existing fire animation. Prepare-recipe still requires the original
approval action; direct generation retains its automatic continuation behavior.
Reduced-motion disables decorative movement. UI artwork never enters model refs.

Validation: 366 offline Python tests, frontend and asset-reuse tests passed.
Callback integration verifies author -> review -> repair -> review -> compilation,
without extra model calls or fabricated token percentages. DOM tests cover the
indeterminate bar, elapsed time, round text, plan-ready and loading/render states.
SVG markup parses as XML. A browser screenshot could not be produced in this
workspace (Chromium process blocked), so actual mobile visual playback remains
for the next UI reload. Do not interrupt a currently running job to update.
