# ADR-001 — SentinelRAG Architecture

**Status:** Accepted  
**Date:** 5 October 2026  
**Decision owner:** Wahib Najm Al-dain Al-Refaei  
**Domain:** SOC Operations and Cybersecurity Incident Response

## Context

The capstone requires a complete internet-deployed RAG system with documented ingestion choices, hybrid retrieval with reranking, Recall@5 above 80%, authentication, three-user testing, RAGAS evaluation, cost analysis, and a one-page ADR.

SentinelRAG uses 26 authoritative NIST, CISA, OWASP, and MITRE ATT&CK sources. The final evaluation index contains 7,570 chunks.

## Decision

| Area | Decision | Why |
|---|---|---|
| Sources | 26 official NIST/CISA/OWASP/MITRE sources | Incident-response answers need attributable evidence, not random web content. |
| Chunking | Structure-aware recursive chunks, ~350 tokens, ~60 overlap | Preserves procedures and local context while keeping passages focused. |
| Embeddings | `intfloat/multilingual-e5-small`, 384 dimensions | Retrieval-oriented, CPU-friendly, multilingual, and suitable for modest Railway resources. |
| Vector store | Persistent ChromaDB | 7,570 chunks do not require distributed vector infrastructure; Chroma adds persistence and metadata simply. |
| Lexical search | BM25 on the same deterministic chunks | Exact ATT&CK IDs, CVEs, protocols, and acronyms benefit from lexical matching. |
| Fusion | Reciprocal Rank Fusion | Vector and BM25 scores are incomparable; rank fusion avoids unsafe score normalization. |
| Retrieval breadth | Vector Top-25 + BM25 Top-20 | This final configuration produced 25/30 Recall@5 hits = 83.33%, above the strict >80% requirement. |
| Reranking | Cohere rerank-v3.5 | Adds a dedicated relevance stage without loading another local CrossEncoder. |
| Final context | Top-5 evidence passages | Matches Recall@5 evaluation and limits irrelevant context sent to generation. |
| Generation | Cohere command-r7b-12-2024 | Low-cost generation with grounded-document support and native citation metadata. |
| UI | Streamlit + shared-password authentication | Meets interface/authentication requirements with a simple inspectable implementation. |
| Deployment | Railway, split web app + private OpenVINO embedding service | Isolates embedding-model memory from Streamlit and keeps the public process lightweight. |
| Evaluation | 30 Golden Questions + frozen 20-question RAGAS set | Makes retrieval and answer quality measurable rather than assumed. |

## Alternatives considered

**FAISS:** rejected because metadata and persistence would require more application plumbing.

**Elasticsearch/OpenSearch:** rejected because operational overhead is unnecessary for a 7,570-chunk corpus.

**Managed vector database:** rejected because it adds cost, credentials, and network dependency without a clear benefit at this scale.

**Vector-only retrieval:** rejected because exact cybersecurity identifiers and acronyms benefit strongly from BM25.

**Local CrossEncoder reranker:** rejected because it would add another memory-heavy local model.

**Single Railway process with SentenceTransformers:** replaced in production after deployment work showed that embedding-model memory should be isolated. Production now uses a private OpenVINO embedding service while preserving the same E5 retrieval semantics.

## Consequences

Positive outcomes:

- Recall@5 = **83.33%**
- RAGAS Faithfulness = **0.996429**
- RAGAS Answer Relevancy = **0.912540**
- RAGAS Context Precision = **0.940694**
- RAGAS Context Recall = **1.000000**
- source IDs, pages/sections, evidence text, and citation metadata remain visible
- the system is reproducible and deployable with modest infrastructure

Accepted tradeoffs:

- Cohere remains an external dependency for reranking and generation
- the single-worker embedding service is not designed for heavy burst concurrency
- shared-password authentication is adequate for the capstone but not enterprise IAM
- ChromaDB is intentionally selected for this corpus size, not as a universal production choice
- the 20-question RAGAS set is a deterministic subset of the development Golden Set, not an independent held-out benchmark

This architecture is accepted because it satisfies the capstone while prioritizing evidence quality, measurable retrieval performance, deployment reliability, and cost awareness.
