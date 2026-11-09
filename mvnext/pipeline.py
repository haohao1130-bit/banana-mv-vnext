"""Validate one screenplay, request camera-only decisions, seal H3 delivery."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

FIELDS = ('subject_definitions', 'summary', 'retention_analysis',
          'detailed_description', 'overall_soundscape', 'non_diegetic_music')
CAMERA = {
    'size': ('wide', 'full', 'medium', 'close', 'detail'),
    'angle': ('eye', 'low', 'high', 'side', 'overhead', 'rear'),
    'motion': ('static', 'track', 'push', 'pull', 'pan', 'arc', 'handheld'),
}


class ContractError(ValueError):
    pass


def decode(raw):
    if isinstance(raw, dict):
        return copy.deepcopy(raw)
    if not isinstance(raw, str):
        raise ContractError('Expected JSON object')
    text = re.sub(r'<think>.*?</think>', '', raw, flags=re.S).strip()
    if text.startswith('```json\n') and text.endswith('```'):
        text = text[8:-3].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContractError('Incomplete or invalid JSON; no render queued') from exc
    if not isinstance(value, dict):
        raise ContractError('Expected JSON object')
    return value


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ContractError('Unexpected or missing fields: ' + ', '.join(keys))


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ContractError(f'Expected integer {low}..{high}')


def prose(value):
    if not isinstance(value, str) or not value.strip():
        raise ContractError('Nonempty text required')
    # Model-authored text cannot inject protocol blocks or media/voice tags.
    if any(c in value for c in ('<', '>', '[', ']', '\n', '\r')) or re.search(r'\(S\d+\)', value):
        raise ContractError('Narrative text contains reserved protocol syntax')


def validate_script(raw, song_frames, pictures):
    """Song frames are authoritative; never pad, retime or invent an event."""
    integer(song_frames, 1, 24 * 300)
    if not isinstance(pictures, list) or not 1 <= len(pictures) <= 9:
        raise ContractError('Supply 1..9 ordered reference paths')
    script = decode(raw)
    exact(script, ('title', 'subjects', 'clips'))
    prose(script['title'])
    if not isinstance(script['subjects'], list) or not script['subjects']:
        raise ContractError('Subjects required')
    ids, voices = set(), set()
    for subject in script['subjects']:
        exact(subject, ('id', 'name', 'picture', 'appearance', 'voice'))
        sid = subject['id']
        integer(sid, 1, 99)
        integer(subject['picture'], 1, len(pictures))
        if sid in ids:
            raise ContractError('Duplicate subject')
        ids.add(sid)
        prose(subject['name']); prose(subject['appearance'])
        voice = subject['voice']
        if voice is not None:
            integer(voice, 1, 99)
            if voice in voices:
                raise ContractError('Duplicate source vocal identity')
            voices.add(voice)
    clips = script['clips']
    if not isinstance(clips, list) or not 1 <= len(clips) <= 60:
        raise ContractError('Supply 1..60 clips')
    cursor, events = 0, set()
    for index, clip in enumerate(clips):
        exact(clip, ('index', 'start_frame', 'frames', 'opening', 'outgoing', 'beats'))
        integer(clip['index'], index, index)
        integer(clip['start_frame'], cursor, cursor)
        integer(clip['frames'], 1, 345)  # largest native 5+17k grid <=15s
        if index < len(clips)-1 and clip['frames'] < 124:
            raise ContractError('Only final source window may be shorter than 124 frames')
        prose(clip['opening']); prose(clip['outgoing'])
        if not isinstance(clip['beats'], list) or not clip['beats']:
            raise ContractError('Each clip needs events')
        previous = -1
        for beat in clip['beats']:
            exact(beat, ('id', 'at_frame', 'action', 'singer'))
            prose(beat['id']); prose(beat['action'])
            if beat['id'] in events:
                raise ContractError('Duplicate event ID')
            events.add(beat['id'])
            integer(beat['at_frame'], previous+1, clip['frames']-1)
            previous = beat['at_frame']
            singer = beat['singer']
            if singer is not None:
                integer(singer, 1, 99)
                if singer not in ids or next(s for s in script['subjects'] if s['id']==singer)['voice'] is None:
                    raise ContractError('Singer must bind to a source vocal identity')
        cursor += clip['frames']
    if cursor != song_frames:
        raise ContractError('Script must cover the complete source song exactly')
    return script


def validate_camera(raw, script):
    camera = decode(raw)
    exact(camera, ('clips',))
    if not isinstance(camera['clips'], list) or len(camera['clips']) != len(script['clips']):
        raise ContractError('Camera must cover all clips')
    for index, (row, clip) in enumerate(zip(camera['clips'], script['clips'])):
        exact(row, ('index', 'shots'))
        integer(row['index'], index, index)
        if not isinstance(row['shots'], list) or not row['shots']:
            raise ContractError('Shots required')
        previous = -1
        for n, shot in enumerate(row['shots']):
            exact(shot, ('at_frame', *CAMERA))
            integer(shot['at_frame'], previous+1, clip['frames']-1)
            if n == 0 and shot['at_frame'] != 0:
                raise ContractError('First shot starts at zero')
            for key, allowed in CAMERA.items():
                if shot[key] not in allowed:
                    raise ContractError('Camera fields accept enums only')
            previous = shot['at_frame']
    return camera


def clock(frame):
    ms = round(frame*1000/24)
    return f'{ms//60000:02d}:{ms//1000%60:02d}.{ms%1000:03d}'


def compile_prompt(script, clip, camera):
    definitions = [f"<Subject {s['id']}>" + (f" (S{s['voice']})" if s['voice'] else '') +
                   f" {s['name']} references <Picture {s['picture']}>; {s['appearance']}"
                   for s in script['subjects']]
    shots = []
    for index, shot in enumerate(camera['shots']):
        start = shot['at_frame']
        end = camera['shots'][index+1]['at_frame'] if index+1<len(camera['shots']) else clip['frames']
        beats = [b for b in clip['beats'] if start <= b['at_frame'] < end]
        actions = []
        for beat in beats:
            cue = f"At local +{clock(beat['at_frame']-start)}: {beat['action']}"
            if beat['singer'] is not None:
                cue += f"; only <Subject {beat['singer']}> lip-syncs to the unchanged source vocal"
            actions.append(cue)
        prefix = f'[Shot {index+1}] ' + (f'At {clock(start)}, ' if index else '')
        shots.append(prefix + ', '.join(f'{k}: {shot[k]}' for k in CAMERA) + '. ' +
                     (' '.join(actions) if actions else 'Continue the current action across this camera cut.'))
    values = ('\n'.join(definitions) + '\n<Audio 1> is the supplied source song.',
              clip['opening'] + ' ' + ' '.join(b['action'] for b in clip['beats']) + ' ' + clip['outgoing'],
              '<Audio 1>: fully_copy — preserve source recording and timing. References preserve identities; current appearance follows the script.',
              '\n'.join(shots), 'Supplied source audio unchanged. No generated dialogue or added sound layers.',
              'The supplied source song; no replacement music.')
    return '\n\n'.join(k+':\n'+v for k,v in zip(FIELDS, values)) + '\n'


def prepare(project, story, song, song_frames, pictures, model):
    """Exactly one writer call and one camera call. No GPU render operations.

    model(role, payload) is injected; production model integration is pending.
    A failed attempt keeps raw responses in a separate attempt directory.
    """
    root = Path(project)
    if root.exists():
        raise ContractError('Use a new project path; existing drafts are preserved')
    if not isinstance(story, str) or not story.strip():
        raise ContractError('Story required')
    song = Path(song)
    pictures = [Path(p) for p in pictures]
    # Validate file access before model use. No media bytes go to the repository.
    assets = {'song': {'sha256': digest(song.read_bytes()), 'frames': song_frames},
              'pictures': [{'slot': i+1, 'sha256': digest(p.read_bytes())} for i,p in enumerate(pictures)]}
    integer(song_frames, 1, 7200)
    if not 1 <= len(pictures) <= 9:
        raise ContractError('Supply 1..9 references')
    root.mkdir(parents=True, exist_ok=False)
    raw = model('screenplay', {'story': story, 'song_frames': song_frames, 'fps':24,
        'picture_count':len(pictures), 'contract':'Complete whole-song screenplay; chronological events; exact source-frame coverage. Schema in README.'})
    (root/'screenplay_raw.json').write_bytes(encoded(raw))
    script = validate_script(raw, song_frames, pictures)
    baseline = encoded(script)
    camera_raw = model('camera', {'script':copy.deepcopy(script), 'allowed':CAMERA,
        'contract':'Camera-only clips/index/shots/at_frame and enums. No narrative fields.'})
    (root/'camera_raw.json').write_bytes(encoded(camera_raw))
    if encoded(script) != baseline:
        raise ContractError('Screenplay changed during camera planning')
    camera = validate_camera(camera_raw, script)
    files = {'screenplay.json':baseline, 'camera.json':encoded(camera), 'assets.json':encoded(assets)}
    for clip, row in zip(script['clips'], camera['clips']):
        files[f"{clip['index']:02d}_prompt.txt"] = compile_prompt(script, clip, row).encode()
    manifest = {'version':1, 'fps':24, 'song_frames':song_frames,
                'clip_count':len(script['clips']), 'files':{n:digest(b) for n,b in files.items()},
                'status':'prepared_not_gpu_validated'}
    for name, data in files.items():
        (root/name).write_bytes(data)
    # Commit readiness last; partial attempts never have a valid ready marker.
    with tempfile.NamedTemporaryFile(dir=root, delete=False) as output:
        output.write(encoded(manifest)); staged=output.name
    os.replace(staged, root/'ready.json')
    return manifest


def inspect(project, song, pictures):
    root = Path(project)
    manifest = json.loads((root/'ready.json').read_text())
    if manifest.get('version') != 1 or not isinstance(manifest.get('files'), dict):
        raise ContractError('Unsupported manifest')
    count=manifest.get('clip_count')
    integer(count, 1, 60)
    expected={'assets.json','screenplay.json','camera.json'} | {f'{i:02d}_prompt.txt' for i in range(count)}
    if set(manifest['files']) != expected:
        raise ContractError('Manifest file inventory mismatch')
    for name, sha in manifest['files'].items():
        if digest((root/name).read_bytes()) != sha:
            raise ContractError('Sealed file changed: '+name)
    assets=json.loads((root/'assets.json').read_text())
    if digest(Path(song).read_bytes()) != assets['song']['sha256']:
        raise ContractError('Source song changed')
    if [digest(Path(p).read_bytes()) for p in pictures] != [p['sha256'] for p in assets['pictures']]:
        raise ContractError('Reference identity/order changed')
    script=validate_script(json.loads((root/'screenplay.json').read_text()), manifest['song_frames'], list(pictures))
    camera=validate_camera(json.loads((root/'camera.json').read_text()), script)
    if len(script['clips']) != count:
        raise ContractError('Clip count mismatch')
    for clip,row in zip(script['clips'],camera['clips']):
        if (root/f"{clip['index']:02d}_prompt.txt").read_text() != compile_prompt(script,clip,row):
            raise ContractError('Prompt differs from authoritative script/camera')
    return manifest
