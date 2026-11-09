"""Bounded, non-blocking review of the master timeline before deterministic slicing."""
import copy
import json
import re
from pathlib import Path
import uuid

from banana_mv.lyrics_reference import OPTIONAL_TIMING_POLICY, lyric_conflicts
from banana_mv.review_output import reviewed_json, content_hash

REVIEW_SYSTEM = '''Review the ENTIRE continuous shooting timeline against the original brief.
Return only {"issues":[{"index":0,"reason":"evidence and minimum necessary correction"}]}.
Indices refer to beats, NOT render clips. Use the supplied indexed timeline and
absolute start/end milliseconds. The original brief's explicit event windows,
reference identities, scene-specific vocal permissions and required outcome take
priority over generated definitions and generic ending suggestions.
Check for events performed before their commissioned interval, an early final
sung line or premature resolution followed by a long idle ending, and actions
that were summarized instead of staged. A camera beat is one concrete view;
actual stage/ring or viewpoint cuts need their own timeline entries, not an
untimed list of cuts inside one camera field. Do not impose a shot count,
minimum cut rate, mandatory singer coverage, literal lyric illustration or genre.
Check present state versus newly performed action and cross-strand continuity.
Completed events persist as results; similar NEW exchanges, ordinary repeated
performance, reaction shots and motivated montage are allowed.
Report only definite material contradictions, with supplied source evidence.
No SRT is normal. Explicit user timing in the brief remains applicable without
SRT. With SRT check explicit sung claims, not missing singing coverage.
For a necessary retiming identify every beat whose content/timing must change;
include a contradictory stable role table as an issue at index 0, with the exact
role conflict. Return {"issues":[]} when there is no definite issue.
Do not repair in this step.'''

REPAIR_SYSTEM = '''Repair ONLY the assigned contiguous beat range of a continuous film.
Return JSON only: {"beats":[replacement timeline entries]}.
Use exactly the existing beat schema: at_ms, shot_id, state, continuation_state,
camera, ongoing_camera, mode, action, ongoing. Global integer milliseconds.
You may add/remove beats and retime events INSIDE the editable range. Preserve
its start time and never reach its exclusive end. Preserve all unedited beats,
the original brief, scene-specific roles, mandatory events and causal continuity.
Read the full film and both neighbors before repairing. Current state is a
snapshot, action is a concrete new visible event, not a narrative milestone label.
Stage an action through readable preparation/contact/consequence where required.
Represent actual editorial cuts with separate beats. No quota or rigid cut grid.
Avoid replaying completed motion at the left boundary or invalidating the next
unchanged state. If that is impossible, do not invent a different story.
Optionally return "subject_definitions" ONLY when an issue explicitly identifies
a conflicting identity/scene/vocal binding. Change only that conflicting binding;
keep original reference mapping and all other roles intact.
User-specified time windows override generic completion/hold suggestions.
No new song, lyrics, speech or mandatory SRT coverage.'''


def timed_issues(film, source):
    """Conservative lyric check only for explicit claims with supplied timed cues."""
    cues=source.get('srt_cues') or []
    if not cues:
        return []
    issues=[]
    for i,beat in enumerate(film['beats']):
        start=beat['at_ms']/1000
        end=(film['beats'][i+1]['at_ms'] if i+1<len(film['beats']) else source['duration_ms'])/1000
        local=[c for c in cues if c['start']<end and c['end']>start]
        text=' '.join(beat[k] for k in ('state','action','camera'))
        for issue in lyric_conflicts(text,local,all_cues=cues):
            issues.append({'index':i,'reason':issue['reason']})
    return issues


def review_film(cfg, req, source, film, rewrite, originals, work, parse_film):
    """Never reject a usable master merely because review/repair fails."""
    from banana_mv.shoot_plan import _text, _pictures
    folder=Path(work)/'preproduction'
    folder.mkdir(exist_ok=True)
    current=copy.deepcopy(film)
    audit={'version':1,'scope':'whole_film','status':'unchecked','rounds':0,
           'checks':[],'issues':[],'repairs':[],'format_attempts':[],'warnings':[]}
    if not req.get('screenplay_review',True):
        audit['status']='disabled'
        audit['warnings'].append('Whole-film semantic review was disabled; this is not a QA pass.')
        audit['output_hash']=content_hash(current)
        return current,audit
    maximum=min(2,max(0,int(req.get('screenplay_repair_rounds',2))))
    call_cfg=copy.deepcopy(cfg)
    call_cfg.setdefault('rewriter',{})['max_length']=max(16384,int(cfg.get('rewriter',{}).get('max_length',8192)))
    def call(system,payload):
        return _text(rewrite(call_cfg,system,[('text',json.dumps(payload,ensure_ascii=False))]+
                             _pictures(originals),uuid.uuid4().hex[:8]))
    def timeline():
        return [dict(beat,index=i,end_ms=(current['beats'][i+1]['at_ms']
                    if i+1<len(current['beats']) else source['duration_ms']))
                for i,beat in enumerate(current['beats'])]
    try:
        for round_index in range(maximum+1):
            audit['rounds']=round_index+1
            issues,formats=reviewed_json(REVIEW_SYSTEM+'\n'+OPTIONAL_TIMING_POLICY,
                {'source':source,'subject_definitions':current['subject_definitions'],
                 'timeline':timeline()},call,folder,f'film_review_{round_index:02d}',
                set(range(len(current['beats']))),req.get('review_format_retries',2))
            audit['format_attempts'].append(formats)
            exact=timed_issues(current,source)
            audit['checks'].append({'round':round_index+1,'film_hash':content_hash(current),
                                    'format_status':formats['status'],'timing_issues':exact})
            if issues is None:
                audit['status']='review_failed_open';audit['issues']=exact
                audit['error']=formats.get('error','Invalid review output')
                audit['warnings'].append('Whole-film review incomplete; the timeline has NOT passed QA.')
                break
            issues=issues+exact
            audit['issues']=issues
            if not issues:
                audit['status']='passed';break
            if round_index==maximum:
                audit['status']='warnings'
                audit['warnings'].append('Confirmed issues remain after bounded repairs; review before rendering.')
                break
            # Merge adjacent flagged beats; preserve every unflagged gap/neighbor.
            groups=[]
            for idx in sorted({row['index'] for row in issues}):
                if groups and idx==groups[-1][-1]+1:groups[-1].append(idx)
                else:groups.append([idx])
            # Descending edits keep original indices of earlier groups stable.
            for group in reversed(groups):
                lo,hi=group[0],group[-1]
                end=current['beats'][hi+1]['at_ms'] if hi+1<len(current['beats']) else source['duration_ms']
                reasons=[v for v in issues if v['index'] in group]
                record={'round':round_index+1,'indices':group,'accepted':False}
                try:
                    raw=call(REPAIR_SYSTEM+'\n'+OPTIONAL_TIMING_POLICY,{
                        'source':source,'film':current,'issues':reasons,
                        'editable_range':{'first_index':lo,'last_index':hi,
                            'start_ms':current['beats'][lo]['at_ms'],'end_ms_exclusive':end},
                        'previous_beat':current['beats'][lo-1] if lo else None,
                        'next_beat':current['beats'][hi+1] if hi+1<len(current['beats']) else None})
                    name=f'film_repair_{round_index:02d}_{lo:04d}_{uuid.uuid4().hex[:8]}.txt'
                    (folder/name).write_text(raw,encoding='utf-8');record['raw_file']=name
                    body=raw.strip()
                    if body.startswith('```'):body=body.split('\n',1)[1].rsplit('```',1)[0].strip()
                    delivery=json.loads(body)
                    replacement=delivery['beats']
                    if not isinstance(replacement,list) or not replacement or any(not isinstance(b,dict) for b in replacement):
                        raise ValueError('Repair must contain a nonempty beats array.')
                    if replacement[0]['at_ms']!=current['beats'][lo]['at_ms']:
                        raise ValueError('Repair moved the range entry time.')
                    if any(type(b.get('at_ms')) is not int or not current['beats'][lo]['at_ms']<=b['at_ms']<end for b in replacement):
                        raise ValueError('Repair crossed an unchanged neighbor boundary.')
                    candidate=copy.deepcopy(current)
                    candidate['beats'][lo:hi+1]=replacement
                    if 'subject_definitions' in delivery:
                        # Role changes are allowed only when the reviewer explicitly flags a role conflict.
                        if not any(re.search(r'role|identity|vocal|subject|角色|身份|演唱|聲部',v['reason'],re.I) for v in reasons):
                            raise ValueError('Unrequested subject-definition rewrite.')
                        candidate['subject_definitions']=delivery['subject_definitions']
                    candidate=parse_film(json.dumps(candidate,ensure_ascii=False),source['duration_ms'])
                    record.update(accepted=True,before_hash=content_hash(current),after_hash=content_hash(candidate))
                    current=candidate
                except (ValueError,KeyError,TypeError,RuntimeError,OSError) as error:
                    record['error']=str(error)
                audit['repairs'].append(record)
    except (ValueError,KeyError,TypeError,RuntimeError,OSError) as error:
        audit['status']='review_failed_open';audit['error']=str(error)
        audit['warnings'].append('Review/repair failed; usable film retained without a QA pass.')
    audit['output_hash']=content_hash(current)
    return current,audit
