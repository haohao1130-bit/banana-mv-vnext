import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from banana_mv.whole_film import ensure_film
from test_continuous_pipeline_wiring import native_film
from test_unified_direction import timeline
import test_shoot_plan as fixtures

class PlanningProgressTests(unittest.TestCase):
    def test_events_follow_actual_author_review_repair_compile_calls(self):
        master=native_film();replacement=dict(master['beats'][1],action='A fresh response.',filming_prompt='A side close-up follows the fresh response.')
        events=[]
        writer=Mock(side_effect=[json.dumps(master),'{"issues":[{"index":1,"reason":"Action needs clarification."}]}',json.dumps({'beats':[replacement]}),'{"issues":[]}'])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req.update(screenplay_review=True,srt_cues=[])
            ensure_film(cfg,req,timeline(),images,root,writer,progress=events.append)
        self.assertEqual(writer.call_count,4)
        self.assertEqual([e['stage'] for e in events],['author','review','repair','review','compile','compile','compile','compile'])
        self.assertEqual(events[2]['round'],1)
        self.assertEqual(events[3]['round'],2)
        self.assertEqual(events[-1]['done'],3)
        self.assertEqual(events[-1]['total'],3)
        self.assertFalse(any('percent' in e or 'tokens' in e for e in events))
