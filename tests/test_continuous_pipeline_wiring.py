"""Cross-layer contracts: real compiler and worker, deterministic model responses."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from html.parser import HTMLParser

from banana_mv.whole_film import (compile_window, ensure_film, parse_film,
                                  direction_context, FACE_GUIDANCE)
from banana_mv.whole_film_review import review_film, timed_issues, window_timing_issues
from banana_mv.preproduction import preview
from banana_mv.director import MODES
from banana_mv.server import graph_options
from banana_mv.core import build_workflow
from banana_mv.scene_state import digest
from banana_mv.mv_scope import ending_contract
from banana_mv.shoot_plan import adaptation_direction, validate_native_mv_format
import test_shoot_plan as fixtures
from test_unified_direction import timeline
from test_whole_film import film


def native_film():
    master=film()
    for beat in master['beats']:
        beat['filming_prompt']=beat['camera']+' '+beat['action']
        beat['ongoing_filming_prompt']=beat['ongoing_camera']+' '+beat['ongoing']
    return master


class ContinuousWiringTests(unittest.TestCase):
    def test_every_style_and_control_reaches_author_and_final_prompt(self):
        for style in MODES:
            for enabled in (True,False):
                with self.subTest(style=style,enabled=enabled),tempfile.TemporaryDirectory() as tmp:
                    root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
                    req.update(prompt='@圖片1：成人主角。',director=style,
                        face_identity=enabled,dynamic_cuts=enabled,story_plan=enabled,
                        intensity='extreme' if enabled else 'normal',srt_cues=[])
                    writer=Mock(return_value=json.dumps(native_film()))
                    ensure_film(cfg,req,timeline(),images,root,writer)
                    source=json.loads(writer.call_args.args[2][0][1])
                    system=writer.call_args.args[1]
                    self.assertNotIn('render_windows',source)
                    self.assertEqual(source['direction']['selected_style'],style)
                    self.assertIn(style,source['direction']['scene_recipes'])
                    self.assertEqual(source['direction']['face_identity'],enabled)
                    self.assertEqual(source['direction']['dynamic_cuts'],enabled)
                    self.assertIn('<Picture 1>',source['reference_brief'])
                    self.assertIn('<Picture 1>',source['direction']['user_role_declarations'])
                    self.assertIn('Separate character identity from scene-specific performance instances',system)
                    self.assertIn('waist-up or closer',system)
                    self.assertEqual(FACE_GUIDANCE in system,enabled)
                    prompt=(root/'preproduction/00_prompt.txt').read_text()
                    self.assertEqual(FACE_GUIDANCE in prompt,enabled)
                    self.assertIn('EARLY_CAUSE',prompt)
                    self.assertEqual(writer.call_count,1)
                    self.assertEqual(source['adaptation'],adaptation_direction(req))
                    recorded=json.loads((root/'preproduction/whole_film_input.json').read_text())
                    self.assertEqual(recorded['source'],source)

    def test_generic_identity_scene_instances_and_current_state_only(self):
        master=native_film()
        master['subject_definitions']=(
            '<Subject 1> is the stage performer from <Picture 1>, the only singer.\n'
            '<Subject 2> is the same person from <Picture 1> at the workshop, silent.\n'
            '<Subject 3> is the silent colleague from <Picture 2>.')
        master['beats'][1].update(state='At the workshop, <Subject 2> wears a shirt and holds a wrench.',
            continuation_state='At the workshop, <Subject 2> holds the wrench, sleeves rolled up.',
            filming_prompt='An eye-level medium shot tracks <Subject 2> carrying the wrench toward the bench.',
            ongoing_filming_prompt='The side-on medium view follows <Subject 2> carrying the wrench toward the bench.')
        master['beats'][2].update(state='At the workshop bench, <Subject 2> holds the wrench.',
            filming_prompt='A locked side close-up frames <Subject 2> tightening a fresh bolt.')
        # The inherited current state contains neither the prior cause nor future result.
        text,rows=compile_window(master,dict(index=1,start=4,seconds=4),chain=True)
        body=text.split('detailed_description:',1)[1].split('overall_soundscape:',1)[0]
        self.assertIn('sleeves rolled up',body);self.assertIn('wrench',body)
        self.assertNotIn('EARLY_CAUSE',text);self.assertNotIn('CONTACT',text)
        self.assertNotIn('FUTURE_END',text)
        self.assertNotIn('New visible action:',body)
        self.assertEqual(text.count('<Picture 2>'),2)  # two scene instances, same source
        self.assertIn('<Picture 3>',text)
        self.assertEqual(rows[0]['action'],'The lead steadies against the railing.')
        validate_native_mv_format(text,4,require_native=True)

    def test_image_alias_is_normalized_before_chain_slot_shift(self):
        master=native_film();master['subject_definitions']='The actor comes from <Image 1>.'
        master['beats'][1]['ongoing_filming_prompt']='A side view follows the person from <image 1>.'
        text,_=compile_window(master,dict(index=1,start=4,seconds=1),chain=True)
        self.assertNotIn('<Image',text);self.assertNotIn('<image',text)
        self.assertIn('person from <Picture 2>',text)
        self.assertIn('actor comes from <Picture 2>',text)

    def test_missing_native_prose_is_repaired_without_reauthoring_neighbors(self):
        master=native_film();master['beats'][1].pop('filming_prompt')
        seen=[]
        def model(cfg,system,parts,token):
            payload=json.loads(parts[0][1]);seen.append((system,payload))
            if system.startswith('Write ONE'):return json.dumps(master)
            if system.startswith('Repair '):
                self.assertIn('SCENE',system.upper())
                self.assertIn(FACE_GUIDANCE,system)
                return json.dumps({'beats':[native_film()['beats'][1]]})
            return '{"issues":[]}'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req.update(screenplay_review=True,srt_cues=[],director='story',face_identity=True)
            ensure_film(cfg,req,timeline(),images,root,model)
            audit=json.loads((root/'screenplay_review.json').read_text())
            repaired=json.loads((root/'preproduction/whole_film.json').read_text())['film']
        self.assertEqual(audit['status'],'passed');self.assertEqual(len(seen),4)
        self.assertEqual(repaired,native_film())
        self.assertEqual(seen[2][1]['source']['direction']['selected_style'],'story')
        self.assertEqual([v['at_ms'] for v in repaired['beats']],[0,3000,6500,8000])

    def test_missing_native_prose_after_budget_warns_and_ui_shows_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req.update(screenplay_review=True,screenplay_repair_rounds=0,srt_cues=[])
            writer=Mock(side_effect=[json.dumps(film()),'{"issues":[]}'])
            plan=ensure_film(cfg,req,timeline(),images,root,writer)
            self.assertEqual(writer.call_count,2)
            self.assertEqual(plan['quality_status'],'warnings')
            self.assertTrue(any('Native photography prose is missing' in w for w in plan['quality_warnings']))
            job={'request':{'vnext_preproduction':True},'segments':timeline()}
            # Preview reads prepared prompts only after ready marker.
            (root/'preproduction/ready.json').write_text('{}')
            response=preview(job,root)
            self.assertTrue(any('Native photography prose is missing' in w for w in response['quality_warnings']))
            self.assertTrue(all(s['prompt_prepared'] for s in response['segments']))

    def test_missing_guide_is_nonblocking_but_never_claimed_as_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            Path(cfg['guides']['ref']).unlink();req.update(screenplay_review=True,srt_cues=[])
            writer=Mock(side_effect=[json.dumps(native_film()),'{"issues":[]}'])
            result=ensure_film(cfg,req,timeline(),images,root,writer)
            self.assertEqual(result['quality_status'],'warnings')
            self.assertTrue(any('guide was unavailable' in w for w in result['quality_warnings']))
            self.assertEqual(writer.call_count,2)

    def test_srt_is_optional_and_explicit_future_lyric_onset_is_caught(self):
        master=native_film()
        master['beats'][1]['filming_prompt']='The performer sings: <d>[Chinese] 結尾這一句</d>'
        source={'duration_ms':9000,'render_windows':timeline(),'srt_cues':[]}
        self.assertEqual(timed_issues(master,source),[])
        self.assertEqual(window_timing_issues(master,source),[])
        source['srt_cues']=[{'start':8,'end':9,'text':'結尾這一句'}]
        self.assertTrue(timed_issues(master,source))
        self.assertTrue(window_timing_issues(master,source))
        master['beats'][1]['filming_prompt']='The performer tightens the bolt; singing remains off-screen.'
        self.assertEqual(timed_issues(master,source),[])
        self.assertEqual(window_timing_issues(master,source),[])
        # A broad interval overlaps the last lyric, but does NOT permit singing it at entry.
        master['beats']=[dict(master['beats'][0],filming_prompt='The performer sings: <d>[Chinese] 結尾這一句</d>')]
        self.assertTrue(timed_issues(master,source))

    def test_full_master_return_for_local_repair_only_applies_assigned_range(self):
        master=native_film();returned=copy.deepcopy(master)
        returned['beats'][0]['action']='UNREQUESTED_CHANGE'
        returned['beats'][2]['action']='A different fresh bolt is tightened.'
        returned['beats'][2]['filming_prompt']='A side close-up shows a different fresh bolt being tightened.'
        writer=Mock(side_effect=['{"issues":[{"index":2,"reason":"The bolt action is unclear."}]}',
                                json.dumps(returned),'{"issues":[]}'])
        with tempfile.TemporaryDirectory() as tmp:
            result,audit=review_film({}, {},{'duration_ms':9000,'srt_cues':[]},master,writer,[],tmp,parse_film)
        self.assertEqual(audit['status'],'passed')
        self.assertEqual(result['beats'][:2],master['beats'][:2])
        self.assertEqual(result['beats'][3:],master['beats'][3:])
        self.assertEqual(result['beats'][2],returned['beats'][2])
        self.assertEqual(audit['repairs'][0]['ignored_outside_range'],3)

    def test_render_settings_and_native_text_reach_existing_h3_graph(self):
        for enabled in (True,False):
            req=dict(director='action',director_version=2,optimizer_version=1,
                intensity='high',motion_lora=enabled,kitchen_attention=enabled,
                sparse_attention=not enabled,sampling_steps=8,prompt='boxing',
                director_authority=True,story_plan=True,rewrite=True)
            seg=dict(index=1,start=4,seconds=4,director_plan={'mode':'action','event':'A fresh boxing exchange.'})
            text,_=compile_window(native_film(),seg,chain=True,face_identity=enabled)
            options=graph_options(req,4,seg)
            graph=build_workflow(['actor.png','opponent.png'],'song.wav',854,480,96,text,42,'tail.png',**options)
            self.assertEqual(graph['7']['inputs']['prompt'],text)
            self.assertEqual(graph['7']['inputs']['audio_mode'],'lock_source')
            self.assertEqual(options['steps'],8)
            self.assertEqual(options['motion_lora'],enabled)
            self.assertEqual(options['kitchen_attention'],enabled)
            self.assertEqual(options['sparse_attention'],not enabled)
            self.assertIn('17',graph)
            self.assertEqual('attention_backend' in graph,enabled)
            self.assertEqual('sparse_attention' in graph,not enabled)
            loras=[n for n in graph.values() if n['class_type']=='LoraLoaderModelOnly']
            self.assertEqual(bool(loras),enabled)

    def test_legacy_saved_master_fingerprint_and_prepared_prompt_survive_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            segments=timeline();source={'brief':req['prompt'],'duration_ms':9000,
                'adaptation':adaptation_direction(req),'srt_cues':req['srt_cues'],'lyrics':req['lyrics'],
                'music_evidence':[{'source_start':s['start'],'source_end':s['start']+s['seconds'],
                    'evidence':s.get('audio_evidence',{})} for s in segments],
                'ending':ending_contract(req,9.0,segments)}
            folder=root/'preproduction';folder.mkdir()
            master=film();(folder/'whole_film.json').write_text(json.dumps({'version':1,'input_sha256':digest(source),'film':master}))
            text,_=compile_window(master,segments[0]);(folder/'00_prompt.txt').write_text(text)
            before=(folder/'00_prompt.txt').read_bytes()
            writer=Mock(side_effect=AssertionError('legacy resume must not call writer'))
            ensure_film(cfg,req,segments,images,root,writer)
            writer.assert_not_called()
            self.assertEqual((folder/'00_prompt.txt').read_bytes(),before)

    def test_complete_native_master_saved_then_windows_exclude_neighbors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req.update(srt_cues=[],mode='chain')
            master=native_film();writer=Mock(return_value=json.dumps(master))
            ensure_film(cfg,req,timeline(),images,root,writer)
            full=(root/'preproduction/whole_film_prompt.txt').read_text()
            self.assertIn('EARLY_CAUSE',full);self.assertIn('FUTURE_END',full)
            middle=(root/'preproduction/01_prompt.txt').read_text()
            self.assertNotIn('EARLY_CAUSE',middle)
            self.assertNotIn('CONTACT',middle)
            self.assertNotIn('FUTURE_END',middle)
            self.assertNotIn(req['prompt'],middle)
            self.assertNotIn(req['lyrics'],middle)
            self.assertEqual(writer.call_count,1)
            # A clipped continuation inherits the current pose, not the prior initiation.
            self.assertIn('steadies against the railing',middle)
            self.assertIn('Current visible state:',middle)

    def test_failed_repair_cannot_disappear_into_an_empty_followup_review(self):
        master=native_film()
        writer=Mock(side_effect=['{"issues":[{"index":1,"reason":"The action contradicts the supplied story."}]}',
                                '{"beats":[]}','{"issues":[]}'])
        with tempfile.TemporaryDirectory() as tmp:
            result,audit=review_film({}, {'screenplay_repair_rounds':1},
                {'duration_ms':9000,'srt_cues':[]},master,writer,[],tmp,parse_film)
        self.assertEqual(result,master)
        self.assertEqual(audit['status'],'warnings')
        self.assertTrue(audit['issues']);self.assertTrue(audit['warnings'])
        self.assertFalse(audit['repairs'][0]['accepted'])

    def test_folded_controls_remain_inside_form_without_duplicate_ids(self):
        class FormParser(HTMLParser):
            def __init__(self):super().__init__();self.form=False;self.panels=[];self.controls={};self.ids=[]
            def handle_starttag(self,tag,attrs):
                a=dict(attrs)
                if tag=='form':self.form=True
                if tag=='details':self.panels.append(a.get('id'));self.assert_closed=a.get('open')
                if 'id' in a:self.ids.append(a['id'])
                if tag in ('input','select','textarea') and 'id' in a:self.controls[a['id']]=(self.form,tuple(self.panels))
            def handle_endtag(self,tag):
                if tag=='details':self.panels.pop()
                if tag=='form':self.form=False
        parser=FormParser();parser.feed((Path(__file__).parents[1]/'banana_mv/web/index.html').read_text())
        self.assertEqual(len(parser.ids),len(set(parser.ids)))
        for key,panel in [('story_plan','director-options'),('audio_analysis','director-options'),
            ('face_identity','director-options'),('kitchen_attention','render-options'),
            ('motion_lora','render-options'),('rewrite_retries','rewrite-options')]:
            self.assertTrue(parser.controls[key][0]);self.assertIn(panel,parser.controls[key][1])


if __name__=='__main__':unittest.main()
