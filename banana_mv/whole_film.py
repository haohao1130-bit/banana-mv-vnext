"""Author one continuous film; compile render windows without another writer."""
import copy
import json
from pathlib import Path
import re
import uuid
import time

from banana_mv.scene_state import atomic_json, digest, rewrite_retry_count
from banana_mv.shoot_plan import (_text, _pictures, adaptation_direction,
    REFERENCE_PERFORMANCE, CLIP_INTENSITY, DYNAMIC_EDITING, AUTO_FILMING, source_role_settings)
from banana_mv.mv_scope import ending_contract, continuous_film_ending_contract
from banana_mv.lyrics_reference import OPTIONAL_TIMING_POLICY

SYSTEM = '''Write ONE continuous music-video shooting script for the entire supplied song.
The story and photography are authored together, before any technical slicing.
Develop the user's story with expressive performance, motivated coverage and montage.
Return JSON only:
{"subject_definitions":"stable Subject/Picture identity, scene and vocal bindings",
 "beats":[{"at_ms":0,"shot_id":"s1","state":"complete current visible state",
 "camera":"concrete framing and camera movement",
 "filming_prompt":"finished native H3 shot prose: composition, action and photography",
 "ongoing_filming_prompt":"finished native shot prose for the already underway phase",
 "ongoing_camera":"the already underway camera view, without restarting its move",
 "continuation_state":"present state during the ongoing phase, without resetting its starting pose",
 "mode":"performance, band, action, story or another supported director mode",
 "action":"new action starting at this global time",
 "ongoing":"only the motion or present activity that remains underway"}]}
Respect the source.ending finale contract. Technical render slices never decide
when the whole-film story ends. The user's explicit final beat or final lyric
may continue until the actual song end; do not demand a padded final hold.
The supplied duration_ms is the WHOLE SONG's duration, not a clip length.
Use GLOBAL integer milliseconds: 1 second = 1000 ms; 12.5 seconds = 12500 ms.
Budget all events across that complete duration. Do not write a few seconds of
story followed by a remaining long hold. Do not guess, rescale or compress the
user's explicit time windows to fit a shorter timeline.
First beat starts at 0; later times strictly
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
subject_definitions contains stable identity/reference and scene/vocal duties ONLY.
It contains no story recap, event list, opening action, climax, final pose, future
outcome or instruction to perform the ending. Each rendered window receives this
shared table, so global plot in that table would leak into every window;
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
USER TIMING AND DELIVERABLE:
Treat explicit time ranges in the original brief as commissioned story windows,
not loose inspiration. Keep the assigned event in its supplied window. Generic
ending/hold suggestions yield to explicit user timing and final-shot requests.
Plan the full duration before drafting. Fill it with developed events, not an
accelerated outline followed by a long aftermath. Preserve creative freedom
inside the user's constraints; do not change the premise or outcome.
Deliver an executable shot timeline rather than milestone summaries. Each actual
change of scene or camera view gets its own beat and shot_id; a camera field
specifies ONE current view. For montage write its constituent timed shots, not
"intercut", "rapid cuts" or multiple viewpoints as a substitute for a shot list.
Choose density from the event; no fixed shot count or cut-every-N-seconds rule.
Action identifies who does what to whom, the visible movement/direction and
result. Give important interactions their preparation, contact and consequence
at their correct times; vary framing and speed according to what must be seen.
A state contains only the established current condition; it does not perform
this beat's action, recount previous causes or announce later plot outcomes.
For one identity in multiple scenes, explicitly bind its duty in each scene.
Bind referenced actors to actual supplied <Picture N> slots and do not give
background characters vocal duties that conflict with the user's assigned cast.
Use English for camera, action, state and role prose; retain source lyrics and
names in their language. Do not translate the complete filming script to match
the user's input language.
'''


PHOTOGRAPHY = """You enhance reference-conditioned video prompts (Ref2VA), not synopsis prose.
Apply the supplied official guide's reference labels and shot-writing language.
The transport is the timeline JSON schema above, NOT six headers in the JSON.
The compiler emits the six sections after slicing; author their detailed_description
NOW, for the whole film, before any slicing. In EVERY beat additionally return:
"filming_prompt": finished English shot prose, without a Shot label or timestamp;
"ongoing_filming_prompt": finished prose for entering the already underway phase.
Compose each as a filmable current view: establish the scene, visible subjects and
screen positions, framing and camera height/angle, relevant foreground/depth and
lighting, concrete ordered action/reaction, and motivated camera path, speed and
extent (or a deliberate locked-off view). Describe what the camera actually sees.
Use meaningful close-ups, spatially readable coverage, expressive performance,
focus or speed changes and motivated montage when they serve the user's event.
Choose techniques freely; this is not a checklist of effects for every shot.
A phrase like 'dynamic camera', 'cinematic montage' or 'orbit the lead' is not a
completed shooting description. Expand HOW the event is filmed rather than
copying state/action summaries. One beat is one current view; give each actual
cut its own global time and shot_id. Separate parallel locations into real shots;
shared identity never puts different scene instances in one physical composition.
Use the supplied reference_manifest to retain explicit source identities and
locations. Give referenced Subjects their source Picture labels; shared identity
in different scene instances may use the same Picture. Never infer a Picture
number from a Subject or speaker number. Keep original supporting cast unbound
when it has no reference. Bind <Subject N> to supplied <Picture N> in natural English definition lines;
use the same labels inside shot prose and keep scene-specific vocal duties.
State/action fields remain editorial continuity metadata, not the final prompt.
The ongoing prose preserves established momentum and the current condition;
it does not replay an impact, entrance, clothing change or completed action.
Each filming paragraph describes ONLY its timed phase, not the earlier cause or
a later phase. An impact, fall and settled aftermath each belong at their own
event times, even if the camera remains in the same shot. Keep completed actions,
future outcomes and global story explanations out of current and ongoing prose.
No new lyrics or audio layers. Source song rules and optional SRT policy override
any sound examples or per-clip word-count suggestions in the official guide.
Write only the complete JSON; do not append an explanation or a second script.
"""


def photography_system(cfg):
    # Reuse the same installed guide as the native path; no download or dependency.
    guide_path=cfg.get('guides',{}).get('ref')
    guide=Path(guide_path).read_text(encoding='utf-8') if guide_path and Path(guide_path).is_file() else ''
    # The native six-section deliverable belongs to the compiler, not this JSON
    # transport. Feeding its retention examples here induced thousands of Shot
    # references in real job 6d6f5c958f15 before any timeline was delivered.
    if re.search(r'^## 1\.',guide,re.M):
        chapters=re.split(r'(?=^## \d+\.)',guide,flags=re.M)
        guide='\n'.join(c for c in chapters if re.match(r'^## (?:2|5)\.',c))
    transport='''FINAL DELIVERY CONTRACT: Return only a JSON object with subject_definitions
and beats. Do not generate summary, retention_analysis, detailed_description,
overall_soundscape or non_diegetic_music fields: the compiler writes those six
sections afterward. Never enumerate Shot appearances in a shared definition or
retention list. Place each actual view on the timed beats array; camera prose is
finished English photography for that phase only, without Shot labels.
'''
    return ('Official Ref2VA writing guide (reference and shot prose only):\n'+guide+'\n' if guide else '')+PHOTOGRAPHY+'\n'+transport



FACE_GUIDANCE = """REFERENCE FACE PRIORITY: For each referenced person, preserve their own
source face geometry, eyes, nose, lips and jaw through expressions, profiles and
motion. Do not blend, beautify into a different identity, or reassign a reference.
This strengthens facial identity, not wardrobe, pose, lighting or composition.
Current story state governs mutable appearance. It does not force frontal views."""


def direction_context(req, image_count):
    from banana_mv.director import MODES, RECIPES, mode_candidates
    allowed,excluded=mode_candidates(req)
    selected=req.get('director','auto')
    modes=sorted(allowed if selected=='auto' else (allowed | {selected})-excluded)
    return {'selected_style':selected,'intensity':req.get('intensity','high'),
            'dynamic_cuts':req.get('dynamic_cuts',True),
            'face_identity':req.get('face_identity',True),
            'scene_recipes':{m:RECIPES[m] for m in modes if m in MODES},
            'excluded_modes':sorted(excluded),
            'user_role_declarations':source_role_settings(req.get('prompt',''),image_count)}


def direction_system(source):
    from banana_mv.filming_review import SCENE_INSTANCE_POLICY
    d=source.get('direction',{})
    text=SCENE_INSTANCE_POLICY+'\n'+AUTO_FILMING+'\n'+REFERENCE_PERFORMANCE
    text+='\n'+source.get('adaptation','')
    text+='\n'+CLIP_INTENSITY[d.get('intensity','high')]
    text+='\n'+(DYNAMIC_EDITING if d.get('dynamic_cuts',True) else
        'Prefer motivated longer takes; develop blocking and reframing without forcing cuts.')
    text+='\nUse direction.selected_style as the requested visual emphasis, not permission to change the story. Apply scene_recipes only where that activity occurs; they are possibilities across the film, not a required complete cycle in every shot or window. Respect excluded_modes and original user roles. When a permitted singer appears, prefer waist-up or closer when readable lip sync matters; do not require singer coverage.'
    if d.get('face_identity',True):text+='\n'+FACE_GUIDANCE
    return text


def photography_gaps(film):
    return [i for i,b in enumerate(film['beats']) if any(
        not isinstance(b.get(k),str) or not b[k].strip()
        for k in ('filming_prompt','ongoing_filming_prompt'))]


def delivery_warnings(cfg, film, modern):
    if not modern:return []
    warnings=[]
    if photography_gaps(film):
        warnings.append('Native photography prose is missing in beats '+
            ', '.join(map(str,photography_gaps(film)))+
            '; these beats use legacy outline compilation, NOT a completed photography delivery.')
    guide=cfg.get('guides',{}).get('ref')
    if not guide or not Path(guide).is_file():
        warnings.append('The installed official Ref2VA guide was unavailable; built-in photography guidance was used.')
    return warnings


def definition_text(value):
    """Render structured identity tables without dropping fields or guessing slots."""
    if isinstance(value,str) and value.strip():return value
    if isinstance(value,(list,dict)) and value:
        return json.dumps(value,ensure_ascii=False,indent=2)
    raise ValueError('全曲攝影稿缺少身份定義；需有非空文字、陣列或物件。')


def parse_film(raw, duration_ms):
    text=_text(raw).strip()
    if text.startswith('```'):text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
    data=json.loads(text)
    if not isinstance(data,dict):raise ValueError('全曲攝影稿需為 JSON 物件。')
    data['subject_definitions']=definition_text(data.get('subject_definitions'))
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
        prose_key='ongoing_filming_prompt' if beat['at_ms']<start_ms else 'filming_prompt'
        if isinstance(beat.get(prose_key),str) and beat[prose_key].strip():
            row['filming_prompt']=beat[prose_key]
        row['mode']=beat.get('mode','story')
        row['action']=beat['action'] if beat['at_ms']>=start_ms else beat['ongoing']
        result.append(row)
    return result


def compile_window(film, seg, *, chain=False, face_identity=False, reference_manifest=None):
    start=round(seg['start']*1000);end=round((seg['start']+seg['seconds'])*1000)
    rows=window(film,start,end);lines=[];shot=0;previous=None
    for row in rows:
        ms=row['at_ms'];clock=f'{ms//60000:02d}:{ms//1000%60:02d}.{ms%1000:03d}'
        if row['shot_id']!=previous:
            shot+=1;prefix=f'[Shot {shot}] '+(f'At {clock}, ' if shot>1 else '')
        else:prefix=f'At local {clock}, within the same continuous shot, '
        # New masters already contain the actual native shooting prose. Old saved
        # projects keep their previous compiler without another creative call.
        prose=row.get('filming_prompt') or (row['camera']+' Current visible state: '+row['state']+' New visible action: '+row['action'])
        if 'filming_prompt' in row:
            # Present state is the only inherited handoff. No previous event,
            # whole-song brief, neighboring beat or future outcome is forwarded.
            prose='Current visible state: '+row['state']+' '+prose
        lines.append(prefix+prose)
        previous=row['shot_id']
    # Normalize reference aliases before keyframe insertion shifts their slots.
    canonical=lambda value:re.sub(r'<\s*(?:Image|Picture)\s*(\d+)\s*>',
        lambda m:f'<Picture {int(m[1])}>',value,flags=re.I)
    from banana_mv.reference_bindings import bind_definitions
    bound,_=bind_definitions(film['subject_definitions'],reference_manifest or [])
    definitions=canonical(bound)
    linked={int(n) for n in re.findall(r'<Picture (\d+)>',definitions)}
    for entry in reference_manifest or []:
        if entry['picture'] not in linked:
            definitions+='\n'+f'<Picture {entry["picture"]}> is the supplied visual reference labeled '+json.dumps(entry['label'],ensure_ascii=False)+'. Use this reference only for its declared subject or setting when depicted; current mutable state overrides initial appearance.'
            linked.add(entry['picture'])
    lines=[canonical(line) for line in lines]
    if chain and seg['index']>0:
        shift=lambda s:re.sub(r'<Picture (\d+)>',lambda m:f'<Picture {int(m[1])+1}>',s)
        definitions='<Picture 1> is the actual preceding last frame, not another actor.\n'+shift(definitions)
        lines=[shift(line) for line in lines]
    used=list(dict.fromkeys(re.findall(r'<Subject \d+>',definitions+' '+ ' '.join(lines))))
    visual_retention=[label+': fully_preserved - preserve the assigned reference role wherever this subject is visible; current mutable appearance follows the shot state.' for label in used]
    if chain and seg['index']>0:
        visual_retention.insert(0,'<Picture 1> ([Shot 1] first frame): fully_preserved - use the actual preceding last frame as the boundary anchor, not a new actor.')
    identity=(' '+FACE_GUIDANCE if face_identity else '')
    task='reference generation + audio reuse'
    if chain and seg['index']>0:task='keyframe completion + reference generation + audio reuse'
    text='\n\n'.join((
        'subject_definitions:\n'+definitions+'\n<Audio 1> is the supplied source-song window.',
        'summary:\n['+task+'] Continue this interval of the continuous film. Current visible state governs mutable appearance.',
        'retention_analysis:\n'+'\n'.join(visual_retention)+('\n' if visual_retention else '')+'<Audio 1>: fully_copy - reuse the supplied recording unchanged. Preserve reference identity; current state defines appearance.'+identity,
        'detailed_description:\n'+'\n'.join(lines),
        'overall_soundscape:\n<Audio 1> unchanged; no generated dialogue or sound layers.',
        'non_diegetic_music:\nThe supplied original song unchanged.'))
    return text,rows


def ensure_film(cfg, req, segments, originals, work, rewrite, progress=None):
    """One creative call, bounded delivery retries, then deterministic slicing."""
    folder=Path(work)/'preproduction';folder.mkdir(exist_ok=True)
    duration_ms=round((segments[-1]['start']+segments[-1]['seconds'])*1000)
    path=folder/'whole_film.json'
    saved=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None
    # A saved v1/v2 master must keep its original fingerprint and finale rules.
    # Only fresh v3 masters use the source-duration finale policy.
    saved_version=saved.get('version',1) if saved is not None else 3
    modern=saved_version>=2
    source={'brief':req.get('prompt',''),'duration_ms':duration_ms,
            'adaptation':adaptation_direction(req),
            'srt_cues':req.get('srt_cues',[]),'lyrics':req.get('lyrics',''),
            'music_evidence':[{'source_start':s['start'],'source_end':s['start']+s['seconds'],
                               'evidence':s.get('audio_evidence',{})} for s in segments],
            'ending':(continuous_film_ending_contract(req,duration_ms/1000)
                      if saved_version>=3 else ending_contract(req,duration_ms/1000,segments))}
    if saved_version>=3:
        source['ending_policy_version']=2
    if modern:
        from banana_mv.core import map_image_mentions
        source.update(photography_contract=2,
            reference_brief=map_image_mentions(req.get('prompt',''),len(originals)),
            direction=direction_context(req,len(originals)),
            render_windows=[{'index':s['index'],'start':s['start'],'seconds':s['seconds']} for s in segments])
    fingerprint=digest(source)
    from banana_mv.reference_bindings import reference_manifest, bind_definitions
    references=reference_manifest(req.get('prompt',''),len(originals))
    source['reference_manifest']=references
    if path.is_file():
        film=parse_film(json.dumps(saved['film']),duration_ms)
        if saved['input_sha256']!=fingerprint:raise ValueError('完整攝影稿與目前素材設定不符。')
    else:
        writer_cfg=copy.deepcopy(cfg)
        writer_cfg.setdefault('rewriter',{})['max_length']=max(16384,int(cfg.get('rewriter',{}).get('max_length',8192)))
        system=SYSTEM+'\n'+photography_system(cfg)+'\n'+direction_system(source)+'\n'+OPTIONAL_TIMING_POLICY
        atomic_json(folder/'reference_manifest.json',references)
        writer_source={k:v for k,v in source.items() if k!='render_windows'}
        atomic_json(folder/'whole_film_input.json',{'version':2,'input_sha256':fingerprint,
            'source':writer_source,'render_windows':source.get('render_windows',[])})
        from banana_mv.local_guide import guide_record
        atomic_json(folder/'whole_film_guide.json',guide_record(cfg.get('guides',{}).get('ref','')))
        (folder/'whole_film_commission.txt').write_text(system,encoding='utf-8')
        parts=[('text',json.dumps(writer_source,ensure_ascii=False))]+_pictures(originals)
        # Saved raw deliveries belong to this immutable job. Recover a complete
        # response before paying for another creative call; never close truncated JSON.
        film=None;recovery=[]
        for candidate in sorted(folder.glob('whole_film_raw_*.txt'),key=lambda p:p.stat().st_mtime):
            try:
                film=parse_film(candidate.read_text(encoding='utf-8'),duration_ms)
                recovery.append({'raw_file':candidate.name,'accepted':True})
                break
            except (ValueError,TypeError,OSError) as exc:
                recovery.append({'raw_file':candidate.name,'accepted':False,'error':str(exc)})
        if recovery:
            atomic_json(folder/'whole_film_recovery.json',{'input_sha256':fingerprint,'attempts':recovery})
        for attempt in range(0 if film is not None else rewrite_retry_count(req)+1):
            if progress:progress({'stage':'author','attempt':attempt+1})
            started=time.monotonic()
            request_id=uuid.uuid4().hex[:8]
            raw=rewrite(writer_cfg,system,parts,request_id)
            try:
                from banana_mv.services import DATA as service_data
                trace_path=service_data/'rewriter_runs'/(request_id+'.json')
                actual_seed=json.loads(trace_path.read_text(encoding='utf-8')).get('seed') if trace_path.is_file() else None
            except (ValueError,OSError):
                actual_seed=None
            atomic_json(folder/'whole_film_generation.json', {'attempt':attempt+1,
                'actual_textgenerate_seed':actual_seed,
                'rewrite_request_id':request_id,
                'rewriter_parameters':{k:writer_cfg['rewriter'].get(k) for k in
                    ('model','thinking','mtp','max_length','temperature','top_p','top_k')},
                'elapsed_seconds':round(time.monotonic()-started,3),
                'output_characters':len(raw),'max_generated_tokens':writer_cfg['rewriter']['max_length'],
                'actual_token_count':None,'note':'TextGenerate returns text; actual token usage is unavailable.'})
            (folder/f'whole_film_raw_{uuid.uuid4().hex[:8]}.txt').write_text(raw,encoding='utf-8')
            try:film=parse_film(raw,duration_ms);break
            except (ValueError,TypeError) as exc:
                if attempt==rewrite_retry_count(req):raise
                parts=[('text',json.dumps(writer_source,ensure_ascii=False)+'\nPrevious delivery was unreadable: '+str(exc)+'. Return the complete continuous timeline JSON.')]+_pictures(originals)
        atomic_json(path,{'version':saved_version,'input_sha256':fingerprint,'film':film,
                          'quality_status':'not_visually_verified'})
    # Master review sees the whole song BEFORE any deterministic slicing.
    from banana_mv.whole_film_review import review_film
    from banana_mv.review_output import content_hash
    review_path=Path(work)/'screenplay_review.json'
    prior_review={}
    if review_path.is_file():
        try:prior_review=json.loads(review_path.read_text(encoding='utf-8'))
        except (ValueError,OSError):pass
    if (prior_review.get('version')==4 and prior_review.get('scope')=='whole_film'
            and prior_review.get('output_hash')==content_hash(film)
            and (prior_review.get('status')!='disabled' or not req.get('screenplay_review',True))):
        audit=prior_review
    else:
        before=copy.deepcopy(film)
        film,audit=review_film(cfg,req,source,film,rewrite,originals,work,parse_film,progress=progress)
        if film!=before:
            atomic_json(folder/('whole_film_before_review_'+uuid.uuid4().hex[:8]+'.json'),before)
            atomic_json(path,{'version':saved_version,'input_sha256':fingerprint,'film':film,
                             'quality_status':audit['status']})
    warnings=delivery_warnings(cfg,film,modern)
    if modern:
        _,binding_warnings=bind_definitions(film['subject_definitions'],references)
        warnings.extend(binding_warnings)
    for warning in warnings:
        if warning not in audit['warnings']:audit['warnings'].append(warning)
    if warnings and audit['status']=='passed':audit['status']='warnings'
    atomic_json(review_path,audit)
    if progress:progress({'stage':'compile','done':0,'total':len(segments)})
    # Preserve the complete native shooting prompt before exporting any window.
    # This is an audit artifact, not a long-duration H3 render request.
    if modern:
        full_prompt,_=compile_window(film,{'index':0,'start':0,'seconds':duration_ms/1000},
                                    face_identity=req.get('face_identity',True),reference_manifest=references)
        (folder/'whole_film_prompt.txt').write_text(full_prompt,encoding='utf-8')
    rows=[]
    from banana_mv.shoot_plan import validate_native_mv_format
    from banana_mv.core import normalize_mv_prompt
    for seg in segments:
        text,local=compile_window(film,seg,chain=req.get('mode')=='chain',face_identity=modern and req.get('face_identity',True),reference_manifest=references if modern else None)
        old_prompt=folder/f'{seg["index"]:02d}_prompt.txt'
        if not modern and old_prompt.is_file():text=old_prompt.read_text(encoding='utf-8')
        text=normalize_mv_prompt(text,len(originals)+int(req.get('mode')=='chain' and seg['index']>0))
        validate_native_mv_format(text,seg['seconds'],require_native=True)
        (folder/f'{seg["index"]:02d}_prompt.txt').write_text(text,encoding='utf-8')
        if progress:progress({'stage':'compile','done':seg['index']+1,'total':len(segments)})
        from banana_mv.director import MODES
        modes=[r['mode'] for r in local if r['mode'] in MODES]
        mode='action' if 'action' in modes else (modes[0] if modes else 'story')
        rows.append({'index':seg['index'],'mode':mode,'handoff_version':1,
                     'event':'\n'.join(r['state']+' '+r['action'] for r in local)})
    plan={'version':5,'shared_setup':film['subject_definitions'],'segments':rows,
          'ending_contract':source['ending'],'whole_film_version':1,'visual_verified':False,
          'quality_status':audit['status'],'quality_warnings':audit.get('warnings',[])}
    atomic_json(Path(work)/'director_plan.json',plan)
    atomic_json(folder/'whole_film_windows.json',{'version':6,'clip_count':len(segments),'whole_film_version':1})
    return plan
