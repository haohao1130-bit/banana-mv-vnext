# Continuous-film pipeline audit — 2026-11-10

## Contract

Author the complete timed story AND photography before rendering. The upstream
shooting timeline describes causal actions, actual views, composition, camera
movement and editorial cut times. It also contains already authored native H3
shot paragraphs. Save the complete six-section `whole_film_prompt.txt` first,
then export render windows from that approved timeline. No window writer is
called. A technical 10/15-second boundary is not a new story or editorial cut.

Each H3 request receives only:

- Stable reference identity, setting and scene-specific role definitions.
- The current visible state: remaining wardrobe, held props, physical condition,
  position, pose and movement needed now. This is not a plot recap.
- The native Shot paragraphs belonging to that window, in local time.
- Source-audio reuse instructions.

A mid-phase entry uses `continuation_state` and `ongoing_filming_prompt`, not the
phase's already completed initiation. An actual contact, fall or changed outcome
must be authored at its own time rather than hidden in an earlier long synopsis.
Stable definitions must not contain the opening, climax or ending instructions.
The complete brief, adjacent events and source lyrics are not forwarded to H3.
The global author/reviewer may know the whole story; the renderer cannot.

This is a context boundary, not a claim that deterministic code understands every
possible event inside free prose. Incorrectly authored past/future content inside
a supposedly local paragraph still requires semantic review and a real 9B test.

## Wiring findings and changes

| Item | Finding | Result |
| --- | --- | --- |
| Official Ref2VA guide | Previously bypassed by whole-film path | Reused by author and repair; missing installed file produces a visible warning |
| Finished shooting prose | Compiler used to concatenate outline metadata | Uses authored native paragraphs; keeps current state separately; missing delivery gets bounded repair/warnings |
| Complete native master | Only JSON master and individual prompt files | Saves `preproduction/whole_film_prompt.txt` before window exports |
| Style selection | Absent from whole-film commission | `direction.selected_style`, existing activity recipes, exclusions and explicit role declarations reach author and repair |
| Intensity and cuts | Author used controls, repair could lose them | Shared direction contract applies to author and repair; camera recipes remain scene-scoped |
| Face-priority toggle | Not read by whole-film author | Stronger source-face guidance when enabled, also in native output; no hardcoded Subject 1/Picture 1 identity assumption |
| One identity, multiple scenes | Only shortened role wording | Existing scene-instance policy restored; same source picture can bind separate stable scene-role Subjects |
| Reference media aliases | Shift occurred before alias normalization | Image/Picture aliases canonicalized before chain insertion; existing connected-media validation reused |
| Native retention section | Generic source-audio sentence only | Referenced Subjects used by the current shots and actual first-frame anchor have retention entries |
| Optional SRT | Master review lacked exact render-window context | Supplies source/local cut clocks and cue excerpts; deterministic checks inspect actual selected phase prose, never require lyric coverage |
| Early final lyric | A long beat could overlap the true later cue | Explicit sung onset is checked with existing 0.75-second tolerance; no SRT means no precise lyric claim validation |
| Local repair returning full master | Rejected on first timestamp despite valid local replacement | Extracts only assigned interval; other returned changes are not applied; unchanged definitions accepted |
| Failed repair followed by empty review | Could become a false pass | Unresolved failed edits persist until repaired or warned after the fixed budget |
| Warnings in UI | Only generic global-review status shown | Existing warning area includes exact saved warning details |
| Legacy saved jobs | Must not be re-authored on resume | Version-1 fingerprint and existing prepared prompts retained; new contracts use a version-2 saved master |
| Render engine | No redesign needed | Existing lock_source, sampling, attention, LoRA, chain input, original-song assembly and tiny-tail threshold retained |
| UI folds | Existing controls need to remain functional | Director/music/identity, render acceleration and retry controls remain in the form, separately folded; IDs/values unchanged |

New jobs save the actual author payload in `whole_film_input.json` and the system
commission in `whole_film_commission.txt` for inspection. Render-window coordinates
are recorded separately from the author payload; they are review/export mechanics,
not a requested creative grid. The author still receives supplied music evidence.

## Research and applicability

1. MiniMax H3 official full-reference guide:
   https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md
   Sections 1 and 5 define the six fields, timed Shot notation and concrete
   composition/action/camera prose. The guide explicitly distinguishes detailed
   shooting descriptions from plot summaries. This is directly applicable to H3.
2. MiniMax H3 base shot/camera guide:
   https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md
   Sections 4.2–4.3 specify ordered local cut times and natural camera movement
   descriptions with meaningful extent/speed. These are directly applicable shot
   language rules, not a fixed shot count or camera-effects checklist.
3. ScreenSkills script-supervisor role and skills:
   https://www.screenskills.com/job-profiles/browse/film-and-tv-drama/technical/script-supervisor-film-and-tv-drama
   https://www.screenskills.com/skills-checklists/scripted-film-and-tv/script-supervisor-department/script-supervisor-skills/
   Continuity breakdowns track cast, action, costume, props, timings and camera
   details so separately filmed material can be edited coherently. This supports
   the state-handoff analogy. Real films are often shot out of story order; they
   do not literally use a universal 10/15-second prompt splitter.
4. MovieAgent primary project/code:
   https://github.com/showlab/MovieAgent
   https://github.com/showlab/MovieAgent/blob/main/movie_agent/run.py
   `ScenePlanning` precedes `ShotPlotCreate`, which reads characters, scene plot,
   emotional tone, key props and cinematography notes; `VideoAudioGen` consumes
   shot annotations afterward. This is a concrete planning/execution separation
   to borrow, not proof of H3/9B compatibility or a reason to adopt its framework.

The strict no-neighbor-plot renderer payload is our deliberate implementation
choice. The sources support planning, shot detail and continuity management; they
do not prove this exact isolation policy is an industry-wide or H3 requirement.
No new external framework, model dependency or GPU environment change is needed.

## Validation

- `python -m unittest discover -s tests -q`: 355 tests passed.
- `node tests/check_ui.cjs`: passed.
- `node tests/check_asset_reuse.cjs`: passed.
- New cross-layer tests cover all nine style choices, toggles on/off, role/image
  declarations, scene-instance commission, current-state-only handoff, alias shift,
  native-prose repair/warnings, missing guide warnings, optional SRT and explicit
  early lyrics, bounded failed repair state, local extraction from full returns,
  native prompt/attention/LoRA settings reaching the existing workflow, legacy
  resume and folded controls remaining in the form.
- Existing worker integration tests still cover generation interruption/resume,
  unchanged saved parts, original audio mode and chain reference shifting.
- Existing regressions retain short-tail threshold, distinct repeated actions,
  original supporting cast, source audio and translation/read-only review behavior.

Offline model responses and rendering are mocked. This validates code wiring and
isolation behavior for the supplied cases, NOT actual 9B creativity, English quality,
visual character consistency, hand quality, H3 fidelity or measured GPU speed.
Create a new local CU130 recipe after updating to inspect native shot writing.
No video generation is required for the first acceptance pass. Existing saved
recipes deliberately keep their old authored content. Main/Colab are not changed.
