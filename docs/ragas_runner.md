# RAGAS runner: review, validation, and controlled scoring

Status: implementation and offline contract tests. No provider scoring has been
performed by this change. Main, Railway, runtime requirements, Golden Labels,
question selection, and source-reviewed references are unchanged.

## What the supplied files are for

`ragas20_reference_candidates.md` is the human-readable review copy of the 20
questions and reference answers. Read the answer and review note, and inspect
its supporting evidence when needed. It is not executable and must not replace
application answers. The review ZIP includes candidate JSON and the complete
37-passage evidence bundle. Keep the ZIP; do not upload it to Railway, overwrite
the Chroma database, edit hashes, or put secrets in it.

Approval concerns a specific frozen reference-set hash:
`5b28da0ae185ca6bb2c7efca6b17e49cad24c37fb8695445ea12eb6807dcdf39`.
The files still say that human approval is pending. A conversational request to
continue implementation is not a declaration that the references were reviewed.
Any actual approval and reviewer identity must be recorded truthfully, separately
from the immutable candidate file. Reference approval is not authorization for
paid/trial-quota API requests.

## Evaluation quality, without cherry-picking

Use the fixed 20 IDs already selected and source-reviewed. Check question clarity,
scope, answerability, source fidelity, and reference coverage before collecting
scores. A real data error should be documented and repaired through review and a
new version before scoring, not hidden. Do not remove difficult questions, select
ones whose answers score highest, weaken references, or repeatedly sample judge
outputs until a preferred score appears. Keep baseline and subsequent improvement
runs separate. This remains an in-sample assessment of a development Golden Set,
not an independent held-out accuracy claim. No high score is guaranteed.

The instructor requires Faithfulness, Answer Relevancy, Context Precision, and
Context Recall. This implementation calls the actual `ragas==0.4.3` collections
classes; it does not invent a different metric with the same name. Context
Precision uses references. Relevancy has three independent generated questions,
not one cached question reused three times. Its cosine result is not clipped to
increase it. Undefined metrics stop scoring rather than being silently averaged
away. Report each metric, sample count, and failures; no arbitrary composite or
pass threshold is imposed.

## Separation of responsibilities

- `scripts/ragas_execution.py`: validation, request reservations, checkpoints,
  immutable inputs, and partial/full reports. Standard library only.
- `scripts/ragas_cohere.py`: explicit modern Ragas interfaces, one-attempt Cohere
  HTTPS JSON transport, Pydantic validation, and an explicit E5 embedding callback.
- `scripts/evaluate_ragas.py`: validates saved outputs by default. Only the explicit
  run mode enables the provider transport, after reference approval and budget gates.

This scoring runner consumes saved REAL application outputs. It does not yet
capture new answers from the public Streamlit site or from the application
pipeline. Capturing one initial pilot output and then the rest is the next
integration task; its reranking/generation calls need their own approved budget.
Do not populate the answer package with reference answers, synthetic test answers,
old summaries, or guessed retrieved contexts. The two supplementary reference-only
passages are not inserted into the application's retrieved contexts.

## Input contract

The answer package has protocol `sentinelrag-recorded-answers-v1`, a `provenance`
object, and `questions`. Provenance must identify the frozen pipeline commit,
index SHA-256, Golden Set Git blob, generator model, capture method and exact
retrieval configuration: vector=25, BM25=20, RRF=60, final=5. Record deployed
frontend and embedding-service commits separately if a live capture is used;
current live services may not share a commit. The current runner expects capture
from the frozen repository snapshot. A live capture with different provenance
requires an explicit reviewed adapter, not falsified commit fields.

Each row has `id`, exact `user_input`, actual `response`, ranked
`retrieved_contexts`, and corresponding `retrieved_chunk_ids`; citations can be
included. Reference material and scores must not be put into an output row.
A one-question pilot package may contain only q01. Later append further actual
outputs while retaining the previous records unchanged. Structural/provenance
checks do not alone prove that arbitrary user-supplied output was captured honestly;
the capture integration still needs to preserve evidence and runtime provenance.

Default validation performs no paid calls and loads no model:

```bash
python scripts/evaluate_ragas.py --references PATH_TO_CANDIDATES_JSON --answers PATH_TO_REAL_OUTPUT_JSON
```

Do not run this yet without a real captured-output file. Do not change Railway
or its requirements to run evaluation. Use an isolated evaluation environment:
Ragas 0.4.3 with the already-pinned OpenVINO service dependencies. The exact full
evaluation environment and capture path still need a live pilot compatibility check.

Explicit run mode additionally requires all of `--run`,
`--approve-reference-hash`, `--reviewer`, `--judge-model`, and
`--max-judge-requests`, plus a privately configured COHERE_API_KEY. There is no
API key in command-line arguments, reports, or CI. A missing approval, changed
reference set, missing output, or execution inside a Railway service is blocked.
Do not use explicit run mode until the user approves the reference set, quota,
model and pilot budget. The program records a reviewer attestation, not an
independently verified claim of human expertise.

## Spending, rate limits, and resuming

The SQLite evaluation ledger is separate from the corpus and lives under .cache.
Every judge HTTP attempt is durably reserved before sending. Successful raw
responses (including provider usage fields), the exact prompt/schema, and a
checksum are saved. The key includes question, metric and ordinal: identical
prompts in independent relevancy draws are not collapsed. Completed subcalls
and completed metric results are reused on resume, including the pilot.

The lifetime request cap applies to JUDGE requests in that ledger, not to
application reranking/generation, local embeddings, hosting, or other app traffic.
The baseline judge estimate remains 220 requests for 20 questions with 5 contexts;
application reranking/generation add the previously estimated 40 requests. The
ledger cap cannot be silently raised when resuming. It is not a dollar/token cap
and does not enforce the account's global shared quota.

There are no automatic HTTP retries, parsing-repair LLM calls, redirects, or
provider fallbacks. Attempts that time out or remain reserved after a crash
remain counted and are not automatically resent: whether the provider completed
or billed them can be unknown. A malformed cached response also remains visible
for reconciliation instead of spending again. Explicit recovery for uncertain
requests is a future operator procedure, not an excuse to delete the ledger.
Do not discard the state directory or copy only the final JSON between machines.

The CLI uses a 4.1-second minimum gap between judge reservations (about 14.6/min),
with durable pacing across restarts. It does not police unrelated live-app traffic.
Judge max output is 4096 tokens; truncation is rejected and recorded, not scored.
A one-question run defaults to the first frozen question; a later limit of 20
includes it rather than adding a 21st question. Do not rerun to obtain a higher score.

OpenVINO E5 relevance embeddings use query-prefix behavior for both the original
and generated question texts. They run on the evaluation machine, once per uncached
text, never by silently switching to Cohere Embed or HF Inference. They are not
batch-invoked concurrently against a single worker. The model is loaded once per
process; evaluation on a memory-limited production service is intentionally blocked.

## Offline test scope and remaining checks

The standard-library tests cover resumption, independent draws, budgets,
rate-limit persistence, immutable inputs/checkpoints, crash ambiguity, and no
fabricated success for undefined scores. The integration suite runs the REAL
four Ragas classes with mocked Cohere response JSON and mock 384-d vectors, with
socket connections forbidden. Those fixture scores test arithmetic and adapter
contracts only and must never be reported as project RAGAS results.

Remaining before a real score report: human reference approval, real output
capture, confirmation of account quota and judge model, and a live one-question
compatibility pilot. Same-model generation and judging can introduce bias and
must be disclosed. Offline tests cannot certify the live judge's output quality.

## Primary API references

- https://docs.ragas.io/en/v0.4.3/concepts/metrics/available_metrics/faithfulness/
- https://docs.ragas.io/en/v0.4.3/concepts/metrics/available_metrics/answer_relevance/
- https://docs.ragas.io/en/v0.4.3/concepts/metrics/available_metrics/context_precision/
- https://docs.ragas.io/en/v0.4.3/concepts/metrics/available_metrics/context_recall/
- https://docs.cohere.com/v2/reference/chat
- https://docs.cohere.com/v2/docs/structured-outputs
- https://docs.cohere.com/v2/docs/rate-limits
