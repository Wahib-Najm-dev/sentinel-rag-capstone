import unittest
from scripts.run_q01_ragas_pilot import build_evidence, extract_answer, PILOT_CAP, PILOT_QID

class Q01PilotUnitTests(unittest.TestCase):
    def test_fixed_gate(self):
        self.assertEqual(PILOT_QID,"q01")
        self.assertEqual(PILOT_CAP,13)

    def test_rerank_parser_keeps_order_and_scores(self):
        candidates=[{"chunk_id":f"c{i}","text":f"t{i}"} for i in range(6)]
        response={"results":[
            {"index":5,"relevance_score":.9},{"index":2,"relevance_score":.8},
            {"index":4,"relevance_score":.7},{"index":0,"relevance_score":.6},
            {"index":1,"relevance_score":.5},
        ]}
        out=build_evidence(candidates,response)
        self.assertEqual([x["chunk_id"] for x in out],["c5","c2","c4","c0","c1"])
        self.assertEqual([x["rerank_rank"] for x in out],[1,2,3,4,5])

    def test_duplicate_rerank_index_rejected(self):
        candidates=[{"chunk_id":f"c{i}","text":f"t{i}"} for i in range(5)]
        response={"results":[{"index":0,"relevance_score":.9}]*5}
        with self.assertRaises(ValueError):
            build_evidence(candidates,response)

    def test_incomplete_chat_rejected(self):
        with self.assertRaises(ValueError):
            extract_answer({"finish_reason":"MAX_TOKENS","message":{"content":[{"type":"text","text":"x"}]}})

    def test_chat_text_extracted(self):
        text,citations=extract_answer({"finish_reason":"COMPLETE","message":{"content":[{"type":"text","text":"A"}],"citations":[]}})
        self.assertEqual(text,"A")
        self.assertEqual(citations,[])

if __name__=="__main__":
    unittest.main()
