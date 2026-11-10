"""Old MV allocation/directing restored with local-only photography commissions."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from banana_mv.whole_film import ensure_film
from banana_mv.classic_mv import ending, interval_ending
import test_shoot_plan as fixtures
from test_unified_direction import timeline
from test_native_photography import native_delivery

class ClassicMVTests(unittest.TestCase):
    def test_one_allocation_then_local_directors_with_complete_guide_and_old_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req.update(mv_director_version=1,native_camera_version=2,authoring_mode='classic_mv')
            cfg.setdefault('rewriter',{})['whole_film_mode']='chained'
            calls=[]
            def model(config,system,parts,id_):
                calls.append((system,parts))
                if 'Locked local filming commission:\n' not in parts[0][1]:
                    self.assertNotIn('OFFICIAL_NATIVE_GUIDE_MARKER',system)
                    return fixtures.allocation()
                payload=json.loads(parts[0][1].split('Locked local filming commission:\n')[1])
                self.assertIn('1. TIME AND CONTINUITY',system)
                self.assertIn('6. LIGHTING',system)
                self.assertIn('Dynamic editing is enabled',system)
                self.assertIn('IDENTITY AND PERFORMANCE',system)
                self.assertIn('OFFICIAL_NATIVE_GUIDE_MARKER',system)
                self.assertNotIn('locked_beats',payload)
                self.assertEqual(payload['required_cuts_ms'],[0])
                text=parts[0][1]
                self.assertNotIn('PRIVATE_FULL_STORY',text)
                self.assertNotIn('FUTURE_STORY_MARKER',text)
                if 'CURRENT_COUNTER' in text:
                    self.assertNotIn('HUMAN_OPENING',text);self.assertNotIn('FINAL_BEAT',text)
                cuts=[0,1000] if payload['duration_seconds']>1 else [0]
                return native_delivery(cuts)
            ensure_film(cfg,req,timeline(),images,root,model)
            self.assertEqual(len(calls),1+len(timeline()))
            master=json.loads((root/'preproduction/whole_film.json').read_text())
            self.assertEqual(master['version'],9)
            self.assertEqual(master['film']['authoring_mode'],'classic_mv')
            self.assertFalse((root/'preproduction/whole_film_spine.json').exists())
            self.assertFalse(list((root/'preproduction').glob('whole_film_chapter_*.json')))
            ensure_film(cfg,req,timeline(),images,root,model)
            self.assertEqual(len(calls),1+len(timeline()))
    def test_no_per_interval_climax_and_only_small_residual_tail_sustains_ending(self):
        segs=[{'index':0,'start':0,'seconds':15},{'index':1,'start':15,'seconds':15},{'index':2,'start':30,'seconds':2}]
        contract=ending({'project_scope':'full'},segs)
        self.assertEqual(contract['short_tail_seconds'],2)
        self.assertEqual(interval_ending(contract,segs[0])['phase'],'continuing')
        self.assertEqual(interval_ending(contract,segs[1])['phase'],'resolving')
        self.assertEqual(interval_ending(contract,segs[2])['phase'],'terminal_hold')
        segs[-1]['seconds']=8.5
        self.assertEqual(ending({'project_scope':'full'},segs)['short_tail_seconds'],0)
    def test_old_director_layer_has_scene_permissions_and_no_split_screen(self):
        from banana_mv.classic_mv import MV_SCOPE
        self.assertIn('never split-screen',MV_SCOPE)
        self.assertIn('singer role in one location never permits lip-sync in another',MV_SCOPE)
        self.assertIn('never N/A',MV_SCOPE)
        self.assertIn('not identity, gender',MV_SCOPE)
