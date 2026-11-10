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


    def test_surplus_chapter_beats_are_safely_clipped_not_fatal(self):
        spine=_validated_spine(script(),DURATION)
        raw={'beats':[beat(30000,'s3','At the chapter boundary.'),
                      beat(0,'s1','Valid opening event.'),
                      beat(10000,'s2','Valid chapter development.'),
                      beat(10000,'s2','Accidental duplicate event.'),
                      beat(32000,'s4','Beyond the chapter, drop this.')],
             'exit_state':{'location':'railing','pose':'moving'}}
        piece=_validated_chapter(raw,spine,spine['chapters'][0])
        self.assertEqual([b['at_ms'] for b in piece['beats']],[0,10000])
        self.assertEqual(piece['beats'][-1]['action'],'Valid chapter development.')
        self.assertEqual(piece['exit_state']['chapter_end_ms'],30000)
        self.assertEqual(piece['exit_state']['chapter_exit_target'],spine['chapters'][0]['exit_target'])
        self.assertEqual(len(raw['beats']),5)  # original model response is untouched

    def test_micro_chapters_are_rebinned_to_requested_segment_edges(self):
        from banana_mv.whole_film import _chapter_boundaries
        segments=[{'index':i,'start':float(i*10),
                   'seconds':10.0 if i<5 else 8.5} for i in range(6)]
        edges=_chapter_boundaries(segments,DURATION)
        self.assertEqual(edges,[0,10000,20000,30000,40000,50000,58500])
        raw={'subject_definitions':script()['subject_definitions'],
             'chapters':[chapter(0,3600,'Opening at 3.6 seconds.'),
                         chapter(3600,7300,'The first reaction.'),
                         chapter(7300,15000,'Consequences follow.'),
                         chapter(15000,35000,'Chorus develops.'),
                         chapter(35000,DURATION,'Resolve at song end.')]}
        aligned=_validated_spine(raw,DURATION,edges)
        self.assertEqual([(c['start_ms'],c['end_ms']) for c in aligned['chapters']],
                         list(zip(edges,edges[1:])))
        self.assertIn('Opening at 3.6 seconds.',aligned['chapters'][0]['goal'])
        self.assertIn('The first reaction.',aligned['chapters'][0]['goal'])
        self.assertIn('Resolve at song end.',aligned['chapters'][-1]['goal'])
        self.assertEqual(aligned['chapters'][0]['start_ms'],0)
        self.assertEqual(aligned['chapters'][-1]['end_ms'],DURATION)



    def test_boolean_ongoing_is_normalized_without_rejecting_valid_json(self):
        spine=_validated_spine(script(),DURATION)
        first=beat(0,'s1','The performer begins the exchange.')
        second=beat(11000,'s2','The performer sidesteps.')
        first['ongoing']=True
        second['ongoing']=False
        output=_validated_chapter({'beats':[first,second],
                                   'exit_state':{'pose':'moving'}},
                                  spine,spine['chapters'][0])
        self.assertEqual(output['beats'][0]['ongoing'],first['action'])
        self.assertEqual(output['beats'][1]['ongoing'],second['action'])
        self.assertIs(first['ongoing'],True)  # leave the raw model data intact

    def test_real_9b_spill_does_not_leak_song_finale_as_chapter_handoff(self):
        spine=_validated_spine(script(),DURATION)
        first=beat(0,'A','The opening jab begins.')
        second=beat(10000,'A','The defense resets.')
        future=beat(54500,'A','The ending knockout lands.')
        for b in (first,second,future):
            b['ongoing']=True
        output=_validated_chapter({'beats':[first,second,future],
                                   'exit_state':'The ending knockout lands.'},
                                  spine,spine['chapters'][0])
        self.assertEqual([b['at_ms'] for b in output['beats']],[0,10000])
        self.assertNotIn('knockout',json.dumps(output['exit_state']))
        self.assertEqual(output['exit_state']['last_visible_state'],
                         second['continuation_state'])

    def test_chapter_prompt_isolates_first_15_seconds_from_final_lyric(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            images,cfg,req=fixtures.ShootPlanTests().fixture(root)
            req.update(authoring_mode='chained',screenplay_review=False,
                       prompt='Opening fight. Save the FINAL VICTORY for the end.',
                       srt_cues=[{'start':0.34,'end':2.9,'text':'Opening jab'},
                                 {'start':13.68,'end':16.08,'text':'Boundary crossing'},
                                 {'start':54.5,'end':56.58,'text':'FINAL VICTORY LYRIC'}])
            segments=[{'index':i,'start':float(i*15),
                       'seconds':15.0 if i<3 else 13.5} for i in range(4)]
            macro={'subject_definitions':script()['subject_definitions'],
                   'chapters':[chapter(0,15000,'Establish the opening.'),
                               chapter(15000,30000,'Make the defense adapt.'),
                               chapter(30000,45000,'Increase the pressure.'),
                               chapter(45000,DURATION,'Resolve at the end.')]}
            pieces=[{'beats':[beat(start,'s1','Advance this chapter.')],
                     'exit_state':{'pose':'in progress'}}
                    for start in (0,15000,30000,45000)]
            writer=Mock(side_effect=[json.dumps(macro)]+[json.dumps(p) for p in pieces])
            ensure_film(cfg,req,segments,images,root,writer)
            payload=json.loads(writer.call_args_list[1].args[2][0][1])
            self.assertEqual(payload['chapter']['start_ms'],0)
            self.assertEqual(payload['chapter']['end_ms'],15000)
            self.assertNotIn('brief',payload['source'])
            self.assertNotIn('lyrics',payload['source'])
            self.assertNotIn('reference_brief',payload['source'])
            self.assertNotIn('ending',payload['source'])
            self.assertEqual(len(payload['spine']['chapters']),1)
            self.assertEqual([c['text'] for c in payload['source']['srt_cues']],
                             ['Opening jab','Boundary crossing'])
            self.assertEqual(payload['source']['srt_cues'][-1]['end'],15.0)
            self.assertNotIn('FINAL VICTORY LYRIC',json.dumps(payload))
            self.assertNotIn('Save the FINAL VICTORY',json.dumps(payload))
            self.assertIn('This chapter ONLY covers 0ms to 15000ms',
                          writer.call_args_list[1].args[1])
            self.assertIn('Do NOT write the ending or climax yet.',
                          writer.call_args_list[1].args[1])
            final_payload=json.loads(writer.call_args_list[4].args[2][0][1])
            self.assertEqual([c['text'] for c in final_payload['source']['srt_cues']],
                             ['FINAL VICTORY LYRIC'])


if __name__=='__main__':
    unittest.main()
