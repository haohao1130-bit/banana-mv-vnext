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
from banana_mv.preproduction import prepare, compile_prompt, event_units, camera_plan, preview
import test_shoot_plan as fixtures
from test_unified_direction import timeline
from banana_mv.shoot_plan import allocation_delivery, ensure_shoot_plan


def cameras():
    return json.dumps({'clips':[{'index':i,'shots':[
        {'at_ms':0,'event_ids':[f'c{i}e0'],'camera':'Wide tracking view with warm side light.'}]} for i in range(3)]})


class PreproductionTests(unittest.TestCase):
    def test_vnext_residual_tail_uses_current_three_second_threshold(self):
        from banana_mv.mv_scope import ending_contract,clip_ending
        req={'vnext_preproduction':True,'project_scope':'full','segment_seconds':10}
        for tail in (2.9,3.0,8.5):
            rows=[{'index':0,'start':0,'seconds':10},{'index':1,'start':10,'seconds':tail}]
            contract=ending_contract(req,10+tail,rows)
            self.assertEqual(contract['resolve_start_by'],0 if tail<=3 else 10)
            if tail<=3:
                self.assertEqual(contract['settle_by'],10)
                seg=dict(rows[-1],song_seconds=10+tail,segment_count=2,direction_ending_contract=contract)
                self.assertEqual(clip_ending(req,seg)['phase'],'terminal_hold')
            else:self.assertEqual(contract['short_tail_seconds'],0)
            self.assertEqual(ending_contract(req,10+tail)['resolve_start_by'],contract['resolve_start_by'])
        self.assertGreater(ending_contract(req,2.5)['settle_by'],0)

    def test_actual_failure_shape_missing_right_delimiters_and_end_is_readable(self):
        raw=('=== SETUP ===\n<Picture 1> is the singer.\n'
             '=== CLIP 0 action\nA feint causes a defensive reaction.\n'
             '=== CLIP 1 story\nThe counter lands and the opponent steps back.\n'
             '=== CLIP 2 story\nBoth regain balance; the commissioned ending follows.')
        setup,data=allocation_delivery(raw,3,flexible=True)
        self.assertEqual([r['index'] for r in data['segments']],[0,1,2])
        self.assertEqual(data['segments'][1]['prompt'],'The counter lands and the opponent steps back.')
        with self.assertRaises(ValueError):allocation_delivery(raw,3,flexible=False)
        with self.assertRaises(ValueError):allocation_delivery(raw.split('=== CLIP 2')[0],3,flexible=True)

    def test_saved_failed_delivery_can_be_recovered_without_writer_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req['camera_review']=False
            req['vnext_preproduction']=True
            raw=fixtures.allocation().replace('=== CLIP 0 story ===','=== CLIP 0 story').replace('=== END ===','')
            path=root/'director_attempt_03.json'
            path.write_text(json.dumps({'raw_response':raw,'error':'old delimiter error'}))
            before=path.read_bytes();model=Mock(side_effect=AssertionError('unnecessary model call'))
            plan=ensure_shoot_plan(cfg,req,timeline(),images,root,model)
            self.assertEqual(len(plan['segments']),3)
            model.assert_not_called();self.assertEqual(path.read_bytes(),before)

    def test_compiler_places_each_causal_event_at_its_assigned_view(self):
        seg={'index':0,'seconds':15,'director_plan':{'event':
            'The fighter feints; the opponent opens their guard.\n'
            'The counter lands; the opponent loses balance and steps back.\n'
            'The opponent remains down and reacts; the winner catches her breath.'},
            'fixed_reference_settings':'<Picture 1> identifies the fighter.'}
        row={'index':0,'shots':[
            {'at_ms':0,'event_ids':['c0e0','c0e1'],'camera':'Side-on medium two-shot; both gloves and torsos remain visible.'},
            {'at_ms':11000,'event_ids':['c0e2'],'camera':'Low wide view includes the fallen opponent in the foreground.'}]}
        camera_plan(json.dumps({'clips':[row]}),[seg],linked=True)
        text=compile_prompt({'request':{'mode':'independent'}},seg,row)
        first,second=text.split('detailed_description:\n')[1].split('[Shot 2]')
        self.assertIn('counter lands',first);self.assertNotIn('remains down',first)
        self.assertIn('remains down',second);self.assertNotIn('fighter feints',second)
        self.assertEqual(text.count('The counter lands'),1)
        self.assertNotIn('Continue the commissioned action',text)

    def test_preview_exposes_all_prepared_prompts_without_affecting_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'preproduction';folder.mkdir()
            (folder/'ready.json').write_text('{}')
            for i in range(3):(folder/f'{i:02d}_prompt.txt').write_text(f'prepared {i}')
            job={'request':{'vnext_preproduction':True},'segments':timeline()}
            response=preview(copy.deepcopy(job),root)
            self.assertTrue(all(s['prompt_prepared'] for s in response['segments']))
            self.assertFalse(any(s.get('prompt') for s in job['segments']))

    def test_native_director_receives_only_current_commission_and_can_expand_performance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req['camera_review']=False
            job={'request':req,'segments':[dict(s,director_plan={'event':f'Event {s["index"]}.'}) for s in timeline()]}
            model=Mock(side_effect=[fixtures.native_prompt(i) for i in range(3)])
            prepare(cfg,job,images,root,model)
            self.assertEqual(model.call_count,3)
            for i,call in enumerate(model.call_args_list):
                self.assertIn('OFFICIAL_NATIVE_GUIDE_MARKER',call.args[1])
                self.assertIn('Actively invent',call.args[1])
                payload=json.loads(call.args[2][0][1])
                self.assertEqual(payload['current_clip']['index'],i)
                self.assertNotIn('whole_screenplay',payload)
                self.assertNotIn('PRIVATE_FULL_STORY',call.args[2][0][1])
                self.assertIn('summary describes ONLY this interval',call.args[1])
                self.assertIn('ending',payload['current_clip'])
                text=call.args[2][0][1]
                for other in range(3):
                    if other!=i:self.assertNotIn(f'Event {other}.',text)
                self.assertEqual((root/f'preproduction/{i:02d}_prompt.txt').read_text(),fixtures.native_prompt(i))

    def test_legacy_and_preproduction_share_local_commission_for_same_script(self):
        from banana_mv.shoot_plan import write_shoot_prompt, LOCAL_FILMING_COMMISSION
        # Old MV terminal hold, action handoff, and return from a parallel strand.
        cases=[
            'Opening state: The man is already slumped in his chair. New progression: Breathing and a slow reframe. Outgoing state: He remains slumped.',
            'Opening state: The opponent is already moving backward. New progression: He hits the railing and regains his footing. Outgoing state: Guard raised.',
            'Opening state: The ring exchange has paused at distance. New progression: The stage singer performs; return to the ring for a new feint. Outgoing state: The guard reacts.',
        ]
        for event in cases:
            for faithful in (False,True):
                with self.subTest(event=event,faithful=faithful),tempfile.TemporaryDirectory() as tmp:
                    root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
                    req.update(camera_review=False,story_plan=not faithful)
                    seg=dict(timeline()[0],director_plan={'event':event,'mode':'story','handoff_version':1},
                             fixed_reference_settings='<Picture 1> identifies the singer; <Picture 2> identifies the opponent.')
                    before=copy.deepcopy(seg)
                    legacy=Mock(return_value=fixtures.native_prompt(0))
                    write_shoot_prompt(cfg,req,seg,images,None,legacy)
                    fresh=Mock(return_value=fixtures.native_prompt(0))
                    prepare(cfg,{'request':req,'segments':[before]},images,root,fresh)
                    old_input=legacy.call_args.args[2][0][1]
                    system=fresh.call_args.args[1];payload=json.loads(fresh.call_args.args[2][0][1])
                    self.assertIn(LOCAL_FILMING_COMMISSION,old_input)
                    self.assertIn(LOCAL_FILMING_COMMISSION,system)
                    self.assertIn(event,old_input)
                    self.assertEqual(payload['current_clip']['event'],event)
                    self.assertEqual(payload['current_clip']['fixed_reference_settings'],before['fixed_reference_settings'])
                    policy='ADAPTATION: FAITHFUL' if faithful else 'ADAPTATION: FREE'
                    self.assertIn(policy,old_input);self.assertIn(policy,payload['direction'])
                    self.assertNotIn('whole_screenplay',payload)
                    self.assertEqual(fresh.call_count,1)
                    self.assertEqual((root/'preproduction/00_prompt.txt').read_text(),fixtures.native_prompt(0))

    def test_original_roles_reach_writer_even_when_generated_setup_is_wrong(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req['camera_review']=False
            req['prompt']=('@圖片1：歌手，成年女性，主唱。\n@圖片2：對手，成年男性，衛冕選手。\n'
                           '歌手在舞台演唱；競賽場景專注競技。\n最後對手倒地，故事結束。')
            job={'request':req,'segments':[dict(s,director_plan={'event':'Opening state: The opponent is already down. New progression: He tries to rise.'},
                fixed_reference_settings='Both characters sing everywhere.') for s in timeline()]}
            model=Mock(side_effect=[fixtures.native_prompt(i) for i in range(3)])
            prepare(cfg,job,images,root,model)
            for call in model.call_args_list:
                payload=json.loads(call.args[2][0][1]);source=payload['user_role_declarations']
                self.assertIn('<Picture 1>：歌手',source)
                self.assertIn('<Picture 2>：對手',source)
                self.assertIn('競賽場景專注競技',source)
                self.assertNotIn('最後對手倒地',source)
                self.assertIn('override',call.args[1])
                self.assertIn('already established at frame zero',call.args[1])

    def test_allocation_brief_plans_boundary_energy_without_fixed_transition_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req['camera_review']=False
            req['vnext_preproduction']=True
            model=Mock(return_value=fixtures.allocation())
            ensure_shoot_plan(cfg,req,timeline(),images,root,model)
            system=model.call_args.args[1]
            self.assertIn('Design adjacent boundaries together',system)
            self.assertIn('need not finish the same physical action',system)
            self.assertIn('not mandatory',system)
            self.assertIn('NOT a self-contained miniature story',system)

    def test_interrupted_native_writing_preserves_completed_drafts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req['camera_review']=False
            job={'request':req,'segments':[dict(s,director_plan={'event':f'Event {s["index"]}.'}) for s in timeline()]}
            with self.assertRaises(RuntimeError):
                prepare(cfg,job,images,root,Mock(side_effect=[fixtures.native_prompt(0),RuntimeError('interrupted')]))
            first=(root/'preproduction/00_prompt.txt').read_bytes()
            self.assertFalse((root/'preproduction/ready.json').exists())
            model=Mock(side_effect=[fixtures.native_prompt(1),fixtures.native_prompt(2)])
            prepare(cfg,job,images,root,model)
            self.assertEqual(model.call_count,2)
            self.assertEqual((root/'preproduction/00_prompt.txt').read_bytes(),first)
            self.assertTrue((root/'preproduction/ready.json').exists())

    def test_worker_prepares_every_prompt_before_queue_and_resumes_without_9b(self):
        for mode in ('independent','chain'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root,mode)
                req.update(camera_review=False,screenplay_review=False,vnext_preproduction=True,audio_analysis=False)
                work=root/'abcdef123456';work.mkdir()
                job={'id':work.name,'request':req,'segments':timeline(),'status':'running',
                     'size':[32,32],'images_comfy':['ref0.png','ref1.png'],'seed':42,
                     'duration':9,'output_size':[32,32]}
                calls=[];graphs=[];downloads=[0]
                def model(*args):
                    calls.append(args);return fixtures.allocation() if len(calls)==1 else fixtures.native_prompt(len(calls)-2)
                def queue(cfg,graph):
                    self.assertEqual(len(calls),4)
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
                self.assertEqual(len(calls),4)
                self.assertEqual((work/'00_part_v1.mp4').read_bytes(),first)
                self.assertTrue(all(g['7']['inputs']['audio_mode']=='lock_source' for g in graphs))
                self.assertEqual(graphs[1]['7']['inputs']['prompt'],graphs[2]['7']['inputs']['prompt'])
                text=graphs[-1]['7']['inputs']['prompt']
                self.assertIn('<Picture 3>' if mode=='chain' else '<Picture 2>',text)
                self.assertEqual('17' in graphs[-1],mode=='chain')

    def test_review_still_waits_for_original_approve_button(self):
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req['camera_review']=False
            req.update(camera_review=False,screenplay_review=False,vnext_preproduction=True,plan_review=True,audio_analysis=False)
            work=root/'abcdef123456';work.mkdir()
            job={'id':work.name,'request':req,'segments':timeline(),'status':'running',
                 'size':[32,32],'images_comfy':['ref0.png','ref1.png'],'seed':42,
                 'duration':9,'output_size':[32,32]}
            model=Mock(side_effect=[fixtures.allocation()]+[fixtures.native_prompt(i) for i in range(3)]);queue=Mock()
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
            req['camera_review']=False
            job={'request':req,'segments':[dict(s,director_plan={'event':'A quiet scene.'}) for s in timeline()]}
            job['request']['h3_validation_version']=1
            with self.assertRaises(ValueError):prepare(cfg,job,images,root,Mock(return_value='not a native prompt'))
            self.assertTrue(list((root/'preproduction').glob('director_00_raw_*.txt')))
            self.assertFalse((root/'preproduction/ready.json').exists())

    def test_original_cast_and_fifteen_second_window_are_not_restricted(self):
        event='An original monkey guitarist performs while the referenced singer listens.'
        seg={'index':0,'seconds':15,'director_plan':{'event':event},'fixed_reference_settings':'<Picture 1> identifies the singer. The monkey has no uploaded picture.'}
        text=compile_prompt({'request':{'mode':'independent'}},seg,{'shots':[{'at_ms':0,'camera':'One continuous tracking shot.'}]})
        self.assertIn(event,text)
        self.assertIn('no uploaded picture',text)
        self.assertEqual(text.count('[Shot 1]'),1)


if __name__=='__main__':unittest.main()
