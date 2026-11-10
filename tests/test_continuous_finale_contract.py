"""Regression contracts for source-duration endings in new continuous films."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from banana_mv.mv_scope import (ending_contract, continuous_film_ending_contract,
                                clip_ending)
from banana_mv.whole_film import ensure_film
from test_unified_direction import timeline
from test_whole_film import film
import test_shoot_plan as fixtures


class SourceDurationFinaleTests(unittest.TestCase):
    def test_new_film_finale_does_not_move_with_clip_slicing(self):
        req={'project_scope':'full','story_scope_version':1}
        reference=continuous_film_ending_contract(req,58.5)
        self.assertEqual(reference['end_time'],58.5)
        self.assertEqual(reference['hold_seconds'],0)
        self.assertEqual(reference['settle_by'],58.5)
        for width in (5,10,15,20):
            windows=[]
            at=0.0
            while at<58.5:
                seconds=min(width,58.5-at)
                windows.append({'index':len(windows),'start':at,'seconds':seconds})
                at+=seconds
            # No render-window argument is allowed to change this contract.
            self.assertEqual(continuous_film_ending_contract(req,58.5),reference)
            for row in windows[:-1]:
                segment=dict(row,song_seconds=58.5,segment_count=len(windows),
                             direction_ending_contract=reference)
                scoped=clip_ending(req,segment)
                self.assertEqual(scoped['phase'],'continuing')
                self.assertFalse(scoped['finish_work'])
                self.assertNotIn('settle_by',scoped)
            segment=dict(windows[-1],song_seconds=58.5,segment_count=len(windows),
                         direction_ending_contract=reference)
            scoped=clip_ending(req,segment)
            self.assertEqual(scoped['phase'],'finale')
            self.assertEqual(scoped['end_time'],58.5)
            self.assertNotIn('terminal_hold',scoped['instruction'])

    def test_legacy_scope_remains_length_sensitive_for_saved_projects(self):
        req={'project_scope':'full'}
        a=ending_contract(req,58.5,[{'seconds':10},{'seconds':8.5}])
        b=ending_contract(req,58.5,[{'seconds':15},{'seconds':13.5}])
        self.assertNotEqual(a['resolve_start_by'],b['resolve_start_by'])
        self.assertNotIn('finale_policy',a)
        self.assertNotIn('finale_policy',b)

    def test_actual_textgenerate_seed_is_saved_without_prompt_data(self):
        from unittest.mock import patch
        from banana_mv import services
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            cfg={'comfy_input_dir':str(root),'rewriter':dict(services.DEFAULTS['rewriter'])}
            with patch.object(services,'DATA',root):
                graph,_=services.build_rewrite_graph(cfg,'private system',[('text','private prompt')],'run1234')
            seed=graph['generate']['inputs']['sampling_mode.seed']
            trace=json.loads((root/'rewriter_runs/run1234.json').read_text())
            self.assertEqual(trace['seed'],seed)
            self.assertEqual(trace['parameters']['mtp'],cfg['rewriter']['mtp'])
            self.assertNotIn('private prompt',json.dumps(trace))
            self.assertNotIn('private system',json.dumps(trace))

    def test_legacy_v2_master_keeps_old_ending_policy(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req['screenplay_review']=False
            writer=Mock(return_value=json.dumps(film()))
            ensure_film(cfg,req,timeline(),images,root,writer)
            path=root/'preproduction/whole_film.json'
            saved=json.loads(path.read_text())
            saved.update(version=2,input_sha256='legacy-fixture-fingerprint')
            path.write_text(json.dumps(saved))
            # Test the historical v2 *source projection* without forging a
            # real historical digest from a newly authored v3 fixture.
            with patch('banana_mv.whole_film.digest',return_value='legacy-fixture-fingerprint') as fingerprint:
                ensure_film(cfg,req,timeline(),images,root,writer)
            source=fingerprint.call_args.args[0]
            self.assertEqual(source['ending'],ending_contract(req,9,timeline()))
            self.assertNotIn('ending_policy_version',source)
            self.assertEqual(writer.call_count,1)
            self.assertEqual(json.loads(path.read_text())['version'],2)

    def test_render_graph_reads_mode_without_invoking_old_ending(self):
        from unittest.mock import patch
        from banana_mv import server
        from test_unified_direction import request
        req=request(project_scope='full',director_version=2)
        seg=dict(timeline()[0],
                 direction_ending_contract=continuous_film_ending_contract(req,9),
                 song_seconds=9,segment_count=3)
        baseline=server.graph_options(req,seg['seconds'],seg)
        with patch('banana_mv.mv_scope.clip_ending',
                   side_effect=AssertionError('render entry must not recompute ending')):
            rendered=server.graph_options(req,seg['seconds'],seg)
        self.assertEqual(rendered,baseline)
        self.assertIn('director_mode',rendered)

    def test_excerpt_never_receives_full_song_finale(self):
        contract=continuous_film_ending_contract({'project_scope':'excerpt'},58.5)
        self.assertFalse(contract['finish_work'])
        self.assertNotIn('finale_policy',contract)

    def test_new_author_receives_v3_and_actual_source_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req['screenplay_review']=False
            req['project_scope']='full'
            writer=Mock(return_value=json.dumps(film()))
            plan=ensure_film(cfg,req,timeline(),images,root,writer)
            self.assertEqual(writer.call_count,1)
            payload=json.loads(writer.call_args.args[2][0][1])
            self.assertEqual(payload['ending_policy_version'],2)
            self.assertEqual(payload['ending']['finale_policy'],'source_duration_v2')
            self.assertEqual(payload['ending']['end_time'],9)
            master=json.loads((root/'preproduction/whole_film.json').read_text())
            self.assertEqual(master['version'],5)
            generation=json.loads((root/'preproduction/whole_film_generation.json').read_text())
            self.assertEqual(len(generation['rewrite_request_id']),8)
            self.assertEqual(generation['rewriter_parameters']['max_length'],16384)
            self.assertEqual(plan['ending_contract']['finale_policy'],'source_duration_v2')
            ensure_film(cfg,req,timeline(),images,root,writer)
            self.assertEqual(writer.call_count,1)  # saved master, no new 9B call

if __name__=='__main__':
    unittest.main()

