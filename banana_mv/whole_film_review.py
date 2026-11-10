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
Index -1 means the WHOLE FILM needs repair: use it for global clock compression,
misplaced climax across multiple intervals, lost parallel storyline, or a shared
role-table conflict. For a truly local flaw use its zero-based beat index.
Do NOT report only index 0 for a problem involving the whole timeline.
Read start_seconds/end_seconds, which the program calculated from at_ms/end_ms.
Do not infer units from the number of digits: 800 ms = 0.8 seconds, NOT 8 seconds;
8000 ms = 8 seconds, NOT 80 seconds. The last beat holds until the source end.
A long final beat may contain an early climax even if the beat interval overlaps
a late lyric. Match the described action's onset, not merely interval overlap.
The source's duration_seconds is authoritative. Do not invent timeline ranges. The original brief's explicit event windows,
reference identities, scene-specific vocal permissions and required outcome take
priority over generated definitions and generic ending suggestions.
Check for events performed before their commissioned interval, an early final
sung line or premature resolution followed by a long idle ending, and actions
that were summarized instead of staged. A camera beat is one concrete view;
actual stage/ring or viewpoint cuts need their own timeline entries, not an
untimed list of cuts inside one camera field. Do not impose a shot count,
minimum cut rate, mandatory singer coverage, literal lyric illustration or genre.
Read filming_prompt and ongoing_filming_prompt as the actual H3 shooting text
when present; check them against metadata and source, including scene/vocal roles.
Shared subject definitions must contain stable identity/scene-role bindings only,
not plot, opening actions, ending instructions or future outcomes. Each downstream
window receives this table. Flag leaked shared plot as index -1. Each filming
paragraph describes only its timed current phase, not past causes or future phases.
Check present state versus newly performed action and cross-strand continuity.
Completed events persist as results; similar NEW exchanges, ordinary repeated
performance, reaction shots and motivated montage are allowed.
Report only definite material contradictions, with supplied source evidence.
No SRT is normal. Explicit user timing in the brief remains applicable without
SRT. With SRT check explicit sung claims, not missing singing coverage.
For retiming that cannot fit inside the currently assigned neighboring beats,
use index -1 so the editor can redistribute time across the complete source.
For local fixes identify every neighboring beat that actually must change.
Support every issue with actual supplied start_seconds and original user wording.
"No SRT" does not erase time directives in the brief or imply missing lyrics.
Never invent constraints (e.g. delaying discovery) contrary to the original brief. Return {"issues":[]} when there is no definite issue.
Do not repair in this step.'''

REPAIR_SYSTEM = '''Repair ONLY the assigned contiguous beat range of a continuous film.
Return JSON only: {"beats":[replacement timeline entries]}.
Use exactly the existing beat schema: at_ms, shot_id, state, continuation_state,
camera, ongoing_camera, mode, action, ongoing. Also preserve and update
filming_prompt and ongoing_filming_prompt when present: these are the actual
shooting descriptions, and must agree with the repaired metadata. Global integer milliseconds.
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


GLOBAL_REPAIR_SYSTEM = """Repair the COMPLETE continuous film's timing and staging.
Return JSON only: {"beats":[the complete repaired beat list]}.
Use the original schema with integer at_ms; 1 second equals 1000 milliseconds.
Start at 0, strictly increase, remain below source.duration_ms. The final beat
continues to the actual source end. Preserve the user's story, identities,
scene-specific vocal duties and explicit event windows. Generic ending advice
never overrides explicit user timing. Keep valid actions and camera intentions;
redistribute their times and expand underdeveloped action as necessary.
A globally compressed clock is a whole-timeline repair, not a one-beat edit.
Do not multiply all timestamps by a guessed scale or pad the rest with aftermath.
Write the full duration as a film. Represent real edits with concrete timed views,
without imposing a shot quota. Current state is not action or a plot recap.
Do not make up lyrics, musical facts, sound effects or precise sung times when no
such timing evidence is supplied. No SRT is normal and does not require singing
coverage. The original brief's explicit time windows still govern the story.
Optionally return subject_definitions only to correct a reported shared binding
conflict; preserve the actual reference slots and every unaffected identity.
Return the COMPLETE replacement timeline, not a change description."""


def clock_context(film, source):
    """Program-calculated display clocks for models; never retime the film."""
    duration=source['duration_ms']
    rows=[]
    for i,beat in enumerate(film['beats']):
        end=film['beats'][i+1]['at_ms'] if i+1<len(film['beats']) else duration
        rows.append(dict(beat,index=i,end_ms=end,start_seconds=beat['at_ms']/1000,
                         end_seconds=end/1000,span_seconds=(end-beat['at_ms'])/1000))
    return {'duration_ms':duration,'duration_seconds':duration/1000,
            'milliseconds_per_second':1000,'srt_provided':bool(source.get('srt_cues')),
            'timeline':rows}


def timed_issues(film, source):
    """Conservative lyric check only for explicit claims with supplied timed cues."""
    cues=source.get('srt_cues') or []
    if not cues:
        return []
    issues=[]
    for i,beat in enumerate(film['beats']):
        start=beat['at_ms']/1000
        end=(film['beats'][i+1]['at_ms'] if i+1<len(film['beats']) else source['duration_ms'])/1000
        local=[dict(c,clip_start=c['start']-start,clip_end=c['end']-start) for c in cues if c['start']<end and c['end']>start]
        text=' '.join(beat.get(k,'') for k in ('state','action','camera','filming_prompt','ongoing_filming_prompt'))
        for issue in lyric_conflicts(text,local,all_cues=cues,at_start=True):
            issues.append({'index':i,'reason':issue['reason']})
    return issues



def render_clock(film, source):
    """Compact exact cut clocks; avoids duplicating every full H3 prompt in QA."""
    from banana_mv.whole_film import window
    from banana_mv.lyrics_reference import excerpt
    result=[]
    for seg in source.get('render_windows',[]):
        start=round(seg['start']*1000);end=round((seg['start']+seg['seconds'])*1000)
        rows=window(film,start,end)
        result.append({'index':seg['index'],'source_start_seconds':seg['start'],
            'seconds':seg['seconds'],'local_srt':excerpt(source,seg),
            'views':[{'local_seconds':r['at_ms']/1000,'shot_id':r['shot_id'],
                      'global_seconds':(start+r['at_ms'])/1000} for r in rows]})
    return result


def window_timing_issues(film, source):
    """Check actual sliced prose against local SRT; no model call or coverage quota."""
    from banana_mv.whole_film import window
    from banana_mv.lyrics_reference import excerpt
    from bisect import bisect_right
    if not source.get('srt_cues'):return []
    issues=[];times=[b['at_ms'] for b in film['beats']]
    for seg in source.get('render_windows',[]):
        start=round(seg['start']*1000);end=round((seg['start']+seg['seconds'])*1000)
        rows=window(film,start,end)
        for i,row in enumerate(rows):
            at=row['at_ms']/1000
            until=rows[i+1]['at_ms']/1000 if i+1<len(rows) else seg['seconds']
            # Treat each timed phase as its actual local view, even when shot_id
            # stays the same. Reconstructing only Shot labels loses such phases.
            text=row.get('filming_prompt') or row['camera']+' '+row['state']+' '+row['action']
            local=excerpt(source,seg)
            cues=[c for c in local if c['clip_start']<until+.75 and c['clip_end']>at-.75]
            for issue in lyric_conflicts(text,cues,all_cues=source['srt_cues']):
                idx=bisect_right(times,start+row['at_ms'])-1
                item={'index':idx,'reason':f"Render window {seg['index']} local {at:g}–{until:g}s: "+issue['reason']}
                if item not in issues:issues.append(item)
    return issues


def review_film(cfg, req, source, film, rewrite, originals, work, parse_film):
    """Never reject a usable master merely because review/repair fails."""
    from banana_mv.shoot_plan import _text, _pictures
    from banana_mv.whole_film import photography_system, direction_system, photography_gaps
    folder=Path(work)/'preproduction'
    folder.mkdir(exist_ok=True)
    current=copy.deepcopy(film)
    audit={'version':3,'scope':'whole_film','status':'unchecked','rounds':0,
           'checks':[],'issues':[],'repairs':[],'format_attempts':[],'warnings':[]}
    if not req.get('screenplay_review',True):
        audit['status']='disabled'
        audit['warnings'].append('Whole-film semantic review was disabled; this is not a QA pass.')
        audit['output_hash']=content_hash(current)
        return current,audit
    pending=[]  # Failed edits remain unresolved; a fresh empty review cannot erase them.
    maximum=min(2,max(0,int(req.get('screenplay_repair_rounds',2))))
    def call(system,payload):
        call_cfg=copy.deepcopy(cfg)
        # Reviews return compact issues; full repairs retain the author's output budget.
        call_cfg.setdefault('rewriter',{})['max_length']=(max(16384,int(cfg.get('rewriter',{}).get('max_length',8192)))
            if system.startswith('Repair ') else 4096)
        if system.startswith('Repair '):
            system+='\n'+photography_system(cfg)+'\n'+direction_system(source)
        return _text(rewrite(call_cfg,system,[('text',json.dumps(payload,ensure_ascii=False))]+
                             _pictures(originals),uuid.uuid4().hex[:8]))
    try:
        for round_index in range(maximum+1):
            audit['rounds']=round_index+1
            clock=clock_context(current,source)
            issues,formats=reviewed_json(REVIEW_SYSTEM+'\n'+OPTIONAL_TIMING_POLICY,
                {'source':source,'subject_definitions':current['subject_definitions'],
                 'clock':{k:v for k,v in clock.items() if k!='timeline'},
                 'timeline':clock['timeline'],
                 'camera_review_enabled':req.get('camera_review',True),
                 'render_clock':render_clock(current,source)},call,folder,f'film_review_{round_index:02d}',
                set(range(len(current['beats']))) | {-1},req.get('review_format_retries',2))
            audit['format_attempts'].append(formats)
            exact=timed_issues(current,source)
            window_issues=window_timing_issues(current,source)
            for issue in window_issues:
                if issue not in exact:exact.append(issue)
            if source.get('photography_contract')==2 and req.get('camera_review',True):
                for idx in photography_gaps(current):
                    exact.append({'index':idx,'reason':'The native filming_prompt or ongoing_filming_prompt is missing. Convert this already approved beat into concrete H3 shot prose without changing its story, time, identity or camera intent.'})
            audit['checks'].append({'round':round_index+1,'film_hash':content_hash(current),
                                    'format_status':formats['status'],'timing_issues':exact,
                                    'window_timing_issues':window_issues})
            if issues is None:
                audit['status']='review_failed_open';audit['issues']=exact
                audit['error']=formats.get('error','Invalid review output')
                audit['warnings'].append('Whole-film review incomplete; the timeline has NOT passed QA.')
                break
            for item in pending:
                from bisect import bisect_right
                idx=-1 if item['global'] else max(0,bisect_right([b['at_ms'] for b in current['beats']],item['start_ms'])-1)
                issue={'index':idx,'reason':item['reason']}
                if issue not in issues:issues.append(issue)
            issues=issues+exact
            audit['issues']=issues
            if not issues:
                audit['status']='passed';break
            if round_index==maximum:
                audit['status']='warnings'
                audit['warnings'].append('Confirmed issues remain after bounded repairs; review before rendering.')
                break
            global_repair=any(row['index']==-1 for row in issues)
            groups=[]
            if global_repair:
                groups=[list(range(len(current['beats'])))]
            else:
                for idx in sorted({row['index'] for row in issues}):
                    if groups and idx==groups[-1][-1]+1:groups[-1].append(idx)
                    else:groups.append([idx])
            # Descending edits keep indices of earlier local groups stable.
            for group in reversed(groups):
                lo,hi=group[0],group[-1]
                end=current['beats'][hi+1]['at_ms'] if hi+1<len(current['beats']) else source['duration_ms']
                reasons=issues if global_repair else [v for v in issues if v['index'] in group]
                record={'round':round_index+1,'indices':group,'accepted':False,
                        'scope':'whole_film' if global_repair else 'local'}
                try:
                    raw=call((GLOBAL_REPAIR_SYSTEM if global_repair else REPAIR_SYSTEM)+'\n'+OPTIONAL_TIMING_POLICY,{
                        'source':source,'film':current,'clock':clock_context(current,source),'issues':reasons,
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
                    # A local repair may redundantly return the entire master.
                    # Extract only the editable interval, never apply its other edits.
                    if (not global_repair and lo>0 and replacement[0].get('at_ms')==0):
                        start=current['beats'][lo]['at_ms']
                        scoped=[b for b in replacement if type(b.get('at_ms')) is int and start<=b['at_ms']<end]
                        if scoped:
                            record['ignored_outside_range']=len(replacement)-len(scoped)
                            replacement=scoped
                    if replacement[0]['at_ms']!=current['beats'][lo]['at_ms']:
                        raise ValueError('Repair moved the range entry time.')
                    if any(type(b.get('at_ms')) is not int or not current['beats'][lo]['at_ms']<=b['at_ms']<end for b in replacement):
                        raise ValueError('Repair crossed an unchanged neighbor boundary.')
                    candidate=copy.deepcopy(current)
                    candidate['beats'][lo:hi+1]=replacement
                    if 'subject_definitions' in delivery:
                        from banana_mv.whole_film import definition_text
                        definitions=definition_text(delivery['subject_definitions'])
                        # Redundant unchanged definitions are harmless in a full-master return.
                        if definitions!=current['subject_definitions']:
                            if not any(re.search(r'role|identity|vocal|subject|角色|身份|演唱|聲部',v['reason'],re.I) for v in reasons):
                                raise ValueError('Unrequested subject-definition rewrite.')
                            candidate['subject_definitions']=definitions
                    candidate=parse_film(json.dumps(candidate,ensure_ascii=False),source['duration_ms'])
                    record.update(accepted=True,before_hash=content_hash(current),after_hash=content_hash(candidate))
                    pending=[v for v in pending if not (global_repair or (not v['global'] and current['beats'][lo]['at_ms']<=v['start_ms']<end))]
                    current=candidate
                except (ValueError,KeyError,TypeError,RuntimeError,OSError) as error:
                    record['error']=str(error)
                    for reason in reasons:
                        item={'start_ms':current['beats'][lo]['at_ms'],'global':global_repair,'reason':reason['reason']}
                        if item not in pending:pending.append(item)
                audit['repairs'].append(record)
    except (ValueError,KeyError,TypeError,RuntimeError,OSError) as error:
        audit['status']='review_failed_open';audit['error']=str(error)
        audit['warnings'].append('Review/repair failed; usable film retained without a QA pass.')
    audit['output_hash']=content_hash(current)
    return current,audit
