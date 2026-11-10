"""Regression checks for bounded upstream macro/chapter authoring."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from banana_mv.whole_film import (_validated_spine, _validated_chapter,
                                  _json_object, ensure_film)
import test_shoot_plan as fixtures


DURATION=58500


def chapter(start,end,goal):
    return {'start_ms':start,'end_ms':end,'goal':goal,
            'entry':'Continue from established scene state.',
            'exit_target':'Hand off the current physical state.'}


def beat(at,shot,action):
    return {'at_ms':at,'shot_id':shot,'state':'The adult performer is beside the railing.',
            'continuation_state':'The performer remains beside the railing.',
            'camera':'Medium view, eye level.',
            'ongoing_camera':'Continue the established medium view.',
            'action':action,'ongoing':'The performer keeps moving.',
            'mode':'action',
            'filming_prompt':'<Subject 1> moves naturally beside the railing in a medium view; the camera tracks sideways at eye level under warm backlighting.',
            'ongoing_filming_prompt':'In the continuing eye-level medium view, <Subject 1> maintains established movement without repeating the entrance.'}


def script():
    return {'subject_definitions':'<Subject 1> is the adult performer bound to <Picture 1>.',
            'chapters':[chapter(0,30000,'The performer establishes the conflict.'),
                        chapter(30000,DURATION,'The consequence reaches the commissioned ending.')]}


def chunks():
    first={'beats':[beat(0,'s1','The performer begins the conflict.')],
           'exit_state':{'location':'railing','pose':'moving','props':[]}}
    second={'beats':[beat(30000,'s1','The performer reacts to the next event.')],
            'exit_state':{'location':'railing','pose':'standing','props':[]}}
    return first,second


class ChainedFilmTests(unittest.TestCase):
    def test_spine_requires_full_coverage_and_chapter_handoff(self):
        spine=_validated_spine(script(),DURATION)
        self.assertEqual(spine['chapters'][-1]['end_ms'],DURATION)
        a,b=chunks()
        self.assertEqual(_validated_chapter(a,spine,spine['chapters'][0])['exit_state']['pose'],'moving')
        with self.assertRaises(ValueError):
            broken=script()
            broken['chapters'][1]['start_ms']=30001
            _validated_spine(broken,DURATION)
        with self.assertRaises(ValueError):
            malformed=dict(b,beats=[beat(29999,'s1','An early duplicate.')])
            _validated_chapter(malformed,spine,spine['chapters'][1])
        self.assertEqual(_json_object('```json\n{"beats":[]}\n```')['beats'],[])

    def test_full_song_chained_calls_and_saved_master_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req.update(authoring_mode='chained',screenplay_review=False)
            segments=[{'index':i,'start':float(i*10),
                       'seconds':10.0 if i<5 else 8.5} for i in range(6)]
            part_a,part_b=chunks()
            responses=[json.dumps(script()),json.dumps(part_a),json.dumps(part_b)]
            writer=Mock(side_effect=responses)
            plan=ensure_film(cfg,req,segments,images,root,writer)
            self.assertEqual(writer.call_count,3)
            self.assertEqual(plan['ending_contract']['end_time'],58.5)
            payload=json.loads(writer.call_args_list[2].args[2][0][1])
            self.assertEqual(payload['previous_exit_state'],part_a['exit_state'])
            self.assertEqual(payload['chapter']['start_ms'],30000)
            saved=json.loads((root/'preproduction/whole_film.json').read_text())
            self.assertEqual([x['at_ms'] for x in saved['film']['beats']],[0,30000])
            self.assertEqual(json.loads((root/'preproduction/whole_film_generation.json').read_text())['mode'],'chained')
            ensure_film(cfg,req,segments,images,root,writer)
            self.assertEqual(writer.call_count,3)

    def test_bad_chapter_retries_only_that_chapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req.update(authoring_mode='chained',screenplay_review=False,rewrite_retries=1)
            segments=[{'index':i,'start':float(i*10),
                       'seconds':10.0 if i<5 else 8.5} for i in range(6)]
            part_a,part_b=chunks()
            writer=Mock(side_effect=[json.dumps(script()),json.dumps(part_a),
                                     json.dumps({'beats':[]}),json.dumps(part_b)])
            ensure_film(cfg,req,segments,images,root,writer)
            self.assertEqual(writer.call_count,4)
            self.assertTrue((root/'preproduction/whole_film_chapter_00.json').is_file())
            self.assertTrue((root/'preproduction/whole_film_chapter_01.json').is_file())


if __name__=='__main__':
    unittest.main()
