# Reference provenance and repair outcomes

The local guide has been confirmed downloaded on the user's Windows host. This
patch handles the remaining provenance and review defects observed in job
1ba4eaa9f538; it does not claim a successful new 9B screenplay.

The author receives a derived reference_manifest containing only labels from
explicit @Picture declarations. Names are matched exactly against structured
Subject names or identity prefixes. Subject order is never used to assign a
Picture. Multiple scene instances may share one unambiguous reference identity.
Ambiguous labels or conflicting explicit mappings generate warnings rather than
silently switching people. Supporting cast can legitimately remain unbound.

The compiler normalizes structured definitions into Subject lines, supplies
unrepresented user-declared reference labels (including settings and props), and
retains defined Subjects even if shot text uses names rather than Subject tags.
Only the declaration's identifying label is inherited; the rest of the input
line is not copied, so future actions or initial mutable clothing are not added
to the handoff. Existing chain numbering is applied after source binding.
A shared reference label does not require that character/setting in every shot.

Review instructions explicitly distinguish lyric imagery from physical story
facts and require evidence before asserting a narrative contradiction. Missing
user-requested parallel threads may be reported without imposing periodic cuts,
equal screen time or mandatory singing. These are model instructions, not proof
that the reviewer will obey them; inspect a new real recipe.

Repair records now separate format_accepted, content_changed, and
issue_resolution. An unchanged candidate is unresolved_no_op and cannot erase
its issue through a later empty review. A changed candidate is pending_recheck;
only a successful subsequent complete review marks it resolved_by_recheck.
Retries remain bounded and failures/nonchanges remain nonblocking warnings.
The audit version is bumped so older review results are not mistaken for the
new contract. Saved version-1 prompts retain their compatibility behavior.

Validation uses the real failure's structured subject shape, four-reference
provenance, name-only shots, chain shifts, ambiguous/conflicting references,
original supporting cast, no future/clothing leakage and no-op/full recheck
semantics. Actual model creativity, English photography and visual fidelity still
require the next local 9B recipe. No ComfyUI environment or render engine changes.
