import json
import tempfile
import unittest
from pathlib import Path

from scripts.capture_ragas_answers import (
    CaptureUncertain, build_package, capture_one, check_reference_approval,
    complete_stage, read_complete, reserve_stage,
)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.evidence = [{
            "chunk_id": "c1", "source_id": "s1", "title": "T", "page": 1,
            "section_id": "x", "text": "Evidence text.", "rerank_rank": 1,
            "rerank_score": 0.9,
        }]
        self.retrieve_calls = 0
        self.generate_calls = 0

    def tearDown(self):
        self.tmp.cleanup()

    def retrieve(self, question):
        self.retrieve_calls += 1
        return self.evidence, 40

    def generate(self, question, evidence):
        self.generate_calls += 1
        return {"answer": "Grounded answer.", "citations": [{"evidence_ids": ["evidence_1"]}]}

    def test_reference_approval_exact_scope(self):
        path = self.root / "approval.json"
        value = {
            "protocol": "ragas20-reference-approval-v1", "status": "approved",
            "reference_set_sha256": "5b28da0ae185ca6bb2c7efca6b17e49cad24c37fb8695445ea12eb6807dcdf39",
            "approved_by": "project_owner", "approval_source": "ChatGPT conversation",
            "approval_message": "يعتمد", "approval_timestamp_utc": "2026-10-05T05:05:55Z",
            "scope": "reference_answers_only", "human_expert_review_claimed": False,
            "paid_or_trial_api_execution_authorized": False,
        }
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(check_reference_approval(path)["scope"], "reference_answers_only")
        value["paid_or_trial_api_execution_authorized"] = True
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(ValueError):
            check_reference_approval(path)

    def test_capture_and_resume_do_not_repeat_calls(self):
        a = capture_one("q01", "Question?", self.root, self.retrieve, self.generate)
        b = capture_one("q01", "Question?", self.root, self.retrieve, self.generate)
        self.assertEqual(a, b)
        self.assertEqual(self.retrieve_calls, 1)
        self.assertEqual(self.generate_calls, 1)
        self.assertEqual(a["retrieved_chunk_ids"], ["c1"])

    def test_generation_failure_preserves_retrieval_and_blocks_retry(self):
        def fail(question, evidence):
            self.generate_calls += 1
            raise TimeoutError("fixture")
        with self.assertRaises(TimeoutError):
            capture_one("q01", "Question?", self.root, self.retrieve, fail)
        self.assertEqual(self.retrieve_calls, 1)
        with self.assertRaises(CaptureUncertain):
            capture_one("q01", "Question?", self.root, self.retrieve, self.generate)
        self.assertEqual(self.retrieve_calls, 1)
        self.assertEqual(self.generate_calls, 1)

    def test_retrieval_failure_blocks_automatic_retry(self):
        calls = []
        def fail(question):
            calls.append(question)
            raise RuntimeError("fixture")
        with self.assertRaises(RuntimeError):
            capture_one("q01", "Question?", self.root, fail, self.generate)
        with self.assertRaises(CaptureUncertain):
            capture_one("q01", "Question?", self.root, self.retrieve, self.generate)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.retrieve_calls, 0)

    def test_evidence_rank_and_duplicate_validation(self):
        bad = [dict(self.evidence[0], rerank_rank=2)]
        with self.assertRaises(ValueError):
            capture_one("q01", "Question?", self.root, lambda q:(bad, 1), self.generate)

    def test_reference_is_never_in_output_record(self):
        row = capture_one("q01", "Question?", self.root, self.retrieve, self.generate)
        self.assertNotIn("reference", row)
        self.assertNotIn("gold_evidence", row)
        self.assertNotIn("scores", row)

    def test_package_marks_no_reference_injection(self):
        row = capture_one("q01", "Question?", self.root, self.retrieve, self.generate)
        package = build_package([row], {"pipeline_commit": "x"})
        self.assertFalse(package["references_injected_into_capture"])
        self.assertIsNone(package["scores"])

    def test_completed_stage_checksum_is_verified(self):
        fingerprint = "abc"
        reserve_stage(self.root, "q01", "retrieve", fingerprint)
        complete_stage(self.root, "q01", "retrieve", fingerprint, {"a": 1})
        path = self.root / "stages/q01.retrieve.json"
        row = json.loads(path.read_text())
        row["result"] = {"a": 2}
        path.write_text(json.dumps(row))
        with self.assertRaises(ValueError):
            read_complete(self.root, "q01", "retrieve", fingerprint)

    def test_changed_question_does_not_reuse_stage(self):
        capture_one("q01", "Question?", self.root, self.retrieve, self.generate)
        with self.assertRaises(ValueError):
            capture_one("q01", "Changed?", self.root, self.retrieve, self.generate)


if __name__ == "__main__":
    unittest.main()
