import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from banana_mv.whole_film import parse_film,compile_window,ensure_film
from banana_mv.whole_film_review import review_film,timed_issues
import test_shoot_plan as fixtures
from test_unified_direction import timeline

FIXTURE=Path(__file__).parent/'fixtures/whole_film_early_finale.json'

def actual():return parse_film(FIXTURE.read_text(),58500)
def source():return {'brief':'Use a single scene-specific vocalist. Final line starts at 54.5 seconds.','duration_ms':58500,
                     'srt_cues':[{'start':54.5,'end':56.58,'text':'抱歉，我的下一拳比鐘聲先到！'}]}

class MasterReviewTests(unittest.TestCase):
    def test_real_failure_is_in_master_not_time_conversion(self):
        f=actual();self.assertEqual(timed_issues(f,source())[0]['index'],5)
        text,rows=compile_window(f,{'index':2,'start':30,'seconds':15})
        self.assertIn('At 00:11.000',text)
        self.assertIn('New visible action:',text)
        self.assertEqual(rows[1]['at_ms'],5000)
        # The final 54.5 s beat remains in the final source window.
        self.assertEqual(compile_window(f,{'index':3,'start':45,'seconds':13.5})[1][-1]['at_ms'],9500)

    def test_srt_optional_and_non_singing_coverage_is_not_an_error(self):
        f=actual();s=source();s['srt_cues']=[];self.assertEqual(timed_issues(f,s),[])
        s=source()
        for b in f['beats']:
            b['state']='Both performers hold their established position.'
            b['action']='A new physical exchange continues.'
            b['camera']='A clear side-on shot.'
        self.assertEqual(timed_issues(f,s),[])
        f['beats'][5]['state']='The performer sings the final line.'
        f['beats'][5]['action']='最後一句「抱歉，我的下一拳比鐘聲先到！」'
        f['beats'][5]['at_ms']=54500;f['beats'][6]['at_ms']=57000
        self.assertEqual(timed_issues(f,s),[])

    def test_invalid_json_retries_then_records_failed_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=actual();writer=Mock(return_value='{"issues": [')
            result,audit=review_film({}, {'review_format_retries':1},source(),f,writer,[],tmp,parse_film)
            self.assertEqual(writer.call_count,2)
            self.assertEqual(result,f);self.assertEqual(audit['status'],'review_failed_open')
            self.assertTrue(audit['issues']);self.assertTrue(audit['warnings'])

    def test_nonempty_review_repairs_only_flagged_range_then_rechecks_complete_film(self):
        f=actual();replacement=copy.deepcopy(f['beats'][3:])
        for b,t in zip(replacement,[28500,54500,55500,57000]):b['at_ms']=t
        writer=Mock(side_effect=[json.dumps({'issues':[{'index':i,'reason':'The scheduled climax occurs earlier than the explicit user window.'} for i in range(3,7)]}),
                                json.dumps({'beats':replacement}),'{"issues":[]}'])
        with tempfile.TemporaryDirectory() as tmp:
            result,audit=review_film({}, {},source(),f,writer,[],tmp,parse_film)
        self.assertEqual(writer.call_count,3);self.assertEqual(audit['status'],'passed')
        self.assertEqual(result['beats'][:3],f['beats'][:3])
        self.assertEqual(result['subject_definitions'],f['subject_definitions'])
        self.assertNotEqual(audit['checks'][0]['film_hash'],audit['checks'][1]['film_hash'])
        payload=json.loads(writer.call_args_list[2].args[2][0][1])
        self.assertEqual(len(payload['timeline']),7)
        self.assertEqual(payload['timeline'][5]['at_ms'],55500)
        self.assertEqual(f,actual())

    def test_moving_range_boundary_is_rejected_without_destroying_original(self):
        f=actual();changed=copy.deepcopy(f['beats'][5]);changed['at_ms']=40000
        writer=Mock(side_effect=['{"issues":[]}',json.dumps({'beats':[changed]}),'{"issues":[]}'])
        with tempfile.TemporaryDirectory() as tmp:
            result,audit=review_film({}, {'screenplay_repair_rounds':1},source(),f,writer,[],tmp,parse_film)
        self.assertEqual(result,f);self.assertEqual(audit['status'],'warnings')
        self.assertFalse(audit['repairs'][0]['accepted'])

    def test_distinct_similar_actions_and_montage_are_not_keyword_rejected(self):
        f=actual();s=source();s['srt_cues']=[]
        for b in f['beats']:b['action']='A new jab and a new block.'
        with tempfile.TemporaryDirectory() as tmp:
            writer=Mock(return_value='{"issues":[]}')
            result,audit=review_film({}, {},s,f,writer,[],tmp,parse_film)
        self.assertEqual(result,f);self.assertEqual(audit['status'],'passed');self.assertEqual(writer.call_count,1)

    def test_disabled_review_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer=Mock(side_effect=AssertionError('must not call'))
            _,audit=review_film({}, {'screenplay_review':False},source(),actual(),writer,[],tmp,parse_film)
        writer.assert_not_called();self.assertEqual(audit['status'],'disabled');self.assertTrue(audit['warnings'])

    def test_integration_reviews_before_slicing_and_resume_reuses_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req["screenplay_review"]=True
            from test_whole_film import film
            writer=Mock(side_effect=[json.dumps(film()),'{"issues":[]}'])
            ensure_film(cfg,req,timeline(),images,root,writer)
            self.assertEqual(writer.call_count,2)
            self.assertEqual(json.loads((root/'screenplay_review.json').read_text())['status'],'passed')
            ensure_film(cfg,req,timeline(),images,root,writer)
            self.assertEqual(writer.call_count,2)

if __name__=='__main__':unittest.main()
