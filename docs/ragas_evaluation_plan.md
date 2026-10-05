# RAGAS evaluation preparation - 20 questions

Status: preparation only. No RAGAS scores have been measured by this change.
The deployed application and its dependencies are not changed by this branch.

## Basis and scope

The supplied project requirements require a RAGAS result on 20 questions and prohibit invented metrics. The existing 30-question Golden Set identifies correct source/chunk IDs but has no reference-answer field. A correct chunk ID is not itself a written answer.

The source snapshot is commit `8309d67b917945f75692931aca77c68915a72c19` and the frozen Golden Questions Git blob is `c908c6dce6434f7259db3af8991da7d8b41c563d`. Preparation checks this blob with checkout line endings normalized to LF and does not alter the Golden Set.

The four metrics below are the planned evaluation protocol; their individual names should not be represented as a verbatim quotation from the assignment. The final deliverable is an actual measured report, not this plan.

## Frozen sample selection

Rank all 30 IDs by SHA-256 of `sentinelrag-ragas20-v1`, a NUL separator, and the ID. Select the first 20 hash ranks and present them in ID order. This does not use old hit/miss results or generated answers. The script never opens the old Recall reports.

Selected IDs:

`q01,q03,q04,q08,q09,q11,q12,q13,q14,q15,q16,q17,q18,q19,q20,q23,q26,q27,q28,q30`

Do not change the seed, sample, questions, labels, or references in response to evaluation scores. This sample is drawn from a set already used for retrieval development: it is an in-sample project assessment, not an independent held-out generalization benchmark. It does not cover every topic in the 30-question collection.

## Reference-answer review

`python scripts/prepare_ragas.py --prepare-review` exports a review JSON and Markdown packet into `.cache/ragas-review/`.

It opens the tracked SQLite index in `mode=ro` with `query_only=ON`, checks the schema, selects only `sentinelrag_chunks`, and retrieves the exact previously labelled gold chunks. It validates source IDs and compares the database SHA-256 before and after the operation. It does not instantiate Chroma, deserialize a pickle, load an embedding model, call Cohere, or perform ingestion.

Each packet row contains the unchanged question/labels, verbatim gold evidence with source/page/section and text SHA-256, an EMPTY reference, and `review_status=pending`. It is a review packet, not a generated-results report. Existing output directories are not overwritten.

Write a reference answer using these gold sources before collecting the evaluated system answer. Check each claim and the coverage of the question. When evidence is insufficient, record the limitation and investigate it explicitly; do not fabricate content, quietly replace the question, or remove a difficult sample. Do not use the application's answer, annotation notes alone, or the current retrieved Top-5 as the ground-truth answer. The reviewer approves `reference`, `review_status`, and `reviewed_by` only after checking the sources.

`--check-reviewed PATH` exits with code 2 while references are incomplete. Passing this structural check is NOT a semantic-quality certification: a human reference review and comparison against the frozen evidence remain required. Before a paid evaluation, the evaluator must validate packet evidence/provenance against the source snapshot, not rely only on editable approval flags.

## Planned metrics and their inputs

Candidate library version: `ragas==0.4.3`, to be installed in an isolated evaluation environment, not the Railway production services. A live Cohere adapter is NOT implemented or tested by this preparation change.

| Metric | Required input | Interpretation |
|---|---|---|
| Faithfulness | question, actual system answer, retrieved contexts | Support of answer claims by the retrieved contexts; not independent real-world truth. |
| Answer Relevancy, strictness=3 | question, actual answer, explicit embedding adapter | Alignment with the question using generated questions and cosine similarity. |
| Context Precision With Reference | question, reviewed reference, ranked contexts | Whether useful contexts rank before less useful contexts. |
| Context Recall | question, reviewed reference, retrieved contexts | Coverage of the reference claims in retrieved contexts. |

The existing result named Recall@5 is a question-level hit rate (25/30 = 83.33%). It is not interchangeable with RAGAS Context Recall. No new Recall or RAGAS score is claimed here. Report individual metrics and valid sample counts; do not silently average away failures or invent a composite pass threshold.

Before implementing the paid stage, explicitly set the judge provider/model and the embedding adapter: do not fall back to OpenAI defaults or HF Inference. Prefer the already usable Cohere provider. If using the same Command R7B model for answers and judging, disclose same-model evaluation bias. Relevancy embeddings can use the existing E5 implementation, with an explicitly recorded backend and prefix policy.

## API request plan - NOT actual usage

For fresh answers to 20 questions with five contexts each and no retries, the v0.4.3 collection implementations imply this baseline:

| Operation | Requests |
|---|---:|
| Application reranking | 20 |
| Application answer generation | 20 |
| Faithfulness: statement generation and verdicts | 40 |
| Answer Relevancy: three generated questions each | 60 |
| Context Precision: one judgment per context | 100 |
| Context Recall: one judgment per sample | 20 |
| Total | 260 |

This is a planning estimate, not a guaranteed count, a configured enforcement cap, an invoice, or proof that the account has sufficient quota. Failures/retries add calls; empty or cached operations can reduce them. At most 80 question-text embeddings are planned for relevancy plus 20 query embeddings for the application; these must not silently switch to a paid embedding provider.

Cohere documentation checked 2026-10-05 lists trial allowance as 1,000 API calls/month, Command R7B Chat at 20 requests/minute, and Rerank at 10/minute. The account's actual remaining quota is UNKNOWN. Historical remaining-quota estimates are not current evidence. Requests from the live app also share its account quota.

Published Command R7B production rates are $0.0375 per million billed input tokens and $0.15 per million billed output tokens. Chat cost is `(input_tokens * 0.0375 + output_tokens * 0.15) / 1_000_000`; this excludes reranking and hosting. No dollar total is stated before the needed token counts and rerank price/unit have been checked. Trial quota and production pricing must be reported separately.

The paid evaluator still needs: explicit user approval, endpoint rate limiting, actual-attempt accounting including SDK retries, a durable request budget, immutable per-question outputs, resumability without duplicate completed calls, and failure reporting. A first pilot question must be one of the frozen 20 and reused when resuming, not become a 21st evaluation sample. Do not run it inside the constrained Railway service merely to reuse installed libraries.

## Reproducibility and result recording

Capture source commit(s), index and Golden Set hashes, model and provider IDs, tokenizer/embedding backend, prompt hashes, package versions, retrieval parameters (25/20, RRF 60, final 5), exact answers and contexts, citations, start/end timestamps, latency definition, token billing fields, retries, and per-metric results. Report the actual deployed frontend and embedding service versions separately if they differ.

Persist partial results honestly with their failed/pending IDs; publish a complete 20-question score report only after all required records have been collected and reviewed. Do not copy the three-user usability rating or the UI citation count into RAGAS fields.

## Checks executed for preparation

- 14 stdlib unit tests with synthetic SQLite fixtures; these are code tests, not model metrics.
- The GitHub workflow also exports real gold evidence from the repository database and checks that incomplete references block readiness and that the tracked database/Golden Set are unchanged.
- No API credentials are supplied to the workflow. It imports no RAGAS, Cohere, PyTorch, Transformers, or OpenVINO packages.
- Review artifacts are stored as `ragas20-reference-review` with 14-day retention; they are not automatically committed or approved.

Successful real-data preparation run: https://github.com/Wahib-Najm-dev/sentinel-rag-capstone/actions/runs/37260973749

## Primary documentation consulted

- https://docs.ragas.io/en/v0.4.3/concepts/metrics/available_metrics/faithfulness/
- https://docs.ragas.io/en/v0.4.3/concepts/metrics/available_metrics/answer_relevance/
- https://docs.ragas.io/en/v0.4.3/concepts/metrics/available_metrics/context_precision/
- https://docs.ragas.io/en/v0.4.3/concepts/metrics/available_metrics/context_recall/
- https://github.com/vibrantlabsai/ragas/tree/v0.4.3/src/ragas/metrics/collections
- https://docs.cohere.com/v2/docs/rate-limits
- https://docs.cohere.com/docs/command-r7b

Next: write and review the 20 source-grounded reference answers, then implement/test the Cohere scoring adapter and resumable runner offline before requesting approval for paid calls.
