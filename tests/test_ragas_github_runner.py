import unittest
from scripts.run_ragas_github import (
    ALLOWED_SCOPES, CONFIRMATIONS, REQUESTS_PER_QUESTION,
    extract_generation, rerank_evidence,
)

class GitHubRagasRunnerTests(unittest.TestCase):
    def test_budget_contract(self):
        self.assertEqual(REQUESTS_PER_QUESTION,13)
        self.assertEqual(ALLOWED_SCOPES,{"q01":1,"all20":20})
        self.assertEqual(CONFIRMATIONS["q01"],"APPROVE-Q01-13")
        self.assertEqual(CONFIRMATIONS["all20"],"APPROVE-ALL20-260")

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
