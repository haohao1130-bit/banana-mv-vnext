"""Move camera preparation before rendering; reuse the working MV engine."""
import json
from pathlib import Path
import re
import uuid

from banana_mv.core import normalize_mv_prompt
from banana_mv.scene_state import atomic_json, parse_object, rewrite_retry_count
from banana_mv.shoot_plan import _text, _pictures, AUTO_FILMING, DYNAMIC_EDITING, CLIP_INTENSITY, REFERENCE_PERFORMANCE
from banana_mv.lyrics_reference import excerpt, OUTPUT_POLICY

CAMERA_SYSTEM = '''You are the whole-song cinematographer. The supplied screenplay is final.
Plan photography for every clip in ONE JSON response. Return:
{"clips":[{"index":0,"shots":[{"at_ms":0,"camera":"English photographic instructions"}]}]}.
Camera prose specifies composition, subject position, perspective, lighting, focus,
camera movement and editorial attention. Do not author or paraphrase story actions,
dialogue, costume changes or outcomes. Refer to commissioned actors by their names.
The compiler will insert the original commissioned event text unchanged.
Choose shot counts and timing from the event; no fixed quota or mandatory cuts.
First shot starts at 0; subsequent at_ms values increase within that clip duration.
Plan free MV intercuts and parallel locations without resetting ongoing events.
Source lyrics and vocal assignments are fixed. No new dialogue or soundtrack.
References define identities and environments, not mandatory attendance or poses.'''


def camera_plan(raw, segments):
    """Only check fields needed to address clips and place cuts on the timeline."""
    data=parse_object(_text(raw));rows=data.get('clips')
    if not isinstance(rows,list) or len(rows)!=len(segments):
        raise ValueError('全曲攝影稿需交齊各段。')
    for seg,row in zip(segments,rows):
        if not isinstance(row,dict) or row.get('index')!=seg['index']:
            raise ValueError('攝影段落順序不符。')
        shots=row.get('shots')
        if not isinstance(shots,list) or not shots:
            raise ValueError('攝影稿缺少鏡頭。')
        previous=-1
        for i,shot in enumerate(shots):
            if not isinstance(shot,dict):raise ValueError('鏡頭需為物件。')
            start=shot.get('at_ms');camera=shot.get('camera')
            if type(start) is not int or not previous<start<seg['seconds']*1000 or (i==0 and start!=0):
                raise ValueError('切鏡時間需從零開始，遞增且位於當段內。')
            if not isinstance(camera,str) or not camera.strip():raise ValueError('缺少攝影內容。')
            previous=start
    return data


def compile_prompt(job, seg, row):
    """Keep commissioned event prose intact; camera planning cannot replace it."""
    offset=int(job['request'].get('mode')=='chain' and seg['index']>0)
    def connected(text):
        return re.sub(r'<Picture (\d+)>',lambda m:f'<Picture {int(m[1])+offset}>',text)
    event=connected(seg['director_plan']['event'])
    setup=connected(seg.get('fixed_reference_settings') or job.get('plan_preview_setup',''))
    first=('<Picture 1> is the preceding last frame, a continuity guide rather than a new actor.\n' if offset else '')
    lines=[]
    for i,shot in enumerate(row['shots']):
        ms=shot['at_ms']; clock=f'{ms//60000:02d}:{ms//1000%60:02d}.{ms%1000:03d}'
        prefix=f'[Shot {i+1}] '+(f'At {clock}, ' if i else '')
        lines.append(prefix+connected(shot['camera'])+('\n'+event if i==0 else
            '\nContinue the commissioned action at this point in its original order; this cut adds no new event.'))
    return '\n\n'.join((
        'subject_definitions:\n'+first+setup+'\n<Audio 1> is the supplied original song window.',
        'summary:\n[reference generation + audio reuse] '+event,
        'retention_analysis:\n<Audio 1>: fully_copy - reuse the original recording unchanged. Preserve assigned reference identities and current script appearance.',
        'detailed_description:\n'+'\n'.join(lines),
        'overall_soundscape:\nThe supplied source recording unchanged. '+OUTPUT_POLICY+' No new dialogue or generated sound layers.',
        'non_diegetic_music:\nThe supplied original song; no replacement music.'))


def prepare(cfg,job,originals,work,rewrite):
    """Reuse the allocated full story; one whole-song camera request before GPU."""
    folder=Path(work)/'preproduction';folder.mkdir(exist_ok=True)
    ready=folder/'ready.json'
    if ready.is_file():return
    screenplay={'shared_setup':job.get('plan_preview_setup',''),
        'clips':[{'index':s['index'],'seconds':s['seconds'],
                  'event':s['director_plan']['event'],
                  'fixed_reference_settings':s.get('fixed_reference_settings',''),
                  'local_srt':excerpt(job['request'],s),
                  'audio_evidence':s.get('audio_evidence',{})} for s in job['segments']],
        'lyrics':job['request'].get('lyrics',''),
        'srt_cues':job['request'].get('srt_cues',[])}
    atomic_json(folder/'screenplay.json',screenplay)
    path=folder/'camera.json'
    if path.is_file():
        camera=camera_plan(path.read_text(encoding='utf-8'),job['segments'])
    else:
        payload=json.dumps(screenplay,ensure_ascii=False)
        system=CAMERA_SYSTEM+'\n'+AUTO_FILMING+'\n'+REFERENCE_PERFORMANCE+'\n'+CLIP_INTENSITY[job['request'].get('intensity','high')]
        system+='\n'+(DYNAMIC_EDITING if job['request'].get('dynamic_cuts',True) else 'Prefer motivated longer takes.')
        parts=[('text',payload)]+_pictures(originals)
        for attempt in range(rewrite_retry_count(job['request'])+1):
            raw=rewrite(cfg,system,parts,uuid.uuid4().hex[:8])
            (folder/f'camera_raw_{attempt:02d}.txt').write_text(raw,encoding='utf-8')
            try:
                camera=camera_plan(raw,job['segments']);break
            except ValueError as error:
                if attempt==rewrite_retry_count(job['request']):raise
                parts=[('text',payload+'\nReturn complete camera JSON. Fix: '+str(error))]+_pictures(originals)
        atomic_json(path,camera)
    for seg,row in zip(job['segments'],camera['clips']):
        prompt=normalize_mv_prompt(compile_prompt(job,seg,row),len(originals)+int(job['request'].get('mode')=='chain' and seg['index']>0))
        (folder/f'{seg["index"]:02d}_prompt.txt').write_text(prompt,encoding='utf-8')
    atomic_json(ready,{'version':1,'clip_count':len(job['segments'])})


def prompt(work,index):
    # Missing files are execution errors; there is no semantic review gate.
    folder=Path(work)/'preproduction'
    if not (folder/'ready.json').is_file():raise ValueError('全曲備稿尚未完成。')
    return (folder/f'{index:02d}_prompt.txt').read_text(encoding='utf-8')
