# GitHub Actions RAGAS evaluation

Workflow: `.github/workflows/ragas-evaluation.yml`

It evaluates the frozen SentinelRAG sample with the instructor-required metrics:

- Faithfulness
- Answer Relevancy
- Context Precision
- Context Recall

## Isolation

The workflow runs on GitHub-hosted Ubuntu, not Railway. It does not require the private Railway embedding service. It assembles and verifies the tracked OpenVINO FP16 E5 artifact locally and uses it for vector retrieval and Answer Relevancy embeddings.

Cohere is used only for the same application reranker/generator models and for the RAGAS judge. Provider calls go through the durable SQLite ledger with no automatic retry.

## Required GitHub secret

Repository Actions secret:

`COHERE_API_KEY`

Do not commit the key to any file.

## Authorization gates

The evaluator supports:

The q01 pilot completed successfully in GitHub Actions run `37271975469` using exactly 13/13 Cohere attempts. Its four scores are frozen in `data/eval/ragas_q01_pilot_result.json` and q01 must not be silently rerun.

The only remaining live scope is:

- `remaining19`: exact confirmation `APPROVE-REMAINING19-247`, lifetime cap 247 additional Cohere attempts.

The final report combines the verified q01 scores with q03-q30. Creating this workflow does not authorize the remaining 19-question run; a new explicit approval is required.

## Triggering from this evaluation branch

The workflow listens for a push that changes:

`data/eval/ragas_workflow_trigger.json`

A non-executing remaining19 example is stored as `data/eval/ragas_workflow_trigger.example.json`.

The workflow also declares `workflow_dispatch`; because this evaluation workflow is intentionally kept off production `main`, the branch trigger is the reliable path until it is later merged.

## Resumption

Every future run uploads `ragas-evaluation-state` for 30 days with hidden files explicitly enabled. It contains the durable request ledger, actual recorded answers and contexts, and partial/final RAGAS reports. The successful q01 run predates that fix: its hidden state directory was not uploaded, so its scores and attempt count were preserved from the GitHub Actions log and are transparently marked as such.

To resume, set `resume_run_id` in the next trigger to the prior Actions run ID. Completed provider requests are reused. Reserved or failed requests are not silently repeated.

## Output

`.ragas-state/ragas_report.json` and `.ragas-state/ragas_report.md` record individual and mean values for all four required metrics. Partial means are explicitly marked as partial and are not presented as the completed 20-question result.

The question sample and references are frozen; questions are not swapped after seeing scores.
