"""Opt-in native H3 camera-director pass after locked continuous-film authoring.

The movie timeline still owns WHAT and WHEN. The older Banana MV per-window
native H3 enhancement owns HOW to photograph those beats, including additional
coverage inside the fixed event windows. Python only checks and caches delivery.
"""
import copy
import hashlib
import json
import re
import uuid
from pathlib import Path

from banana_mv.core import normalize_mv_prompt
from banana_mv.scene_state import atomic_json, digest, rewrite_retry_count
from banana_mv.shoot_plan import (
    _pictures, _text, NATIVE_ENHANCER_SYSTEM, LOCAL_FILMING_COMMISSION,
    AUTO_FILMING, REFERENCE_PERFORMANCE, CLIP_INTENSITY,
    DYNAMIC_EDITING, adaptation_direction, validate_native_mv_format,
)
from banana_mv.whole_film import window, compile_window


NATIVE_FILMING_CONTRACT = """NATIVE H3 CAMERA DIRECTOR — protected continuous-film shot expansion.
Your job is a finished, visually inventive Ref2VA MOVING-IMAGE PROMPT, not a
summary, event ledger, commentary, JSON, or compiler echo.
Use the supplied official VIDEO_PROMPT_WRITING_GUIDE_ref_en.md to author all
six native sections. Deliver the complete detailed_description as finished
shooting prose with motivated cinematic blocking, character reactions and camera
decisions. Commit to shots; do NOT write generic "current visible state" headers,
synopsis fragments, "dynamic camera" filler or identical camera positions.
For EVERY picture-bearing view, describe the exact visible action and bodily
response in sequence, screen direction, proximity, foreground/depth, lighting,
expressions, and camera starting position/path/arrival or deliberate locked view.
In action scenes clearly articulate footwork, evasion, contact/near miss,
opponent reaction and change of advantage across the commissioned beats. In
performance scenes articulate actual mouth movement, gaze, microphone hand,
breathing and expressive body performance consistent with assigned vocal duty.
Do NOT freeze the lead for reference preservation. Source pictures fix identity
and initial design, never standing poses or facial expressions.
The supplied LOCKED_BEATS and their timestamps are inviolable screenplay
events and scene-role permissions. Preserve the start time and order of EVERY
cut in required_cuts_ms; you may insert EXTRA camera cuts within a beat's time
range for expressive coverage and reaction inserts, but must not move the
committed beat/cut, repeat an impact, create new plot outcomes or disclose the
final act in an earlier window. Intercut concert/ring only as SEPARATE
timestamped views. A shot takes place at ONE physical location.
Return only the complete native six-section H3 prompt with [Shot N] numbering
and LOCAL At mm:ss.mmm cut times. [Shot 1] has no At timestamp.
No fake sound or invented dialogue. Original <Audio 1> fully_copy and
scene-specific singing restrictions remain absolute.
Do not copy the draft detailed_description as your answer; improve its actual
photography while retaining all locked beats and their event boundaries.
"""

def _cut_times(rows):
    cuts=[]
    prev=None
    for row in rows:
        if row['shot_id']!=prev:
            cuts.append(row['at_ms'])
        prev=row['shot_id']
    return cuts


def _delivered_cuts(text):
    section=re.search(r'(?ms)^\s*detailed_description\s*:(.*?)^\s*overall_soundscape\s*:',text)
    if not section:raise ValueError('原生 H3 交稿缺少 detailed_description。')
    parts=list(re.finditer(r'\[Shot\s+(\d+)\]',section.group(1)))
    if not parts:raise ValueError('原生 H3 未提供實際分鏡。')
    times=[0]
    for p in parts[1:]:
        fragment=section.group(1)[p.end():]
        match=re.match(r'\s*At\s+(\d+):(\d{2})\.(\d{1,3})',fragment,re.I)
        if not match:
            raise ValueError('新增鏡頭缺少 H3 本段時間碼。')
        times.append((int(match[1])*60+int(match[2]))*1000+int(match[3].ljust(3,'0')))
    return times


def _normalize_clock_format(text):
    """Format-only normalization: preserve every timestamp's numeric value."""
    text=text.strip()
    if text.startswith('```') and text.endswith('```'):
        text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
    def clock(m):
        shot,minute,second,fraction=m.groups()
        ms=int(fraction.ljust(3,'0'))
        if int(shot)==1 and int(minute)==0 and int(second)==0 and ms==0:
            return '[Shot 1] '
        return f'[Shot {shot}] At {int(minute):02d}:{second}.{ms:03d}, '
    return re.sub(r'\[Shot\s+(\d+)\]\s*[Aa]t\s+(\d{1,2}):(\d{2})\.(\d{1,3})(?!\d)\s*,?\s*',clock,text)


def _verify(text, seconds, required, expected_refs):
    validate_native_mv_format(text,seconds,require_native=True)
    delivered=_delivered_cuts(text)
    lost=[at for at in required if at not in delivered]
    if lost:
        raise ValueError('攝影導演遺失原始鏡頭切點（毫秒）：'+', '.join(map(str,lost)))
    if any(a>=b for a,b in zip(delivered,delivered[1:])):
        raise ValueError('攝影導演交稿鏡頭時間未嚴格遞增。')
    if expected_refs:
        # The official guide requires binding the provided source identities.
        definitions=text.split('summary:',1)[0]
        missing=[n for n in expected_refs if f'<Picture {n}>' not in definitions]
        if missing:
            raise ValueError('攝影導演漏掉原本的圖片綁定：'+str(missing))
    if 'Current visible state:' in text or 'New visible action:' in text:
        raise ValueError('攝影導演複製了 Python 中繼狀態文字，尚未寫成攝影咒語。')
    return text


def enhance_window(cfg, req, seg, film, originals, compiled, rewrite, folder,
                   references=None, progress=None):
    """Generate the native H3 prose from a locked window; preserve existing on failure.

    Existing accepted passes are content-addressed so restart, translation and
    review do not regenerate. Fail open to the validated compiler text on bounded
    writer errors, but emit a visible QA warning rather than pretending it passed.
    """
    folder=Path(folder)
    i=seg['index']
    local=window(film,round(seg['start']*1000),
                 round((seg['start']+seg['seconds'])*1000))
    classic=req.get('native_camera_version')==2
    required=[0] if classic else _cut_times(local)
    from banana_mv.reference_bindings import reference_manifest
    refs=references if references is not None else reference_manifest(req.get('prompt',''),len(originals))
    expected_refs=[row['picture'] for row in refs]
    guide_file=Path(cfg.get('guides',{}).get('ref') or '__missing_camera_guide__')
    try:guide_text=guide_file.read_text(encoding='utf-8-sig') if guide_file.is_file() else ''
    except (OSError,UnicodeError):guide_text=''
    saved=folder/f'{i:02d}_native_h3.json'
    warning_file=folder/f'{i:02d}_native_h3_warning.json'
    # Restore the FULL official H3 filming guide, but only to the local
    # camera-director call. The 9B does NOT receive the whole-song brief here.
    # Do not silently truncate the camera guide: that was the regression.
    system=(NATIVE_ENHANCER_SYSTEM+'\n'+guide_text+'\n'+NATIVE_FILMING_CONTRACT+
        '\nNative output sections, in order: subject_definitions, summary, '
        'retention_analysis, detailed_description, overall_soundscape, '
        'non_diegetic_music. Keep <Audio 1>: fully_copy.')
    if classic:
        from banana_mv.classic_mv import AUTO_FILMING as CLASSIC_CAMERA, DYNAMIC_EDITING as CLASSIC_EDIT, REFERENCE_PERFORMANCE as CLASSIC_ACTING, MV_SCOPE, adaptation
        system=(NATIVE_ENHANCER_SYSTEM+'\n'+guide_text+'\n'+MV_SCOPE+'\n'+adaptation(req)+'\n'+CLASSIC_ACTING+'\n'+CLASSIC_CAMERA+'\n'+(CLASSIC_EDIT if req.get('dynamic_cuts',True) else 'Prefer motivated longer takes.'))
    intens=req.get('intensity','high')
    ctx={
      'duration_seconds':seg['seconds'],
      'timeline_clock':'LOCAL milliseconds inside this render window',
      'required_cuts_ms':required,
      'locked_beats':[{'at_ms':row['at_ms'],'shot_id':row['shot_id'],
                       'scene_and_start_state':row['state'],
                       'visible_action':row['action'],
                       'camera_intention':row['camera']}
                      for row in local],
      'source_song':'<Audio 1>, unchanged, only named vocal scenes lip-sync',
      'local_srt':seg.get('local_srt',[]),
      'music_evidence':seg.get('audio_evidence',{}),
      'reference_manifest':refs,
      'event_policy':'Expand performance and coverage within each locked event; camera intentions are starting suggestions, not mandatory framings. Plot outcomes and scene/vocal roles stay fixed.',
      'reference_and_audio_setup':compiled.split('summary:',1)[0],
      'direction':{
         'adaptation':'FREE' if req.get('story_plan',True) else 'FAITHFUL',
         'intensity':intens,
         'selected_style':req.get('director','auto'),
         'camera_energy':CLIP_INTENSITY.get(intens,CLIP_INTENSITY['high']),
         'dynamic_cuts':req.get('dynamic_cuts',True),
         'face_identity':req.get('face_identity',True)
      }
    }
    if classic:
        from banana_mv.classic_mv import interval_ending
        ctx['ending']=interval_ending(film.get('ending_contract',{}),seg)
        ctx['current_clip_commission']=ctx.pop('locked_beats')
        ctx['event_policy']='The local commission defines events, scene roles and explicit user timing; storage entries are NOT camera cuts. Choose motivated MV coverage and internal full-frame intercuts freely.'
        ctx['source_song']='<Audio 1> unchanged. Vocals are soundtrack only outside the explicitly assigned singing scene.'
        system+='\n'+CLIP_INTENSITY.get(intens,CLIP_INTENSITY['high'])
    message=('Enhance ONLY this local timeline into real native H3 filming prose; '
             'the story and every required cut time are locked. Compose a cinematic '
             'series of camera views rather than echoing the event outline. '
             'No other chapter is visible.\n'
             'Locked local filming commission:\n'+json.dumps(ctx,ensure_ascii=False))
    if classic:
        message=('Target video duration: '+str(seg['seconds'])+' seconds.\nOriginal prompt — current interval only. Shared world and scene-specific vocal roles:\n'+ctx['reference_and_audio_setup']+'\nThe local commission is the screenplay, not a fixed shot list. Allocate coverage and cuts from music and visible events.\nLocked local filming commission:\n'+json.dumps(ctx,ensure_ascii=False))
    parts=[('text',message)]+_pictures(originals)
    retries=min(1,rewrite_retry_count(req))
    rw=copy.deepcopy(cfg)
    rw.setdefault('rewriter',{})['max_length']=min(8192,max(4096,int(
        rw.get('rewriter',{}).get('max_length',8192))))
    folder.mkdir(parents=True,exist_ok=True)
    identity={'version':2,'compiled_sha256':digest(compiled),
              'context_sha256':digest(ctx),'system_sha256':digest(system),
              'rewriter_sha256':digest(rw.get('rewriter',{})),
              'image_sha256':[hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in originals]}
    if saved.is_file() and guide_text.strip():
        try:
            cached=json.loads(saved.read_text(encoding='utf-8'))
            if cached.get('identity')==identity:
                accepted=_verify(cached['prompt'],seg['seconds'],required,expected_refs)
                warning_file.unlink(missing_ok=True)
                return accepted,None
        except (ValueError,KeyError,TypeError,OSError):pass
    # Save the exact guide/commission/parameters to diagnose real model failures.
    atomic_json(folder/f'{i:02d}_native_h3_input.json',
                {'identity':identity,'system':system,'context':ctx,
                 'required_cuts_ms':required,'rewriter':rw.get('rewriter',{}),
                 'guide_path':str(guide_file),'guide_characters':len(guide_text)})
    issues=[];calls=0
    if not guide_text.strip():
        issues.append('完整官方 H3 指南無法讀取；未以空白指南假裝恢復攝影。')
    for attempt in range(0 if issues else retries+1):
        if progress:progress({'stage':'native_camera','done':i,
                              'total':req.get('segment_count',0),'attempt':attempt+1})
        try:
            calls+=1
            result=_text(rewrite(rw,system,parts,uuid.uuid4().hex[:8])).strip()
            (folder/f'{i:02d}_native_h3_raw_{uuid.uuid4().hex[:8]}.txt').write_text(
                result,encoding='utf-8')
            verified=normalize_mv_prompt(_normalize_clock_format(result),len(originals))
            _verify(verified,seg['seconds'],required,expected_refs)
            atomic_json(saved,dict(identity=identity,prompt=verified,
                                   original_compiler_prompt_sha256=digest(compiled),
                                   native_camera_calls=calls))
            warning_file.unlink(missing_ok=True)
            return verified,None
        except (RuntimeError,OSError) as exc:
            issues.append(str(exc));break  # Transport failure is not a format retry.
        except (ValueError,TypeError,KeyError) as exc:
            issues.append(str(exc))
            if attempt<retries:
                parts=[('text',message+'\nPREVIOUS DELIVERY ERROR: '+str(exc)+
                        '\nFix formatting/shot clock/role bindings while preserving '
                        'the already locked event timeline.')]+_pictures(originals)
    warning=('第 '+str(i+1)+' 段 H3 攝影導演未交出可驗證的攝影稿；'
             '沿用較簡略的舊編譯稿，非攝影驗收通過：'+issues[-1])
    saved.unlink(missing_ok=True)
    atomic_json(warning_file,
                {'version':2,'warning':warning,'attempts':calls,
                 'errors':issues,'fallback_used':True})
    return compiled,warning



def direct_window(cfg, req, seg, film, originals, rewrite, folder, references=None, progress=None):
    """Shared author/revision output path; shift chain references exactly once."""
    from banana_mv.lyrics_reference import excerpt
    compiled,_=compile_window(film,seg,chain=False,face_identity=req.get('face_identity',True),
                              reference_manifest=references)
    camera_seg=dict(seg,local_srt=excerpt(req,seg))
    text,warning=enhance_window(cfg,req,camera_seg,film,originals,compiled,rewrite,folder,
                               references=references,progress=progress)
    if req.get('mode')=='chain' and seg['index']>0:
        text=re.sub(r'<Picture (\d+)>',lambda m:f'<Picture {int(m[1])+1}>',text)
        text='subject_definitions:\n<Picture 1> is the actual preceding last frame, a continuity anchor rather than another actor.\n'+re.sub(r'^\s*subject_definitions\s*:\s*','',text,count=1)
    text=normalize_mv_prompt(text,len(originals)+int(req.get('mode')=='chain' and seg['index']>0))
    validate_native_mv_format(text,seg['seconds'],require_native=True)
    atomic_json(Path(folder)/f'{seg["index"]:02d}_native_h3_delivery.json',
                {'version':1,'status':'fallback' if warning else 'native',
                 'final_prompt_sha256':digest(text),'warning':warning,'visual_verified':False})
    return text,warning
