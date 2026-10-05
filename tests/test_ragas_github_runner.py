import unittest
from scripts.run_ragas_github import (
    CONFIRMATIONS, REQUESTS_PER_QUESTION, SCOPE_IDS,
    combine_q01_seed, extract_generation, rerank_evidence,
)

class GitHubRagasRunnerTests(unittest.TestCase):
    def test_budget_contract(self):
        self.assertEqual(REQUESTS_PER_QUESTION,13)
        self.assertEqual(tuple(SCOPE_IDS),("remaining19",))
        self.assertEqual(len(SCOPE_IDS["remaining19"]),19)
        self.assertEqual(SCOPE_IDS["remaining19"][0],"q03")
        self.assertEqual(SCOPE_IDS["remaining19"][-1],"q30")
        self.assertEqual(CONFIRMATIONS,{"remaining19":"APPROVE-REMAINING19-247"})

    def test_q01_seed_combines_without_rerun(self):
        seed={
            "metrics":{
                "Faithfulness":1.0,
                "Answer Relevancy":0.9599938696232599,
                "Context Precision":0.5333333333155555,
                "Context Recall":1.0,
            },
            "raw_state_artifact_note":"fixture",
        }
        metrics={
            name:{"status":"complete","value":0.5}
            for name in ("Faithfulness","Answer Relevancy","Context Precision","Context Recall")
        }
        remainder={
            "expected_questions":19,
            "questions":[{"id":f"q{i:02d}","metrics":metrics} for i in range(2,21)],
        }
        combined=combine_q01_seed(remainder,seed)
        self.assertEqual(combined["expected_questions"],20)
        self.assertEqual(combined["questions"][0]["id"],"q01")
        self.assertEqual(combined["questions"][0]["metrics"]["Faithfulness"]["value"],1.0)
        self.assertEqual(combined["summary"]["Context Recall"]["valid_count"],20)
    def test_generation_matches_app_nonempty_semantics(self):
        answer,citations,finish=extract_generation({
            "finish_reason":"MAX_TOKENS",
            "message":{"content":[{"type":"text","text":"usable"}],"citations":[]},
        })
        self.assertEqual(answer,"usable")
        self.assertEqual(citations,[])
        self.assertEqual(finish,"MAX_TOKENS")

    def test_empty_generation_rejected(self):
        with self.assertRaises(ValueError):
            extract_generation({"finish_reason":"COMPLETE","message":{"content":[]}})

    def test_rerank_exact_top_five(self):
        candidates=[{"chunk_id":f"c{i}","text":f"t{i}"} for i in range(6)]
        response={"results":[
            {"index":5,"relevance_score":.9},{"index":2,"relevance_score":.8},
            {"index":4,"relevance_score":.7},{"index":0,"relevance_score":.6},
            {"index":1,"relevance_score":.5},
        ]}
        out=rerank_evidence(candidates,response)
        self.assertEqual([x["chunk_id"] for x in out],["c5","c2","c4","c0","c1"])
        self.assertEqual([x["rerank_rank"] for x in out],[1,2,3,4,5])

    def test_duplicate_rerank_result_rejected(self):
        candidates=[{"chunk_id":f"c{i}","text":f"t{i}"} for i in range(5)]
        with self.assertRaises(ValueError):
            rerank_evidence(candidates,{"results":[{"index":0,"relevance_score":.9}]*5})

if __name__=="__main__":
    unittest.main()
