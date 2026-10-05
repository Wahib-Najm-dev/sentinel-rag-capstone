"""Offline tests use synthetic SQLite fixtures, never real API/model scores."""
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_ragas import (
    COLLECTION, budget_plan, digest_file, export_packet, load_golden,
    make_packet, read_gold_evidence, select_questions, validate_review,
)


def fixture_rows():
    return [{"id": f"q{i:02d}", "question": f"Fixture question {i}?", "topic": "fixture",
             "gold_chunk_ids": [f"chunk{i}"], "gold_source_ids": ["fixture-source"]}
            for i in range(1, 31)]


def fixture_db(path, rows):
    with sqlite3.connect(path) as c:
        c.executescript('''
          CREATE TABLE collections(id TEXT, name TEXT);
          CREATE TABLE segments(id TEXT, collection TEXT);
          CREATE TABLE embeddings(id INTEGER, segment_id TEXT, embedding_id TEXT);
          CREATE TABLE embedding_metadata(id INTEGER, key TEXT, string_value TEXT, int_value INTEGER);
        ''')
        c.execute("INSERT INTO collections VALUES('col',?)", (COLLECTION,))
        c.execute("INSERT INTO segments VALUES('seg','col')")
        for i, row in enumerate(rows, 1):
            c.execute("INSERT INTO embeddings VALUES(?, 'seg', ?)", (i, row['gold_chunk_ids'][0]))
            for key, value in {"chroma:document": f"Fixture evidence {i}.", "source_id": "fixture-source", "title": "Fixture"}.items():
                c.execute("INSERT INTO embedding_metadata VALUES(?,?,?,NULL)", (i, key, value))
            c.execute("INSERT INTO embedding_metadata VALUES(?,'page',NULL,?)", (i, i))
    c.close()


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.rows = fixture_rows()
        self.database = self.root / "index.sqlite3"
        fixture_db(self.database, self.rows)

    def tearDown(self):
        self.temp.cleanup()

    def test_twenty_unique_and_order_independent(self):
        a = select_questions(self.rows)
        self.assertEqual(len(a), 20)
        self.assertEqual(a, select_questions(list(reversed(self.rows))))
        self.assertEqual(len({r['id'] for r in a}), 20)

    def test_sampling_does_not_use_previous_scores(self):
        other = copy.deepcopy(self.rows)
        for r in other:
            r['hit'] = False
            r['score'] = 0.99
        self.assertEqual([r['id'] for r in select_questions(self.rows)], [r['id'] for r in select_questions(other)])

    def test_frozen_git_blob_and_crlf_checkout(self):
        path = self.root / "golden.json"
        raw = (json.dumps(self.rows, indent=2) + '\n').encode()
        sha = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        path.write_bytes(raw.replace(b'\n', b'\r\n'))
        self.assertEqual(load_golden(path, sha), self.rows)
        path.write_bytes(raw + b' ')
        with self.assertRaises(ValueError):
            load_golden(path, sha)

    def test_duplicate_ids_fail(self):
        path = self.root / "golden.json"
        rows = copy.deepcopy(self.rows)
        rows[-1]['id'] = rows[0]['id']
        raw = json.dumps(rows).encode()
        sha = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        path.write_bytes(raw)
        with self.assertRaises(ValueError):
            load_golden(path, sha)

    def test_read_only_preserves_database_bytes(self):
        before = digest_file(self.database)
        data, observed = read_gold_evidence(self.database, select_questions(self.rows))
        self.assertEqual(before, observed)
        self.assertEqual(before, digest_file(self.database))
        self.assertEqual(len(data), 20)
        self.assertFalse(self.database.with_name(self.database.name + '-journal').exists())

    def test_missing_database_is_not_created(self):
        missing = self.root / 'missing.sqlite3'
        with self.assertRaises(FileNotFoundError):
            read_gold_evidence(missing, self.rows)
        self.assertFalse(missing.exists())

    def test_wrong_gold_source_fails(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['gold_source_ids'] = ['wrong']
        with self.assertRaises(ValueError):
            read_gold_evidence(self.database, rows)

    def test_missing_gold_chunk_fails(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['gold_chunk_ids'] = ['absent']
        with self.assertRaises(ValueError):
            read_gold_evidence(self.database, rows)

    def test_no_reference_or_score_is_fabricated(self):
        packet = make_packet(self.rows, self.database)
        self.assertIsNone(packet['scores'])
        self.assertEqual(packet['api_calls_performed'], 0)
        self.assertEqual(len(validate_review(packet, self.rows)), 20)
        self.assertTrue(all(r['reference'] == '' for r in packet['questions']))

    def test_question_changes_are_rejected(self):
        packet = make_packet(self.rows, self.database)
        packet['questions'][0]['user_input'] += 'changed'
        with self.assertRaises(ValueError):
            validate_review(packet, self.rows)

    def test_evidence_changes_are_rejected(self):
        packet = make_packet(self.rows, self.database)
        packet['questions'][0]['gold_evidence'][0]['text'] += 'changed'
        with self.assertRaises(ValueError):
            validate_review(packet, self.rows)

    def test_review_is_not_automatically_approved(self):
        packet = make_packet(self.rows, self.database)
        for row in packet['questions']:
            row['reference'] = 'Fixture reviewed reference, not a real project answer.'
            row['review_status'] = 'approved'
        self.assertEqual(len(validate_review(packet, self.rows)), 20)
        for row in packet['questions']:
            row['reviewed_by'] = 'fixture-reviewer'
        self.assertEqual(validate_review(packet, self.rows), [])

    def test_export_refuses_to_overwrite(self):
        packet = make_packet(self.rows, self.database)
        output = self.root / 'review'
        export_packet(packet, output)
        self.assertTrue((output / 'ragas20_reference_review.md').is_file())
        with self.assertRaises(FileExistsError):
            export_packet(packet, output)

    def test_call_plan_is_not_actual_usage(self):
        plan = budget_plan()
        self.assertEqual(plan['cohere_requests_baseline'], 260)
        self.assertEqual(plan['judge_requests_total'], 220)
        self.assertEqual(plan['rerank_requests'], 20)
        self.assertIsNone(plan['account_quota_remaining'])
        self.assertIsNone(plan['estimated_invoice_usd'])


if __name__ == '__main__':
    unittest.main()
