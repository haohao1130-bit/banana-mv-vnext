"""Regression tests for global screenplay QA and local repair."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from banana_mv.screenplay_review import audit_and_repair


def clip(index, event):
    return {'index':index,'mode':'story','handoff_version':1,'event':event}


class ScreenplayReviewTests(unittest.TestCase):
    def test_only_flagged_clip_is_replaced_then_whole_script_is_rechecked(self):
        original=[
            clip(0,'Opening state: The bell rings. New progression: The champion presses forward and lands two clean jabs. Outgoing state: The challenger is cornered.'),
            clip(1,'Opening state: The champion is staggering. New progression: The challenger wins immediately. Outgoing state: The champion is down.'),
            clip(2,'Opening state: The challenger is exhausted. New progression: She sees a weakness and prepares a feint. Outgoing state: The trap is ready.'),
        ]
        replacement=('Opening state: The challenger remains cornered by the champion. '
                     'New progression: She absorbs his pressure, blocks another jab and '
                     'starts noticing a weakness in his guard. Outgoing state: The champion '
                     'still controls the ring while she has identified the opening.')
        calls=[]
        def rewrite(cfg,system,parts,token):
            data=json.loads(parts[0][1]);calls.append((system,data))
            if len(calls)==1:
                return json.dumps({'issues':[{'index':1,'reason':'does not inherit prior pressure and resolves too early'}]})
            if len(calls)==2:
                return replacement
            if len(calls)==3:
                self.assertEqual(data['clips'][0]['event'],original[0]['event'])
                self.assertEqual(data['clips'][1]['event'],replacement)
                self.assertEqual(data['clips'][2]['event'],original[2]['event'])
                return '{"issues":[]}'
            raise AssertionError('unexpected extra 9B call')
        task={'brief':'Champion dominates the middle, challenger reverses at the end.',
              'timeline':[{'index':i,'start':i*15,'seconds':15} for i in range(3)]}
        with tempfile.TemporaryDirectory() as root:
            rows,audit=audit_and_repair({}, {'vnext_preproduction':True},task,'stable setup',
                'Challenger wins in the final scene.',original,rewrite,root,[])
            self.assertEqual(len(calls),3)
            self.assertEqual([r['event'] for r in rows],
                [original[0]['event'],replacement,original[2]['event']])
            self.assertEqual(audit['status'],'passed')
            self.assertEqual(audit['rounds'],2)
            self.assertEqual(audit['repairs'][0]['index'],1)
            saved=json.loads((Path(root)/'screenplay_review.json').read_text())
            self.assertEqual(saved['status'],'passed')

    def test_persistent_issue_warns_but_keeps_usable_script(self):
        original=[clip(0,'Opening state: Set. New progression: The champion attacks. Outgoing state: Challenger retreats.')]
        candidate=('Opening state: The challenger is retreating. New progression: '
                   'The champion continues pressing, forcing another defensive step. '
                   'Outgoing state: The challenger remains under severe pressure.')
        outputs=[json.dumps({'issues':[{'index':0,'reason':'needs stronger causal link'}]}),
                 candidate,json.dumps({'issues':[{'index':0,'reason':'still weak'}]})]
        writer=Mock(side_effect=outputs)
        task={'brief':'A boxing match','timeline':[{'index':0,'start':0,'seconds':15}]}
        with tempfile.TemporaryDirectory() as root:
            rows,audit=audit_and_repair({}, {'vnext_preproduction':True,'screenplay_repair_rounds':1},
                task,'','',original,writer,root,[])
            self.assertEqual(rows[0]['event'],candidate)
            self.assertEqual(audit['status'],'warnings')
            self.assertEqual(writer.call_count,3)

    def test_invalid_review_keeps_original_script_and_records_failure(self):
        original=[clip(0,'Opening state: Ready. New progression: The bell rings. Outgoing state: The match begins.')]
        task={'brief':'Boxing','timeline':[{'index':0,'start':0,'seconds':15}]}
        with tempfile.TemporaryDirectory() as root:
            rows,audit=audit_and_repair({}, {'vnext_preproduction':True},task,'','',original,
                Mock(return_value='unparseable'),root,[])
            self.assertEqual(rows,original)
            self.assertEqual(audit['status'],'review_failed_open')
            self.assertTrue((Path(root)/'screenplay_review.json').exists())


if __name__=='__main__':
    unittest.main()
