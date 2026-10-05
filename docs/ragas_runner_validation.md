# RAGAS runner validation record

Date: 2026-10-05. Tested implementation commit:
`0945b39f8ad20df92fb6f3342211f93919b52a7d`.

## Actual checks completed

GitHub Actions run 37265874827, job offline-contracts (111622475131):
https://github.com/Wahib-Najm-dev/sentinel-rag-capstone/actions/runs/37265874827

- Evaluation-only dependency installation and `pip check`: succeeded.
- 22 standard-library execution tests: succeeded. They cover durable reservations,
  lifetime budgets, successful-response reuse, independent relevance draws,
  uncertain/failed-request blocking, persisted pacing, immutable checkpoints,
  frozen questions, required metrics and undefined-result handling.
- 6 adapter contract tests: succeeded with the REAL ragas==0.4.3 metric classes,
  mocked Cohere JSON responses and mocked 384-dimensional embedding vectors.
  The full four-metric contract forbids socket connections while executing.
- Mock fixture metric values are NOT SentinelRAG results and are never published
  as a real score report. No Cohere requests or model inference was performed.

The existing reference-preparation workflow, run 37265874828, also succeeded:
https://github.com/Wahib-Najm-dev/sentinel-rag-capstone/actions/runs/37265874828
It retains the original 26 preparation/source-review tests and now also runs the
22 standard-library execution tests. The third-party Ragas contracts are run in
their dedicated dependency-equipped job rather than the stdlib-only job.

## Compatibility issue detected before any paid requests

The initial contract run failed because an unconstrained langchain-community
installation removed the VertexAI import still used by Ragas 0.4.3. This was
not a model/provider error and did not affect Railway. The isolated test job was
corrected with the following constraints, and then passed:

```
ragas==0.4.3
numpy==2.4.6
pydantic==2.13.5
langchain-community==0.3.31
langchain==0.3.27
langchain-core>=0.3.78,<1
langchain-openai<1
```

These are evaluation-only compatibility constraints, not a complete transitive
lockfile or instructions to change the production requirements. Lock and record
the full evaluation environment when integrating actual answer capture and the
OpenVINO backend. Library packaging dependencies on other provider SDKs do not
mean those providers are used: the judge transport is explicitly Cohere and
there is no automatic paid embedding fallback.

## Frozen data and honest approval state

The twenty question IDs and the reviewed reference-set hash remain unchanged:
`5b28da0ae185ca6bb2c7efca6b17e49cad24c37fb8695445ea12eb6807dcdf39`.
No Golden Labels, corpus bytes, retrieval settings, application prompt, production
requirements, main branch, or Railway deployment were modified in this step.
Human reference approval and authorization for paid/trial-quota requests remain
pending. A request to continue implementing code does not claim that a human has
reviewed every answer. The candidate Markdown is for review, not execution; the
ZIP is the candidate/evidence bundle, not a production upload.

## What remains before real evaluation

The scorer operates on saved genuine application outputs. The capture integration
for producing those outputs (with exact ranked contexts, chunk IDs and provenance)
is the next task. It must not use reference answers as application output or inject
reference-only supplemental evidence into retrieved contexts.

Confirm reference approval, the actual remaining account quota, the judge model,
and the pilot call budget before real requests. A pilot must use q01 from the
frozen twenty and be reused on resume. Capture reranking/generation calls are not
covered by the judge-only ledger cap and need explicit accounting. Live provider
JSON compatibility, evaluator reliability, and real end-to-end scores are not
proved by mocked offline contract tests.

To seek better results, improve question validity and source/reference fidelity
before scoring and improve the RAG system transparently if needed. Do not select
questions by their resulting scores, weaken references, omit hard cases, or rerun
stochastic judgments until favorable. Retain baseline and improved runs separately.
