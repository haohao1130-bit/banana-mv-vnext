"""Whole-screenplay QA and local repairs before any clip directing begins.

This is a best-effort creative review, not a hard rendering gate. The screenplay
remains the source of truth; individual filming models see their local slices.
"""
import json
from pathlib import Path
import uuid

from banana_mv.scene_state import atomic_json


REVIEW_SYSTEM = """You are a continuity editor reviewing a COMPLETE multi-clip screenplay.
Review the entire original user brief and the whole chronological screenplay.
Return only JSON: {"issues":[{"index":0,"reason":"specific flaw"}]}.
Inspect explicit required dramatic beats, escalating stakes, cause and effect,
adjacent Outgoing/Opening states, completed action replay, premature resolution,
vocal role/location scope, and one-time climax. The next clip INHERITS the
previous achieved state; it must never reperform its predecessor's last action.
A character can punch repeatedly if these are distinct new exchanges.
Do not complain about routine recurring performances or deliberate montage.
Identify the minimum offending clip indices (zero-based). For a broken handoff,
prefer repairing the later clip unless the earlier clip itself violates the brief.
Use {"issues":[]} when coherent; do not require mechanical beat quotas.
Do not rewrite the screenplay in this review step."""


REPAIR_SYSTEM = """You are a screenplay editor repairing exactly ONE assigned clip.
Return only the replacement CLIP BODY in prose, not a JSON wrapper.
Keep the original shared setup, identities, source song, vocal roles and
the clip's duration and location constraints. Preserve all valid events.
Correct the stated issue and connect causally with immediate neighbors.
Opening state is ALREADY TRUE; New progression performs this interval's
unique new actions; Outgoing state is the achieved result for the next clip.
Do not restage a finished action, move a future climax earlier, or rewrite
other clips. No shot list. Keep Opening state:, New progression:, Outgoing state:
as separate paragraphs."""


def _json_result(raw):
    text=str(raw).strip()
    if text.startswith('&#96;'):
        raise ValueError('invalid review wrapper')
    if text.startswith('```'):
        text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
    result=json.loads(text)
    if not isinstance(result,dict) or not isinstance(result.get('issues'),list):
        raise ValueError('review issues must be a list')
    return result['issues']


def audit_and_repair(cfg, req, task, shared, outcome, rows, rewrite, work, originals):
    """Review globally, repair flagged slots, review again; never block on QA."""
    if not (req.get('vnext_preproduction') and req.get('screenplay_review', True)):
        return rows, {'status':'disabled','rounds':0}
    from banana_mv.shoot_plan import _text, _pictures
    current=[dict(row) for row in rows]
    audit={'status':'unchecked','rounds':0,'issues':[],'repairs':[]}
    max_repairs=min(2, max(0,int(req.get('screenplay_repair_rounds',2))))
    folder=Path(work)
    def model_call(system,data):
        return _text(rewrite(cfg,system,[('text',json.dumps(data,ensure_ascii=False))]+
                      _pictures(originals),uuid.uuid4().hex[:8]))
    def snapshot():
        return [{'index':r['index'],'mode':r['mode'],'event':r['event'],
                 'timeline':task['timeline'][i]} for i,r in enumerate(current)]
    try:
        for pass_number in range(max_repairs+1):
            issues=_json_result(model_call(REVIEW_SYSTEM,{
                'original_brief':task['brief'],
                'user_role_declarations':task.get('user_role_declarations',''),
                'story_outcome':outcome,'shared_setup':shared,
                'clips':snapshot()}))
            filtered=[]
            for issue in issues:
                if not isinstance(issue,dict) or type(issue.get('index')) is not int or not isinstance(issue.get('reason'),str):
                    raise ValueError('invalid issue entry')
                idx=issue['index']
                if not 0<=idx<len(current):
                    raise ValueError('issue index outside screenplay')
                if issue['reason'].strip() and idx not in [v['index'] for v in filtered]:
                    filtered.append({'index':idx,'reason':issue['reason'].strip()})
            audit['rounds']=pass_number+1
            audit['issues']=filtered
            if not filtered:
                audit['status']='passed'
                break
            if pass_number==max_repairs:
                audit['status']='warnings'
                break
            for issue in filtered:
                idx=issue['index']
                draft=model_call(REPAIR_SYSTEM,{
                    'original_brief':task['brief'],'story_outcome':outcome,
                    'shared_setup':shared,'issue':issue,
                    'target_clip':snapshot()[idx],
                    'previous_clip':snapshot()[idx-1] if idx else None,
                    'next_clip':snapshot()[idx+1] if idx+1<len(current) else None,
                    'all_clip_states':[{'index':r['index'],'event':r['event']} for r in current],
                }).strip()
                if len(draft)<60 or draft.startswith('{') or 'Opening state:' not in draft or 'New progression:' not in draft or 'Outgoing state:' not in draft:
                    audit['repairs'].append({'index':idx,'round':pass_number+1,'accepted':False})
                    continue
                before=current[idx]['event']
                current[idx]['event']=draft
                audit['repairs'].append({'index':idx,'round':pass_number+1,'accepted':True,
                                         'old_length':len(before),'new_length':len(draft)})
        else:
            audit['status']='warnings'
    except (ValueError,KeyError,TypeError,RuntimeError) as error:
        audit['status']='review_failed_open'
        audit['error']=str(error)
    atomic_json(folder/'screenplay_review.json',audit)
    return current,audit
