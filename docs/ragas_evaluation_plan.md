# RAGAS evaluation preparation - 20 questions

## Final execution status

The planned evaluation below was completed successfully on 5 October 2026. The final 20-question results are recorded in [ragas_report.md](ragas_report.md): Faithfulness **0.996429**, Answer Relevancy **0.912540**, Context Precision **0.940694**, and Context Recall **1.000000**. The successful GitHub Actions run is https://github.com/Wahib-Najm-dev/sentinel-rag-capstone/actions/runs/37274291495.


Status: reference preparation and assistant source review. No RAGAS scores or paid evaluation calls have been produced. The deployed application and production dependencies are unchanged by this branch.

## Instructor requirements: confirmation on 2026-10-05

The user explicitly confirmed at 2026-10-05T04:11:31Z that the instructor requires **Faithfulness, Answer Relevancy, Context Precision, and Context Recall**. These four metrics are mandatory, not optional alternatives. This confirmation supersedes the earlier statement that their names were only a proposed protocol. No numeric passing threshold for these four metrics was supplied. Do not apply the separate Recall@5 >80% requirement to every RAGAS metric.

The other delivery requirements remain: a public GitHub repository, working live demo, comprehensive README, one-page ADR, cost analysis for 1,000/10,000/100,000 users, and the documented three-user usability test. Completing reference preparation does not complete these deliverables.

## Frozen source and sample

Source snapshot: `8309d67b917945f75692931aca77c68915a72c19`.
Golden Questions Git blob: `c908c6dce6434f7259db3af8991da7d8b41c563d`.
Index SHA-256: `bab9519517382c1161d05fe0d68857d02b0123c099c1615486e159921d22064c`.

Rank all 30 IDs by SHA-256 of `sentinelrag-ragas20-v1`, a NUL separator, and the ID. Select the first 20 hash ranks and present them in ID order. The preparation code does not open old hit/miss reports or system-generated answers.

Frozen IDs:
`q01,q03,q04,q08,q09,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q23,q26,q27,q28,q30`

This is an in-sample project assessment drawn from the Golden Set used for retrieval development, not an independent held-out benchmark. It does not cover every topic. Do not change the seed, questions, labels, or reference texts in response to scores.

## Source-grounded reference review

The existing Golden Set contains source/chunk IDs, not written reference answers. `scripts/prepare_ragas.py --prepare-review` exports all 35 original gold passages through SQLite `mode=ro` and `query_only=ON`, with source/page/section and text hashes. Database bytes and Golden Questions are checked for changes. No Chroma client, pickle deserialization, model inference, or provider calls are used.

The original 20 drafts remain unchanged in `data/eval/ragas20_reference_drafts.json` for provenance. The assistant reviewed all 20 against the exact passages. Corrections, review notes and source anchors are versioned in `data/eval/ragas20_reference_review_spec.json`.

Two coverage gaps were resolved using adjacent passages already in the SAME frozen indexed sources:

| Question | Supplementary reference evidence | Resolution |
|---|---|---|
| q12 | `5079b2582ae70b563cb81165`, OWASP Logging | Supplies authorization failures, session-management failures and application/system error events missing from the two original excerpt windows. |
| q18 | `26169b2b7a4e388c31f20369`, OWASP Forgot Password | Supplies single-use tokens, expiry after an appropriate period, and no account change before a valid token. No numeric token lifetime is stated. |

These are **reference-only supplements**. They are not added to `gold_chunk_ids`, not injected into application Top-5 contexts, and not used to alter the stored Recall result. The reference support bundle now contains 35 original plus 2 supplementary passages. No question has been removed.

Other edits constrain q01/q11 to the documented scope and remove unsupported qualifiers in q15/q17. The versioned specification explains the review for every ID. No system answer is used as its own reference.

`python scripts/audit_ragas_references.py` independently reloads the frozen Golden Set/index, verifies exact support text hashes and anchors, builds all 20 candidate reference answers, and exports:
- `.cache/ragas-review/ragas20_reference_candidates.json`
- `.cache/ragas-review/ragas20_reference_candidates.md`
- `.cache/ragas-review/ragas20_review_evidence.json`

The JSON includes a deterministic reference-set SHA-256. The Markdown provides all questions, references and review notes; the evidence JSON contains full source passages. A future scoring run must record and check this fingerprint before and after execution.

Assistant source review is distinct from human approval. Automated source-anchor checks prove traceability, NOT entailment or exhaustive factual adequacy. `human_approval` remains pending with no invented reviewer; `paid_execution_authorized=false`. The original empty review packet still blocks the old `--check-reviewed` command. The candidate-v2 schema requires explicit approval handling in the future evaluator; do not simply rename it as an approved v1 packet. The assistant can implement the runner offline while human review is pending, but must not execute paid scoring on unapproved references.

## Four required metrics and report structure

Candidate library version: `ragas==0.4.3`, isolated from Railway production. A live Cohere adapter and scoring runner have NOT been implemented/tested by the reference-preparation change.

| Required report name | Planned inputs and meaning |
|---|---|
| Faithfulness | Actual answer claims supported by the actual retrieved contexts. Not an independent real-world truth check. |
| Answer Relevancy | Actual question and answer, with generated questions and an explicit embedding adapter; planned strictness=3. Not a factual-correctness score. |
| Context Precision | The reference-based variant, using the question, reviewed reference and ranked actual Top-5 contexts; evaluates relevance and ordering. |
| Context Recall | Reference claims covered by the actual retrieved contexts. Distinct from the project's question-level Recall@5 hit rate. |

The final report must contain 20 question IDs and all four measured results per question, then a separate aggregate for each metric with valid/failed counts and stated limitations. Missing or failed scores remain missing with error details; do not replace them with invented zeros or silently average away failures. Do not replace the four required metrics with one unlabeled composite score, citation-span count, usability rating, or the earlier 83.33% Recall@5 result. Answer Relevancy can have cosine-derived values outside [0,1]; do not silently clamp returned values to improve presentation.

Explicitly set the judge provider/model and embedding adapter; no default OpenAI or HF Inference fallback. Prefer the already usable Cohere provider. Disclose same-model judge bias if Command R7B generates and evaluates answers. Record the E5 backend and prefix policy used for relevancy embeddings.

## Request plan - estimate only, not actual usage

Fresh answers to 20 questions, 5 contexts each, and no retries give the following initial planning baseline:

| Operation | Estimated requests |
|---|---:|
| Application reranking | 20 |
| Application generation | 20 |
| Faithfulness statement generation and verdicts | 40 |
| Answer Relevancy generated questions, strictness=3 | 60 |
| Context Precision per-context judgments | 100 |
| Context Recall per-sample judgments | 20 |
| Total | 260 |

This estimate is not an enforcement cap, guaranteed count, invoice, or proof of available quota. Confirm actual library/provider behavior with the metered adapter before execution. Retries can add requests; reused completed outputs can reduce them. Planned embedding work is at most 80 relevancy text embeddings plus 20 application query embeddings, without switching to a paid embedding provider.

Remaining Cohere quota is UNKNOWN. Check actual account usage and current endpoint limits before approval; the live app may share the quota. Production pricing and trial request quota are different. Do not state a dollar total before collecting token counts and verifying current chat/rerank price units. Cost analysis must also include hosting and the stated usage assumptions.

The future runner requires endpoint pacing, a persistent request budget, accounting for actual attempts including SDK retries, immutable per-question cached outputs, crash-safe resumption, and explicit paid-run authorization. Start with one of the same 20 questions and reuse its output; do not create a 21st sample or repeat completed calls. Do not run evaluation inside the constrained production service merely to reuse dependencies.

## Reproducibility and test evidence

Record source commit(s), Golden Set/index/reference-set hashes, model/provider IDs, embedding backend and prefix policy, prompt hashes, package versions, retrieval parameters (25/20, RRF 60, final 5), exact answers/contexts/citations, timestamps, latency definition, billed tokens, retry events and all metric results. When frontend and embedding deployment commits differ, record both.

Preparation now has 14 existing plus 12 additional stdlib tests. Tests cover frozen labels/questions, source text/hash/anchor validation, same-source reference supplements, required metric completeness, pending human approval, no paid authorization, deterministic exports and overwrite protection. These are code tests, not RAGAS model-quality scores. The workflow also rebuilds the candidate set from the real read-only index without API secrets.

Initial preparation run: https://github.com/Wahib-Najm-dev/sentinel-rag-capstone/actions/runs/37260973749
Original-source gap export: https://github.com/Wahib-Najm-dev/sentinel-rag-capstone/actions/runs/37263174475

Artifacts are reproducible from the tracked specification and frozen source files, and are exported as `ragas20-reference-review` with 14-day retention. Inspect the specific run's status before claiming its checks passed.

## Primary metric documentation

- https://docs.ragas.io/en/v0.4.3/concepts/metrics/available_metrics/faithfulness/
- https://docs.ragas.io/en/v0.4.3/concepts/metrics/available_metrics/answer_relevance/
- https://docs.ragas.io/en/v0.4.3/concepts/metrics/available_metrics/context_precision/
- https://docs.ragas.io/en/v0.4.3/concepts/metrics/available_metrics/context_recall/
- https://github.com/vibrantlabsai/ragas/tree/v0.4.3/src/ragas/metrics/collections
- https://docs.cohere.com/v2/docs/rate-limits
- https://docs.cohere.com/docs/command-r7b

Next: implement and offline-test the explicit Cohere/RAGAS adapter and resumable budgeted runner. Confirm reference approval and actual quota before authorizing a one-question paid pilot. Do not merge evaluation-only work merely to restart the working production app.
