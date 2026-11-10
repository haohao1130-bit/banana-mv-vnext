"""Opt-in manuscript advice. Never mutate the saved film or compiled recipe."""
import json
import copy
import uuid
from pathlib import Path
from banana_mv.scene_state import atomic_json
from banana_mv.whole_film_review import commission_review, clock_context, REVIEW_SYSTEM
from banana_mv.lyrics_reference import OPTIONAL_TIMING_POLICY
from banana_mv.review_output import reviewed_json
from banana_mv.shoot_plan import _text


def advise(work, cfg, rewrite, instruction=''):
    cfg=copy.deepcopy(cfg)
    cfg.setdefault('rewriter',{})['max_length']=4096
    folder=Path(work)/'preproduction'
    source=json.loads((folder/'whole_film_input.json').read_text(encoding='utf-8'))['source']
    film=json.loads((folder/'whole_film.json').read_text(encoding='utf-8'))['film']
    source['authoring_chapters']=film.get('authoring_chapters',[])
    # A separate directory keeps advisory output distinct from old automatic audits.
    output=folder/('advice_'+uuid.uuid4().hex[:8]);output.mkdir()
    def call(system,payload):
        payload=dict(payload,user_review_focus=instruction,
                     evidence_priority='Original commission is authoritative; authored history is a draft, not commission fact.')
        system=system+'\n'+OPTIONAL_TIMING_POLICY+'\nAdvice only. Do not rewrite the story. Distinguish evidence from uncertainty.'
        atomic_json(output/('request_'+uuid.uuid4().hex[:8]+'.json'),{'system':system,'payload':payload})
        return _text(rewrite(cfg,system,
            [('text',json.dumps(payload,ensure_ascii=False))],uuid.uuid4().hex[:8]))
    clock=clock_context(film,source)
    if source.get('creative_contract') and source['authoring_chapters']:
        issues,formats=commission_review(source,film,clock,call,output,0,1)
    else:
        issues,formats=reviewed_json(REVIEW_SYSTEM+'\n'+OPTIONAL_TIMING_POLICY,
            {'source':source,'timeline':clock['timeline'],'subject_definitions':film['subject_definitions']},
            call,output,'advice',list(range(len(film['beats']))),retries=1)
    result={'status':'advice_only' if issues is not None else 'incomplete','issues':issues,'format':formats,'user_focus':instruction,
            'visual_verified':False,'recipe_changed':False}
    atomic_json(output/'advice.json',result)
    return result
