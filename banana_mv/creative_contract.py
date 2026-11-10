"""Compact source evidence for cross-chapter commitments; no scene quotas."""
import re

VERSION=1
RELATION=re.compile(r'交錯|交織|並行|平行|穿插|兩條|雙線|回返|intercut|interweav|parallel|alternat|cross.cut',re.I)
DUTY=re.compile(r'唯一|只負責|不演唱|不唱|必須|不得|結局|最終|核心|主軸|only singer|must|never|outcome|finale',re.I)

def creative_contract(brief):
    # Preserve source wording, not model-invented strands or inferred quotas.
    clauses=[p.strip() for p in re.split(r'(?<=[。！？.!?])\s*|\n+',brief or '') if p.strip()]
    relations=[p for p in clauses if RELATION.search(p)]
    duties=[p for p in clauses if DUTY.search(p) and p not in relations]
    return {'version':VERSION,'relationship_evidence':relations,
            'explicit_constraints':duties,
            'scope':'Global commitments, not instructions to perform future events in this chapter.',
            'director_freedom':'Choose actual cuts, density, unequal screen time and chapter locations freely. No periodic return, chapter quota or mandatory singing coverage.'}

CONTRACT_POLICY='''Honor creative_contract as persistent source commitments, not optional decoration.
When the source commissions interwoven narrative strands, plan their meaningful development
across the film, rather than introducing one only at the opening and then abandoning it.
A deliberate early resolution must be supported by the original commission. Do not invent
additional strands for a single-line story. Unequal durations and irregular returns are valid.
Each chapter can change location: previous_exit_state preserves achieved state by scene,
not a command to stay in the preceding scene or camera view. Keep each strand's own
wardrobe, props, condition and causal progress when returning. Never replay its last event.
No split-screen or dual-panel. Every actual cut between locations or viewpoints has a separate timed beat and shot_id.
Do not place two locations in one filming_prompt. Future milestones remain constraints,
not events to perform early. Decide staging freely within these commitments.'''

