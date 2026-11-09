"""Whole-screenplay QA and local repairs before any clip directing begins.

This is a best-effort creative review, not a hard rendering gate. The screenplay
remains the source of truth; individual filming models see their local slices.
"""
import json
from pathlib import Path
import uuid

from banana_mv.scene_state import atomic_json
from banana_mv.review_output import reviewed_json, content_hash
from banana_mv.lyrics_reference import OPTIONAL_TIMING_POLICY, lyric_conflicts


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
A shared role table cannot override the original brief. Check scene-local role
instances: the same identity can perform different duties in different locations.
Check explicit lyric references against timeline.local_srt ONLY when supplied.
No SRT, no singing shot, or no literal lyric coverage is never an issue.
Report only meaningful contradictions with evidence, not stylistic preferences.
Do not rewrite the screenplay in this review step."""


REPAIR_SYSTEM = """You are a screenplay editor repairing exactly ONE assigned clip.
Return only the replacement CLIP BODY in prose, not a JSON wrapper.
Preserve original user directives over any conflicting generated shared setup.
Keep identities, source song, scene-specific vocal roles and
the clip's duration and location constraints. Preserve all valid events.
Correct the stated issue and connect causally with immediate neighbors.
Opening state is ALREADY TRUE; New progression performs this interval's
unique new actions; Outgoing state is the achieved result for the next clip.
Do not restage a finished action, move a future climax earlier, or rewrite
other clips. No shot list. Keep Opening state:, New progression:, Outgoing state:
as separate paragraphs."""


def _json_result(raw):
    from banana_mv.review_output import parse_review
    return parse_review(raw)[0]


def audit_and_repair(cfg, req, task, shared, outcome, rows, rewrite, work, originals):
    """Review globally, repair flagged slots, review again; never block on QA."""
    if not (req.get('vnext_preproduction') and req.get('screenplay_review', True)):
        return rows, {'status':'disabled','rounds':0}
    from banana_mv.shoot_plan import _text, _pictures
    current=[dict(row) for row in rows]
    audit={'status':'unchecked','rounds':0,'issues':[],'repairs':[], 'format_attempts':[], 'checks':[], 'warnings':[]}
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
            payload={'original_brief':task['brief'],
                'user_role_declarations':task.get('user_role_declarations',''),
                'story_outcome':outcome,'shared_setup':shared,'clips':snapshot()}
            audit['rounds']=pass_number+1
            issues,format_log=reviewed_json(REVIEW_SYSTEM+'\n'+OPTIONAL_TIMING_POLICY,
                payload,model_call,folder,f'screenplay_review_{pass_number:02d}',
                {r['index'] for r in current},req.get('review_format_retries',2))
            audit['format_attempts'].append(format_log)
            audit['checks'].append({'round':pass_number+1,'screenplay_hash':content_hash(current),
                                    'format_status':format_log['status']})
            if issues is None:
                audit['status']='review_failed_open';audit['error']=format_log['error']
                audit['warnings'].append('Global review incomplete; screenplay has not passed QA.')
                break
            for i,row in enumerate(current):
                issues.extend({'index':row['index'],'reason':v['reason']} for v in
                    lyric_conflicts(row['event'],task['timeline'][i].get('local_srt',[]),
                        all_cues=[c for t in task['timeline'] for c in t.get('local_srt',[])]))
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
                audit['warnings'].append('Unresolved screenplay issues remain after bounded repairs.')
                break
            for issue in filtered:
                idx=issue['index']
                try:
                    draft=model_call(REPAIR_SYSTEM,{
                        'original_brief':task['brief'],'story_outcome':outcome,
                        'shared_setup':shared,'user_role_declarations':task.get('user_role_declarations',''),
                        'timing_policy':OPTIONAL_TIMING_POLICY,'issue':issue,
                        'target_clip':snapshot()[idx],
                        'previous_clip':snapshot()[idx-1] if idx else None,
                        'next_clip':snapshot()[idx+1] if idx+1<len(current) else None,
                        'all_clip_states':[{'index':r['index'],'event':r['event']} for r in current],
                    }).strip()
                except (ValueError,KeyError,TypeError,RuntimeError,OSError) as error:
                    audit['repairs'].append({'index':idx,'round':pass_number+1,'accepted':False,'error':str(error)})
                    continue
                raw_name=f'screenplay_repair_{pass_number:02d}_{idx:02d}_{uuid.uuid4().hex[:8]}.txt'
                (folder/raw_name).write_text(draft,encoding='utf-8')
                if len(draft)<60 or draft.startswith('{') or 'Opening state:' not in draft or 'New progression:' not in draft or 'Outgoing state:' not in draft:
                    audit['repairs'].append({'index':idx,'round':pass_number+1,'accepted':False,'raw_file':raw_name})
                    continue
                before=current[idx]['event']
                current[idx]['event']=draft
                audit['repairs'].append({'index':idx,'round':pass_number+1,'accepted':True,
                                         'raw_file':raw_name,'old_length':len(before),'new_length':len(draft),
                                         'before_hash':content_hash(before),'after_hash':content_hash(draft)})
        else:
            audit['status']='warnings'
    except (ValueError,KeyError,TypeError,RuntimeError,OSError) as error:
        audit['status']='review_failed_open'
        audit['error']=str(error)
        audit['warnings'].append('Global review incomplete; rendering may continue with warnings.')
    audit['output_hash']=content_hash(current)
    atomic_json(folder/'screenplay_review.json',audit)
    return current,audit

