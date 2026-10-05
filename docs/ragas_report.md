# SentinelRAG RAGAS Evaluation

**Status:** Complete  
**Evaluation date:** 5 October 2026  
**Questions:** 20 / 20 complete  
**GitHub Actions run:** https://github.com/Wahib-Najm-dev/sentinel-rag-capstone/actions/runs/37274291495  
**GitHub Actions job:** https://github.com/Wahib-Najm-dev/sentinel-rag-capstone/actions/runs/37274291495/job/111647791550

## Required metrics

| Metric | Valid / Expected | Mean |
|---|---:|---:|
| Faithfulness | 20 / 20 | **0.996429** |
| Answer Relevancy | 20 / 20 | **0.912540** |
| Context Precision | 20 / 20 | **0.940694** |
| Context Recall | 20 / 20 | **1.000000** |

## Per-question scores

| Question | Faithfulness | Answer Relevancy | Context Precision | Context Recall |
|---|---:|---:|---:|---:|
| q01 | 1.000000 | 0.959994 | 0.533333 | 1.000000 |
| q03 | 1.000000 | 0.993256 | 1.000000 | 1.000000 |
| q04 | 1.000000 | 0.845503 | 1.000000 | 1.000000 |
| q08 | 1.000000 | 0.925701 | 0.887500 | 1.000000 |
| q09 | 1.000000 | 0.927565 | 1.000000 | 1.000000 |
| q11 | 1.000000 | 0.958202 | 1.000000 | 1.000000 |
| q12 | 1.000000 | 0.934776 | 1.000000 | 1.000000 |
| q13 | 1.000000 | 0.948378 | 1.000000 | 1.000000 |
| q14 | 1.000000 | 0.942912 | 1.000000 | 1.000000 |
| q15 | 1.000000 | 0.838587 | 0.588889 | 1.000000 |
| q16 | 1.000000 | 0.940087 | 1.000000 | 1.000000 |
| q17 | 1.000000 | 0.839140 | 1.000000 | 1.000000 |
| q18 | 0.928571 | 0.958339 | 1.000000 | 1.000000 |
| q19 | 1.000000 | 0.828823 | 1.000000 | 1.000000 |
| q20 | 1.000000 | 0.851432 | 1.000000 | 1.000000 |
| q23 | 1.000000 | 0.960212 | 1.000000 | 1.000000 |
| q26 | 1.000000 | 0.816897 | 0.804167 | 1.000000 |
| q27 | 1.000000 | 0.942190 | 1.000000 | 1.000000 |
| q28 | 1.000000 | 0.979856 | 1.000000 | 1.000000 |
| q30 | 1.000000 | 0.858941 | 1.000000 | 1.000000 |

## Evaluation provenance

- generator: `command-r7b-12-2024`
- RAGAS judge: `command-r7b-12-2024`
- reranker: `rerank-v3.5`
- query embedding backend: `openvino-fp16-weights-f32-inference`
- frozen production pipeline snapshot: `8309d67b917945f75692931aca77c68915a72c19`
- frozen index SHA-256: `bab9519517382c1161d05fe0d68857d02b0123c099c1615486e159921d22064c`
- frozen reference-set SHA-256: `5b28da0ae185ca6bb2c7efca6b17e49cad24c37fb8695445ea12eb6807dcdf39`

Frozen question IDs:

`q01, q03, q04, q08, q09, q11, q12, q13, q14, q15, q16, q17, q18, q19, q20, q23, q26, q27, q28, q30`

## Provider-call accounting

The evaluation used an explicit request budget:

- q01 approved pilot: **13** provider attempts
- remaining 19 questions: **247** provider attempts
- complete frozen 20-question evaluation: **260 / 260** authorized attempts

q01 was not rerun. Its successful pilot scores were preserved from GitHub Actions run `37271975469` / job `111640711961`. The remaining 19 questions completed in run `37274291495` with durable evaluation state.

## Methodological note

The 20-question set is a deterministic subset of the project's 30-question development Golden Set. Selection was frozen before scoring and did not use previous Recall hit/miss results.

This satisfies the capstone requirement to report RAGAS on 20 questions, but it should not be presented as an independent held-out benchmark.

No composite RAGAS pass threshold was invented.

## Interpretation

- **Faithfulness 0.996429:** generated answers were almost completely supported by the supplied evidence.
- **Answer Relevancy 0.912540:** answers were strongly aligned with the questions, with some room for tighter focus.
- **Context Precision 0.940694:** the Top-5 evidence was usually highly relevant; q01, q15, and q26 show the main precision weaknesses.
- **Context Recall 1.000000:** the reference-answer content was fully covered by retrieved context for all 20 evaluated questions.

The GitHub Actions artifact `ragas-evaluation-state` also contains the machine-readable JSON report, recorded answers, and durable evaluation ledger.
