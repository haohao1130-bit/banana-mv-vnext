"""Music-led MV commissions and the 5aa82c3 director layer.

Source: banana-mv-public/banana_mv/shoot_plan.py at 5aa82c3.
One whole-song allocation, then isolated native photography. No chapter JSON
camera authoring and no forced beat-to-beat physical-action handoff.
"""
import json
import copy
from pathlib import Path
from banana_mv.scene_state import atomic_json

CREATIVE_DIRECTION = """ADAPTATION: FREE. Act as an inventive MV director, not a literal script formatter.
Proactively develop striking visual events, performance business, interactions,
reaction details and environmental changes that serve the supplied story spine.
Make these choices even when the user supplies no camera or montage instructions.
Treat descriptive staging and camera suggestions as material to reinterpret, unless
explicitly mandatory. Preserve reference identities, vocal roles, fixed geography,
required causal milestones, specified outcome and explicit hard constraints.
Choose genre-appropriate camera positions, perspective, movement and editorial
juxtapositions. Use performance, inserts, reactions and environment as meaningful
coverage; create rhythmic, parallel, contrast or action-matched montage where useful.
Set intensity from the selected level and actual music/story passage. Precision means
committing to executable choices, including bold ones, while keeping cause and effect
readable. Develop the current beat without borrowing later milestones or replaying it.
"""

FAITHFUL_DIRECTION = """ADAPTATION: FAITHFUL. Preserve the supplied events, action meanings, causal
links, participants, props, order and specified camera requests. Translate them into
concrete expressive photography and editing without adding new story events.
"""

REFERENCE_PERFORMANCE = """IDENTITY AND PERFORMANCE: For a referenced actor, preserve the assigned
reference identity and current appearance. References are identity anchors, not a
closed cast list. When the user requests supporting roles without reference images,
create original distinct characters as authorized; missing reference images do NOT
mean those characters cannot exist. Never turn the singer, boxer or another referenced
actor into a requested guitarist, bassist, drummer or other original supporting role.
Only an explicit user restriction forbids additional cast. Preserve original supporting
characters using their fixed name/role, appearance, costume, instrument and stage position;
do not demand an uploaded image, borrow an existing actor's face, or invent <Picture N>.
Use independent <Subject N> definitions with descriptions, without a false picture binding.
In both FREE and FAITHFUL adaptation, interpret broad wording
such as 'keep/maintain the reference image unchanged', 'match the reference completely'
or 'preserve appearance' as identity and appearance continuity, not a performance lock.
A pictured blink, closed eyes, neutral face, gaze or resting pose is a momentary state;
direct eyes opening, expressions changing and the body performing as the event requires.
Only an explicit instruction to sustain a particular expression, eye state, gaze or
pose makes that state a performance constraint for its stated scope.
A reference expression sheet demonstrates the same identity
in different states; it is not an acting menu or a limit on emotional range.
Direct facial expression, gaze, jaw tension, head/neck movement and body response as
changing performances driven by the current event, vocal-role timing and musical
context, at the selected intensity. Show a concrete emotional progression rather
than holding a reference expression throughout. In an angry vocal peak, give anger
visible physical expression; in other passages, choose the performance they require.
Keep subject_definitions focused on stable identity and describe evolving performance
inside the shots. In retention_analysis, preserve identity without claiming the pictured
expression or pose must stay unchanged. Explicit user performance requirements prevail.
An actual first/last-frame anchor constrains that boundary frame, not the entire clip.
Keep lip movement compatible with the supplied audio; add no new vocal material.
"""

AUTO_FILMING = """Direct the visual sequence first: decide what the viewer sees, how attention moves
between performance, action details, reactions and environment, and how those images
connect. Invent the coverage yourself from the current beat and adaptation policy;
the user need not supply a shot list. Select coverage before framing a visible singer
for readable lip sync. A whole event need not remain on the singer's face.
Then complete a concrete shooting decision for EVERY Shot before writing the final
prompt. Treat the following as required decision slots; choose their values freely
from the assigned events, references, genre and musical context:
1. TIME AND CONTINUITY: allocate the shot's local start and end within the clip.
Carry the preceding action state, positions, held objects and consequences forward,
including time off-screen. Budget readable actions and reactions across the full
interval; a technical clip boundary never calls for a pose hold or action stop.
2. SUBJECT AND ACTION: identify the visible subject and reference identity, the
attention or gesture target, the visible action progression and its end state.
3. CAMERA AND PERSPECTIVE: choose the camera's location relative to the subject,
height, viewing angle, shot size and perspective. Express lens effects concretely
when useful, such as spatial depth or compression; numerical focal lengths are optional.
4. COMPOSITION AND SPACE: place the subject in the frame with a clear scale; specify
foreground and background relationships, depth, gaze or movement direction and focus.
Describe the visible environment where an empty scene itself is the subject.
5. CAMERA MOVEMENT: choose a static camera or a specific movement. For movement,
state its direction, target, extent and speed; coordinate it with the visible action.
6. LIGHTING: choose scene-consistent light direction and quality, contrast and the
illuminated visual focus, at the selected photographic intensity.
Resolve every slot as an executable choice. A shot description states what is visible
and how it changes, rather than merely naming a cinematic technique.
Write these decisions naturally inside each Shot of detailed_description, using the
native guide's Shot labels and local cut times. The first shot begins at zero without
a timestamp; each later shot starts at its cut time, and the last ends at clip duration.
Keep the decision worksheet internal; deliver the existing native sections only.
Give adjacent shots independently chosen viewpoints and compositions serving their
attention shifts. Connect them through the same ongoing event and spatial relationships.
Develop compatible staging and performance freely within the assigned story;
primary_mode guides the passage without prescribing every shot's method.
"""

DYNAMIC_EDITING = """Dynamic editing is enabled: actively design editorial coverage, not just camera
movement. Separate changes of storyline from changes of viewpoint within a scene.
For an energetic passage with several distinct action or performance accents, use
purposeful short-shot coverage within that scene as well as intercuts. A scene visit
is not automatically one shot. Give each actual cut its own numbered Shot and local
cut time in detailed_description, with a distinct composition and continuing action.
Select viewpoints that reveal a meaningful subject, spatial relationship, action
turn, reaction, performance detail or visual accent; do not merely rename the same
framing. A push-in, pan or subject moving closer remains one shot, not an editorial cut.
Choose flexible lengths with no minimum duration or fixed shot quota. Keep contact,
response and vocal phrases readable across cuts. Specify the outgoing action state
and the next view's new visual focus so a cut advances the same ongoing event.
Honor explicit continuous-take requests and the assigned ending. Design each other
shot length from its visual function, rather than defaulting to sustained coverage.
"""

MV_SCOPE = """MUSIC-VIDEO DIRECTING, NOT A CONTINUOUS ACTION-FILM SIMULATOR.
The local commission defines this interval's events, current conditions and assigned
outcome. Music motivates full-frame montage among its assigned performance, story,
reaction, insert and environment views. Invent coverage and local cutting freely;
no fixed shot count, cut grid or requirement to finish the previous camera movement.
A reference image identifies its declared actor or location, not an obligatory view.
Each actual view occupies the FULL frame at ONE location. Intercutting means cut
from one full-frame view to the next; never split-screen, dual-panel, side-by-side,
merged sets or borrowing a location reference as another location's crowd design.
SCENE VOCAL PERMISSIONS: read the supplied fixed scene duties literally. An actor's
singer role in one location never permits lip-sync in another location. In a silent
story/action location the original vocals remain soundtrack only, while actors act.
Only film lip-sync in explicitly permitted performance locations. SRT supplies vocal
words/timing, not identity, gender, shot quotas or a physical bell/countdown event.
No new dialogue, lyrics or generated sound layers. overall_soundscape describes
<Audio 1> unchanged; non_diegetic_music identifies that supplied song, never N/A.
Keep invariant identity/scene roles in subject_definitions. Opening state is already
true, not an event to replay. Preserve changed clothing, props and current condition;
do not reenact how they changed. Past/future story is not in this local commission.
Only the assigned milestones/outcome occur here; do not invent an early finale.
Intentional replay or rhythmic motifs are valid when deliberately commissioned.
Deliver only native H3 six-section English prose, retaining names and source lyric
language when necessary. Choose shots that show observable acting and reactions,
not an explanation of the story. The source pictures never freeze a pose.
"""


def adaptation(req):
    return CREATIVE_DIRECTION if req.get('story_plan',True) else FAITHFUL_DIRECTION


def allocation_system(base):
    # Keep the proven local-commission format; restore MV editorial freedom.
    base=base.replace('Keep both parallel strands in each\nnormal-length interval when requested; each strand advances in its own fixed space.',
        'Preserve requested parallel strands as meaningful recurring material across the whole MV. Choose unequal, irregular intercuts naturally; no per-clip scene quota.')
    return base+"\nMUSIC-LED MV: allocate concise local commissions, not a shot-by-shot JSON film. Music carries editing; key user events and the ending remain binding. Recurring performance and motivated montage are welcome. Do not turn lyrics into literal story events. Do not force a complete beginning/climax/ending per interval. SETUP is invariant identity and scene-specific vocal permission only; keep past/future outcomes out of it."


def author(cfg, req, segments, originals, folder, rewrite, progress=None):
    from banana_mv.shoot_plan import ensure_shoot_plan
    folder=Path(folder);allocation=folder/'mv_allocation';allocation.mkdir(exist_ok=True)
    config=copy.deepcopy(cfg)
    config.setdefault('rewriter',{})['max_length']=min(8192,max(4096,int(cfg.get('rewriter',{}).get('max_length',8192))))
    if progress:progress({'stage':'author','substage':'mv_allocation','attempt':1})
    plan=ensure_shoot_plan(config,dict(req,screenplay_review=False),segments,originals,allocation,rewrite)
    beats=[];chapters=[]
    for seg,row in zip(segments,plan['segments']):
        at=round(seg['start']*1000);end=round((seg['start']+seg['seconds'])*1000)
        # Compatibility storage only. This is a clip commission, NOT a locked
        # physical shot. The native director chooses its shots and cut times.
        beats.append({'at_ms':at,'shot_id':f'mv_commission_{seg["index"]}',
            'state':'Use the current opening facts stated in this interval commission.',
            'continuation_state':'Sustain the achieved local condition without replaying its cause.',
            'camera':'The local MV director chooses coverage from music and events.',
            'ongoing_camera':'Choose a motivated return or continuation of this local commission.',
            'action':row['event'],'ongoing':'Continue this interval from its achieved current state.',
            'filming_prompt':row['event'],'ongoing_filming_prompt':row['event'],
            'mode':row['mode'],'beat_kind':'mv_commission'})
        chapters.append({'start_ms':at,'end_ms':end,'goal':row['event'],
                         'entry':'Local commission opening facts.','exit_target':'Local commission outgoing state.'})
    film={'subject_definitions':plan['shared_setup'],'beats':beats,
          'authoring_chapters':chapters,'authoring_mode':'classic_mv',
          'duration_ms':round((segments[-1]['start']+segments[-1]['seconds'])*1000),
          'ending_contract':plan['ending_contract'],
          'macro_creative_contract':'Music-led MV; each local commission is isolated from other intervals.'}
    atomic_json(folder/'whole_film_generation.json',{'mode':'classic_mv','allocation_calls_expected':1,
        'camera_calls_expected':len(segments),'note':'Format retries, when needed, are recorded separately.'})
    return film


def ending(req, segments):
    from banana_mv.mv_scope import continuous_film_ending_contract, SHORT_ENDING_TAIL_SECONDS
    total=segments[-1]['start']+segments[-1]['seconds']
    contract=continuous_film_ending_contract(req,total)
    tail=segments[-1]['seconds'];nominal=max(s['seconds'] for s in segments)
    if contract['finish_work'] and len(segments)>1 and tail<nominal and tail<=SHORT_ENDING_TAIL_SECONDS:
        contract.update(short_tail_seconds=tail,settle_by=total-tail)
        contract['instruction']+=' The final residual interval is at most three seconds: sustain the achieved ending there without replay or a new finale; put its decisive event in the preceding full interval. Explicit commissioned event timing remains authoritative.'
    return contract


def interval_ending(contract, seg):
    end=seg['start']+seg['seconds'];total=contract.get('end_time',end)
    tail=contract.get('short_tail_seconds',0)
    if not contract.get('finish_work'):return contract
    if tail and seg['start']>=total-tail-0.001:
        return {'phase':'terminal_hold','instruction':'This tiny residual interval sustains the achieved current ending. Use performance, reactions or present conditions; never replay the decisive event.'}
    if end>=total-tail-0.001:
        return {'phase':'resolving','instruction':'Complete only the locally commissioned outcome at its assigned musical timing. A tiny later tail, if present, sustains this result; no invented closing pose is required.'}
    return {'phase':'continuing','instruction':'Continue this local MV commission. A technical boundary does not end the story or require a closing pose.'}
