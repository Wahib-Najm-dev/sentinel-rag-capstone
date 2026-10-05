"""Real ragas==0.4.3 metric execution with mock HTTP and mock E5 vectors only.

Fixture numbers are NOT SentinelRAG results. No socket/model/API is used.
"""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.ragas_execution import Ledger, METRICS, score_records
from scripts.ragas_cohere import CohereJudge, E5Embeddings, create_metrics, validate_binary_fields


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Ledger(Path(self.temp.name)/'fixture.sqlite3', {'fixture':True}, 12, interval=0)
        self.sent = []
        self.precision = 0
        self.mode = 'normal'
        self.judge = CohereJudge(self.state, self.send, 'command-r7b-12-2024')
        self.emb = E5Embeddings(self.state, lambda text: [1.0]+[0.0]*383, 'fixture-only-not-a-real-model')

    def tearDown(self): self.temp.cleanup()

    def send(self, payload):
        self.sent.append(payload)
        self.assertEqual(payload['response_format'], {'type':'json_object'})
        self.assertNotIn('documents', payload)
        schema = json.loads(payload['messages'][-1]['content'].split('JSON_SCHEMA=')[-1])
        title = schema['title']
        if title == 'StatementGeneratorOutput':
            reply = {'statements':['Alpha.', 'Beta.']}
        elif title == 'NLIStatementOutput':
            reply = {'statements': [dict(statement=s,reason='fixture only',verdict=v)
                                   for s,v in [('Alpha.',1),('Beta.',0)]]}
            if self.mode == 'omitted': reply['statements'].pop()
        elif title == 'AnswerRelevanceOutput':
            reply = {'question':'Fixture generated question?', 'noncommittal':0}
        elif title == 'ContextPrecisionOutput':
            reply = {'reason':'fixture only','verdict': self.precision % 2}
            self.precision += 1
        elif title == 'ContextRecallOutput':
            reply = {'classifications':[dict(statement='Alpha.',reason='fixture only',attributed=1),
                                        dict(statement='Beta.',reason='fixture only',attributed=0)]}
        else:
            self.fail('Unexpected actual Ragas schema: ' + title)
        return {'finish_reason':'MAX_TOKENS' if self.mode == 'truncated' else 'COMPLETE',
                'message':{'content':[{'type':'text','text':json.dumps(reply)}]},
                'usage':{'billed_units':{'input_tokens':1,'output_tokens':1}}}

    def test_all_four_real_metrics_and_resume_without_network(self):
        row={'id':'q01','user_input':'Fixture question?', 'response':'Alpha. Beta.',
             'retrieved_contexts':['First fixture.', 'Second fixture.'], 'retrieved_chunk_ids':['f1','f2']}
        refs={'q01': {'user_input':'Fixture question?', 'reference':'Alpha. Beta.'}}
        metrics=create_metrics(self.judge, self.emb)
        with patch('socket.socket.connect', side_effect=AssertionError('Network forbidden in offline tests')):
            report=asyncio.run(score_records([row],refs,metrics,self.judge,self.state))
            asyncio.run(score_records([row],refs,metrics,self.judge,self.state))
        values=report['questions'][0]['metrics']
        for name,value in zip(METRICS,[.5,1.0,.5,.5]):
            self.assertAlmostEqual(values[name]['value'],value)
        self.assertEqual(len(self.sent),8)  # 2 + 3 + 2 contexts + 1
        self.assertEqual(report['completed_questions'],1)
        self.assertEqual(report['status'],'partial')
        draws=[p for p in self.sent if 'AnswerRelevanceOutput' in p['messages'][-1]['content']]
        self.assertEqual(len(draws),3)

    def test_replay_partial_metric_uses_persisted_subcalls(self):
        metric=create_metrics(self.judge,self.emb)['Faithfulness']
        self.judge.begin('q01','Faithfulness')
        asyncio.run(metric.ascore(user_input='q',response='Alpha. Beta.',retrieved_contexts=['c']))
        self.judge.begin('q01','Faithfulness')
        asyncio.run(metric.ascore(user_input='q',response='Alpha. Beta.',retrieved_contexts=['c']))
        self.assertEqual(len(self.sent),2)

    def test_truncated_output_is_not_a_score(self):
        self.mode='truncated'
        self.judge.begin('q01','Faithfulness')
        metric=create_metrics(self.judge,self.emb)['Faithfulness']
        with self.assertRaises(ValueError):
            asyncio.run(metric.ascore(user_input='q',response='a',retrieved_contexts=['c']))
        self.assertEqual(len(self.sent),1)

    def test_omitted_statement_judgment_rejected(self):
        self.mode='omitted'
        self.judge.begin('q01','Faithfulness')
        metric=create_metrics(self.judge,self.emb)['Faithfulness']
        with self.assertRaises(ValueError):
            asyncio.run(metric.ascore(user_input='q',response='a',retrieved_contexts=['c']))

    def test_bad_vector_rejected_without_paid_embedding_fallback(self):
        emb=E5Embeddings(self.state,lambda text:[0.0]*384,'fixture-zero')
        with self.assertRaises(ValueError): emb.embed_text('q')
        self.assertEqual(self.state.count(),0)

    def test_nonbinary_verdict_rejected(self):
        for bad in (2,-1,True,'1',1.0):
            with self.assertRaises(ValueError): validate_binary_fields({'verdict':bad})


if __name__ == '__main__': unittest.main()
