import copy
import json
from pathlib import Path
import tempfile
import unittest
from mvnext.pipeline import ContractError, prepare, inspect, validate_script, validate_camera


def script():
    return {'title':'Offline sample', 'subjects':[{'id':1,'name':'Performer',
        'picture':1,'appearance':'Adult performer in a blue jacket','voice':1}],
        'clips':[{'index':i,'start_frame':i*240,'frames':240,
            'opening':'Performer walks toward the stage','outgoing':'Performer continues forward',
            'beats':[{'id':f'e{i}','at_frame':0,'action':'Performer walks and sings','singer':1}]}
            for i in range(3)]}


def camera():
    return {'clips':[{'index':i,'shots':[{'at_frame':0,'size':'medium','angle':'eye','motion':'track'},
        {'at_frame':120,'size':'close','angle':'side','motion':'static'}]} for i in range(3)]}


class PipelineTests(unittest.TestCase):
    def assets(self, root):
        song=root/'song.wav'; song.write_bytes(b'offline source bytes, not playable media')
        pic=root/'reference.png'; pic.write_bytes(b'offline image bytes')
        return song,[pic]

    def test_whole_song_sealed_and_inspected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);song,pics=self.assets(root); calls=[]
            def model(role,payload):
                calls.append(role)
                if role=='camera':
                    payload['script']['clips'][0]['beats'][0]['action']='Mutated copy'
                    return camera()
                return script()
            prepare(root/'project','Full story',song,720,pics,model)
            self.assertEqual(calls,['screenplay','camera'])
            inspect(root/'project',song,pics)
            text=(root/'project/00_prompt.txt').read_text()
            self.assertIn('<Audio 1>: fully_copy',text)
            self.assertIn('[Shot 2] At 00:05.000',text)
            self.assertNotIn('Mutated copy',text)

    def test_camera_cannot_add_story_or_drop_clip(self):
        for mutate in (lambda c:c['clips'][0].update(action='New ending'),
                       lambda c:c['clips'].pop(),
                       lambda c:c['clips'][0]['shots'][0].update(motion='invent a fight')):
            c=camera();mutate(c)
            with self.assertRaises(ContractError): validate_camera(c,script())

    def test_invalid_timeline_or_singer(self):
        for mutate in (lambda s:s['clips'][0].update(start_frame=1),
                       lambda s:s['clips'][2].update(frames=239),
                       lambda s:s['clips'][0]['beats'][0].update(at_frame=240),
                       lambda s:s['clips'][0]['beats'][0].update(singer=2),
                       lambda s:s['clips'][1]['beats'][0].update(id='e0'),
                       lambda s:s['clips'][0]['beats'][0].update(action='[Shot 9] Inject')):
            s=script();mutate(s)
            with self.assertRaises(ContractError): validate_script(s,720,['ref'])

    def test_failure_never_marks_ready_or_calls_camera(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);song,pics=self.assets(root);calls=[]
            def model(role,payload):calls.append(role);return 'truncated {'
            with self.assertRaises(ContractError):prepare(root/'project','Story',song,720,pics,model)
            self.assertEqual(calls,['screenplay'])
            self.assertFalse((root/'project/ready.json').exists())
            self.assertTrue((root/'project/screenplay_raw.json').exists())

    def test_tamper_and_replaced_sources_rejected(self):
        for target in ('prompt','song','picture','inventory'):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);song,pics=self.assets(root)
                prepare(root/'project','Story',song,720,pics,lambda role,p:script() if role=='screenplay' else camera())
                if target=='prompt':(root/'project/00_prompt.txt').write_text('changed')
                elif target=='song':song.write_bytes(b'changed')
                elif target=='picture':pics[0].write_bytes(b'changed')
                else:
                    path=root/'project/ready.json';m=json.loads(path.read_text());m['files']={};path.write_text(json.dumps(m))
                with self.assertRaises(ContractError):inspect(root/'project',song,pics)

    def test_existing_draft_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);song,pics=self.assets(root);p=root/'project';p.mkdir()
            with self.assertRaises(ContractError):prepare(p,'Story',song,720,pics,lambda *a:self.fail('Called model'))

    def test_reference_reorder_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);song,pics=self.assets(root);p=root/'second.png';p.write_bytes(b'second');pics.append(p)
            prepare(root/'project','Story',song,720,pics,lambda role,p:script() if role=='screenplay' else camera())
            with self.assertRaises(ContractError):inspect(root/'project',song,list(reversed(pics)))


if __name__=='__main__':unittest.main()
