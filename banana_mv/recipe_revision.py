"""User-approved opt-in recipe revisions: stage, compare, accept or discard.

Unlike automatic screenplay review, no candidate is published without a
matching plan revision and explicit user approval.
"""
import copy
import json
import uuid
from pathlib import Path

from banana_mv.core import normalize_mv_prompt
from banana_mv.scene_state import atomic_json, digest
from banana_mv.shoot_plan import _text, validate_native_mv_format
from banana_mv.whole_film import _json_object, compile_window, parse_film
from banana_mv.director import MODES


REVISE_SYSTEM = """Revise ONLY the specified range of an existing music video.
Return one JSON object: {"beats":[complete replacement beats for this range]}.
Every replacement beat must contain GLOBAL integer at_ms, shot_id, state,
continuation_state, camera, ongoing_camera, action, ongoing, mode,
filming_prompt and ongoing_filming_prompt. Keep those fields as nonempty prose.
Keep the first at_ms exactly equal to editable_range.start_ms. All times
must be strictly increasing and strictly below editable_range.end_ms_exclusive.
Correct the specific director advice while retaining the original intent,
singing permissions, character identity, photography and neighboring state.
Do not change an unrelated beat, alter the timing outside this range, move
the ending, invent a split-screen scene or quote future lyrics in an early act.
Both filming prompt fields are complete native H3 shot prose for their
respective current and already-ongoing phases. No commentary or markdown."""


def _selected_ranges(film, issues):
    beats=film['beats']
    chapters=film.get('authoring_chapters') or []
    if not isinstance(issues,list) or not issues:
        raise ValueError('蕉大師尚未提出可供修訂的具體建議。')
    selections={}
    for ticket in issues:
        if not isinstance(ticket,dict):
            continue
        chapter=ticket.get('target_chapter')
        index=ticket.get('index')
        if type(chapter) is int and 0<=chapter<len(chapters):
            c=chapters[chapter]
            indices=[i for i,b in enumerate(beats) if c['start_ms']<=b['at_ms']<c['end_ms']]
            name=('chapter',chapter)
        elif type(index) is int and 0<=index<len(beats):
            indices=[index]
            name=('beat',index)
        else:
            continue
        if not indices:
            continue
        if name not in selections:
            selections[name]={'indices':indices,'issues':[]}
        selections[name]['issues'].append(ticket)
    if not selections:
        raise ValueError('審稿建議沒有有效的章節或鏡頭索引。')
    # Bound each explicit review invocation. Keep edits ordered and disjoint.
    ranges=sorted(selections.values(),key=lambda g:g['indices'][0])
    if len(ranges)>6:
        raise ValueError('本次建議涵蓋超過六個局部區塊，請縮小審稿範圍。')
    touched=set()
    for row in ranges:
        if touched.intersection(row['indices']):
            raise ValueError('建議區塊互相重疊，請先縮小修訂範圍。')
        touched.update(row['indices'])
    return ranges


def _write_text(path, value):
    path=Path(path)
    temp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex[:8]+'.tmp')
    try:
        temp.write_text(value,encoding='utf-8')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _compiled(film, job, folder):
    from banana_mv.reference_bindings import reference_manifest
    references=reference_manifest(job['request'].get('prompt',''),
                                  len(job.get('images_comfy',[])))
    req=job['request']
    plan=json.loads((folder.parent/'director_plan.json').read_text(encoding='utf-8'))
    plan['shared_setup']=film['subject_definitions']
    output={}
    for seg in job['segments']:
        i=seg['index']
        text,rows=compile_window(film,seg,
            chain=req.get('mode')=='chain',
            face_identity=req.get('face_identity',True),
            reference_manifest=references)
        text=normalize_mv_prompt(text,len(job['images_comfy'])+
                                 int(req.get('mode')=='chain' and i>0))
        validate_native_mv_format(text,seg['seconds'],require_native=True)
        modes=[row['mode'] for row in rows if row['mode'] in MODES]
        mode='action' if 'action' in modes else (modes[0] if modes else 'story')
        plan['segments'][i]={'index':i,'mode':mode,'handoff_version':1,
                             'event':'\n'.join(row['state']+' '+row['action'] for row in rows)}
        output[i]=text
    total=round((job['segments'][-1]['start']+job['segments'][-1]['seconds'])*1000)
    complete,_=compile_window(film,{'index':0,'start':0,'seconds':total/1000},
                               face_identity=req.get('face_identity',True),
                               reference_manifest=references)
    return plan,output,complete


def draft(work, job, cfg, rewrite, advice, base_revision):
    """Generate a candidate without mutating official manuscript, prompts or job."""
    folder=Path(work)/'preproduction'
    master=json.loads((folder/'whole_film.json').read_text(encoding='utf-8'))
    original=master['film']
    duration=round((job['segments'][-1]['start']+job['segments'][-1]['seconds'])*1000)
    ranges=_selected_ranges(original,advice.get('issues'))
    candidate=copy.deepcopy(original)
    inputs=json.loads((folder/'whole_film_input.json').read_text(encoding='utf-8'))['source']
    id_=uuid.uuid4().hex[:12]
    staging=folder/'recipe_revisions'/id_
    staging.mkdir(parents=True,exist_ok=False)
    config=copy.deepcopy(cfg)
    config.setdefault('rewriter',{})['max_length']=min(6144,max(3072,
                                       int(cfg.get('rewriter',{}).get('max_length',8192))))
    # Reverse order preserves index positions of earlier untouched groups.
    for row in reversed(ranges):
        indices=row['indices']
        lo,hi=indices[0],indices[-1]
        start=original['beats'][lo]['at_ms']
        end=original['beats'][hi+1]['at_ms'] if hi+1<len(original['beats']) else duration
        scope_lyrics=[cue for cue in inputs.get('srt_cues',[])
                      if isinstance(cue,dict) and cue.get('start',float('inf'))<end/1000
                      and cue.get('end',0)>start/1000]
        payload={'editable_range':{'start_ms':start,'end_ms_exclusive':end},
                 'original_beats':original['beats'][lo:hi+1],
                 'previous_beat':original['beats'][lo-1] if lo else None,
                 'next_beat':original['beats'][hi+1] if hi+1<len(original['beats']) else None,
                 'local_srt':scope_lyrics,
                 'issues':row['issues'],
                 'subject_definitions':original['subject_definitions'],
                 'rule':'Return only this range. Preserve unaffected neighboring events.'}
        atomic_json(staging/f'input_{lo:04d}.json',payload)
        raw=_text(rewrite(config,REVISE_SYSTEM,
                          [('text',json.dumps(payload,ensure_ascii=False))],
                          uuid.uuid4().hex[:8]))
        _write_text(staging/f'raw_{lo:04d}.txt',raw)
        returned=_json_object(raw).get('beats')
        if not isinstance(returned,list):
            raise ValueError('局部修稿缺少 beats 陣列。')
        cleaned=[copy.deepcopy(b) for b in returned if isinstance(b,dict)
                 and type(b.get('at_ms')) is int and start<=b['at_ms']<end]
        cleaned.sort(key=lambda b:b['at_ms'])
        if not cleaned or cleaned[0]['at_ms']!=start or any(
                cleaned[i]['at_ms']>=cleaned[i+1]['at_ms']
                for i in range(len(cleaned)-1)):
            raise ValueError('修訂版沒有完整保留章節起點或時間遞增順序。')
        for beat in cleaned:
            if isinstance(beat.get('ongoing'),bool) or not beat.get('ongoing'):
                beat['ongoing']=beat.get('action') or 'underway'
            for field in ('filming_prompt','ongoing_filming_prompt'):
                if not isinstance(beat.get(field),str) or not beat[field].strip():
                    raise ValueError('修訂版缺少 H3 拍攝描述：'+field)
        candidate['beats'][lo:hi+1]=cleaned
    candidate=parse_film(json.dumps(candidate,ensure_ascii=False),duration)
    if digest(candidate)==digest(original):
        raise ValueError('本次修訂沒有改變丹方；原稿保留。')
    plan,prompts,full_prompt=_compiled(candidate,job,folder)
    before_plan=json.loads((Path(work)/'director_plan.json').read_text(encoding='utf-8'))
    preview=[]
    for seg in job['segments']:
        i=seg['index']
        original_prompt=(folder/f'{i:02d}_prompt.txt').read_text(encoding='utf-8')
        old=before_plan['segments'][i]
        new=plan['segments'][i]
        if old.get('event')!=new.get('event') or original_prompt!=prompts[i]:
            preview.append({'index':i,'start':seg['start'],'end':seg['start']+seg['seconds'],
                            'before_event':old.get('event',''),'after_event':new.get('event',''),
                            'before_h3':original_prompt,'after_h3':prompts[i]})
    result={'version':1,'id':id_,'base_revision':base_revision,
            'base_master_hash':digest(original),'candidate_master_hash':digest(candidate),
            'master':dict(master,film=candidate,quality_status='user_revision_unreviewed'),
            'plan':plan,'prompts':{str(k):v for k,v in prompts.items()},
            'full_prompt':full_prompt,'preview':preview,
            'original_hash':digest(before_plan)}
    atomic_json(staging/'candidate.json',result)
    return {'status':'ready','id':id_,'base_revision':base_revision,
            'candidate_master_hash':result['candidate_master_hash'],
            'changed_segments':[p['index'] for p in preview],
            'preview':preview,'recipe_changed':False,
            'message':'候選修訂版已生成；未採用前原丹方保持不變。'}


def accept(work, job, revision, write_state, plan_revision):
    """Atomic-like multi-file publication with backup, rollback and stale guard."""
    folder=Path(work)/'preproduction'
    state=job.get('recipe_revision') or {}
    if state.get('status')!='ready' or state.get('id')!=revision:
        raise ValueError('修訂版不存在或已失效。')
    if state.get('base_revision')!=job.get('plan_revision') or plan_revision(job)!=state['base_revision']:
        raise ValueError('原丹方版本已變更，請重新產生修訂版。')
    source=folder/'recipe_revisions'/revision/'candidate.json'
    candidate=json.loads(source.read_text(encoding='utf-8'))
    master_file=folder/'whole_film.json'
    master=json.loads(master_file.read_text(encoding='utf-8'))
    if digest(master['film'])!=candidate['base_master_hash']:
        raise ValueError('原始全曲攝影稿已變更，不能套用舊修訂版。')
    paths={master_file:json.dumps(candidate['master'],ensure_ascii=False,indent=2),
           Path(work)/'director_plan.json':json.dumps(candidate['plan'],ensure_ascii=False,indent=2),
           folder/'whole_film_prompt.txt':candidate['full_prompt']}
    for seg in job['segments']:
        i=seg['index']
        paths[folder/f'{i:02d}_prompt.txt']=candidate['prompts'][str(i)]
    backups={p:(p.read_bytes() if p.is_file() else None) for p in paths}
    archive=folder/'recipe_revisions'/revision/'originals'
    archive.mkdir(exist_ok=True)
    for p,content in backups.items():
        if content is not None:
            (archive/('preproduction_' if p.parent==folder else 'project_')+p.name).write_bytes(content)
    previous=copy.deepcopy(job)
    try:
        for p,value in paths.items():
            _write_text(p,value)
        job['plan_preview_setup']=candidate['plan']['shared_setup']
        for seg in job['segments']:
            idx=seg['index']
            seg['director_plan']=candidate['plan']['segments'][idx]
            seg['prompt']=candidate['prompts'][str(idx)]
            seg['prompt_prepared']=True
            seg['fixed_reference_settings']=candidate['plan']['shared_setup']
        job.pop('plan_translation',None)  # translation was for the old source revision
        job['recipe_revision']={'status':'adopted','id':revision,
                                'base_revision':state['base_revision'],
                                'changed_segments':state['changed_segments'],
                                'recipe_changed':True}
        job['plan_revision']=plan_revision(job)
        write_state(job)
    except Exception:
        for p,data in backups.items():
            if data is None:
                p.unlink(missing_ok=True)
            else:
                tmp=p.with_name('.'+p.name+'.rollback.tmp')
                tmp.write_bytes(data)
                tmp.replace(p)
        try:
            write_state(previous)
        except Exception:
            pass
        raise
    return job
