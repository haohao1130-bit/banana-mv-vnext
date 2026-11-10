"""Opt-in manuscript revisions: unpublished preview, adoption, rollback and isolation."""
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from banana_mv import recipe_revision as revisions
from banana_mv import server
from banana_mv.whole_film import compile_window
from test_continuous_pipeline_wiring import native_film


class RecipeRevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.work=self.root/'abcdef123456'
        self.work.mkdir()
        self.folder=self.work/'preproduction'
        self.folder.mkdir()
        (self.folder/'ready.json').write_text('{"version":5}')
        self.segments=[{'index':0,'start':0.0,'seconds':4.0},
                       {'index':1,'start':4.0,'seconds':4.0},
                       {'index':2,'start':8.0,'seconds':1.0}]
        self.film=native_film()
        self.film['authoring_chapters']=[
            {'start_ms':0,'end_ms':6500,'goal':'Opening','entry':'Beginning','exit_target':'Prepared'},
            {'start_ms':6500,'end_ms':9000,'goal':'Closing','entry':'Prepared','exit_target':'Finished'}]
        self.film['macro_creative_contract']='Preserve the ending.'
        (self.folder/'whole_film.json').write_text(json.dumps(
            {'version':4,'input_sha256':'original-input','film':self.film}),encoding='utf-8')
        (self.folder/'whole_film_input.json').write_text(json.dumps(
            {'source':{'brief':'A full story, final outcome at the end.',
             'srt_cues':[{'start':0.5,'end':1.5,'text':'Opening lyric'},
                         {'start':8.0,'end':8.8,'text':'Future finale lyric'}]}}),encoding='utf-8')
        plan={'version':5,'shared_setup':self.film['subject_definitions'],
              'segments':[],'ending_contract':{}}
        for seg in self.segments:
            text,rows=compile_window(self.film,seg)
            (self.folder/f'{seg["index"]:02d}_prompt.txt').write_text(text,encoding='utf-8')
            plan['segments'].append({'index':seg['index'],'mode':'story',
                                     'handoff_version':1,
                                     'event':'\n'.join(x['state']+' '+x['action'] for x in rows)})
        (self.work/'director_plan.json').write_text(json.dumps(plan),encoding='utf-8')
        (self.folder/'whole_film_prompt.txt').write_text('ORIGINAL MASTER',encoding='utf-8')
        self.job={'id':self.work.name,'status':'plan_ready','request':{
            'plan_review':True,'prompt':'@圖片1：成人主角。','mode':'independent',
            'face_identity':False},
            'segments':[dict(s,director_plan=copy.deepcopy(plan['segments'][i]),
                             fixed_reference_settings=plan['shared_setup'],
                             prompt=(self.folder/f'{i:02d}_prompt.txt').read_text())
                        for i,s in enumerate(self.segments)],
            'images_comfy':['one.png'],'seed':42,
            'size':[854,480],'output_size':[854,480],'duration':9}
        self.state_patch=patch.object(server,'RUNS',self.root)
        self.state_patch.start();self.addCleanup(self.state_patch.stop)
        self.job['plan_revision']=server.plan_revision(self.job)
        self.base_revision=self.job['plan_revision']
        self.advice={'status':'advice_only','issues':[
            {'target_chapter':0,'index':0,'reason':'Open with stronger conflict.',
             'repair_instruction':'Improve opening causal exchange, preserve ending.'}]}
        self.job['recipe_advice']=self.advice
        changed=copy.deepcopy(self.film['beats'][:2])
        changed[0]['action']='The lead notices a new obstacle.'
        changed[0]['filming_prompt']='A low close view follows the lead discovering a new obstacle and reacting.'
        self.model=Mock(return_value=json.dumps({'beats':changed}))
        self.writer=Mock()
        self.cfg={'rewriter':{'max_length':8192}}
        server.write_state(self.job)

    def stage(self):
        result=revisions.draft(self.work,self.job,self.cfg,self.model,self.advice,self.base_revision)
        self.job['recipe_revision']=result
        server.write_state(self.job)
        return result

    def test_staging_keeps_original_files_and_excludes_future_lyric(self):
        before={p:p.read_bytes() for p in [self.folder/'whole_film.json',
                self.work/'director_plan.json',self.folder/'00_prompt.txt']}
        result=self.stage()
        self.assertEqual(result['status'],'ready')
        self.assertTrue(result['preview'])
        self.assertIn(0,result['changed_segments'])
        for p,data in before.items():
            self.assertEqual(p.read_bytes(),data)
        payload=json.loads(self.model.call_args.args[2][0][1])
        self.assertEqual([c['text'] for c in payload['local_srt']],['Opening lyric'])
        self.assertNotIn('Future finale lyric',json.dumps(payload))
        self.assertNotIn('full story',json.dumps(payload).lower())
        self.assertIn('after_h3',result['preview'][0])
        self.assertNotIn('Future finale lyric',result['preview'][0]['after_h3'])

    def test_accept_updates_story_prompts_and_approval_revision(self):
        result=self.stage()
        updated=revisions.accept(self.work,self.job,result['id'],server.write_state,server.plan_revision)
        self.assertEqual(updated['recipe_revision']['status'],'adopted')
        self.assertNotEqual(updated['plan_revision'],self.base_revision)
        self.assertEqual(updated['plan_revision'],server.plan_revision(updated))
        saved=json.loads((self.folder/'whole_film.json').read_text())['film']
        self.assertIn('notices a new obstacle',saved['beats'][0]['action'])
        self.assertIn('new obstacle',(self.folder/'00_prompt.txt').read_text())
        self.assertIn('new obstacle',updated['segments'][0]['director_plan']['event'])
        self.assertEqual(updated['segments'][0]['prompt'],(self.folder/'00_prompt.txt').read_text())
        self.assertTrue(list((self.folder/'recipe_revisions'/result['id']/'originals').glob('*')))
        self.assertNotIn('plan_translation',updated)
        self.assertEqual(server.read_state(self.job['id'])['plan_revision'],updated['plan_revision'])
        self.assertEqual(updated['status'],'plan_ready')
        self.assertEqual(updated['recipe_advice']['status'],'stale_after_adoption')
        self.assertEqual(json.loads((self.work/'screenplay_review.json').read_text())['status'],
                         'user_revision_unreviewed')
        self.assertEqual(json.loads((self.work/'director_plan.json').read_text())['quality_status'],
                         'user_revision_unreviewed')

    def test_apply_failure_rolls_back_original_files_and_status(self):
        result=self.stage()
        before={p:p.read_bytes() for p in [self.folder/'whole_film.json',
                self.work/'director_plan.json',self.folder/'00_prompt.txt',
                self.folder/'01_prompt.txt',self.folder/'02_prompt.txt']}
        original_write=revisions._write_text
        count=[0]
        def sabotage(path,value):
            count[0]+=1
            if count[0]==3:
                raise OSError('simulated failure')
            return original_write(path,value)
        with patch.object(revisions,'_write_text',side_effect=sabotage):
            with self.assertRaisesRegex(OSError,'simulated failure'):
                revisions.accept(self.work,self.job,result['id'],server.write_state,
                                 server.plan_revision)
        for p,data in before.items():
            self.assertEqual(p.read_bytes(),data)
        saved=server.read_state(self.job['id'])
        self.assertEqual(saved['plan_revision'],self.base_revision)
        self.assertEqual(saved['recipe_revision']['status'],'ready')

    def test_discard_and_stale_revision_are_non_destructive(self):
        result=self.stage()
        before=(self.folder/'whole_film.json').read_bytes()
        self.job['recipe_revision']['base_revision']='outdated'
        with self.assertRaisesRegex(ValueError,'已變更'):
            revisions.accept(self.work,self.job,result['id'],server.write_state,
                             server.plan_revision)
        self.assertEqual((self.folder/'whole_film.json').read_bytes(),before)
        self.job['recipe_revision']=result
        with patch.object(server,'GPU_LOCK',threading.Lock()):
            discarded=server.discard_recipe_revision(self.job['id'],result['id'])
        self.assertEqual(discarded['recipe_revision']['status'],'discarded')
        self.assertEqual((self.folder/'whole_film.json').read_bytes(),before)

    def test_http_routes_bound_to_explicit_user_actions(self):
        handler=object.__new__(server.Handler)
        handler.send_json=Mock()
        for url,body,fn in [
            ('/api/mv/recipe-revise',{'id':self.job['id']},'request_recipe_revision'),
            ('/api/mv/recipe-accept',{'id':self.job['id'],'revision':'rev'},'accept_recipe_revision'),
            ('/api/mv/recipe-keep',{'id':self.job['id'],'revision':'rev'},'discard_recipe_revision')]:
            with self.subTest(url=url):
                handler.path=url;handler.body_json=Mock(return_value=body)
                with patch.object(server,fn,return_value={'status':'plan_ready'}) as target:
                    handler.do_POST()
                    self.assertEqual(target.call_args.args,tuple(body.values()))


if __name__=='__main__':
    unittest.main()

class NativeRecipeRevisionTests(unittest.TestCase):
    setUp=RecipeRevisionTests.setUp
    def test_native_revision_enhances_only_changed_windows_then_adopts_exact_output(self):
        from PIL import Image
        from banana_mv.native_photography import _cut_times
        from banana_mv.whole_film import window
        from test_native_photography import native_delivery
        self.job['request'].update(native_camera_version=1,rewrite_retries=0,mode='chain')
        image=self.work/'ref.png';Image.new('RGB',(8,8),'red').save(image)
        guide=self.work/'guide.md';guide.write_text('OFFICIAL full guide '+('camera composition '*400))
        self.cfg['guides']={'ref':str(guide)}
        # Give unaffected segments distinctive accepted camera prose to preserve.
        original_prompts={}
        for seg in self.job['segments']:
            prompt='UNCHANGED_NATIVE_'+str(seg['index'])+'\n'+(self.folder/f'{seg["index"]:02d}_prompt.txt').read_text()
            # Keep native section order valid: marker goes into a descriptive section.
            prompt=prompt.replace('UNCHANGED_NATIVE_'+str(seg['index'])+'\n','').replace('summary:\n','summary:\nUNCHANGED_NATIVE_'+str(seg['index'])+' ')
            (self.folder/f'{seg["index"]:02d}_prompt.txt').write_text(prompt)
            original_prompts[seg['index']]=prompt
        self.job['plan_revision']=server.plan_revision(self.job)
        changed=copy.deepcopy(self.film['beats'][:2]);changed[0]['action']='Newly discovered obstacle'
        changed[0]['filming_prompt']='New obstacle in a low shot.'
        calls=[]
        def writer(cfg,system,parts,id_):
            calls.append(system)
            if system.startswith('Revise ONLY'):return json.dumps({'beats':changed})
            payload=json.loads(parts[0][1].split('Locked local filming commission:\n')[1])
            return native_delivery(payload['required_cuts_ms'])
        result=revisions.draft(self.work,self.job,self.cfg,writer,self.advice,self.job['plan_revision'],originals=[image])
        self.assertEqual(len(calls),2)  # one local story edit, one affected window camera call
        saved=json.loads((self.folder/'recipe_revisions'/result['id']/'candidate.json').read_text())
        self.assertIn('Camera starts low',saved['prompts']['0'])
        self.assertEqual(saved['prompts']['1'],original_prompts[1])
        self.assertEqual(saved['prompts']['2'],original_prompts[2])
        self.assertEqual((self.folder/'00_prompt.txt').read_text(),original_prompts[0])
        self.job['recipe_revision']=result
        updated=revisions.accept(self.work,self.job,result['id'],server.write_state,server.plan_revision)
        self.assertEqual(updated['segments'][0]['prompt'],saved['prompts']['0'])
        self.assertEqual((self.folder/'01_prompt.txt').read_text(),original_prompts[1])
        delivery=json.loads((self.folder/'00_native_h3_delivery.json').read_text())
        self.assertEqual(delivery['status'],'native')
    def test_failed_native_revision_warns_and_leaves_active_prompt_untouched(self):
        from PIL import Image
        self.job['request'].update(native_camera_version=1,rewrite_retries=0)
        image=self.work/'ref.png';Image.new('RGB',(8,8),'red').save(image)
        guide=self.work/'guide.md';guide.write_text('FULL GUIDE')
        self.cfg['guides']={'ref':str(guide)}
        changed=copy.deepcopy(self.film['beats'][:2]);changed[0]['action']='New obstacle'
        changed[0]['filming_prompt']='New obstacle close up.'
        original=(self.folder/'00_prompt.txt').read_bytes()
        writer=Mock(side_effect=[json.dumps({'beats':changed}),RuntimeError('text backend offline')])
        result=revisions.draft(self.work,self.job,self.cfg,writer,self.advice,self.base_revision,originals=[image])
        candidate=json.loads((self.folder/'recipe_revisions'/result['id']/'candidate.json').read_text())
        self.assertTrue(any('text backend offline' in w for w in candidate['plan']['quality_warnings']))
        self.assertEqual((self.folder/'00_prompt.txt').read_bytes(),original)
