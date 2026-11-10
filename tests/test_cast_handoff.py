import json
import unittest
from banana_mv.whole_film import _chapter_stable_cast, _ongoing_handoff, CHAPTER_SYSTEM
from test_chained_whole_film import beat

class CastHandoffTests(unittest.TestCase):
    def test_stable_roles_are_preserved_without_keyword_deletion(self):
        rows=[{'id':'甲','identity':'成年女性，高馬尾紅絲帶，黑金上衣',
               'scene_duties':'舞台唯一主唱；擂台只交手',
               'duties':'最後一句只由甲演唱；高潮段仍由甲演唱；擂台不唱',
               'reference':'<Picture 1>','outcome':'future plot outside stable schema'}]
        for final in (False,True):
            result=json.loads(_chapter_stable_cast(json.dumps(rows,ensure_ascii=False),final=final))
            for k in ('identity','scene_duties','duties','reference'):
                self.assertEqual(result[0][k],rows[0][k])
            self.assertNotIn('outcome',result[0])
    def test_exit_snapshot_drops_free_form_events_but_keeps_each_scene(self):
        from banana_mv.whole_film import _present_exit_state
        raw={'scene_states':{'ring':{'position':'corner','pose':'guard raised',
               'physical_condition':'sweating','props':['gloves'],'action':'COMPLETED_PUNCH'},
               'stage':{'position':'center stage','pose':'standing at microphone'}},
             'chapter_exit_target':'FUTURE_VICTORY','event':'COMPLETED_PUNCH'}
        handoff=_present_exit_state(raw)
        self.assertEqual(handoff['scene_states']['ring']['pose'],'guard raised')
        self.assertNotIn('COMPLETED_PUNCH',json.dumps(handoff))
        self.assertNotIn('FUTURE_VICTORY',json.dumps(handoff))
        self.assertEqual(_present_exit_state('A completed punch hits the opponent.'),{})
    def test_compiled_cast_uses_same_structural_projection_as_chapters(self):
        from test_chained_whole_film import beat
        from banana_mv.whole_film import compile_window
        definitions=json.dumps([{'id':'甲','identity':'adult performer',
            'scene_duties':'最後一句只由甲演唱','outcome':'FUTURE_VICTORY'}],ensure_ascii=False)
        film={'subject_definitions':definitions,'beats':[beat(0,'a','Current event')]}
        prompt,_=compile_window(film,dict(index=0,start=0,seconds=10))
        self.assertIn('最後一句只由甲演唱',prompt)
        self.assertNotIn('FUTURE_VICTORY',prompt)
    def test_handoff_carries_ongoing_result_without_replaying_contact(self):
        b=beat(6080,'A','COMPLETED_CONTACT')
        b.update(state='BEFORE_CONTACT',filming_prompt='REPLAY_CONTACT',
                 continuation_state='Braced against the railing.',ongoing='Breathing while braced.',
                 ongoing_camera='Locked side view.',ongoing_filming_prompt='The locked view holds the braced performer.')
        handoff=_ongoing_handoff(b)
        self.assertEqual(handoff['state'],'Braced against the railing.')
        self.assertEqual(handoff['shot_id'],'A')
        for past in ('COMPLETED_CONTACT','BEFORE_CONTACT','REPLAY_CONTACT'):
            self.assertNotIn(past,json.dumps(handoff))
        self.assertIn('ONE physical location',CHAPTER_SYSTEM)
        self.assertIn('distinct shot_id',CHAPTER_SYSTEM)
