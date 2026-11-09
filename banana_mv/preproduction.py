"""Move camera preparation before rendering; reuse the working MV engine."""
import json
from pathlib import Path
import re
import uuid

from banana_mv.core import normalize_mv_prompt
from banana_mv.scene_state import atomic_json, parse_object, rewrite_retry_count
from banana_mv.shoot_plan import _text, _pictures, AUTO_FILMING, DYNAMIC_EDITING, CLIP_INTENSITY, REFERENCE_PERFORMANCE
from banana_mv.lyrics_reference import excerpt, OUTPUT_POLICY
from banana_mv.mv_scope import clip_ending

CAMERA_SYSTEM = '''You are the whole-song cinematographer. The supplied screenplay is final.
Plan photography for every clip in ONE JSON response. Return:
{"clips":[{"index":0,"shots":[{"at_ms":0,"event_ids":["c0e0"],"camera":"English photographic instructions"}]}]}.
Camera prose specifies composition, subject position, perspective, lighting, focus,
camera movement and editorial attention. Do not author or paraphrase story actions,
dialogue, costume changes or outcomes. Refer to commissioned actors by their names.
Each supplied event has a stable ID. Assign the IDs to shots in their supplied order,
each ID once. A shot may cover several consecutive events: choose coverage from the
action, not one shot per ID. The compiler inserts those exact events in that shot.
An attack, contact and response can stay in ONE continuous shot. Leave enough time
to see preparation, execution and the consequence; do not jump to the end state.
Every camera entry describes only its current continuous view. Put the NEXT cut
in another shot entry, not inside camera prose. at_ms is the only cut clock.
SRT/beat times are reference context, NOT a list of mandatory cuts. Source SRT times
are global; local_srt clip_start/clip_end belong only to that source interval.
Use each clip's ending context. Intermediate clips keep moving; only the assigned
final event ends the work. Reserve the final consequence and its visible response
before the ending. Never paste the global ending into every clip.
Choose shot counts and timing from the event; no fixed quota or mandatory cuts.
First shot starts at 0; subsequent at_ms values increase within that clip duration.
Plan free MV intercuts and parallel locations without resetting ongoing events.
Source lyrics and vocal assignments are fixed. No new dialogue or soundtrack.
References define identities and environments, not mandatory attendance or poses.'''


def event_units(seg):
    """Lossless paragraph/line units; keep multi-phase action clauses together."""
    text=seg['director_plan']['event']
    lines=[line.strip() for line in text.splitlines() if line.strip() and not re.match(r'^Mode\s*:',line,re.I)]
    return [{'id':f'c{seg["index"]}e{i}','text':line} for i,line in enumerate(lines)]


def camera_plan(raw, segments, *, linked=False):
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
        if linked:
            # Address correspondence, not a semantic/creative review. The compiler
            # must know where to put each source event instead of stuffing Shot 1.
            expected=[e['id'] for e in event_units(seg)]
            assigned=[]
            for shot in shots:
                ids=shot.get('event_ids')
                if not isinstance(ids,list) or not ids or any(not isinstance(e,str) for e in ids):
                    raise ValueError('每鏡需引用事件編號；一鏡可拍多個連續事件。')
                assigned.extend(ids)
            if assigned!=expected:
                raise ValueError('鏡頭事件編號需依原順序交齊，每個編號一次；可自由合併於同一鏡。')
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
    events={e['id']:connected(e['text']) for e in event_units(seg)}
    for i,shot in enumerate(row['shots']):
        ms=shot['at_ms']; clock=f'{ms//60000:02d}:{ms//1000%60:02d}.{ms%1000:03d}'
        prefix=f'[Shot {i+1}] '+(f'At {clock}, ' if i else '')
        if 'event_ids' in shot:
            action='\n'.join(events[e] for e in shot['event_ids'])
        else:
            # Existing v1 plans stay readable; never migrate a saved production.
            action=event if i==0 else 'Continue the commissioned action at this point in its original order; this cut adds no new event.'
        lines.append(prefix+connected(shot['camera'])+'\n'+action)
    return '\n\n'.join((
        'subject_definitions:\n'+first+setup+'\n<Audio 1> is the supplied original song window.',
        'summary:\n[reference generation + audio reuse] Film this commissioned interval in the supplied event order, using the connected identities and unchanged source song.',
        'retention_analysis:\n<Audio 1>: fully_copy - reuse the original recording unchanged. Preserve assigned reference identities and current script appearance.',
        'detailed_description:\n'+'\n'.join(lines),
        'overall_soundscape:\nThe supplied source recording unchanged. '+OUTPUT_POLICY+' No new dialogue or generated sound layers.',
        'non_diegetic_music:\nThe supplied original song; no replacement music.'))


NATIVE_DIRECTOR = """You are the screen director and native H3 Ref2VA prompt writer.
Read the isolated current-interval commission: one continuous slice of a longer work,
not a miniature complete story. Expand
ONLY this interval into a complete production-ready filming prompt, using
the official six-section format below. Preserve commissioned identities, vocal
roles, core events, causal progression and local outcome. Actively invent the
specific performance, physical choreography, expressions, reactions, blocking,
composition, lighting, coverage and montage that bring those events to life.
One event may unfold across several shots. Choose shot count and pacing from the
scene and music; every cut reveals a new detail, action phase or reaction. Choose
close-ups, inserts, wide views, subjective angles and temporal speed changes when
they serve the event, rather than cycling a checklist. Show preparation, execution
and consequence. Temporal effects change visual action only; source music stays
unchanged. Parallel scenes remain distinct and their action progresses across cuts.
User_role_declarations quote the user's explicit source instructions. They override
conflicting generated fixed settings or events. Preserve who performs which role
in which location; an unassigned co-star is not another vocalist. Keep stable
Subject/voice bindings across the project; picture order does not imply a voice.
Opening state is already established at frame zero, not a scene to reconstruct.
Film only New progression, ending in Outgoing state. Across shots advance from the
state already reached: do not describe the complete action in Shot 1 and replay
its preparation, contact or consequence in subsequent shots. Cover each action
phase at its actual chronological position. New angles may show ongoing action
or fresh reactions, not restart a completed milestone.
The summary describes ONLY this interval's visible progression. Shared settings
establish identities and places, not an opening sequence or a plot synopsis.
Use the current state and the commission's incoming/outgoing energy cues to stage
the first and last shots. Carry momentum by the chosen movement, rhythm, attention,
composition, emotion or contrast; a new subject or location can receive that energy.
Complete a readable shot at the boundary without forcing the story to settle.
Film an opening or resolution only when explicitly assigned in this commission;
otherwise stay in progress. If assigned a residual ending hold, sustain its present
result without replaying the decisive event. The commission's actual events remain
authoritative over generic ending-phase hints.
SRT and music analysis provide timing context, not mandatory cut points.
The supplied recording is unchanged: retention_analysis includes <Audio 1>:
fully_copy. Only assigned vocalists lip-sync the original lyrics at supplied timing.
Keep audio reuse and vocal roles intact; overall_soundscape and non_diegetic_music
refer to the supplied recording. External effects are mixed separately. Write no
new speech, lyrics or replacement music. Supporting cast without photos keeps its
script identity. Reference pictures identify assets; they do not dictate framing.
Return only the complete native six-section prompt in English, keeping source
lyrics and visible text in their original language. Use clip-local cut times.
"""


def prepare(cfg,job,originals,work,rewrite):
    """Complete every native director prompt before the existing render loop."""
    from banana_mv.shoot_plan import validate_native_mv_format, source_role_settings, native_shot_replay_warning
    folder=Path(work)/'preproduction';folder.mkdir(exist_ok=True)
    ready=folder/'ready.json'
    if ready.is_file():return
    screenplay={'version':5,'shared_setup':job.get('plan_preview_setup',''),
        'clips':[{'index':s['index'],'seconds':s['seconds'],
                  'event':s['director_plan']['event'],
                  'ending':clip_ending(job['request'],s),
                  'fixed_reference_settings':s.get('fixed_reference_settings',''),
                  'local_srt':excerpt(job['request'],s),
                  'audio_evidence':s.get('audio_evidence',{})} for s in job['segments']]}
    atomic_json(folder/'screenplay.json',screenplay)
    guide=Path(cfg['guides']['ref']).read_text(encoding='utf-8')
    system=NATIVE_DIRECTOR+'\n'+guide
    req=job['request']
    style=AUTO_FILMING+'\n'+REFERENCE_PERFORMANCE+'\n'+CLIP_INTENSITY[req.get('intensity','high')]
    style+='\n'+(DYNAMIC_EDITING if req.get('dynamic_cuts',True) else 'Prefer motivated longer takes.')
    # Write against the original image numbering. At render time chain mode adds
    # its actual preceding frame, so shift original references only after writing.
    for seg in job['segments']:
        path=folder/f'{seg["index"]:02d}_prompt.txt'
        if path.is_file():continue
        payload={'user_role_declarations':source_role_settings(req.get('prompt',''),len(originals)),
                 'current_clip':screenplay['clips'][seg['index']],
                 'duration_seconds':seg['seconds'],'direction':style}
        parts=[('text',json.dumps(payload,ensure_ascii=False))]+_pictures(originals)
        for attempt in range(rewrite_retry_count(req)+1):
            raw=rewrite(cfg,system,parts,uuid.uuid4().hex[:8])
            (folder/f'director_{seg["index"]:02d}_raw_{uuid.uuid4().hex[:8]}.txt').write_text(raw,encoding='utf-8')
            try:
                text=validate_native_mv_format(normalize_mv_prompt(_text(raw),len(originals)),seg['seconds'],require_native=req.get('h3_validation_version')==1)
                warning=native_shot_replay_warning(text)
                if warning:
                    atomic_json(folder/f'{seg["index"]:02d}_replay_warning.json',
                                {'attempt':attempt+1,'warning':warning,'auto_retry':attempt<rewrite_retry_count(req)})
                    if attempt<rewrite_retry_count(req):
                        parts=[('text',json.dumps(payload,ensure_ascii=False)+
                               '\nThe previous draft passed format checks but repeated a completed event: '+warning+
                               '\nRewrite this interval cleanly. Keep each action once, progress through shots, preserve the commissioned outcome and original audio.')]+_pictures(originals)
                        continue
                # A semantic warning never blocks a renderable draft after retries.
                break
            except ValueError as error:
                if attempt==rewrite_retry_count(req):raise
                parts=[('text',json.dumps(payload,ensure_ascii=False)+'\nCorrect native format or local timing: '+str(error))]+_pictures(originals)
        if req.get('mode')=='chain' and seg['index']>0:
            text=re.sub(r'<Picture (\d+)>',lambda m:f'<Picture {int(m[1])+1}>',text)
            text='subject_definitions:\n<Picture 1> is the actual preceding last frame, a continuity guide rather than another actor.\n'+re.sub(r'^\s*subject_definitions\s*:\s*','',text,count=1)
        path.write_text(text,encoding='utf-8')
    atomic_json(ready,{'version':5,'clip_count':len(job['segments'])})


def prompt(work,index):
    # Missing files are execution errors; there is no semantic review gate.
    folder=Path(work)/'preproduction'
    if not (folder/'ready.json').is_file():raise ValueError('全曲備稿尚未完成。')
    return (folder/f'{index:02d}_prompt.txt').read_text(encoding='utf-8')


def preview(job,work):
    """Enrich a read-only status response, without marking any clip as rendered."""
    folder=Path(work)/'preproduction'
    if not job.get('request',{}).get('vnext_preproduction') or not (folder/'ready.json').is_file():return job
    for seg in job['segments']:
        path=folder/f'{seg["index"]:02d}_prompt.txt'
        if not seg.get('prompt') and path.is_file():
            seg['prompt']=path.read_text(encoding='utf-8')
            seg['prompt_prepared']=True
    return job
