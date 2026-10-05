"""Synthetic tests for reference preparation; no model-quality claims or APIs."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.audit_ragas_references import DRAFT_SHA256, METRICS, build_candidates, export_review
from scripts.export_ragas_reference_context import INDEX_SHA256
from scripts.prepare_ragas import GOLDEN_BLOB, canonical_digest, select_questions
from test_ragas_preparation import fixture_rows


class ReferenceAuditTests(unittest.TestCase):
    def setUp(self):
        self.golden = fixture_rows()
        selected = select_questions(self.golden)
        self.packet = {'golden_git_blob': GOLDEN_BLOB, 'golden_semantic_sha256': canonical_digest(self.golden),
                       'index_sha256': INDEX_SHA256, 'selection_seed': 'fixture', 'questions': []}
        self.drafts = {k: v for k, v in self.packet.items() if k != 'questions'}
        self.drafts['questions'] = []
        self.spec = {'protocol': 'ragas20-source-review-spec-v1', 'required_metrics': METRICS.copy(),
                     'human_approval': {'status': 'pending', 'reviewed_by': None}, 'paid_execution_authorized': False,
                     'original_drafts_sha256': DRAFT_SHA256, 'index_sha256': INDEX_SHA256,
                     'golden_git_blob': GOLDEN_BLOB, 'source_commit': 'fixture',
                     'requirement_confirmation': {'source': 'fixture'}, 'assistant_review_notes': {},
                     'reference_replacements': {}, 'supplementary_reference_chunks': {}, 'source_anchors': {}}
        self.context = []
        for row in selected:
            cid = row['gold_chunk_ids'][0]
            text = 'Fixture source evidence for ' + row['id'] + '.'
            evidence = {'chunk_id': cid, 'source_id': 'fixture-source', 'text': text,
                        'text_sha256': hashlib.sha256(text.encode()).hexdigest()}
            self.packet['questions'].append({'id': row['id'], 'user_input': row['question'],
                'gold_chunk_ids': row['gold_chunk_ids'].copy(), 'gold_source_ids': row['gold_source_ids'].copy(),
                'gold_evidence': [evidence]})
            self.drafts['questions'].append({'id': row['id'], 'supporting_chunk_ids': row['gold_chunk_ids'].copy(),
                                            'reference_draft': 'Fixture answer.'})
            self.spec['assistant_review_notes'][row['id']] = 'Fixture note, not human approval.'
            self.spec['source_anchors'][cid] = text

    def run_build(self):
        return build_candidates(self.spec, self.drafts, self.packet, self.context, self.golden)

    def test_deterministic_and_inputs_unchanged(self):
        before = copy.deepcopy((self.spec, self.drafts, self.packet, self.context, self.golden))
        one = self.run_build()
        self.assertEqual(one, self.run_build())
        self.assertEqual(len(one['questions']), 20)
        self.assertEqual(before, (self.spec, self.drafts, self.packet, self.context, self.golden))
        self.assertIsNone(one['scores'])
        self.assertEqual(one['human_approval']['status'], 'pending')
        self.assertFalse(one['paid_execution_authorized'])

    def test_missing_required_metric_rejected(self):
        self.spec['required_metrics'].pop()
        with self.assertRaisesRegex(ValueError, 'four'):
            self.run_build()

    def test_human_approval_not_inferred(self):
        self.spec['human_approval'] = {'status': 'approved', 'reviewed_by': 'invented'}
        with self.assertRaisesRegex(ValueError, 'human approval'):
            self.run_build()

    def test_paid_execution_not_authorized(self):
        self.spec['paid_execution_authorized'] = True
        with self.assertRaisesRegex(ValueError, 'paid execution'):
            self.run_build()

    def test_changed_question_rejected(self):
        self.packet['questions'][0]['user_input'] += ' changed'
        with self.assertRaisesRegex(ValueError, 'Question text'):
            self.run_build()

    def test_changed_gold_labels_rejected(self):
        self.packet['questions'][0]['gold_chunk_ids'].append('new-label')
        with self.assertRaisesRegex(ValueError, 'Golden labels'):
            self.run_build()

    def test_changed_source_bytes_rejected(self):
        self.packet['questions'][0]['gold_evidence'][0]['text'] += ' changed'
        with self.assertRaisesRegex(ValueError, 'text hash'):
            self.run_build()

    def test_missing_anchor_rejected(self):
        cid = self.packet['questions'][0]['gold_chunk_ids'][0]
        self.spec['source_anchors'][cid] = 'not in original evidence'
        with self.assertRaisesRegex(ValueError, 'anchor not found'):
            self.run_build()

    def test_empty_reference_rejected(self):
        self.spec['reference_replacements'][self.packet['questions'][0]['id']] = ' '
        with self.assertRaisesRegex(ValueError, 'Empty reference'):
            self.run_build()

    def test_other_source_supplement_rejected(self):
        qid = self.packet['questions'][0]['id']
        self.spec['supplementary_reference_chunks'][qid] = ['extra']
        self.spec['source_anchors']['extra'] = 'Fixture extra'
        self.context = [{'chunk_id': 'extra', 'source_id': 'wrong-source', 'text': 'Fixture extra',
                         'text_sha256': hashlib.sha256(b'Fixture extra').hexdigest()}]
        with self.assertRaisesRegex(ValueError, 'same original source'):
            self.run_build()

    def test_same_source_supplement_does_not_change_gold(self):
        qid = self.packet['questions'][0]['id']
        self.spec['supplementary_reference_chunks'][qid] = ['extra']
        self.spec['source_anchors']['extra'] = 'Fixture extra'
        self.context = [{'chunk_id': 'extra', 'source_id': 'fixture-source', 'text': 'Fixture extra',
                         'text_sha256': hashlib.sha256(b'Fixture extra').hexdigest()}]
        result = self.run_build()
        row = result['questions'][0]
        self.assertEqual(row['gold_chunk_ids'], self.packet['questions'][0]['gold_chunk_ids'])
        self.assertNotIn('extra', row['gold_chunk_ids'])
        self.assertEqual(row['support_checks'][-1]['role'], 'reference_only_supplement')

    def test_existing_output_not_overwritten(self):
        result = self.run_build()
        evidence = {e['chunk_id']: e for q in self.packet['questions'] for e in q['gold_evidence']}
        with tempfile.TemporaryDirectory() as d:
            export_review(result, evidence, Path(d))
            before = (Path(d) / 'ragas20_reference_candidates.json').read_bytes()
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                export_review(result, evidence, Path(d))
            self.assertEqual(before, (Path(d) / 'ragas20_reference_candidates.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
