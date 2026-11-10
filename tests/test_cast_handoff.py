import json
import unittest
from banana_mv.whole_film import _chapter_stable_cast, _ongoing_handoff, CHAPTER_SYSTEM
from test_chained_whole_film import beat

class CastHandoffTests(unittest.TestCase):
    def test_actual_macro_field_names_survive_in_early_and_final_chapters(self):
        rows=[{'id':'小語','identity':'成年女性，高馬尾紅絲帶，黑金上衣',
               'duties':'演唱會中演唱原曲；擂台不演唱；在終場鐘聲前打出致勝一拳',
               'scene_duties':'舞台唯一主唱；擂台只交手',
               'reference':'<Picture 1>','outcome':'final victory'},
              {'id':'拳王','identity':'成年男性，黑金拳擊短褲',
               'scene_duties':'不參與演唱；後期被抓住破綻反擊'}]
        for final in (False,True):
            result=json.loads(_chapter_stable_cast(json.dumps(rows,ensure_ascii=False),final=final))
            self.assertEqual(result[0]['identity'],rows[0]['identity'])
            self.assertEqual(result[0]['scene_duties'], '舞台唯一主唱; 擂台只交手')
            self.assertIn('擂台不演唱',result[0]['duties'])
            self.assertNotIn('致勝',result[0]['duties'])
            self.assertEqual(result[1]['scene_duties'],'不參與演唱')
            self.assertNotIn('outcome',result[0])
            self.assertEqual(result[0]['reference'],'<Picture 1>')
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
