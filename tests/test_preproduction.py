"""Real legacy worker with mocked 9B/GPU; only production order changes."""
import copy
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from PIL import Image
from banana_mv import server
from banana_mv.preproduction import prepare, compile_prompt
import test_shoot_plan as fixtures
from test_unified_direction import timeline


def cameras():
    return json.dumps({'clips':[{'index':i,'shots':[
        {'at_ms':0,'camera':'Wide tracking view with warm side light.'},
        {'at_ms':500,'camera':'Cut closer with foreground depth and a slow lateral move.'}]} for i in range(3)]})


class PreproductionTests(unittest.TestCase):
    def test_worker_prepares_every_prompt_before_queue_and_resumes_without_9b(self):
        for mode in ('independent','chain'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root,mode)
                req.update(vnext_preproduction=True,audio_analysis=False)
                work=root/'abcdef123456';work.mkdir()
                job={'id':work.name,'request':req,'segments':timeline(),'status':'running',
                     'size':[32,32],'images_comfy':['ref0.png','ref1.png'],'seed':42,
                     'duration':9,'output_size':[32,32]}
                calls=[];graphs=[];downloads=[0]
                def model(*args):
                    calls.append(args);return fixtures.allocation() if len(calls)==1 else cameras()
                def queue(cfg,graph):
                    self.assertEqual(len(calls),2)
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
                self.assertEqual(len(calls),2)
                self.assertEqual((work/'00_part_v1.mp4').read_bytes(),first)
                self.assertTrue(all(g['7']['inputs']['audio_mode']=='lock_source' for g in graphs))
                self.assertEqual(graphs[1]['7']['inputs']['prompt'],graphs[2]['7']['inputs']['prompt'])
                text=graphs[-1]['7']['inputs']['prompt']
                self.assertIn('<Picture 3>' if mode=='chain' else '<Picture 2>',text)
                self.assertEqual('17' in graphs[-1],mode=='chain')

    def test_review_still_waits_for_original_approve_button(self):
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req.update(vnext_preproduction=True,plan_review=True,audio_analysis=False)
            work=root/'abcdef123456';work.mkdir()
            job={'id':work.name,'request':req,'segments':timeline(),'status':'running',
                 'size':[32,32],'images_comfy':['ref0.png','ref1.png'],'seed':42,
                 'duration':9,'output_size':[32,32]}
            model=Mock(side_effect=[fixtures.allocation(),cameras()]);queue=Mock()
            lock=threading.Lock();lock.acquire()
            for owner,name,value in [(server,'RUNS',root),(server,'GPU_LOCK',lock),
                (server.backend,'DATA',root),(server.backend,'rewrite_local',model),
                (server.backend,'queue_prompt',queue)]:stack.enter_context(patch.object(owner,name,value))
            server.worker(job,cfg,images,root/'song.wav',root/'song.wav')
            self.assertEqual(job['status'],'plan_ready',job.get('error'))
            self.assertTrue((work/'preproduction/ready.json').exists())
            self.assertFalse(any(s.get('prompt') for s in job['segments']))
            queue.assert_not_called()

    def test_camera_failure_saves_diagnostics_without_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            job={'request':req,'segments':[dict(s,director_plan={'event':'A quiet scene.'}) for s in timeline()]}
            with self.assertRaises(ValueError):prepare(cfg,job,images,root,Mock(return_value='not json'))
            self.assertTrue((root/'preproduction/camera_raw_00.txt').exists())
            self.assertFalse((root/'preproduction/ready.json').exists())

    def test_original_cast_and_fifteen_second_window_are_not_restricted(self):
        event='An original monkey guitarist performs while the referenced singer listens.'
        seg={'index':0,'seconds':15,'director_plan':{'event':event},'fixed_reference_settings':'<Picture 1> identifies the singer. The monkey has no uploaded picture.'}
        text=compile_prompt({'request':{'mode':'independent'}},seg,{'shots':[{'at_ms':0,'camera':'One continuous tracking shot.'}]})
        self.assertIn(event,text)
        self.assertIn('no uploaded picture',text)
        self.assertEqual(text.count('[Shot 1]'),1)


if __name__=='__main__':unittest.main()
