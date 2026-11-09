"""Offline regressions: bounded malformed-output recovery and optional timing QA."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from banana_mv.review_output import parse_review, reviewed_json
from banana_mv.lyrics_reference import excerpt, lyric_conflicts
from banana_mv.screenplay_review import audit_and_repair
from banana_mv.filming_review import review_prompt, SCENE_INSTANCE_POLICY


def row(index,event):return {'index':index,'mode':'story','event':event}
CUES=[{'start':27,'end':28,'text':'Earlier lyric phrase'},
      {'start':54.5,'end':56.58,'text':'Final lyric phrase'}]


class ReviewContractTests(unittest.TestCase):
    def test_fences_trailing_comma_and_string_punctuation(self):
        items,method=parse_review('```json\n{"issues":[{"index":0,"reason":"keep ,} literal",},]}\n```',{0})
        self.assertEqual(items[0]['reason'],'keep ,} literal')
        self.assertEqual(method,'trailing_comma_repair')

    def test_truncation_invalid_schema_and_wrong_scope_never_pass(self):
        for raw in ('{"issues":[', '{"issues":[],"ignored":true}', '{"issues":[1],"issues":[]}',
                    '{"issues":[{"index":true,"reason":"x"}]}',
                    '{"issues":[{"index":2,"reason":"x"}]}'):
            with self.assertRaises(ValueError):parse_review(raw,{0})

    def test_malformed_quote_failure_retries_and_saves_raw(self):
        # Same failure class as job 74d03d795224: unescaped quote inside reason.
        writer=Mock(side_effect=['{"issues":[{"index":0,"reason":"wrong "quote""}]}','{"issues":[]}'])
        with tempfile.TemporaryDirectory() as root:
            issues,audit=reviewed_json('review',{},writer,root,'review',{0})
            self.assertEqual(issues,[]);self.assertEqual(len(audit['attempts']),2)
            self.assertEqual(len(list(Path(root).glob('review_*.txt'))),2)
            self.assertIn('Previous response was invalid',writer.call_args.args[0])

    def test_json_failure_budget_does_not_become_empty_pass(self):
        with tempfile.TemporaryDirectory() as root:
            writer=Mock(return_value='bad')
            issues,audit=reviewed_json('review',{},writer,root,'review',{0},retries=99)
            self.assertIsNone(issues);self.assertEqual(writer.call_count,3)
            self.assertEqual(audit['status'],'review_failed_open')

    def test_optional_srt_no_coverage_requirement_or_untimed_invention(self):
        self.assertEqual(lyric_conflicts('She sings "Final lyric phrase"',[]),[])
        local=excerpt({'srt_cues':CUES},{'start':30,'seconds':15})
        self.assertEqual(local,[])
        self.assertEqual(lyric_conflicts('A silent reaction shot, action continues.',local,all_cues=CUES),[])
        self.assertEqual(lyric_conflicts('The theme is "Final lyric phrase".',local,all_cues=CUES),[])
        self.assertTrue(lyric_conflicts('She sings "Earlier lyric phrase"',local,all_cues=CUES))

    def test_global_local_clock_only_checks_explicit_singing(self):
        local=excerpt({'srt_cues':CUES},{'start':45,'seconds':13.5})
        self.assertEqual(local[0]['clip_start'],9.5)
        bad='detailed_description:\n[Shot 1] She sings <d>[English]Final lyric phrase</d>.\n[Shot 2] At 00:03.000, A reaction.\noverall_soundscape: Source.'
        good=bad.replace('[Shot 1] She sings <d>[English]Final lyric phrase</d>.','[Shot 1] A reaction.').replace('At 00:03.000, A reaction.','At 00:09.500, She sings <d>[English]Final lyric phrase</d>.')
        self.assertTrue(lyric_conflicts(bad,local,shot_clock=True,seconds=13.5,all_cues=CUES))
        self.assertEqual(lyric_conflicts(good,local,shot_clock=True,seconds=13.5,all_cues=CUES),[])

    def test_whole_updated_script_rechecked_after_local_repair(self):
        rows=[row(0,'The dancer finishes the leap.'),row(1,'The dancer repeats that same completed leap.')]
        repaired='Opening state: The dancer is already on the floor. New progression: She rises and turns. Outgoing state: She faces the audience.'
        writer=Mock(side_effect=['{"issues":[{"index":1,"reason":"replays completed leap"}]}',repaired,'{"issues":[]}'])
        task={'brief':'A dance develops continuously.','timeline':[{'index':i,'start':i*10,'seconds':10} for i in range(2)]}
        with tempfile.TemporaryDirectory() as root:
            result,audit=audit_and_repair({}, {'vnext_preproduction':True},task,'','',rows,writer,root,[])
            final=json.loads(writer.call_args.args[2][0][1])
            self.assertEqual(final['clips'][0]['event'],rows[0]['event'])
            self.assertEqual(final['clips'][1]['event'],repaired)
            self.assertEqual(audit['status'],'passed')
            self.assertNotEqual(audit['checks'][0]['screenplay_hash'],audit['checks'][1]['screenplay_hash'])

    def test_distinct_similar_exchanges_are_not_rejected_by_parser(self):
        task={'brief':'Repeated distinct exchanges are intentional.', 'timeline':[{'index':0,'start':0,'seconds':10}]}
        with tempfile.TemporaryDirectory() as root:
            rows,audit=audit_and_repair({}, {'vnext_preproduction':True},task,'','',[row(0,'A new jab, recovery, then another new jab.')],Mock(return_value='{"issues":[]}'),root,[])
            self.assertEqual(audit['status'],'passed')

    def test_camera_scene_issue_repairs_only_current_prompt_then_rechecks(self):
        original='A performer fights on the concert stage.'
        fixed='The stage performer sings; the ring instance continues fighting in the ring.'
        writer=Mock(side_effect=['{"issues":[{"index":1,"reason":"fight moved to stage"}]}',fixed,'{"issues":[]}'])
        payload={'current_clip':{'index':1,'event':'Parallel stage and ring.','local_srt':[]},'duration_seconds':10}
        with tempfile.TemporaryDirectory() as root:
            result,audit=review_prompt({}, {},payload,original,writer,[],root,1)
            self.assertEqual(result,fixed);self.assertEqual(audit['status'],'passed')
            self.assertEqual(writer.call_count,3)
            self.assertIn('SAME source Picture',SCENE_INSTANCE_POLICY)
            self.assertNotIn('whole_screenplay',json.loads(writer.call_args.args[2][0][1]))

    def test_camera_format_failure_retains_renderable_draft_with_warning(self):
        payload={'current_clip':{'index':0,'local_srt':[]},'duration_seconds':10}
        with tempfile.TemporaryDirectory() as root:
            result,audit=review_prompt({}, {},payload,'Original renderable draft.',Mock(return_value='bad'),[],root,0)
            self.assertEqual(result,'Original renderable draft.')
            self.assertEqual(audit['status'],'review_failed_open')
            self.assertTrue(audit['warnings'])

    def test_camera_no_srt_no_singing_runs_normally(self):
        payload={'current_clip':{'index':0,'event':'A chase continues.','local_srt':[]},'duration_seconds':10}
        with tempfile.TemporaryDirectory() as root:
            writer=Mock(return_value='{"issues":[]}')
            result,audit=review_prompt({}, {},payload,'The runner turns a corner.',writer,[],root,0)
            self.assertEqual(audit['status'],'passed')
            self.assertEqual(result,'The runner turns a corner.')
            self.assertEqual(writer.call_count,1)

    def test_camera_repair_does_not_receive_full_source_timeline(self):
        payload={'current_clip':{'index':0,'local_srt':[]},'duration_seconds':10}
        writer=Mock(side_effect=['{"issues":[{"index":0,"reason":"explicit wrong-time singing"}]}','Corrected shot.','{"issues":[]}'])
        with tempfile.TemporaryDirectory() as root:
            review_prompt({}, {'srt_cues':CUES},payload,'Current shot.',writer,[],root,0)
            self.assertEqual(json.loads(writer.call_args_list[0].args[2][0][1])['source_srt'],CUES)
            self.assertNotIn('source_srt',json.loads(writer.call_args_list[1].args[2][0][1]))

    def test_global_failure_has_attempts_warning_and_no_fake_pass(self):
        with tempfile.TemporaryDirectory() as root:
            rows,audit=audit_and_repair({}, {'vnext_preproduction':True},
                {'brief':'A story','timeline':[{'index':0,'start':0,'seconds':10}]},'','',
                [row(0,'Existing usable script.')],Mock(return_value='bad'),root,[])
            self.assertEqual(audit['status'],'review_failed_open')
            self.assertEqual(audit['rounds'],1);self.assertEqual(len(audit['format_attempts'][0]['attempts']),3)
            self.assertTrue(audit['warnings'])


if __name__=='__main__':unittest.main()
