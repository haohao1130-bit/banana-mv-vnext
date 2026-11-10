"""Regression protection for restored 9B native H3 camera-direction stage."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from banana_mv import native_photography as camera
from banana_mv.whole_film import compile_window, ensure_film
from banana_mv.shoot_plan import validate_native_mv_format
import test_shoot_plan as fixtures
from test_continuous_pipeline_wiring import native_film
from test_unified_direction import timeline


def native_delivery(cuts,*,extra=None):
    times=sorted(set(cuts+([extra] if extra is not None else [])))
    lines=[]
    for i,at in enumerate(times):
        prefix=f'[Shot {i+1}]'+(f' At {at//60000:02d}:{(at//1000)%60:02d}.{at%1000:03d},' if i else '')
        lines.append(prefix+(' <Subject 1> from <Picture 1> advances across the lit set; '
            'her forward foot catches the floor, shoulders turn, eyes track the opponent. '
            'Camera starts low to her right and tracks laterally toward a dramatic '
            'three-quarter foreground frame, her focused reaction fully visible.'))
    return ('subject_definitions:\n<Subject 1> is the adult lead from <Picture 1>.\n'
            'summary:\nA commissioned cinematic sequence using the supplied reference.\n'
            'retention_analysis:\n<Picture 1>: fully_preserved - retain identity, not pose.\n'
            '<Audio 1>: fully_copy - keep source unchanged.\n'
            'detailed_description:\n'+'\n'.join(lines)+
            '\noverall_soundscape:\n<Audio 1> unchanged.\n'
            'non_diegetic_music:\nThe supplied original music remains unchanged.')


class NativeH3DirectorTests(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root=Path(temp.name)
        images,cfg,req=fixtures.ShootPlanTests().fixture(root)
        req.update(native_camera_version=1,rewrite_retries=0,
                   prompt='@圖片1：成人主角。',face_identity=False)
        f=native_film()
        seg=dict(timeline()[0],audio_evidence={'pulse':{'bpm':120}},
                 local_srt=[])
        compiler,_=compile_window(f,seg)
        return root,images,cfg,req,f,seg,compiler

    def test_native_director_restores_official_guide_and_enriches_shots(self):
        root,images,cfg,req,f,seg,compiled=self.fixture()
        expected=native_delivery([0,3000],extra=1500)
        writer=Mock(return_value=expected)
        actual,warning=camera.enhance_window(
            cfg,req,seg,f,images,compiled,writer,root, references=[{'picture':1,'label':'成人主角'}])
        self.assertIsNone(warning)
        self.assertIn('Camera starts low',actual)
        self.assertNotIn('Current visible state:',actual)
        self.assertEqual(camera._delivered_cuts(actual),[0,1500,3000])
        self.assertNotEqual(actual,compiled)
        validate_native_mv_format(actual,seg['seconds'],require_native=True)
        self.assertIn('OFFICIAL_NATIVE_GUIDE_MARKER',writer.call_args.args[1])
        self.assertIn('NATIVE H3 CAMERA DIRECTOR',writer.call_args.args[1])
        payload=json.loads(writer.call_args.args[2][0][1].split(
            'Locked local filming commission:\n',1)[1])
        self.assertEqual(payload['required_cuts_ms'],[0,3000])
        self.assertEqual([x['at_ms'] for x in payload['locked_beats']],[0,3000])
        self.assertIn('source_song',payload)
        self.assertTrue((root/'00_native_h3.json').is_file())

        cached=camera.enhance_window(cfg,req,seg,f,images,compiled,writer,
                                     root,references=[{'picture':1,'label':'成人主角'}])
        self.assertEqual(cached,(actual,None))
        writer.assert_called_once()

    def test_full_official_guide_survives_even_after_six_thousand_chars(self):
        root,images,cfg,req,f,seg,compiled=self.fixture()
        guide=root/'guide.md'
        full='OFFICIAL_NATIVE_GUIDE_MARKER\n'+('H3 official reference guidance. '*220)+ '\nMANDATORY_END_OF_GUIDE_SENTINEL'
        guide.write_text(full,encoding='utf-8')
        writer=Mock(return_value=native_delivery([0,3000]))
        result,warning=camera.enhance_window(cfg,req,seg,f,images,compiled,
            writer,root,references=[{'picture':1,'label':'成人主角'}])
        self.assertIsNone(warning)
        self.assertIn('MANDATORY_END_OF_GUIDE_SENTINEL',writer.call_args.args[1])
        self.assertIn(full,writer.call_args.args[1])
        payload=json.loads(writer.call_args.args[2][0][1].split(
            'Locked local filming commission:\n',1)[1])
        self.assertEqual(payload['locked_beats'][0]['at_ms'],0)
        self.assertNotIn('whole_song_brief',payload)

    def test_bad_delivery_cannot_move_locked_cut_and_does_not_replace_compiler(self):
        root,images,cfg,req,f,seg,compiled=self.fixture()
        writer=Mock(return_value=native_delivery([0,2700]))
        actual,warning=camera.enhance_window(cfg,req,seg,f,images,compiled,
            writer,root,references=[{'picture':1,'label':'成人主角'}])
        self.assertEqual(actual,compiled)
        self.assertIn('攝影導演未交出可驗證',warning)
        self.assertIn('3000',warning)
        self.assertTrue(json.loads((root/'00_native_h3_warning.json').read_text())['fallback_used'])
        self.assertFalse((root/'00_native_h3.json').exists())

    def test_resumed_existing_plan_never_calls_camera_director_without_opt_in(self):
        root,images,cfg,req,f,seg,compiled=self.fixture()
        req.pop('native_camera_version')
        writer=Mock(return_value=json.dumps(f))
        plan=ensure_film(cfg,req,timeline(),images,root,writer)
        self.assertEqual(writer.call_count,1)
        self.assertNotIn('camera',plan.get('quality_status',''))
        self.assertFalse(list((root/'preproduction').glob('*_native_h3.json')))

    def test_new_full_film_pass_invokes_9b_once_per_clip_and_uses_it(self):
        root,images,cfg,req,f,seg,compiled=self.fixture()
        systems=[]
        def model(config,system,parts,reqid):
            systems.append(system)
            if system.startswith('Write ONE'):
                return json.dumps(f)
            payload=json.loads(parts[0][1].split('Locked local filming commission:\n',1)[1])
            return native_delivery(payload['required_cuts_ms'])
        plan=ensure_film(cfg,req,timeline(),images,root,model)
        self.assertEqual(len(systems),len(timeline())+1)
        self.assertEqual(sum('NATIVE H3 CAMERA DIRECTOR' in s for s in systems),
                         len(timeline()))
        self.assertEqual(len(plan['segments']),len(timeline()))
        for i in range(len(timeline())):
            prompt=(root/f'preproduction/{i:02d}_prompt.txt').read_text()
            self.assertIn('Camera starts low',prompt)
            self.assertNotIn('Current visible state:',prompt)
        self.assertTrue((root/'preproduction/whole_film.json').exists())
        self.assertIn('source',json.loads((root/'preproduction/whole_film_input.json').read_text()))

if __name__=='__main__':
    unittest.main()

class NativeReliabilityTests(unittest.TestCase):
    fixture=NativeH3DirectorTests.fixture
    def test_runtime_failure_and_missing_guide_fail_open(self):
        root,images,cfg,req,f,seg,compiled=self.fixture()
        req['rewrite_retries']=3
        model=Mock(side_effect=RuntimeError('Comfy unavailable'))
        prompt,warning=camera.enhance_window(cfg,req,seg,f,images,compiled,model,root)
        self.assertEqual(prompt,compiled);self.assertIn('Comfy unavailable',warning)
        self.assertEqual(model.call_count,1)
        Path(cfg['guides']['ref']).unlink()
        model.reset_mock()
        prompt,warning=camera.enhance_window(cfg,req,seg,f,images,compiled,model,root)
        self.assertEqual(prompt,compiled);self.assertIn('指南',warning);model.assert_not_called()
    def test_cache_includes_direction_srt_music_model_and_guide(self):
        root,images,cfg,req,f,seg,compiled=self.fixture()
        model=Mock(return_value=native_delivery([0,3000]))
        def run():return camera.enhance_window(cfg,req,seg,f,images,compiled,model,root)
        run();run();self.assertEqual(model.call_count,1)
        req['intensity']='extreme';run();self.assertEqual(model.call_count,2)
        seg['local_srt']=[{'clip_start':1,'clip_end':2,'text':'Current line'}];run();self.assertEqual(model.call_count,3)
        seg['audio_evidence']={'pulse':{'bpm':90}};run();self.assertEqual(model.call_count,4)
        cfg.setdefault('rewriter',{})['temperature']=0.3;run();self.assertEqual(model.call_count,5)
        Path(cfg['guides']['ref']).write_text('Full changed official guide');run();self.assertEqual(model.call_count,6)
    def test_format_only_fix_avoids_a_second_generation(self):
        root,images,cfg,req,f,seg,compiled=self.fixture()
        model=Mock(return_value='```text\n'+native_delivery([0,3000]).replace('[Shot 1]','[Shot 1] At 0:00.0,').replace('At 00:03.000,','at 0:03.0,')+'\n```')
        actual,warning=camera.enhance_window(cfg,req,seg,f,images,compiled,model,root)
        self.assertIsNone(warning);self.assertEqual(model.call_count,1)
        self.assertEqual(camera._delivered_cuts(actual),[0,3000])
    def test_success_clears_stale_warning_and_chain_shifts_once(self):
        root,images,cfg,req,f,seg,compiled=self.fixture()
        camera.enhance_window(cfg,req,seg,f,images,compiled,Mock(return_value='bad'),root)
        self.assertTrue((root/'00_native_h3_warning.json').is_file())
        req.update(mode='chain',srt_cues=[{'start':4.2,'end':4.8,'text':'current'}])
        seg=dict(timeline()[1],audio_evidence={})
        model=Mock(return_value=native_delivery([0,2500]))
        actual,warning=camera.direct_window(cfg,req,seg,f,images,model,root)
        self.assertIsNone(warning)
        self.assertIn('<Picture 2>',actual);self.assertNotIn('<Picture 3>',actual)
        delivered=json.loads((root/'01_native_h3_delivery.json').read_text())
        from banana_mv.scene_state import digest
        self.assertEqual(delivered['final_prompt_sha256'],digest(actual))
        payload=json.loads(model.call_args.args[2][0][1].split('Locked local filming commission:\n')[1])
        self.assertEqual(payload['local_srt'][0]['clip_start'],0.2)
        # A fresh success for the previously failed first window clears warning.
        camera.enhance_window(cfg,req,timeline()[0],f,images,compiled,Mock(return_value=native_delivery([0,3000])),root)
        self.assertFalse((root/'00_native_h3_warning.json').exists())
