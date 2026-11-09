"""Explicit whole-work versus excerpt semantics, independent of clip slicing."""
import math


SHORT_ENDING_TAIL_SECONDS = 3.0


def validate_scope(value):
    if value not in ('full', 'excerpt'):
        raise ValueError('作品範圍必須是 full（本次音檔演完完整故事）或 excerpt（故事片段、保留後續）。')
    return value


def ending_contract(req, total, segments=None):
    scope = validate_scope(req.get('project_scope', 'full'))
    if scope == 'excerpt':
        return {'project_scope':scope, 'finish_work':False,
                'instruction':'This is an excerpt of a larger MV, not the complete work. Continue the supplied story and performance. End on a clean, editable ongoing beat; do not manufacture a full-work finale, farewell, final victory, fade-out or show-ending pose. An allocated local event may still reach its own outcome.'}
    # Source duration never grows. Resolution starts before a tiny padded tail;
    # settling is measured in visible source time, never model alignment padding.
    # At most three residual seconds continue the established ending; the
    # preceding interval must finish the decisive action before the tail starts.
    if segments:
        nominal=max(row['seconds'] for row in segments)
        tail=segments[-1]['seconds']
        short_tail=len(segments)>1 and tail<nominal and tail<=SHORT_ENDING_TAIL_SECONDS
        window=tail+(segments[-2]['seconds'] if short_tail else 0)
    else:
        nominal=float(req.get('segment_seconds',15))
        tail=total%nominal
        if tail<1e-6:tail=min(total,nominal)
        short_tail=total>nominal and tail<=SHORT_ENDING_TAIL_SECONDS
        window=tail+(nominal if short_tail else 0)
    window=min(total,window)
    hold = min(1.5, total * .2)
    settle_by=min(total-hold,total-tail) if short_tail else total-hold
    scope_instruction = ('This uploaded audio is the complete available duration for the entire requested story, even when cropped from a longer song or ending during a verse/chorus. Allocate the complete beginning, development, resolution and specified final image within it. Read the entire story before budgeting time; compress optional middle staging rather than stopping before the ending. Preserve causal progression and all mandatory milestones and the specified outcome.' if req.get('story_scope_version',req.get('story_completion_version'))==1 else 'This is the complete MV. Preserve the outline, causal progression and specified outcome.')
    return {'project_scope':scope, 'finish_work':True,
            'resolve_start_by':round(total-window,6),
            'settle_by':round(settle_by,6), 'end_time':total,
            'short_tail_seconds':round(tail,6) if short_tail else 0,
            'hold_seconds':hold,
            'instruction':scope_instruction+' Begin resolution by resolve_start_by, finish required action by settle_by, then sustain the terminal image through end_time. A short last interval completes an ending already underway; it must not introduce a new unresolved action or a last-second scene switch. Do not extend, replace or fade the source song.'}


def validate_ending(raw, req, segments):
    """A new scoped plan must actually budget resolution and a terminal hold."""
    if 'project_scope' not in req:
        return None  # Preserve existing project fingerprints and saved plans.
    contract = ending_contract(req, segments[-1]['start']+segments[-1]['seconds'],segments)
    if not contract['finish_work']:
        if raw.get('ending_plan') is not None or raw.get('closing_shot') not in ('',None):
            raise ValueError('片段 MV 不得規劃全片終局：ending_plan=null，closing_shot=""。')
        return None
    plan = raw.get('ending_plan')
    if not isinstance(plan,dict):raise ValueError('整首 MV 需有 ending_plan，預留完整收束時間。')
    for field in ('start_time','resolved_by'):
        value=plan.get(field)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError('ending_plan.'+field+'需為有限秒數。')
    if not (0 <= plan['start_time'] <= contract['resolve_start_by'] and
            plan['start_time'] < plan['resolved_by'] <= contract['settle_by']):
        raise ValueError('結尾太晚：需提前完成故事收束，保留最後畫面停留時間。')
    if not isinstance(plan.get('resolution'),str) or not plan['resolution'].strip():
        raise ValueError('ending_plan.resolution需描述如何完成故事主軸。')
    return dict(plan)


def clip_ending(req, segment):
    total=segment.get('song_seconds',segment['start']+segment['seconds'])
    contract=dict(segment.get('direction_ending_contract') or ending_contract(req,total))
    start=segment['start'];end=start+segment['seconds']
    contract['is_last_source_interval']=segment['index']==segment.get('segment_count',1)-1
    if not contract['finish_work']:return contract
    closing=segment.get('direction_ending_plan') or {}
    resolve_start=closing.get('start_time',contract['resolve_start_by'])
    contract['phase']=('continuing' if end<=resolve_start else
                       'terminal_hold' if start>=contract['settle_by'] else 'resolving')
    contract['local_resolution_start']=max(0,resolve_start-start) if end>resolve_start else None
    contract['local_settle_by']=max(0,contract['settle_by']-start) if end>contract['settle_by'] else None
    if contract['phase']=='continuing':
        # Do not leak future ending action or demand closure in an early clip.
        return {'project_scope':'full','finish_work':False,'phase':'continuing',
                'instruction':'Continue only this allocated event. The complete-work ending is reserved for later intervals; do not stage it now.'}
    if contract.get('short_tail_seconds') and contract['is_last_source_interval']:
        contract['phase']='terminal_hold'
    if closing:
        contract['resolution']=closing['resolution']
        due=closing['resolved_by']
        contract['local_resolution_by']=max(0,due-start) if end>=due else None
    return contract

