# Capstone Submission — SentinelRAG

**Track B: Build a Complete RAG System**  
**Project:** SentinelRAG  
**Author:** Wahib Najm Al-dain Al-Refaei  
**Supervisor:** Dr. Yousif Alyousifi

## The five required submission items

1. **Public GitHub repository**  
   https://github.com/Wahib-Najm-dev/sentinel-rag-capstone

2. **Live demo URL**  
   https://sentinel-rag-capstone-production.up.railway.app  
   The application uses shared-password authentication. The evaluator password must be shared privately.

3. **One-page ADR**  
   [ADR.md](ADR.md)

4. **RAGAS score on a 20-question set**  
   [docs/ragas_report.md](docs/ragas_report.md)

   - Faithfulness: **0.996429**
   - Answer Relevancy: **0.912540**
   - Context Precision: **0.940694**
   - Context Recall: **1.000000**

5. **Cost analysis — 1K / 10K / 100K users**  
   [cost_analysis.md](cost_analysis.md)

## Requirement coverage

| Capstone requirement | Evidence |
|---|---|
| Domain documented | [domain.md](domain.md) |
| 20–50 quality documents | 26 verified sources in [data/sources_manifest.csv](data/sources_manifest.csv) |
| Chunking strategy justified | [architecture.md](architecture.md) |
| Embedding model justified | [architecture.md](architecture.md) |
| Vector database justified | [architecture.md](architecture.md) |
| Hybrid search | E5 vector + BM25 + RRF |
| Reranking | Cohere rerank-v3.5 |
| 30 Golden Questions | `data/eval/golden_questions.json` |
| Recall@5 > 80% | **83.33% (25/30)** in `data/eval/recall_report_final_83_33pct.json` |
| Interface | Streamlit |
| Authentication | Shared password |
| Three real users | [docs/user_testing.md](docs/user_testing.md) |
| Deployment | Railway |
| Thorough README | [README.md](README.md) |
| RAGAS report | [docs/ragas_report.md](docs/ragas_report.md) |
| Cost at 1K / 10K / 100K users | [cost_analysis.md](cost_analysis.md) |
| One-page ADR | [ADR.md](ADR.md) |

## Final evaluation summary

- Recall@5: **83.33%**
- RAGAS Faithfulness: **0.996429**
- RAGAS Answer Relevancy: **0.912540**
- RAGAS Context Precision: **0.940694**
- RAGAS Context Recall: **1.000000**
- User testing: **3 users, 4.0/5 average**
- Live deployment: **Railway**
