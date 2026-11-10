# Commission-based chapter repair

New masters use v4 source fingerprints. Macro receives compact verbatim source evidence and requests a 100–150 word creative_contract naming active strands, roles, intercut relationships, causality and outcome. Chapters receive the Macro summary plus original relationship evidence, not the full brief or future chapter list. No split-screen/dual-panel; location cuts require separate timed views. The contract is persisted and included in chapter cache keys. Existing saved v1–v3 masters retain fingerprint compatibility.

New chained masters retain authoring_chapters and macro_creative_contract. Commission review receives the ORIGINAL brief, optional SRT, contract, chapter boundaries and complete timed beats. Tickets name zero-based target_chapter, a source/time evidence reason and repair_instruction. The existing bounded repair loop replaces only each named chapter's beat interval, then checks the complete timeline again. The new path cannot select whole-film rewriting. Invalid review output stays review_failed_open; exhausted/no-op repairs leave warnings. Old saved/single-delivery masters continue through the existing review path.

The checklist covers strand development (including a required strand vanishing for more than one chapter), scene-specific vocal roles, commissioned causal outcome, actual cut representation and no split-screen. Unequal irregular intercutting remains valid; there is no scene count or duration quota. Source extraction is heuristic evidence selection, not semantic recognition. The Macro and reviewer remain responsible for understanding the commission; a well-formed clean review can still be semantically wrong. Python does not claim to prove story quality.

Tests use the 58.5-second duration and the supplied intercut boxing/concert CUE with deterministic mock responses. They verify contract propagation/resume, chapter tickets and stitching, unchanged neighbors, local cut clocks, unequal intercut acceptance, single-strand behavior and malformed-ticket warnings. They do NOT prove a real 9B catches lost strands. No real local 9B generation or H3 rendering was available in this execution environment; no 3–5 second repair-time claim is made.

After updating, create a NEW Prepare recipe task with the same source song/CUE and SRT choice. Resume intentionally reuses saved masters. Inspect creative_contract.json, whole_film_spine.json, whole_film_chapter_*.json, commission_review_*.txt, film_repair_*.txt, screenplay_review.json and the compiled prompts. Verify that the real model preserves both strands and that any missing strand receives an evidence-based chapter ticket. Video rendering is a separate acceptance step.

## Follow-up: f8e6bca315e7

The real run retained a concert return at 38.84s but review incorrectly named chapter 0 (and later Shot index 8 as a chapter). Repair returned beats beyond chapter 0, so none were adopted. Follow-up uses explicit evidence_at_ms, or the first seconds timestamp in the reason when available, to resolve chapter identity. The reported chapter is retained in the audit; no timestamp is moved. Ambiguous/out-of-range tickets still use bounded format retries and warnings. This heuristic can misroute a reason whose first timestamp refers to a different comparison event; explicit evidence_at_ms is preferred and real 9B validation remains required.

Local repair now salvages in-range beats for chapter zero as well as later chapters, sorts/deduplicates those timestamps, and ignores out-of-range events without clamping them into the chapter. Empty unusable repairs retain the existing bounded warning behavior. Review-format failure keeps previously discovered issues visible. Prompts explicitly check mismatched stage/ring state, hidden scene cuts and shared future-ending leakage; these semantic checks remain model judgments.

The recipe-ready view suppresses the duplicate event-plan panel; after leaving recipe review the event panel remains available. The actual H3 prompt viewer is unchanged.

## Upstream cast and handoff repair

Actual Macro tables used identity, duties and scene_duties. The old whitelist discarded all three, leaving only IDs in early chapters. The revised adapter preserves identity/reference/role fields and excludes explicit plot-goal keys. Legacy duty strings are separated by clause, omitting obvious future-ending clauses while preserving other duties. This is conservative text cleanup, not a guarantee of semantic spoiler removal; Macro is explicitly instructed to keep plot goals out of cast definitions. Current shot state remains authoritative for mutable wardrobe and props.

The previous-last-beat handoff now contains only ongoing state, ongoing camera/prose and shot ID; original initiation/action is excluded. Macro and chapter prompts require one physical location per beat and a distinct timed shot_id for actual cuts. Exit-state instructions request current conditions organized by scene, not a past-event recap. No new semantic exception or extra model call is added. New masters are v5 with a fingerprinted handoff contract and updated chapter cache key; saved v1–v4 fingerprints remain compatible. Actual 9B/H3 behavior still needs a fresh recipe run.

## Typed handoff follow-up (supersedes keyword cleanup above)

Removed all keyword-based sentence deletion from stable cast duties. Macro now explicitly separates identity and scene_duties from chapter plot goals. Only explicitly named plot-goal fields are excluded structurally; identity and vocal permissions remain verbatim. Chapters and native H3 export use the same projection, so explicit outcome fields no longer re-enter via the raw Macro table. This is source schema guidance, not a claim that code can detect a future event hidden inside a misused identity string.

Chapter exit_state requests scene_states containing position, pose, physical_condition, wardrobe and props. Before the next chapter, only these typed present-state fields (plus legacy location/condition aliases) are projected. Free-form exit strings and action/goal fields are omitted without failing the chapter. If a legacy model omits typed state, the existing ongoing handoff remains available; full per-scene state may be incomplete and requires real-model inspection. No lexical violent-verb filter or additional inference call was introduced.

CHAPTER_SYSTEM explicitly requires exactly one physical camera view/location per beat and advances to a different beat/shot_id for a location cut. This is a generation instruction, not a new fatal validator. New v6 masters fingerprint the revised handoff contract; saved v1–v5 fingerprints are preserved. creative_contract.py was not modified in this patch.

## Evidence-priority review correction — task 2364aa8fa975

Two actual tickets confused a 15s-stage/17s-ring intercut with failure to stay on the concert stage, and treated lyric imagery as a physical last-ten-second countdown at 30s. Commission review now receives chapter boundaries/IDs without Macro goal/entry/exit_target prose. Original brief is authoritative; generated summaries are drafts. Review and local-repair instructions require evidence for physical countdowns and both event times for claimed replay; a similar guard/standoff is insufficient. No additional model pass, fatal validator or scene quota was added. Policy version 2 prevents reuse of a stale policy-1 review when planning is actually invoked again; prepared saved projects remain resumable.

The new regression verifies assembled model inputs for those conditions and preservation of an accepted irregular intercut with mocked responses. It does not assert a real 9B reviewer has ceased hallucinating. Real-model acceptance requires a fresh recipe task.

## Cumulative progress and intentional editorial repetition

New v7 chapter inputs include compact event_progress.history derived from accepted earlier chapter beats (global event IDs/times and action summaries only), current per-scene state, the current chapter task and a read-only next chapter goal. History means already authored, not video-rendered or universally completed: unfinished momentum can continue and intentional replay/flashback/motif use is permitted. It is not a ban list. History is reconstructed from accepted chapter output on retry/resume and included in checkpoint identity; no model-written history can silently invent completed events. Very long films will need a bounded memory strategy; this patch does not claim arbitrary-length context efficiency.

Commission review now omits the generated Macro summary while retaining verbatim source evidence, the original brief and the full actual timeline. Removed the more-than-one-absent-chapter rule. Unequal intercutting and purposeful replay are not themselves defects; accidental chronology resets require evidence. Policy version 3 avoids reuse of older review judgments when planning runs again.

Targeted repairs receive only the named chapter's beat list and clock rows plus existing neighboring context; their output budget is capped at 6144 tokens and their final delivery contract requests only the editable range. The original brief and global constraints remain available to avoid changing the premise. No extra inference call or new semantic rejection was introduced. Full updated-film review still follows the edit.

Regression checks inspect actual assembled inputs with deterministic model responses. Real 9B quality and runtime, including intended replay recognition, remain unverified until a fresh local recipe run. H3 was not rendered.
