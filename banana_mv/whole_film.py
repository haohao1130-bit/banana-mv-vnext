"""Author one continuous film; compile render windows without another writer."""
import copy
import json
from pathlib import Path
import re
import uuid
import time

from banana_mv.scene_state import atomic_json, digest, rewrite_retry_count
from banana_mv.shoot_plan import (_text, _pictures, adaptation_direction,
    REFERENCE_PERFORMANCE, CLIP_INTENSITY, DYNAMIC_EDITING)
from banana_mv.mv_scope import ending_contract
from banana_mv.lyrics_reference import OPTIONAL_TIMING_POLICY

SYSTEM = '''Write ONE continuous music-video shooting script for the entire supplied song.
The story and photography are authored together, before any technical slicing.
Develop the user's story with expressive performance, motivated coverage and montage.
Return JSON only:
{"subject_definitions":"stable Subject/Picture identity, scene and vocal bindings",
 "beats":[{"at_ms":0,"shot_id":"s1","state":"complete current visible state",
 "camera":"concrete framing and camera movement",
 "ongoing_camera":"the already underway camera view, without restarting its move",
 "continuation_state":"present state during the ongoing phase, without resetting its starting pose",
 "mode":"performance, band, action, story or another supported director mode",
 "action":"new action starting at this global time",
 "ongoing":"only the motion or present activity that remains underway"}]}
Use GLOBAL integer milliseconds. First beat starts at 0; later times strictly
increase and stay within source duration. Last beat lasts to the source end.
Choose beats and shot lengths from events and music, never from a 10/15-second grid.
Keep the same shot_id while one continuous camera view develops across beats;
change shot_id for an actual editorial cut. Each action is authored once at its
chronological position. An already achieved result belongs in state, not action.
state gives the visible subjects' current location, wardrobe, held objects,
physical condition, pose and movement direction needed to start at this instant.
It is a present-tense snapshot, not a recap, cause, future event or plot summary.
continuation_state is the current condition for an entry inside the ongoing phase;
never carry an already changed starting pose or prop into that snapshot.
Each beat supplies a complete relevant snapshot rather than relying on an earlier
paragraph. When a parallel strand returns, its achieved condition persists.
subject_definitions contains stable identity/reference and scene/vocal duties;
put mutable clothing, props and changes only in state. Current state overrides
reference-image initial appearance. Omit absent items unless visibly relevant.
ongoing describes only what can safely continue if a technical window begins
inside this beat, never the initiation of an already completed action. Split an
action into timed phases when its contact or consequence needs its own timing.
A technical boundary is not a cut, an introduction or an ending. Do not write
clip commissions. Only the actual whole-film conclusion resolves the story.
Source recording stays unchanged. Only assigned singers lip-sync; never invent
lyrics, audio events or instruments you have not heard. State vocal duties by scene.
SRT is optional timing reference, not mandatory singing coverage or cut positions.
Use concise English prose; retain source lyrics and names in their language.
'''


def parse_film(raw, duration_ms):
    text=_text(raw).strip()
    if text.startswith('```'):text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
    data=json.loads(text)
    if not isinstance(data,dict) or not isinstance(data.get('subject_definitions'),str):
        raise ValueError('全曲攝影稿缺少身份定義。')
    beats=data.get('beats')
    if not isinstance(beats,list) or not beats:raise ValueError('全曲攝影稿缺少時間軸。')
    previous=-1
    for i,beat in enumerate(beats):
        if not isinstance(beat,dict):raise ValueError('時間點需為物件。')
        at=beat.get('at_ms')
        if type(at) is not int or not previous<at<duration_ms or (i==0 and at!=0):
            raise ValueError('全局時間需從零開始，遞增且位於歌曲內。')
        for key in ('shot_id','state','continuation_state','camera','ongoing_camera','action','ongoing'):
            if not isinstance(beat.get(key),str) or not beat[key].strip():
                raise ValueError('時間點缺少 '+key)
        previous=at
    return data


def window(film, start_ms, end_ms):
    """Select active state + new actions; never forward earlier/future action text."""
    beats=film['beats'];active=max(i for i,b in enumerate(beats) if b['at_ms']<=start_ms)
    result=[]
    for i in range(active,len(beats)):
        beat=beats[i]
        if beat['at_ms']>=end_ms:break
        row={k:beat[k] for k in ('shot_id','state','camera')}
        row['at_ms']=max(0,beat['at_ms']-start_ms)
        if beat['at_ms']<start_ms:
            row['state']=beat['continuation_state']
            row['camera']=beat['ongoing_camera']
        row['mode']=beat.get('mode','story')
        row['action']=beat['action'] if beat['at_ms']>=start_ms else beat['ongoing']
        result.append(row)
    return result


def compile_window(film, seg, *, chain=False):
    start=round(seg['start']*1000);end=round((seg['start']+seg['seconds'])*1000)
    rows=window(film,start,end);lines=[];shot=0;previous=None
    for row in rows:
        ms=row['at_ms'];clock=f'{ms//60000:02d}:{ms//1000%60:02d}.{ms%1000:03d}'
        if row['shot_id']!=previous:
            shot+=1;prefix=f'[Shot {shot}] '+(f'At {clock}, ' if shot>1 else '')
        else:prefix=f'At local {clock}, within the same continuous shot, '
        lines.append(prefix+row['camera']+' Current visible state: '+row['state']+' '+row['action'])
        previous=row['shot_id']
    definitions=film['subject_definitions']
    if chain and seg['index']>0:
        shift=lambda s:re.sub(r'<Picture (\d+)>',lambda m:f'<Picture {int(m[1])+1}>',s)
        definitions='<Picture 1> is the actual preceding last frame, not another actor.\n'+shift(definitions)
        lines=[shift(line) for line in lines]
    text='\n\n'.join((
        'subject_definitions:\n'+definitions+'\n<Audio 1> is the supplied source-song window.',
        'summary:\n[reference generation + audio reuse] Continue this interval of the continuous film. Current visible state governs mutable appearance.',
        'retention_analysis:\n<Audio 1>: fully_copy - reuse the supplied recording unchanged. Preserve reference identity; current state defines appearance.',
        'detailed_description:\n'+'\n'.join(lines),
        'overall_soundscape:\n<Audio 1> unchanged; no generated dialogue or sound layers.',
        'non_diegetic_music:\nThe supplied original song unchanged.'))
    return text,rows


def ensure_film(cfg, req, segments, originals, work, rewrite):
    """One creative call, bounded delivery retries, then deterministic slicing."""
    folder=Path(work)/'preproduction';folder.mkdir(exist_ok=True)
    duration_ms=round((segments[-1]['start']+segments[-1]['seconds'])*1000)
    source={'brief':req.get('prompt',''),'duration_ms':duration_ms,
            'adaptation':adaptation_direction(req),
            'srt_cues':req.get('srt_cues',[]),'lyrics':req.get('lyrics',''),
            'music_evidence':[{'source_start':s['start'],'source_end':s['start']+s['seconds'],
                               'evidence':s.get('audio_evidence',{})} for s in segments],
            'ending':ending_contract(req,duration_ms/1000,segments)}
    fingerprint=digest(source);path=folder/'whole_film.json'
    if path.is_file():
        saved=json.loads(path.read_text());film=parse_film(json.dumps(saved['film']),duration_ms)
        if saved['input_sha256']!=fingerprint:raise ValueError('完整攝影稿與目前素材設定不符。')
    else:
        writer_cfg=copy.deepcopy(cfg)
        writer_cfg.setdefault('rewriter',{})['max_length']=max(16384,int(cfg.get('rewriter',{}).get('max_length',8192)))
        system=(SYSTEM+'\n'+adaptation_direction(req)+'\n'+REFERENCE_PERFORMANCE+
                '\n'+CLIP_INTENSITY[req.get('intensity','high')]+'\n'+
                (DYNAMIC_EDITING if req.get('dynamic_cuts',True) else 'Use motivated longer continuous takes; preserve requested one-take photography.')+
                '\n'+OPTIONAL_TIMING_POLICY)
        parts=[('text',json.dumps(source,ensure_ascii=False))]+_pictures(originals)
        for attempt in range(rewrite_retry_count(req)+1):
            started=time.monotonic()
            raw=rewrite(writer_cfg,system,parts,uuid.uuid4().hex[:8])
            atomic_json(folder/'whole_film_generation.json', {'attempt':attempt+1,
                'elapsed_seconds':round(time.monotonic()-started,3),
                'output_characters':len(raw),'max_generated_tokens':writer_cfg['rewriter']['max_length'],
                'actual_token_count':None,'note':'TextGenerate returns text; actual token usage is unavailable.'})
            (folder/f'whole_film_raw_{uuid.uuid4().hex[:8]}.txt').write_text(raw,encoding='utf-8')
            try:film=parse_film(raw,duration_ms);break
            except (ValueError,TypeError) as exc:
                if attempt==rewrite_retry_count(req):raise
                parts=[('text',json.dumps(source,ensure_ascii=False)+'\nPrevious delivery was unreadable: '+str(exc)+'. Return the complete continuous timeline JSON.')]+_pictures(originals)
        atomic_json(path,{'version':1,'input_sha256':fingerprint,'film':film,
                          'quality_status':'not_visually_verified'})
    rows=[]
    from banana_mv.shoot_plan import validate_native_mv_format
    for seg in segments:
        text,local=compile_window(film,seg,chain=req.get('mode')=='chain')
        validate_native_mv_format(text,seg['seconds'],require_native=True)
        (folder/f'{seg["index"]:02d}_prompt.txt').write_text(text,encoding='utf-8')
        from banana_mv.director import MODES
        modes=[r['mode'] for r in local if r['mode'] in MODES]
        mode='action' if 'action' in modes else (modes[0] if modes else 'story')
        rows.append({'index':seg['index'],'mode':mode,'handoff_version':1,
                     'event':'\n'.join(r['state']+' '+r['action'] for r in local)})
    plan={'version':5,'shared_setup':film['subject_definitions'],'segments':rows,
          'ending_contract':source['ending'],'whole_film_version':1,'visual_verified':False}
    atomic_json(Path(work)/'director_plan.json',plan)
    atomic_json(Path(work)/'screenplay_review.json',{'status':'not_run_whole_film',
        'warnings':['Continuous-film generation is experimental; legacy clip rewrite reviews were not applied.']})
    atomic_json(folder/'whole_film_windows.json',{'version':6,'clip_count':len(segments),'whole_film_version':1})
    return plan
