import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from banana_mv.creative_contract import creative_contract
from banana_mv.whole_film import _chapter_source, parse_film, compile_window
from banana_mv.whole_film_review import review_film, COMMISSION_SYSTEM
from test_chained_whole_film import beat, chapter

CUE='一場熱血的搖滾演唱會，與小語挑戰拳王的激烈拳擊比賽交錯進行。舞台小語是唯一主唱，擂台小語不演唱。最終小語打出致勝一拳。'

class CommissionTests(unittest.TestCase):
    def source(self):
        return {'brief':CUE,'creative_contract':creative_contract(CUE),'duration_ms':58500,
                'srt_cues':[],'authoring_chapters':[chapter(a,b,'Develop current events.') for a,b in
                [(0,15000),(15000,30000),(30000,45000),(45000,58500)]]}
    def film(self):
        return {'subject_definitions':'<Subject 1> is stage singer and ring challenger from <Picture 1>.',
                'beats':[beat(t,'s'+str(i),'Concert opening.' if i==0 else 'A new ring exchange.')
                         for i,t in enumerate([0,15000,30000,45000])]}
    def test_missing_strand_ticket_repairs_only_named_chapter_then_full_recheck(self):
        source=self.source();film=self.film();original=copy.deepcopy(film)
        replacement=[dict(film['beats'][1],action='A fresh ring exchange.'),
                     dict(beat(21000,'stage_return','The singer performs on stage.'),mode='performance'),
                     beat(24000,'ring_return','The challenger continues the established guard.')]
        ticket={'target_chapter':1,'reason':'「交錯進行」: stage exists at 0s only; ring fills 15–58.5s without a stage return.',
                'repair_instruction':'Develop stage performance and cut back to the ongoing ring action inside chapter 1.'}
        writer=Mock(side_effect=[json.dumps({'issues':[ticket]}),json.dumps({'beats':replacement}),'{"issues":[]}'])
        with tempfile.TemporaryDirectory() as tmp:
            result,audit=review_film({}, {},source,film,writer,[],tmp,parse_film)
            self.assertEqual(audit['status'],'passed');self.assertEqual(writer.call_count,3)
            self.assertEqual(result['beats'][0],original['beats'][0])
            self.assertEqual(result['beats'][-2:],original['beats'][-2:])
            repair=writer.call_args_list[1]
            payload=json.loads(repair.args[2][0][1])
            self.assertEqual(payload['target_chapter'],1)
            self.assertEqual(payload['editable_range']['start_ms'],15000)
            self.assertEqual(payload['editable_range']['end_ms_exclusive'],30000)
            self.assertEqual(audit['repairs'][0]['scope'],'chapter')
            self.assertIn('commission_review_01',list(Path(tmp,'preproduction').glob('commission_review_01*'))[0].name)
            prompt,_=compile_window(result,{'index':1,'start':15,'seconds':15})
            self.assertIn('At 00:06.000',prompt)
            self.assertIn('[Shot 3]',prompt)
            self.assertNotIn('GLOBAL',repair.args[1].splitlines()[0])
    def test_unequal_irregular_intercut_passes_without_forced_repair(self):
        film=self.film();film['beats'].insert(2,beat(29000,'stage','The singer performs.'))
        writer=Mock(return_value='{"issues":[]}')
        with tempfile.TemporaryDirectory() as tmp:
            result,audit=review_film({}, {},self.source(),film,writer,[],tmp,parse_film)
        self.assertEqual(audit['status'],'passed');self.assertEqual(result,film);self.assertEqual(writer.call_count,1)
        self.assertIn('equal time',COMMISSION_SYSTEM)
    def test_single_strand_contract_does_not_invent_a_concert(self):
        contract=creative_contract('小語挑戰拳王，最終擊倒拳王。')
        self.assertEqual(contract['relationship_evidence'],[])
        self.assertNotIn('演唱會',json.dumps(contract,ensure_ascii=False))
    def test_cross_chapter_keeps_contract_without_full_brief_or_future_chapters(self):
        source=self.source();source['creative_contract']['macro_summary']='Stage singer and ring fighter intercut; separate timed views, no split-screen.'
        spine={'subject_definitions':self.film()['subject_definitions'],'creative_contract':source['creative_contract']['macro_summary']}
        payload=_chapter_source(source,spine,source['authoring_chapters'][1])
        self.assertNotIn('brief',payload);self.assertNotIn('authoring_chapters',payload)
        self.assertIn('交錯',payload['creative_contract']['relationship_evidence'][0])
        self.assertIn('no split-screen',payload['creative_contract']['macro_summary'])
    def test_invalid_ticket_is_warning_not_pass_or_global_rewrite(self):
        writer=Mock(return_value='{"issues":[{"target_chapter":99,"reason":"missing strand","repair_instruction":"rewrite all"}]}')
        with tempfile.TemporaryDirectory() as tmp:
            result,audit=review_film({}, {'review_format_retries':0},self.source(),self.film(),writer,[],tmp,parse_film)
        self.assertEqual(audit['status'],'review_failed_open');self.assertEqual(audit['repairs'],[])
        self.assertEqual(result,self.film())
    def test_macro_contract_reaches_chapters_and_changes_cache_fingerprint(self):
        from banana_mv.whole_film import ensure_film
        from test_chained_whole_film import script,chunks
        import test_shoot_plan as fixtures
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req.update(prompt=CUE,screenplay_review=False,srt_cues=[])
            spine=script();spine['creative_contract']='Active strands: stage singer and ring challenger. Intercut their development. No split-screen; separate timed shots. End with the commissioned winning punch.'
            a,b=chunks();writer=Mock(side_effect=[json.dumps(spine),json.dumps(a),json.dumps(b)])
            segs=[dict(index=i,start=x,seconds=y) for i,(x,y) in enumerate([(0,15),(15,15),(30,15),(45,13.5)])]
            ensure_film(cfg,req,segs,images,root,writer)
            local=json.loads(writer.call_args_list[1].args[2][0][1])
            self.assertEqual(local['source']['creative_contract']['macro_summary'],spine['creative_contract'])
            self.assertNotIn('brief',local['source'])
            saved=json.loads((root/'preproduction/whole_film.json').read_text())
            self.assertEqual(saved['version'],6)
            self.assertEqual(len(saved['film']['authoring_chapters']),2)
            self.assertTrue((root/'preproduction/creative_contract.json').exists())
            # Resume reuses its persisted master and leaves old checkpoints alone.
            writer.reset_mock();ensure_film(cfg,req,segs,images,root,writer)
            writer.assert_not_called()
    def test_shot_number_and_wrong_chapter_follow_evidence_clock(self):
        from banana_mv.whole_film_review import ticket_chapter
        chapters=self.source()['authoring_chapters']
        for n in (0,8):
            self.assertEqual(ticket_chapter({'target_chapter':n,'reason':'shot_9 at 38.84s has a mismatched state.'},chapters),2)
        self.assertEqual(ticket_chapter({'target_chapter':0,'evidence_at_ms':50500,'reason':'state conflict'},chapters),3)
    def test_chapter_zero_accepts_local_beats_from_oversized_repair(self):
        source=self.source();film=self.film();fixed=copy.deepcopy(film['beats'])
        fixed[0]['filming_prompt']='A single stage close-up shows the singer.'
        fixed[-1]['action']='UNREQUESTED FUTURE CHANGE'
        ticket={'target_chapter':0,'reason':'The opening view combines locations at 0s.',
                'repair_instruction':'Separate current locations without altering later chapters.'}
        writer=Mock(side_effect=[json.dumps({'issues':[ticket]}),json.dumps({'beats':fixed}),'{"issues":[]}'])
        with tempfile.TemporaryDirectory() as tmp:
            result,audit=review_film({}, {},source,film,writer,[],tmp,parse_film)
        self.assertEqual(audit['status'],'passed')
        self.assertEqual(result['beats'][1:],film['beats'][1:])
        self.assertEqual(audit['repairs'][0]['ignored_outside_range'],3)
        self.assertNotEqual(result['beats'][0],film['beats'][0])
