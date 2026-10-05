# RAGAS reference approval and capture gate

The project owner explicitly approved the frozen 20 source-reviewed reference answers in the ChatGPT conversation at 2026-10-05T05:05:55Z with the message `يعتمد`.

This approval is recorded in `data/eval/ragas20_reference_approval.json` and is scoped to the reference answers only. It does **not** claim independent expert review and does **not** authorize trial/paid API execution.

Reference set:
`5b28da0ae185ca6bb2c7efca6b17e49cad24c37fb8695445ea12eb6807dcdf39`.

## Capture policy

`scripts/capture_ragas_answers.py` collects genuine application answers and the final ranked Top-5 contexts without ever reading the reference-answer content. Its default mode validates provenance only and makes zero provider/model calls.

Live capture is intentionally separate from RAGAS scoring. Each retrieval stage and generation stage is reserved before execution and stored independently. A completed stage is reused on resume. A reserved or failed stage is treated as uncertain and is **not** silently retried, because an API request might already have been billed.

The capture verifies:
- frozen 20-question selection;
- tracked Chroma index SHA-256;
- the application runtime source files are unchanged from source snapshot `8309d67b917945f75692931aca77c68915a72c19`;
- retrieval settings Vector 25 / BM25 20 / RRF 60 / final 5;
- Cohere generator `command-r7b-12-2024` and reranker `rerank-v3.5`;
- no reference, gold evidence, or score is injected into the saved application output.

A clean successful question is expected to use one Cohere rerank request and one Cohere chat request. Embedding execution is separate and must be recorded by backend. No live capture has been authorized or performed by this approval commit.
