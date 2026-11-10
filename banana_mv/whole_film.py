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
Apply the compact H3 director guide and supplied reference labels.
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


COMPACT_H3_DIRECTOR_GUIDE = """H3 / Ref2VA compact director notes:
Build one filmable current view per beat: subject positions, motivated camera
angle and movement, lighting, ordered visible action and reaction. Use source
<Picture N> to bind referenced <Subject N>; keep scene/vocal duties separate.
Carry present state forward without replaying entrances, impacts or outcomes.
Use a shot_id change only for an actual editorial cut. No Shot enumeration,
six-section essay, retention_analysis, summary or detailed_description JSON.
Only the compiler writes the native six-section render prompt.
"""

def photography_system(cfg):
    # Never inject the 24KB human guide into 9B's structured-film author call.
    # Keep tiny custom guide notes for existing installations and fixtures.
    guide_path=cfg.get('guides',{}).get('ref')
    guide=Path(guide_path).read_text(encoding='utf-8') if guide_path and Path(guide_path).is_file() else ''
    # Only the compact reference-label and camera chapters are safe here.
    # A long human manual still gets zero injection into the 9B author.
    if re.search(r'^## \d+\.',guide,re.M):
        chapters=re.split(r'(?=^## \d+\.)',guide,flags=re.M)
        guide='\n'.join(c for c in chapters if re.match(r'^## (?:2|5)\.',c))
    tiny_note=('\nInstallation note: '+guide) if 0<len(guide)<=1024 else ''
    return COMPACT_H3_DIRECTOR_GUIDE+tiny_note+'\n'+PHOTOGRAPHY+'''
FINAL DELIVERY CONTRACT: Return only a JSON object with subject_definitions
and beats. Every timed view belongs in beats. Never enumerate Shot appearances
inside subject definitions. Do not return a six-section essay.
'''

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


def _json_object(raw):
    """Decode one complete JSON object, with optional markdown fences or preface."""
    text=_text(raw).strip()
    fenced=re.search(r'^\s*```(?:json)?\s*([\s\S]*?)\s*```\s*$',text,re.I)
    if fenced:text=fenced.group(1).strip()
    if not text.startswith('{'):
        offset=text.find('{')
        if offset<0:raise ValueError('模型未交付 JSON 物件。')
        text=text[offset:]
    data,_=json.JSONDecoder().raw_decode(text)
    if not isinstance(data,dict):raise ValueError('全曲攝影稿需為 JSON 物件。')
    return data

def parse_film(raw, duration_ms):
    data=_json_object(raw)
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
    bound,_=bind_definitions(_chapter_stable_cast(film['subject_definitions']),reference_manifest or [])
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



from banana_mv.creative_contract import creative_contract, CONTRACT_POLICY

SPINE_SYSTEM = """Plan one COMPLETE music video before filming prompts are expanded.
You have the whole source duration, the user's brief and reference image roles.
Return ONLY JSON with: subject_definitions (stable identities and scene/vocal
duties ONLY: no future victory, finale action, initial wardrobe reset or story spoilers), creative_contract (100–150 words), and chapters (ordered, contiguous macro chapters).
The creative_contract names active strands, their scene-specific identities/vocal duties,
commissioned intercutting, core causality and outcome. No split-screen or dual-panel:
intercut different locations with independent timed shot_id values. Do not invent
parallel strands when absent from the commission.
Use identity for reference appearance/wardrobe, and scene_duties for fixed permissions
by location (who sings, who acts, who is silent). Preserve supplied picture bindings.
These fields describe WHO and WHERE, never WHAT happens later. Keep all future
milestones, winning actions and conclusions in chapter goals/creative_contract.
Identity tables retain full identity, reference mapping and scene-specific duties.
Put outcomes and timed plot goals in chapters/creative_contract, NEVER in cast duties.
Each actual view depicts ONE physical location. Plan intercutting as successive
views, not a paired-location paragraph or a split-screen.
Every chapter needs integer start_ms, end_ms, goal, entry, exit_target.
First start_ms is 0, last end_ms equals duration_ms. The supplied
chapter_boundary_options_ms are the EXACT allowed start/end timestamps.
Choose only those boundaries: normally one requested segment_seconds window
(e.g. 15000 ms), or group adjacent whole windows for a Verse/Chorus act.
NEVER invent 3600 ms micro-chapters. These are UPSTREAM AUTHORING CHAPTERS,
not camera cuts: filming beats still follow events and music freely.
Allocate EVERY user-specified timed event,
its cause, consequence and finale. Lyric timing is vocal reference only unless
the user explicitly links a plot milestone to that lyric; do not schedule one
event per cue or infer a physical bell/countdown from sung words.
Keep the user's ending; do not invent a mandatory hero hold. No six-section
H3 essay, no [Shot N] enumeration, no detailed_description or retention_analysis.
"""

CHAPTER_SYSTEM = """Expand ONE chapter of an already locked whole-song macro spine.
Return ONLY JSON with beats (GLOBAL at_ms) and exit_state (complete state at
this chapter's end, organized by scene with current wardrobe, props, physical
condition and ongoing momentum only; no completed action recap or future event). First beat at_ms MUST equal chapter.start_ms; all later
beats are strictly increasing and less than chapter.end_ms. Every beat includes
shot_id, state, continuation_state, camera, ongoing_camera, action, ongoing,
mode, filming_prompt and ongoing_filming_prompt, all as nonempty strings.
exit_state is a JSON object with scene_states: {scene name: {position, pose,
physical_condition, wardrobe, props, character_states: {character id: {position,
pose, physical_condition, wardrobe, props}}, established_facts: [current result facts]}}.
Describe present conditions and achieved results, not how they happened.
For example a character IS down, a bell HAS rung, a contest IS over; retain these
results when established. Do not erase a result just because its cause is a past action.
Do not invent result facts or force a contest schema on other stories.
Do not put punches, impacts, entrances, clothing changes, completed actions or
future goals in exit_state; those are events in beats. Use a held defensive pose
at the corner, not a sentence describing a punch landing.
ongoing is present-tense movement PROSE, never a JSON true or false.
event_progress.history lists events already authored, not an instruction to film them again.
Understand their causes and effects, then write only this chapter's assigned events.
next_chapter_context is read-only planning, never an instruction to stage it early.
Intentional replay, flashback, repeated performance and rhythmic visual motifs are allowed:
make their editorial intent explicit and preserve the present story state on returning.
Accidental chronology reset is the problem, not repetition itself.
Write ONLY this chapter's current events; future lyrics, finale and climax
belong to later chapters. exit_state is the state at THIS boundary, not song end.
Each beat must describe exactly ONE physical camera view at ONE location.
Select one location (for example concert OR ring, never both).
NEVER write '擂台: ...; 演唱會: ...' in the same filming_prompt.
Cross-cutting between locations advances to the NEXT beat with a different shot_id.
Each beat is ONE view at ONE physical location. A stage view and a ring view
are successive separate beats with distinct shot_id and global at_ms. Never put
both places into one state/camera/filming_prompt, even separated by semicolons.
Changing framing from wide to close-up is a new shot unless the camera actually
moves continuously between them. Only an actual continuous view shares shot_id. Write detailed
native H3 filming prose in the two filming_prompt fields, not a Shot list.
previous_last_beat contains only ongoing state/camera, not a past action to reenact.
previous_exit_state stores each scene's current conditions. It does not force this
chapter to stay in the last scene. Return freely to another strand's achieved state.
The opening state inherits previous_exit_state; do not reset action, wardrobe,
position, injury, props, or scene roles. Continue the preceding shot_id if the
same shot continues. Never replay an already completed impact or entrance.
A beat's at_ms is whole-song time, not seconds local to this chapter.
Only events assigned to this chapter occur here. Later chapter goals remain
future events. The final chapter follows the user's actual final cue and song
duration without an invented fixed hold or premature ending.
"""

SPINE_SYSTEM += "\n"+CONTRACT_POLICY+"\n"+OPTIONAL_TIMING_POLICY
CHAPTER_SYSTEM += "\n"+CONTRACT_POLICY+"\n"+OPTIONAL_TIMING_POLICY

def _chapter_boundaries(segments, duration_ms):
    """Actual requested render-window edges are permissible AUTHORING borders."""
    edges={0,duration_ms}
    for seg in segments:
        at=round(seg['start']*1000)
        if 0<at<duration_ms:
            edges.add(at)
    return sorted(edges)


def _validated_spine(data, duration_ms, chapter_boundaries_ms=None):
    definitions=definition_text(data.get('subject_definitions'))
    chapters=data.get('chapters')
    # Accept a coherent but over-fragmented macro plan and COALESCE it; do not
    # send 9B to a dozen 3.6-second calls just because it suggested tiny acts.
    if (not isinstance(chapters,list) or len(chapters)<2 or
            len(chapters)>max(2,min(256,duration_ms//1000+1))):
        raise ValueError('全曲骨架需為合理數量的連續創作章節。')
    at=0
    for chapter in chapters:
        if not isinstance(chapter,dict) or type(chapter.get('start_ms')) is not int or type(chapter.get('end_ms')) is not int:
            raise ValueError('創作章節需包含整數全局時間。')
        if chapter['start_ms']!=at or not at<chapter['end_ms']<=duration_ms:
            raise ValueError('全曲骨架時間重疊或缺段。')
        for key in ('goal','entry','exit_target'):
            if not isinstance(chapter.get(key),str) or not chapter[key].strip():
                raise ValueError('創作章節缺少事件或接力目標：'+key)
        at=chapter['end_ms']
    if at!=duration_ms:raise ValueError('全曲骨架未涵蓋歌曲尾端。')

    if chapter_boundaries_ms is not None:
        edges=sorted(set(chapter_boundaries_ms))
        if not edges or edges[0]!=0 or edges[-1]!=duration_ms:
            raise ValueError('創作章節對齊點未涵蓋歌曲全長。')
        allowed=set(edges)
        if any(c['start_ms'] not in allowed or c['end_ms'] not in allowed for c in chapters):
            # Snap the WHOLE writing plan, not individual scene beats. Preserve
            # every overlapping act goal in order so small narrative events do
            # not disappear during the coalescing of micro-chapters.
            aligned=[]
            for start,end in zip(edges,edges[1:]):
                active=[c for c in chapters
                        if c['start_ms']<end and c['end_ms']>start]
                if not active:
                    raise ValueError('創作章節對齊後缺少故事內容。')
                goals=list(dict.fromkeys(c['goal'] for c in active))
                aligned.append({'start_ms':start,'end_ms':end,
                                'goal':' -> '.join(goals),
                                'entry':active[0]['entry'],
                                'exit_target':active[-1]['exit_target']})
            chapters=aligned
    return {'subject_definitions':definitions,'chapters':chapters,
            'creative_contract':data.get('creative_contract','')}


def _chapter_stable_cast(definitions, *, final=False):
    """Preserve identity/role data; exclude explicit plot-goal fields, not cast fields."""
    try:
        entries=json.loads(definitions) if isinstance(definitions,str) else definitions
    except (ValueError,TypeError):
        return definitions
    if not isinstance(entries,(list,dict)):return definitions
    plot_keys={'goal','goals','ending','outcome','future_events','climax','exit_target',
               'plot','story_arc','final_action'}
    def clean(value):
        if isinstance(value,list):return [clean(row) for row in value]
        if not isinstance(value,dict):return value
        result={k:clean(v) for k,v in value.items() if k not in plot_keys}
        return result
    return json.dumps(clean(entries),ensure_ascii=False)


def _present_exit_state(value):
    """Project typed present-state fields; never forward a free-form event recap.

    Unknown legacy prose is omitted, without rejecting an otherwise usable chapter.
    The ongoing handoff remains available when legacy output has no typed snapshot.
    """
    if not isinstance(value,dict):return {}
    fields={'position','location','pose','physical_condition','condition','wardrobe','props','established_facts'}
    result={k:v for k,v in value.items() if k in fields}
    actors=value.get('character_states')
    if isinstance(actors,dict):
        result['character_states']={name:_present_exit_state(state) for name,state in actors.items()
                                    if isinstance(state,dict)}
    scenes=value.get('scene_states')
    if isinstance(scenes,dict):
        result['scene_states']={name:_present_exit_state(state) for name,state in scenes.items()
                                if isinstance(state,dict)}
    return result


def event_progress(beats):
    """Compact authored history, not previous prompts or a forbidden-event list."""
    return [{'event_id':f"event_{b['at_ms']}",'at_ms':b['at_ms'],
             'event':b['action'],'status':'already_authored'} for b in beats]


def _ongoing_handoff(beat):
    """No completed action or original initiating camera move crosses chapters."""
    return {'shot_id':beat['shot_id'],'state':beat['continuation_state'],
            'camera':beat['ongoing_camera'],'ongoing':beat['ongoing'],
            'filming_prompt':beat.get('ongoing_filming_prompt','')}


def _chapter_source(source, spine, chapter, *, final=False):
    """Never send global lyric/SRT, the full brief or future acts to a chapter."""
    start,end=chapter['start_ms']/1000,chapter['end_ms']/1000
    cues=[]
    for cue in source.get('srt_cues',[]):
        if not isinstance(cue,dict):
            continue
        try:
            a,b=float(cue['start']),float(cue['end'])
        except (KeyError,ValueError,TypeError):
            continue
        if a<end and b>start:
            cues.append(dict(cue,start=max(a,start),end=min(b,end)))
    evidence=[]
    for row in source.get('music_evidence',[]):
        if not isinstance(row,dict):
            continue
        try:
            a,b=float(row['source_start']),float(row['source_end'])
        except (KeyError,ValueError,TypeError):
            continue
        if a<end and b>start:
            evidence.append(row)
    direction=source.get('direction') or {}
    safe_direction={k:direction[k] for k in
        ('selected_style','intensity','scene_recipes','excluded_modes',
         'face_identity','user_role_declarations') if k in direction}
    local={'chapter_start_ms':chapter['start_ms'],
           'chapter_end_ms':chapter['end_ms'],'srt_cues':cues,
           'music_evidence':evidence,
           'subject_definitions':_chapter_stable_cast(spine['subject_definitions'],
                                                     final=final),
           'reference_manifest':source.get('reference_manifest',[]),
           'direction':safe_direction,
           'adaptation':source.get('adaptation','')}
    if 'creative_contract' in source:
        local['creative_contract']={k:v for k,v in source['creative_contract'].items() if k!='explicit_constraints'}
        local['creative_contract']['macro_summary']=spine.get('creative_contract','')
    if final:
        local['ending']=source.get('ending',{})
    return local


def _validated_chapter(data, spine, chapter):
    raw=data.get('beats')
    if not isinstance(raw,list) or not raw:
        raise ValueError('本章缺少 beats，須只重寫本章。')
    start,end=chapter['start_ms'],chapter['end_ms']
    # A beat at end_ms belongs to the NEXT chapter; surplus beats are dropped.
    spill=any(isinstance(b,dict) and type(b.get('at_ms')) is int
              and b['at_ms']>=end for b in raw)
    beats=[dict(b) for b in raw if isinstance(b,dict)
           and type(b.get('at_ms')) is int and start<=b['at_ms']<end]
    beats.sort(key=lambda b:b['at_ms'])
    unique=[]
    for beat in beats:
        if unique and beat['at_ms']==unique[-1]['at_ms']:
            continue
        # Qwen 9B actually returns ongoing: true/false in valid JSON.
        ongoing=beat.get('ongoing')
        if isinstance(ongoing,bool) or not isinstance(ongoing,str) or not ongoing.strip():
            action=beat.get('action')
            beat['ongoing']=action if isinstance(action,str) and action.strip() else 'underway'
        unique.append(beat)
    if not unique:
        # Only genuinely unusable chapters need a bounded single-chapter retry.
        raise ValueError('本章沒有有效的章內鏡頭，須只重寫本章。')
    if unique[0]['at_ms']!=start:
        unique[0]['at_ms']=start
    for beat in unique:
        for key in ('filming_prompt','ongoing_filming_prompt'):
            if not isinstance(beat.get(key),str) or not beat[key].strip():
                raise ValueError('本章缺少完整 H3 拍攝描述：'+key)
    relative=[dict(beat,at_ms=beat['at_ms']-start) for beat in unique]
    parse_film(json.dumps({'subject_definitions':spine['subject_definitions'],
                           'beats':relative},ensure_ascii=False),end-start)
    exit_state=data.get('exit_state')
    if spill:
        # Whole-song hallucinations contaminate the model's exit_state too.
        # Derive the handoff from the latest LOCAL beat and macro chapter goal.
        exit_state={'chapter_end_ms':end,
                    'last_visible_state':unique[-1]['continuation_state'],
                    'chapter_exit_target':chapter['exit_target']}
    if not isinstance(exit_state,(str,list,dict)) or not exit_state:
        raise ValueError('本章沒有結尾狀態，須只重寫本章。')
    return {'beats':unique,'exit_state':exit_state}


def _chained_author(cfg, req, writer_cfg, writer_source, originals, folder,
                    fingerprint, duration_ms, segments, rewrite, progress):
    """Two-level author: one macro spine, incremental chapter calls and checkpoints."""
    retries=rewrite_retry_count(req)
    chapter_edges=_chapter_boundaries(segments,duration_ms)
    spine_path=folder/'whole_film_spine.json'
    spine=None
    if spine_path.is_file():
        try:
            cached=json.loads(spine_path.read_text(encoding='utf-8'))
            if cached.get('input_sha256')==fingerprint:
                spine=_validated_spine(cached['spine'],duration_ms,chapter_edges)
                if spine!=cached['spine']:
                    atomic_json(spine_path,{'input_sha256':fingerprint,'spine':spine})
        except (ValueError,TypeError,KeyError,OSError):
            spine=None
    if spine is None:
        # Macro inference is deliberately smaller than a full-camera-script call.
        macro_cfg=copy.deepcopy(writer_cfg)
        macro_cfg['rewriter']['max_length']=min(3072,max(2048,int(cfg.get('rewriter',{}).get('max_length',8192))))
        error=''
        for attempt in range(retries+1):
            if progress:progress({'stage':'author','substage':'spine','attempt':attempt+1})
            request_id=uuid.uuid4().hex[:8]
            macro_source=dict(writer_source,chapter_boundary_options_ms=chapter_edges)
            prompt=json.dumps(macro_source,ensure_ascii=False)
            if error:prompt+='\nPREVIOUS INVALID SPINE: '+error
            raw=rewrite(macro_cfg,SPINE_SYSTEM,[('text',prompt)]+_pictures(originals),request_id)
            (folder/f'whole_film_spine_raw_{uuid.uuid4().hex[:8]}.txt').write_text(raw,encoding='utf-8')
            try:
                data=_json_object(raw)
                if 'beats' in data:
                    # Compatibility: an existing model/fixture may deliver a
                    # valid full script directly; do not pay for another call.
                    return parse_film(raw,duration_ms)
                spine=_validated_spine(data,duration_ms,chapter_edges)
                atomic_json(spine_path,{'input_sha256':fingerprint,'spine':spine})
                break
            except (ValueError,TypeError,KeyError) as exc:
                error=str(exc)
                if attempt==retries:raise
    assembled=[];previous_exit=None;previous_last=None;receipts=[]
    for index,chapter in enumerate(spine['chapters']):
        checkpoint=folder/f'whole_film_chapter_{index:02d}.json'
        is_final=index==len(spine['chapters'])-1
        local_source=_chapter_source(writer_source,spine,chapter,final=is_final)
        payload={'source':local_source,
                 'spine':{'subject_definitions':local_source['subject_definitions'],
                          'chapters':[chapter]},
                 'chapter_index':index,'chapter':chapter,
                 'previous_exit_state':previous_exit,'previous_last_beat':previous_last,
                 'song_duration_ms':duration_ms,
                 'event_progress':{'history':event_progress(assembled),
                     'instruction':'History is context only, not shots to copy. Continue unfinished momentum. Intentional replay/flashback/motif is allowed when explicitly staged; do not reset story state accidentally.'},
                 'next_chapter_context':spine['chapters'][index+1]['goal'] if not is_final else None}
        chapter_key=digest({'input_sha256':fingerprint,'chapter':chapter,
                            'previous_exit_state':previous_exit,'previous_last_beat':previous_last,
                            'chapter_validator_version':6,'event_history_sha256':digest(event_progress(assembled)),'creative_contract':local_source.get('creative_contract')})
        piece=None
        if checkpoint.is_file():
            try:
                saved=json.loads(checkpoint.read_text(encoding='utf-8'))
                if saved.get('chapter_key')==chapter_key:
                    piece=_validated_chapter(saved['piece'],spine,chapter)
            except (ValueError,TypeError,KeyError,OSError):
                piece=None
        if piece is None:
            error=''
            stage_cfg=copy.deepcopy(writer_cfg)
            stage_cfg['rewriter']['max_length']=min(6144,max(3072,int(cfg.get('rewriter',{}).get('max_length',8192))))
            for attempt in range(retries+1):
                if progress:progress({'stage':'author','substage':'chapter','done':index,
                                       'total':len(spine['chapters']),'attempt':attempt+1})
                started=time.monotonic();request_id=uuid.uuid4().hex[:8]
                prompt=dict(payload)
                if error:prompt['previous_error']=error
                scope=(f'This chapter ONLY covers {chapter["start_ms"]}ms to '
                       f'{chapter["end_ms"]}ms. Do NOT write the ending or climax unless explicitly assigned here by the commission. '
                       'Do NOT use lyrics or events from other chapters.\n'
                       if not is_final else
                       f'This chapter ONLY covers {chapter["start_ms"]}ms to '
                       f'{chapter["end_ms"]}ms. The ending belongs HERE.\n')
                raw=rewrite(stage_cfg,scope+CHAPTER_SYSTEM+'\n'+COMPACT_H3_DIRECTOR_GUIDE,
                            [('text',json.dumps(prompt,ensure_ascii=False))]+_pictures(originals),request_id)
                (folder/f'whole_film_chapter_{index:02d}_raw_{uuid.uuid4().hex[:8]}.txt').write_text(raw,encoding='utf-8')
                try:
                    piece=_validated_chapter(_json_object(raw),spine,chapter)
                    receipts.append({'chapter':index,'request_id':request_id,
                                     'elapsed_seconds':round(time.monotonic()-started,3)})
                    atomic_json(checkpoint,{'chapter_key':chapter_key,'piece':piece})
                    break
                except (ValueError,TypeError,KeyError) as exc:
                    error=str(exc)
                    if attempt==retries:raise
        assembled.extend(piece['beats'])
        previous_exit=_present_exit_state(piece['exit_state'])
        previous_last=_ongoing_handoff(piece['beats'][-1])
        if progress:progress({'stage':'author','substage':'chapter','done':index+1,
                               'total':len(spine['chapters'])})
    film=parse_film(json.dumps({'subject_definitions':spine['subject_definitions'],
                                'beats':assembled},ensure_ascii=False),duration_ms)
    film['authoring_chapters']=spine['chapters']
    film['macro_creative_contract']=spine.get('creative_contract','')
    atomic_json(folder/'whole_film_generation.json',
                {'mode':'chained','chapter_count':len(spine['chapters']),
                 'calls':receipts,'input_sha256':fingerprint})
    return film

def ensure_film(cfg, req, segments, originals, work, rewrite, progress=None):
    """One upstream whole-film authoring job, with chained chapters for long songs."""
    folder=Path(work)/'preproduction';folder.mkdir(exist_ok=True)
    duration_ms=round((segments[-1]['start']+segments[-1]['seconds'])*1000)
    path=folder/'whole_film.json'
    saved=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None
    # A saved v1/v2 master must keep its original fingerprint and finale rules.
    # Only fresh v3 masters use the source-duration finale policy.
    saved_version=saved.get('version',1) if saved is not None else 8
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
    if saved_version>=4:
        source['creative_contract']=creative_contract(req.get('prompt',''))
    if saved_version>=5:source['chapter_handoff_version']=6 if saved_version>=8 else (5 if saved_version>=7 else (4 if saved_version>=6 else 3))
    if saved_version>=8:source['vocal_reference_policy_version']=2
    fingerprint=digest(source)
    from banana_mv.reference_bindings import reference_manifest, bind_definitions
    references=reference_manifest(req.get('prompt',''),len(originals))
    source['reference_manifest']=references
    if saved_version>=4:
        atomic_json(folder/'creative_contract.json',source['creative_contract'])
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
        use_chained=(duration_ms>30000 and req.get('authoring_mode',
            cfg.get('rewriter',{}).get('whole_film_mode','chained'))=='chained')
        actual_commission=(('CHAINED UPSTREAM AUTHORING\nMacro:\n'+SPINE_SYSTEM+
            '\nChapter:\n'+CHAPTER_SYSTEM+'\n'+COMPACT_H3_DIRECTOR_GUIDE)
            if use_chained else system)
        (folder/'whole_film_commission.txt').write_text(actual_commission,encoding='utf-8')
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
        if (film is None and duration_ms>30000 and
                req.get('authoring_mode',cfg.get('rewriter',{}).get('whole_film_mode','chained'))=='chained'):
            film=_chained_author(cfg,req,writer_cfg,writer_source,originals,folder,
                                 fingerprint,duration_ms,segments,rewrite,progress)
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
    if saved_version>=4:
        source['authoring_chapters']=film.get('authoring_chapters',[])
        source['creative_contract']['macro_summary']=film.get('macro_creative_contract','')
        atomic_json(folder/'creative_contract.json',source['creative_contract'])
    # Master review sees the whole song BEFORE any deterministic slicing.
    from banana_mv.whole_film_review import review_film
    from banana_mv.review_output import content_hash
    review_path=Path(work)/'screenplay_review.json'
    prior_review={}
    if review_path.is_file():
        try:prior_review=json.loads(review_path.read_text(encoding='utf-8'))
        except (ValueError,OSError):pass
    if (prior_review.get('version')==(5 if saved_version>=4 else 4) and prior_review.get('scope')=='whole_film'
            and (saved_version<4 or prior_review.get('commission_policy_version')==3)
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
    native_warnings=[]
    from banana_mv.shoot_plan import validate_native_mv_format
    from banana_mv.core import normalize_mv_prompt
    for seg in segments:
        text,local=compile_window(film,seg,chain=req.get('mode')=='chain',face_identity=modern and req.get('face_identity',True),reference_manifest=references if modern else None)
        old_prompt=folder/f'{seg["index"]:02d}_prompt.txt'
        if modern and req.get('native_camera_version')==1:
            # Freeze the whole-song screenplay before asking the OLD native
            # camera director to improve coverage of this one local window.
            # It uses the official H3 guide; no storyline reconstruction.
            from banana_mv.native_photography import enhance_window
            from banana_mv.lyrics_reference import excerpt
            unshifted,_=compile_window(film,seg,chain=False,
                face_identity=req.get('face_identity',True),
                reference_manifest=references)
            camera_seg=dict(seg,local_srt=excerpt(req,seg))
            native,warn=enhance_window(cfg,req,camera_seg,film,originals,
                unshifted,rewrite,folder,references=references,progress=progress)
            if warn:native_warnings.append(warn)
            if req.get('mode')=='chain' and seg['index']>0:
                # No physical keyframe exists at planning time. Author with
                # original image labels, then reserve Picture 1 for the actual
                # previous segment frame during H3 rendering.
                shift=lambda m:f'<Picture {int(m[1])+1}>'
                native=re.sub(r'<Picture (\d+)>',shift,native)
                native='subject_definitions:\n<Picture 1> is the actual preceding last frame, a continuity anchor rather than another actor.\n'+re.sub(
                    r'^\s*subject_definitions\s*:\s*','',native,count=1)
            text=native
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
          'quality_status':audit['status'],'quality_warnings':audit.get('warnings',[])+native_warnings}
    atomic_json(Path(work)/'director_plan.json',plan)
    atomic_json(folder/'whole_film_windows.json',{'version':6,'clip_count':len(segments),'whole_film_version':1})
    return plan

