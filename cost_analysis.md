# SentinelRAG — Cost Analysis

**Pricing check date:** 5 October 2026  
**Currency:** USD

This document provides the required 1K, 10K, and 100K user scenarios. It is a planning model, not a vendor invoice.

## 1. Production components that create cost

Each user question uses:

1. Railway Streamlit application
2. Railway private OpenVINO query-embedding service
3. one Cohere Rerank request
4. one Cohere Command R7B generation request

Document embeddings are precomputed during ingestion, so the full corpus is not re-embedded for each user query.

## 2. Pricing inputs

### Cohere Command R7B

Model: `command-r7b-12-2024`

Published API pricing:

- input: **$0.0375 / 1M tokens**
- output: **$0.15 / 1M tokens**

Official model page: https://docs.cohere.com/docs/command-r7b

### Cohere Rerank

Model: `rerank-v3.5`

For this capstone planning model, reranking is estimated at **$2.00 / 1,000 searches**. This is treated as a planning proxy and should be re-checked before commercial deployment if Cohere changes model pricing.

One SentinelRAG question normally sends fewer than 100 fused candidates, so this analysis treats one user question as one rerank search unit.

### Railway

Published resource rates:

- RAM: **$10 / GB / month**
- CPU: **$20 / vCPU / month**
- network egress: **$0.05 / GB**

Official pricing: https://docs.railway.com/pricing

Railway meters actual resource use, so the baseline below is calculated from observed production metrics rather than a fixed instance size.

## 3. Observed Railway baseline

A 24-hour production metrics sample on 5 October 2026 showed:

| Service | Avg RAM | Avg CPU |
|---|---:|---:|
| sentinel-rag-capstone | 0.13775 GB | 0.00358 vCPU |
| sentinel-embed | 0.52130 GB | 0.00153 vCPU |
| Combined | 0.65905 GB | 0.00511 vCPU |

Estimated monthly baseline:

RAM:

    0.65905 GB × $10 = $6.59 / month

CPU:

    0.00511 vCPU × $20 = $0.10 / month

Observed baseline resource estimate:

**$6.69 / month**

This is a baseline estimate, not a capacity guarantee. Higher concurrency can raise CPU, memory, egress, and replica usage.

## 4. Per-query assumptions

For a transparent planning model, one average RAG question is assumed to use:

- 1 rerank search
- 2,200 Command R7B input tokens
- 350 Command R7B output tokens
- 50 KB outbound network traffic
- local/private query embedding only; corpus embeddings are already stored

The 2,200-token input estimate covers five evidence passages plus instructions, source metadata, and the user question.

The application allows up to 550 output tokens, but 350 is used as a representative planning average.

## 5. Variable cost per query

### Generation

Input:

    2,200 / 1,000,000 × $0.0375 = $0.0000825

Output:

    350 / 1,000,000 × $0.15 = $0.0000525

Generation total:

**$0.000135 / query**

### Reranking

    $2.00 / 1,000 = $0.002000 / query

### Egress assumption

    50 KB / 1,000,000 KB × $0.05 = $0.0000025 / query

### Total variable planning cost

**$0.0021375 / query**

Under these assumptions, reranking dominates the variable per-query cost.

## 6. Required user scenarios

For the capstone table, one active user is defined as **one RAG question per month**. This makes the user-to-query assumption explicit.

| Active users | Queries / month | Variable API + egress | Observed Railway baseline | Estimated monthly total |
|---:|---:|---:|---:|---:|
| 1,000 | 1,000 | $2.14 | $6.69 | **$8.83** |
| 10,000 | 10,000 | $21.38 | $6.69 | **$28.07** |
| 100,000 | 100,000 | $213.75 | $6.69 | **$220.44** |

These totals exclude taxes, currency conversion, unusual retry traffic, and any extra replicas required for higher concurrency.

## 7. Sensitivity: 10 questions per user per month

User count alone does not determine RAG cost; query volume does.

| Active users | Queries / month | Estimated monthly total before scale-out |
|---:|---:|---:|
| 1,000 | 10,000 | **$28.07** |
| 10,000 | 100,000 | **$220.44** |
| 100,000 | 1,000,000 | **$2,144.19** |

At one million monthly questions, the current single-worker embedding service and single web replica should not be treated as a proven production capacity plan. Load testing, concurrency control, horizontal scaling, caching, and retry behavior would need to be evaluated.

## 8. Cost-control decisions in the architecture

SentinelRAG limits cost by:

- embedding the corpus offline instead of on every query
- using a small E5 embedding model
- sending only the Top-5 evidence passages to generation
- using Command R7B instead of a larger Command model
- reranking only the fused candidate set instead of the full corpus
- keeping persistent ChromaDB and BM25 indexes
- using explicit RAGAS provider-attempt budgets and durable evaluation state

## 9. Main uncertainty

The largest uncertainty is rerank-v3.5 pricing because vendor pricing can change. The **$2 / 1K searches** value is therefore a planning assumption, not a guaranteed current invoice rate.

Before commercial deployment:

1. confirm the active Cohere rerank price
2. measure real Command input/output token usage
3. measure Railway CPU and memory under representative load
4. model retries and burst traffic
5. configure spend controls and rate limits
