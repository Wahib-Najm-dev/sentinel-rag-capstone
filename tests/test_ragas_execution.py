import asyncio
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from scripts.ragas_execution import (IDS, METRICS, Ledger, BudgetExceeded, UncertainRequest,
    validate_record, references_valid, score_records, score_selected_records, snapshot_report)


class Clock:
    def __init__(self): self.now, self.sleeps = 100.0, []
    def time(self): return self.now
    def sleep(self, n): self.sleeps.append(n); self.now += n


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'eval.sqlite3'
        self.clock = Clock()
        self.ledger = Ledger(self.path, {'test':True}, 3, clock=self.clock.time, sleep=self.clock.sleep)
        self.row = {'id':'q01','user_input':'Fixture question?', 'response':'Fixture answer.',
                    'retrieved_contexts':['Fixture one.', 'Fixture two.'], 'retrieved_chunk_ids':['a','b']}
        self.refs = {'q01': {'user_input':'Fixture question?', 'reference':'Fixture reference.'}}

    def tearDown(self): self.temp.cleanup()

    def test_resume_does_not_repeat_success(self):
        calls = []
        send = lambda p: calls.append(p) or {'answer':1}
        self.ledger.request('k', {'p':1}, send)
        again = Ledger(self.path, {'test':True}, 3, clock=self.clock.time, sleep=self.clock.sleep)
        self.assertEqual(again.request('k', {'p':1}, send), {'answer':1})
        self.assertEqual(len(calls), 1)
        self.assertEqual(again.count(), 1)

    def test_independent_relevancy_draws_keep_distinct_keys(self):
        for i in range(3): self.ledger.request('draw' + str(i), {'same':'prompt'}, lambda _: {'x':1})
        self.assertEqual(self.ledger.count(), 3)

    def test_lifetime_budget_includes_failed_attempts(self):
        def fail(_): raise TimeoutError('fixture')
        with self.assertRaises(TimeoutError): self.ledger.request('a', {}, fail)
        for k in ('b','c'): self.ledger.request(k, {}, lambda _: {})
        with self.assertRaises(BudgetExceeded): self.ledger.request('d', {}, lambda _: self.fail('must not send'))
        self.assertEqual(self.ledger.count(), 3)

    def test_failure_not_silently_retried(self):
        def fail(_): raise TimeoutError('fixture')
        with self.assertRaises(TimeoutError): self.ledger.request('a', {}, fail)
        with self.assertRaises(UncertainRequest): self.ledger.request('a', {}, lambda _: self.fail('retry'))

    def test_reserved_on_crash_is_blocked(self):
        def crash(_): raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.ledger.request('k', {}, crash)
        with self.assertRaises(UncertainRequest): self.ledger.request('k', {}, lambda _: {})

    def test_config_and_budget_change_blocked(self):
        with self.assertRaises(ValueError): Ledger(self.path, {'test':True}, 4)
        with self.assertRaises(ValueError): Ledger(self.path, {'test':False}, 3)

    def test_prompt_change_blocked(self):
        self.ledger.request('k', {'p':1}, lambda _: {})
        with self.assertRaises(ValueError): self.ledger.request('k', {'p':2}, lambda _: {})

    def test_rate_limit_survives_restart(self):
        self.ledger.request('k', {}, lambda _: {})
        again = Ledger(self.path, {'test':True}, 3, clock=self.clock.time, sleep=self.clock.sleep)
        again.request('j', {}, lambda _: {})
        self.assertAlmostEqual(self.clock.sleeps[0], 4.1)

    def test_zero_budget_rejected(self):
        with self.assertRaises(ValueError): Ledger(self.path, {}, 0)

    def test_corpus_path_rejected(self):
        with self.assertRaises(ValueError): Ledger(self.path.with_name('chroma.sqlite3'), {}, 3)

    def test_existing_unrelated_database_rejected(self):
        path = Path(self.temp.name) / 'other.sqlite3'
        with sqlite3.connect(path) as conn:
            conn.execute('CREATE TABLE important(value TEXT)')
        before = path.read_bytes()
        with self.assertRaises(ValueError): Ledger(path, {}, 3)
        self.assertEqual(path.read_bytes(), before)

    def test_checkpoint_immutable(self):
        self.ledger.save('value', {'a':1})
        self.ledger.save('value', {'a':1})
        with self.assertRaises(ValueError): self.ledger.save('value', {'a':2})

    def test_checkpoint_tampering_rejected(self):
        self.ledger.save('value', {'a':1})
        with sqlite3.connect(self.path) as conn: conn.execute("UPDATE values_cache SET body='{}'")
        with self.assertRaises(ValueError): self.ledger.get('value')

    def test_response_tampering_rejected(self):
        self.ledger.request('k', {}, lambda _: {'value':1})
        with sqlite3.connect(self.path) as conn: conn.execute("UPDATE calls SET response='{}'")
        with self.assertRaises(ValueError): self.ledger.request('k', {}, lambda _: {})

    def test_reference_packet_changes_rejected(self):
        with self.assertRaises(ValueError): references_valid({'questions':[]})

    def test_reference_cannot_be_injected_as_context_field(self):
        row = dict(self.row, reference='Not an actual output')
        with self.assertRaises(ValueError): validate_record(row, self.refs)

    def test_wrong_question_rejected(self):
        with self.assertRaises(ValueError): validate_record(dict(self.row, user_input='changed'), self.refs)

    def test_empty_response_rejected(self):
        with self.assertRaises(ValueError): validate_record(dict(self.row, response=''), self.refs)

    def test_duplicate_contexts_ids_rejected(self):
        with self.assertRaises(ValueError): validate_record(dict(self.row, retrieved_chunk_ids=['a','a']), self.refs)

    def test_four_metrics_are_mandatory(self):
        with self.assertRaises(ValueError): asyncio.run(score_records([self.row], self.refs, {}, None, self.ledger))

    def test_scores_are_cached_without_rerunning_metrics(self):
        calls = []
        class Metric:
            async def ascore(self, **kwargs): calls.append(kwargs); return SimpleNamespace(value=.5)
        judge = SimpleNamespace(begin=lambda *args:None)
        metrics = {name: Metric() for name in METRICS}
        report = asyncio.run(score_records([self.row], self.refs, metrics, judge, self.ledger))
        asyncio.run(score_records([self.row], self.refs, metrics, judge, self.ledger))
        self.assertEqual(len(calls), 4)
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['completed_questions'], 1)
        self.assertNotIn('reference', calls[0])
        self.assertNotIn('reference', calls[1])
        self.assertEqual(calls[2]['reference'], 'Fixture reference.')

    def test_selected_subset_scores_without_q01(self):
        row = {'id':'q03','user_input':'Fixture q03?', 'response':'Fixture answer.',
               'retrieved_contexts':['Fixture context.'], 'retrieved_chunk_ids':['x']}
        refs = {'q03': {'user_input':'Fixture q03?', 'reference':'Fixture reference.'}}
        calls = []
        class Metric:
            async def ascore(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(value=.75)
        judge = SimpleNamespace(begin=lambda *args:None)
        metrics = {name: Metric() for name in METRICS}
        report = asyncio.run(score_selected_records([row], refs, metrics, judge, self.ledger, ('q03',)))
        self.assertEqual(report['expected_questions'], 1)
        self.assertEqual(report['completed_questions'], 1)
        self.assertEqual(report['questions'][0]['id'], 'q03')
        self.assertEqual(len(calls), 4)
    def test_nan_never_averaged_as_success(self):
        class BadMetric:
            async def ascore(self, **kwargs): return SimpleNamespace(value=float('nan'))
        judge = SimpleNamespace(begin=lambda *args:None)
        with self.assertRaises(ValueError):
            asyncio.run(score_records([self.row], self.refs, {n:BadMetric() for n in METRICS}, judge, self.ledger))
        report = snapshot_report(self.ledger, [self.row])
        self.assertEqual(report['completed_questions'], 0)
        self.assertIsNone(report['summary']['Faithfulness']['mean_over_valid'])


if __name__ == '__main__': unittest.main()
