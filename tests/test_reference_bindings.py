import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from banana_mv.reference_bindings import reference_manifest,bind_definitions
from banana_mv.whole_film import compile_window,parse_film
from banana_mv.whole_film_review import review_film,REVIEW_SYSTEM
from test_whole_film import film

class ProvenanceTests(unittest.TestCase):
    def test_four_sources_map_by_declared_name_not_subject_order(self):
        manifest=reference_manifest('@圖片1：Ada，成年主唱。\n@圖片2：Ben，對手。\n@圖片3：舞台。\n@圖片4：擂台。',4)
        rows=[{'subject_id':'<Subject 7>','identity':'Ben，成年男性'},
              {'subject_id':'<Subject 2>','name':'Ada','identity':'成年女性'},
              {'subject_id':'<Subject 9>','name':'Ada','role':'silent ring instance'},
              {'subject_id':'S3','name':'舞台'},{'subject_id':'S4','name':'擂台'}]
        text,warnings=bind_definitions(json.dumps(rows,ensure_ascii=False),manifest)
        self.assertFalse(warnings)
        self.assertIn('<Subject 7>: Identity/reference source: <Picture 2>',text)
        self.assertIn('<Subject 9>: Identity/reference source: <Picture 1>',text)
        self.assertIn('<Subject 3>: Identity/reference source: <Picture 3>',text)
        self.assertIn('<Subject 4>: Identity/reference source: <Picture 4>',text)

    def test_retention_survives_names_in_shots_and_chain_shifts_actual_sources(self):
        master=film();master['subject_definitions']=json.dumps([{'subject_id':'<Subject 8>','name':'Ada'}])
        text,_=compile_window(master,dict(index=1,start=4,seconds=4),chain=True,
            reference_manifest=[{'picture':2,'label':'Ada'}])
        self.assertIn('<Subject 8>: Identity/reference source: <Picture 3>',text)
        self.assertIn('<Subject 8>: fully_preserved',text)
        self.assertNotIn('FUTURE_END',text)

    def test_real_failure_retains_actor_and_scene_picture_declarations(self):
        path=Path(__file__).parent/'fixtures/whole_film_early_finale.json'
        master=parse_film(path.read_text(),58500)
        refs=[{'picture':1,'label':'小語'},{'picture':2,'label':'拳王'},
              {'picture':3,'label':'演唱會場地'},{'picture':4,'label':'拳擊比賽場地'}]
        text,_=compile_window(master,dict(index=0,start=0,seconds=15),reference_manifest=refs)
        for n in range(1,5):self.assertIn(f'<Picture {n}>',text)
        self.assertIn('<Subject 1>: fully_preserved',text)
        self.assertIn('<Subject 2>: fully_preserved',text)
        self.assertIn('演唱會場地',text)

    def test_unreferenced_cast_ambiguous_names_and_conflicts_are_not_guessed(self):
        row=[{'subject_id':'<Subject 2>','name':'Extra'}]
        text,warnings=bind_definitions(json.dumps(row),[{'picture':1,'label':'Ada'}])
        self.assertNotIn('<Picture',text);self.assertFalse(warnings)
        row[0]['name']='Ada'
        text,warnings=bind_definitions(json.dumps(row),[{'picture':1,'label':'Ada'},{'picture':2,'label':'Ada'}])
        self.assertNotIn('<Picture',text);self.assertTrue(warnings)
        row[0]['source']='<Picture 4>'
        text,warnings=bind_definitions(json.dumps(row),[{'picture':1,'label':'Ada'}])
        self.assertIn('<Picture 4>',text);self.assertNotIn('<Picture 1>',text);self.assertTrue(warnings)

    def test_reference_label_does_not_forward_mutable_wardrobe_or_future_story(self):
        refs=reference_manifest('@圖片1：Ada，穿外套。之後脫下外套，最後離開。',1)
        self.assertEqual(refs,[{'picture':1,'label':'Ada'}])
        text,_=bind_definitions(json.dumps([{'subject_id':'<Subject 1>','name':'Ada'}]),refs)
        self.assertNotIn('外套',text);self.assertNotIn('離開',text)

    def test_no_op_repair_cannot_become_pass_after_empty_review(self):
        original=film();source={'duration_ms':9000,'srt_cues':[]}
        writer=Mock(side_effect=['{"issues":[{"index":1,"reason":"Required story thread was lost."}]}',
            json.dumps({'beats':[copy.deepcopy(original['beats'][1])]}),'{"issues":[]}'])
        with tempfile.TemporaryDirectory() as tmp:
            result,audit=review_film({}, {'screenplay_repair_rounds':1},source,original,writer,[],tmp,parse_film)
        self.assertEqual(result,original);self.assertEqual(audit['status'],'warnings')
        repair=audit['repairs'][0]
        self.assertTrue(repair['format_accepted']);self.assertFalse(repair['content_changed'])
        self.assertEqual(repair['issue_resolution'],'unresolved_no_op')
        self.assertTrue(audit['issues'])
        self.assertIn('NOT physical story facts',REVIEW_SYSTEM)

    def test_changed_repair_requires_full_recheck_before_resolved(self):
        original=film();b=copy.deepcopy(original['beats'][1]);b['action']='A new deliberate response.'
        writer=Mock(side_effect=['{"issues":[{"index":1,"reason":"Action is unclear."}]}',json.dumps({'beats':[b]}),'{"issues":[]}'])
        with tempfile.TemporaryDirectory() as tmp:
            result,audit=review_film({}, {},{'duration_ms':9000,'srt_cues':[]},original,writer,[],tmp,parse_film)
        self.assertEqual(audit['status'],'passed')
        self.assertEqual(audit['repairs'][0]['issue_resolution'],'resolved_by_recheck')
        self.assertTrue(audit['repairs'][0]['content_changed'])
