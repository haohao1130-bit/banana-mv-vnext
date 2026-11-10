"""Recover complete chapters outside a prematurely closed macro JSON root."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from banana_mv.whole_film import _spine_delivery, ensure_film
from test_chained_whole_film import script, chunks
import test_shoot_plan as fixtures

class SpineFormatRecoveryTests(unittest.TestCase):
    def test_real_failure_shapes_preserve_all_original_values(self):
        expected=script();expected['creative_contract']='Use parallel scenes; finish the commissioned ending.'
        prefix=json.dumps({k:v for k,v in expected.items() if k!='chapters'},ensure_ascii=False)
        suffix=json.dumps({'chapters':expected['chapters']},ensure_ascii=False)[1:]
        for separator in (',','\n'):
            result,repair=_spine_delivery(prefix+separator+suffix)
            self.assertEqual(result,expected)
            self.assertEqual(repair,'joined_chapters_after_early_root_close')
    def test_valid_or_incomplete_output_is_not_invented(self):
        expected=script()
        self.assertEqual(_spine_delivery(json.dumps(expected)),(expected,None))
        with self.assertRaises(ValueError):_spine_delivery('{"subject_definitions":"蕾絲蕾絲')
        partial={'subject_definitions':'actor','creative_contract':'unchanged'}
        self.assertEqual(_spine_delivery(json.dumps(partial)),(partial,None))
    def test_complete_macro_format_error_needs_no_model_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req.update(rewrite_retries=3,screenplay_review=False)
            expected=script();a,b=chunks()
            raw=json.dumps({'subject_definitions':expected['subject_definitions']})+','+json.dumps({'chapters':expected['chapters']})[1:]
            model=Mock(side_effect=[raw,json.dumps(a),json.dumps(b)])
            segs=[dict(index=i,start=x,seconds=y) for i,(x,y) in enumerate([(0,15),(15,15),(30,15),(45,13.5)])]
            ensure_film(cfg,req,segs,images,root,model)
            attempts=json.loads((root/'preproduction/whole_film_spine_attempts.json').read_text())['attempts']
            self.assertEqual(len(attempts),1)
            self.assertEqual(attempts[0]['status'],'valid')
            self.assertEqual(model.call_count,3) # one Macro, two Chapters
