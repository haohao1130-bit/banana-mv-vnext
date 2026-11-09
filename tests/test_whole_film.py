"""One creative film, deterministic windows, no clip re-authoring."""
import copy
import json
from pathlib import Path
import tempfile
import threading
from contextlib import ExitStack
from unittest.mock import patch
from PIL import Image
from banana_mv import server
import unittest
from unittest.mock import Mock
from banana_mv.whole_film import parse_film, window, compile_window, ensure_film
from banana_mv.story_plan import ensure_plan
from banana_mv.preproduction import prepare
from banana_mv.shoot_plan import validate_native_mv_format
import test_shoot_plan as fixtures
from test_unified_direction import timeline


def film():
    def beat(at,shot,state,action,ongoing,mode='story'):
        return dict(at_ms=at,shot_id=shot,state=state,continuation_state=ongoing,
                    action=action,ongoing=ongoing,camera='Stable side-on medium view.',
                    ongoing_camera='Continue the established side-on view.',mode=mode)
    return {'subject_definitions':'<Subject 1> is the adult lead from <Picture 1>.',
            'beats':[beat(0,'a','The lead stands beside the table.','EARLY_CAUSE: the lead places a cup down.','The lead watches the cup.'),
                     beat(3000,'b','The lead is moving backward.','CONTACT: the lead meets the railing.','The lead steadies against the railing.','action'),
                     beat(6500,'b','The lead is braced at the railing.','The lead rises from the rail.','The lead holds a stable guard.'),
                     beat(8000,'c','The lead stands safely.','FUTURE_END: final reaction.','The lead rests.')]}


class WholeFilmTests(unittest.TestCase):
    def test_subject_tables_are_not_misreported_as_missing(self):
        for definitions in ([{'id':'S1','name':'Lead','appearance':'current source identity'}],
                            {'<Subject 7>':{'source':'<Picture 2>','role':'silent opponent'}},
                            ['<Subject 3> is the environment.']):
            with self.subTest(definitions=definitions):
                original=film();original['subject_definitions']=definitions
                parsed=parse_film('```json\n'+json.dumps(original)+'\n```',9000)
                self.assertEqual(json.loads(parsed['subject_definitions']),definitions)
                self.assertEqual(parsed['beats'],original['beats'])
        for absent in (None,'',[],{}):
            bad=film();bad['subject_definitions']=absent
            with self.assertRaises(ValueError):parse_film(json.dumps(bad),9000)

    def test_saved_structured_identity_delivery_recovers_without_model_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root);req['screenplay_review']=False
            folder=root/'preproduction';folder.mkdir()
            broken=folder/'whole_film_raw_broken.txt';broken.write_text('{"beats":[')
            original=film();definitions=[{'subject_id':'S1','name':'Lead','role':'only singer'}]
            original['subject_definitions']=definitions
            saved=folder/'whole_film_raw_valid.txt';saved.write_text(json.dumps(original))
            before=saved.read_bytes();writer=Mock(side_effect=AssertionError('unnecessary 9B call'))
            ensure_film(cfg,req,timeline(),images,root,writer)
            writer.assert_not_called();self.assertEqual(saved.read_bytes(),before)
            recovery=json.loads((folder/'whole_film_recovery.json').read_text())
            self.assertTrue(recovery['attempts'][-1]['accepted'])
            self.assertEqual(recovery['attempts'][-1]['raw_file'],saved.name)
            master=json.loads((folder/'whole_film.json').read_text())
            self.assertEqual(json.loads(master['film']['subject_definitions']),definitions)

    def test_truncated_saved_output_is_not_closed_or_accepted_as_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root);req['screenplay_review']=False
            folder=root/'preproduction';folder.mkdir()
            saved=folder/'whole_film_raw_truncated.txt';saved.write_text(json.dumps(film())[:-20])
            writer=Mock(return_value=json.dumps(film()))
            ensure_film(cfg,req,timeline(),images,root,writer)
            self.assertEqual(writer.call_count,1)
            recovery=json.loads((folder/'whole_film_recovery.json').read_text())
            self.assertFalse(recovery['attempts'][0]['accepted'])

    def test_cut_inside_action_receives_only_ongoing_state_and_current_events(self):
        f=parse_film(json.dumps(film()),9000)
        rows=window(f,4000,8000)
        self.assertEqual(rows[0]['action'],'The lead steadies against the railing.')
        self.assertEqual(rows[0]['state'],'The lead steadies against the railing.')
        body=json.dumps(rows)
        for forbidden in ('EARLY_CAUSE','CONTACT','FUTURE_END','moving backward'):
            self.assertNotIn(forbidden,body)
        self.assertEqual(rows[0]['camera'],'Continue the established side-on view.')
        self.assertEqual(rows[1]['at_ms'],2500)
        self.assertEqual(window(f,3000,4000)[0]['action'],'CONTACT: the lead meets the railing.')

    def test_same_shot_crosses_window_without_artificial_cut_or_picture_reset(self):
        text,rows=compile_window(film(),dict(index=1,start=4,seconds=4),chain=True)
        validate_native_mv_format(text,4,require_native=True)
        self.assertEqual(text.count('[Shot '),1)
        self.assertIn('within the same continuous shot',text)
        self.assertIn('<Picture 2>',text)
        self.assertIn('actual preceding last frame',text)
        self.assertNotIn('FUTURE_END',text)
        self.assertNotIn('CONTACT:',text)

    def test_one_writer_call_saves_all_windows_and_resume_uses_saved_film(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root);req['screenplay_review']=False
            req.update(whole_film_version=1,vnext_preproduction=True)
            before=copy.deepcopy(cfg);writer=Mock(return_value=json.dumps(film()))
            result=ensure_plan(cfg,req,timeline(),images,root,writer)
            self.assertEqual(writer.call_count,1)
            self.assertEqual(writer.call_args.args[0]['rewriter']['max_length'],16384)
            self.assertEqual(cfg,before)
            payload=json.loads(writer.call_args.args[2][0][1])
            self.assertNotIn('segments',payload)
            self.assertEqual(payload['duration_ms'],9000)
            self.assertEqual(result['segments'][1]['mode'],'action')
            prepare(cfg,{'request':req,'segments':timeline()},images,root,writer)
            self.assertEqual(writer.call_count,1)
            first=(root/'preproduction/00_prompt.txt').read_bytes()
            (root/'preproduction/ready.json').unlink()
            again=ensure_film(cfg,req,timeline(),images,root,writer)
            self.assertEqual(again,result);self.assertEqual(writer.call_count,1)
            self.assertEqual(first,(root/'preproduction/00_prompt.txt').read_bytes())

    def test_delivery_retry_is_bounded_and_raw_output_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root);req['screenplay_review']=False
            req['rewrite_retries']=1
            writer=Mock(side_effect=['{"beats":',json.dumps(film())])
            ensure_film(cfg,req,timeline(),images,root,writer)
            self.assertEqual(writer.call_count,2)
            self.assertEqual(len(list((root/'preproduction').glob('whole_film_raw_*.txt'))),2)

    def test_five_minute_compilation_preserves_global_order_without_more_writing(self):
        f=film();f['beats']=[dict(f['beats'][0],at_ms=t*1000,shot_id=f's{t}',action=f'NEW_EVENT_{t}',ongoing=f'ONGOING_{t}') for t in range(0,300,7)]
        for width in (10,15):
            compiled=[]
            for i,start in enumerate(range(0,300,width)):
                text,rows=compile_window(f,dict(index=i,start=start,seconds=min(width,300-start)))
                validate_native_mv_format(text,min(width,300-start),require_native=True)
                compiled.extend(r['action'] for r in rows if r['action'].startswith('NEW_EVENT_'))
            self.assertEqual(compiled,[b['action'] for b in f['beats']])

    def test_no_srt_is_a_normal_upstream_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root);req['screenplay_review']=False;req.pop('srt_cues')
            writer=Mock(return_value=json.dumps(film()))
            ensure_film(cfg,req,timeline(),images,root,writer)
            self.assertEqual(json.loads(writer.call_args.args[2][0][1])['srt_cues'],[])

    def test_worker_compiles_entire_film_before_queue_and_resumes_without_writer(self):
        for mode in ('independent','chain'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root,mode);req['screenplay_review']=False
                req.update(camera_review=False,screenplay_review=False,vnext_preproduction=True,whole_film_version=1,audio_analysis=False)
                work=root/'abcdef123456';work.mkdir()
                job={'id':work.name,'request':req,'segments':timeline(),'status':'running',
                     'size':[32,32],'images_comfy':['ref0.png','ref1.png'],'seed':42,
                     'duration':9,'output_size':[32,32]}
                calls=[];graphs=[];downloads=[0]
                def model(*args):
                    calls.append(args);return json.dumps(film())
                def queue(cfg,graph):
                    self.assertEqual(len(calls),1)
                    self.assertTrue((work/'preproduction/ready.json').exists())
                    self.assertTrue(all((work/f'preproduction/{i:02d}_prompt.txt').is_file() for i in range(3)))
                    graphs.append(copy.deepcopy(graph));return str(len(graphs))
                def download(cfg,item,dest):
                    downloads[0]+=1
                    if downloads[0]==2:raise RuntimeError('simulated interruption')
                    dest.write_bytes(b'raw')
                lock=threading.Lock();lock.acquire()
                for owner,name,value in [(server,'RUNS',root),(server,'GPU_LOCK',lock),
                    (server.backend,'DATA',root),(server.backend,'rewrite_local',model),
                    (server,'preflight',Mock()),(server,'valid_part',lambda p,*a:p.is_file()),
                    (server,'audio_window',lambda src,dest,*a:dest.write_bytes(b'audio')),
                    (server.backend,'queue_prompt',queue),(server.backend,'history_entry',Mock(return_value=None)),
                    (server,'wait_generation',Mock(return_value={'outputs':{'x':{'videos':[{'filename':'out.mp4'}]}}})),
                    (server.backend,'comfy_download',download),
                    (server,'trim_video',lambda src,dest,*a:dest.write_bytes(b'part')),
                    (server,'last_frame',lambda src,dest:Image.new('RGB',(8,8)).save(dest)),
                    (server,'assemble',lambda parts,song,dest,*a:dest.write_bytes(b'final'))]:
                    stack.enter_context(patch.object(owner,name,value))
                server.worker(job,cfg,images,root/'song.wav',root/'song.wav')
                self.assertEqual(job['status'],'error',job.get('error'))
                first=(work/'00_part_v1.mp4').read_bytes()
                job['resuming']=True;lock.acquire()
                server.worker(job,cfg,images,root/'song.wav',root/'song.wav')
                self.assertEqual(job['status'],'done',job.get('error'))
                self.assertEqual(len(calls),1)
                self.assertEqual((work/'00_part_v1.mp4').read_bytes(),first)
                self.assertTrue(all(g['7']['inputs']['audio_mode']=='lock_source' for g in graphs))
                self.assertEqual(graphs[1]['7']['inputs']['prompt'],graphs[2]['7']['inputs']['prompt'])
                text=graphs[-1]['7']['inputs']['prompt']
                self.assertIn('<Picture 2>' if mode=='chain' else '<Picture 1>',text)
                self.assertEqual('17' in graphs[-1],mode=='chain')

