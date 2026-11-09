"""Nonblocking local filming QA; no renderer or media-numbering changes."""
import json
import uuid
from pathlib import Path
from banana_mv.review_output import reviewed_json, content_hash
from banana_mv.scene_state import atomic_json
from banana_mv.lyrics_reference import OPTIONAL_TIMING_POLICY, lyric_conflicts

SCENE_INSTANCE_POLICY = '''Separate character identity from scene-specific performance instances.
One reference picture may define the same face for several scene instances.
Use distinct stable Subject definitions for explicitly different scene-role instances,
with the SAME source Picture binding when they share identity. Keep supplied picture
numbers unchanged. State each instance's location, appearance and vocal/nonvocal duty.
Do not invent duplicate people sharing a frame unless commissioned. Scene instances
are alternative narrative contexts, not clones. A singing identity does not authorize
the fighting instance to sing. Each shot chooses its actual scene instance and action.
When intercutting, describe only that location's permitted activity: actions from
another strand remain there, rather than moving the fight onto the stage. Return
to each strand's achieved state. Only vocal instances have a source-song speaker ID;
a nonvocal counterpart shares appearance, not an extra vocal assignment.'''

FILM_REVIEW_SYSTEM = '''You review ONE native H3 filming prompt against its local commission.
Return JSON {"issues":[{"index":0,"reason":"specific evidenced contradiction"}]}.
Use the supplied clip_index for every issue. Original role declarations override
conflicting generated prose. Inspect actual detailed_description shots, not just
summary promises: location/action compatibility, scene-specific vocal permission,
stable identity bindings, completed-action replay, chronology and ending scope.
Compare explicit vocal/lyric claims with supplied local SRT, including shots' local
clock. Flag definite future or wrong-interval lyrics, not missing lyrics coverage.
A physical person may have scene-local instances using the same reference image.
Recurring distinct exchanges, performances, reactions and motivated montage are
valid. Report only clear contradictions, not preferences or a demand for a quota.
Do not require an image per instance. Do not judge image contents not supplied.
'''


def review_prompt(cfg, req, payload, text, rewrite, originals, work, index):
    from banana_mv.shoot_plan import _text, _pictures, validate_native_mv_format
    from banana_mv.core import normalize_mv_prompt
    if not req.get('camera_review',True):return text,{'status':'disabled'}
    folder=Path(work);audit={'status':'unchecked','checks':[],'repairs':[],'warnings':[]}
    current=text
    def call(system,data):
        return _text(rewrite(cfg,system,[('text',json.dumps(data,ensure_ascii=False))]+_pictures(originals),uuid.uuid4().hex[:8]))
    budget=min(1,max(0,int(req.get('camera_repair_rounds',1))))
    for round_number in range(budget+1):
        data=dict(payload,clip_index=index,prompt=current,source_srt=req.get('srt_cues',[]))
        issues,log=reviewed_json(FILM_REVIEW_SYSTEM+'\n'+OPTIONAL_TIMING_POLICY,
            data,call,folder,f'{index:02d}_filming_review_{round_number}',{index},req.get('review_format_retries',2))
        audit['checks'].append({'prompt_hash':content_hash(current),'format':log})
        if issues is None:
            audit['status']='review_failed_open';audit['warnings'].append(log['error']);break
        local=payload['current_clip'].get('local_srt',[])
        # Full SRT stays at the reviewer, not in creative shot-writing input.
        issues.extend({'index':index,**item} for item in lyric_conflicts(current,local,
            shot_clock=True,seconds=payload['duration_seconds'],all_cues=req.get('srt_cues',[])))
        audit['issues']=issues
        if not issues:audit['status']='passed';break
        if round_number==budget:
            audit['status']='warnings';audit['warnings'].append('Unresolved filming contradictions; review before rendering.');break
        try:
            # Local replacement only. It sees the current interval and issue evidence,
            # never another interval's full plot or an instruction to rewrite all lyrics.
            fixed=call('Repair only the evidenced contradictions in this one H3 prompt. Preserve all valid shots, actions, causal progression, style and original audio. Return the complete six-section native prompt.\n'+SCENE_INSTANCE_POLICY+'\n'+OPTIONAL_TIMING_POLICY,
                dict(payload,clip_index=index,prompt=current,issues=issues))
            raw_name=f'{index:02d}_filming_repair_{uuid.uuid4().hex[:8]}.txt'
            (folder/raw_name).write_text(fixed,encoding='utf-8')
            candidate=validate_native_mv_format(normalize_mv_prompt(fixed,len(originals)),payload['duration_seconds'],require_native=req.get('h3_validation_version')==1)
            audit['repairs'].append({'accepted':True,'raw_file':raw_name,'before_hash':content_hash(current),'after_hash':content_hash(candidate)})
            current=candidate
        except (ValueError,KeyError,TypeError,RuntimeError,OSError) as exc:
            audit['repairs'].append({'accepted':False,'error':str(exc)})
            audit['status']='warnings';audit['warnings'].append('Filming repair failed; retained previous renderable prompt.');break
    audit['output_hash']=content_hash(current)
    atomic_json(folder/f'{index:02d}_filming_review.json',audit)
    return current,audit
