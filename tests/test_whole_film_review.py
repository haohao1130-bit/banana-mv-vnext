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
            master=film()
            for b in master['beats']:
                b['filming_prompt']=b['camera']+' '+b['state']+' '+b['action']
                b['ongoing_filming_prompt']=b['ongoing_camera']+' '+b['continuation_state']+' '+b['ongoing']
            writer=Mock(side_effect=[json.dumps(master),'{"issues":[]}'])
            ensure_film(cfg,req,timeline(),images,root,writer)
            self.assertEqual(writer.call_count,2)
            self.assertEqual(json.loads((root/'screenplay_review.json').read_text())['status'],'passed')
            ensure_film(cfg,req,timeline(),images,root,writer)
            self.assertEqual(writer.call_count,2)


class CompressedClockRegressionTests(unittest.TestCase):
    def fixture(self):
        raw=(Path(__file__).parent/'fixtures/whole_film_compressed_clock.json').read_text()
        f=parse_film(raw,58500)
        s={'brief':'0:00–0:16 opening exchanges; 0:31–0:43 pressure and observation; '
                   '0:43–0:54.5 final setup; 0:54.5–ending the stage vocalist sings the last line.',
           'duration_ms':58500,'lyrics':'','srt_cues':[]}
        return f,s

    def test_seconds_are_calculated_not_inferred_from_digits(self):
        from banana_mv.whole_film_review import clock_context
        f,s=self.fixture();before=copy.deepcopy(f);clock=clock_context(f,s)
        self.assertEqual(clock['duration_seconds'],58.5)
        self.assertFalse(clock['srt_provided'])
        self.assertEqual(clock['timeline'][1]['start_seconds'],0.8)
        self.assertEqual(clock['timeline'][-1]['start_seconds'],8)
        self.assertEqual(clock['timeline'][-1]['end_seconds'],58.5)
        self.assertEqual(clock['timeline'][-1]['span_seconds'],50.5)
        self.assertEqual(f,before)  # No guessed timestamp scaling.

    def test_no_srt_global_retiming_can_replace_all_beats_then_recheck(self):
        f,s=self.fixture();replacement=copy.deepcopy(f['beats'])
        times=[0,4000,16000,20000,28000,31000,36000,43000,54000,54500,55500]
        for beat,at in zip(replacement,times):beat['at_ms']=at
        replacement[-1]['state']='On the concert stage, the assigned vocalist sings the commissioned final line.'
        writer=Mock(side_effect=['{"issues":[{"index":-1,"reason":"The final vocal action starts at 8 seconds instead of the explicit 54.5-second window; the whole timeline is compressed."}]}',
                                json.dumps({'beats':replacement}),'{"issues":[]}'])
        with tempfile.TemporaryDirectory() as tmp:
            result,audit=review_film({}, {},s,f,writer,[],tmp,parse_film)
        self.assertEqual(audit['status'],'passed');self.assertTrue(audit['repairs'][0]['accepted'])
        self.assertEqual(audit['repairs'][0]['scope'],'whole_film')
        self.assertEqual(result['beats'][-1]['at_ms'],55500)
        self.assertEqual(f['beats'][-1]['at_ms'],8000)
        payload=json.loads(writer.call_args_list[0].args[2][0][1])
        self.assertEqual(payload['timeline'][-1]['start_seconds'],8)
        self.assertEqual(payload['clock']['duration_seconds'],58.5)
        self.assertEqual(writer.call_args_list[0].args[0]['rewriter']['max_length'],4096)
        self.assertEqual(writer.call_args_list[1].args[0]['rewriter']['max_length'],16384)
        self.assertEqual(json.loads(writer.call_args_list[2].args[2][0][1])['timeline'][-1]['at_ms'],55500)

    def test_genuinely_local_edit_still_preserves_unflagged_neighbors(self):
        f,s=self.fixture();replacement=copy.deepcopy(f['beats'][4])
        replacement['action']='The challenger tests the opponent with a new feint.'
        writer=Mock(side_effect=['{"issues":[{"index":4,"reason":"This action repeats its state instead of progressing."}]}',
                                json.dumps({'beats':[replacement]}),'{"issues":[]}'])
        with tempfile.TemporaryDirectory() as tmp:
            result,audit=review_film({}, {},s,f,writer,[],tmp,parse_film)
        self.assertEqual(audit['status'],'passed')
        self.assertEqual(audit['repairs'][0]['scope'],'local')
        self.assertEqual(result['beats'][:4],f['beats'][:4]);self.assertEqual(result['beats'][5:],f['beats'][5:])

    def test_bad_global_repair_remains_nonblocking_and_warns(self):
        f,s=self.fixture()
        issue='{"issues":[{"index":-1,"reason":"The global clock is compressed."}]}'
        writer=Mock(side_effect=[issue,'{"beats":[]}',issue])
        with tempfile.TemporaryDirectory() as tmp:
            result,audit=review_film({}, {'screenplay_repair_rounds':1},s,f,writer,[],tmp,parse_film)
        self.assertEqual(result,f);self.assertEqual(audit['status'],'warnings')
        self.assertFalse(audit['repairs'][0]['accepted']);self.assertEqual(writer.call_count,3)

if __name__=='__main__':unittest.main()
