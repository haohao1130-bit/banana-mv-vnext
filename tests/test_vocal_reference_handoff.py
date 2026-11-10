import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from banana_mv.whole_film import _present_exit_state, SPINE_SYSTEM, CHAPTER_SYSTEM
from banana_mv.whole_film_review import ticket_chapter
from banana_mv.recipe_advice import advise

class VocalHandoffTests(unittest.TestCase):
    def test_ms_evidence_overrides_wrong_but_valid_chapter(self):
        chapters=[{'start_ms':i*10000,'end_ms':(i+1)*10000} for i in range(6)]
        for text,wrong,want in [('shot_2 at 10000ms',3,1),('shot_23 at 52500 ms',4,5),('shot_23 (52.5s)',4,5),('證據 52500毫秒',4,5)]:
            self.assertEqual(ticket_chapter({'reason':text,'target_chapter':wrong},chapters),want)
        self.assertEqual(ticket_chapter({'reason':'no clock','target_chapter':2},chapters),2)
    def test_result_and_actor_states_survive_without_action_recap(self):
        value={'scene_states':{'ring':{'character_states':{'B':{'pose':'down','physical_condition':'breathing','action':'PUNCH_REPLAY'}},'established_facts':['Contest ended','Bell has rung'],'future_goal':'WIN_AGAIN'}}}
        result=_present_exit_state(value)
        self.assertEqual(result['scene_states']['ring']['character_states']['B']['pose'],'down')
        self.assertEqual(result['scene_states']['ring']['established_facts'],['Contest ended','Bell has rung'])
        self.assertNotIn('PUNCH_REPLAY',json.dumps(result));self.assertNotIn('WIN_AGAIN',json.dumps(result))
        self.assertEqual(_present_exit_state('legacy prose'),{})
    def test_vocal_policy_reaches_macro_and_chapter(self):
        for system in (SPINE_SYSTEM,CHAPTER_SYSTEM):
            self.assertIn('not speaker identity or gender',system)
            self.assertIn('never automatically anchor the finale',system)
            self.assertIn('not one beat per lyric cue',system)
    def test_advice_persists_evidence_without_modifying_recipe(self):
        from test_chained_whole_film import beat
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'preproduction';folder.mkdir()
            source={'brief':'Only boxing','duration_ms':10000,'srt_cues':[], 'creative_contract':{'relationship_evidence':[]}}
            film={'subject_definitions':'[]','authoring_chapters':[{'start_ms':0,'end_ms':10000}], 'beats':[beat(0,'A','Boxing continues.')]}
            (folder/'whole_film_input.json').write_text(json.dumps({'source':source}))
            path=folder/'whole_film.json';path.write_text(json.dumps({'film':film}));before=path.read_bytes()
            writer=Mock(return_value='{"issues":[]}')
            result=advise(tmp,{},writer,'Check continuity')
            self.assertEqual(path.read_bytes(),before)
            self.assertFalse(result['recipe_changed']);self.assertEqual(writer.call_count,1)
            self.assertTrue(list(folder.glob('advice_*/advice.json')))
            self.assertIn('Check continuity',writer.call_args.args[2][0][1])


class AdviceServerTests(unittest.TestCase):
    def test_advice_request_preserves_ready_revision_and_releases_lock(self):
        import copy
        import threading
        from banana_mv import server
        state={'id':'test','status':'plan_ready','plan_revision':'unchanged','request':{}}
        lock=threading.Lock()
        def save(value):
            state.clear();state.update(copy.deepcopy(value))
        class InlineThread:
            def __init__(self,target,**kwargs):self.target=target
            def start(self):self.target()
        with patch.object(server,'GPU_LOCK',lock), patch.object(server,'read_state',side_effect=lambda _:copy.deepcopy(state)), patch.object(server,'write_state',side_effect=save), patch.object(server.backend,'load_config',return_value={}), patch.object(server,'job_dir',return_value=Path('/unused')), patch.object(server.threading,'Thread',InlineThread), patch('banana_mv.recipe_advice.advise',side_effect=RuntimeError('Model unavailable')):
            server.request_recipe_advice('test','Check stage')
        self.assertFalse(lock.locked())
        self.assertEqual(state['status'],'plan_ready')
        self.assertEqual(state['plan_revision'],'unchanged')
        self.assertEqual(state['recipe_advice']['status'],'error')
