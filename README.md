# SentinelRAG

Evidence-grounded Retrieval-Augmented Generation for SOC operations and cybersecurity incident response.

**Live demo:** https://sentinel-rag-capstone-production.up.railway.app  
**Public repository:** https://github.com/Wahib-Najm-dev/sentinel-rag-capstone  
**Author:** Wahib Najm Al-dain Al-Refaei  
**Supervisor:** Dr. Yousif Alyousifi

> The demo is password-protected as required by the capstone. Share the evaluator password privately; it is never committed to GitHub.

## Capstone deliverables

| Required item | SentinelRAG deliverable |
|---|---|
| Public GitHub repository | This repository |
| Live deployed demo | https://sentinel-rag-capstone-production.up.railway.app |
| One-page ADR | [ADR.md](ADR.md) |
| RAGAS score on 20 questions | [docs/ragas_report.md](docs/ragas_report.md) |
| Cost analysis for 1K / 10K / 100K users | [cost_analysis.md](cost_analysis.md) |

Supporting evidence:

- [Domain and source rationale](domain.md)
- [Architecture and design justification](architecture.md)
- [Three-user testing report](docs/user_testing.md)
- [30-question Recall@5 report](data/eval/recall_report_final_83_33pct.json)
- [RAGAS evaluation plan and reproducibility notes](docs/ragas_evaluation_plan.md)

## Project summary

SentinelRAG answers defensive cybersecurity questions using evidence retrieved from a curated corpus of authoritative sources. The system focuses on SOC operations, incident response, ransomware, logging, forensics, authentication, application security, recovery, Zero Trust, and MITRE ATT&CK.

The system does not ask the LLM to answer from memory alone. It retrieves candidate passages, fuses semantic and lexical search, reranks the candidates, sends only the strongest five evidence passages to the generator, and displays the supporting evidence and source metadata to the user.

## Final measured results

| Evaluation | Result |
|---|---:|
| Verified authoritative sources | 26 |
| Final indexed chunks | 7,570 |
| Golden questions | 30 |
| Recall@5 | **83.33% (25/30)** |
| Recall@5 requirement | **Passed: >80%** |
| RAGAS questions | 20 |
| RAGAS Faithfulness | **0.996429** |
| RAGAS Answer Relevancy | **0.912540** |
| RAGAS Context Precision | **0.940694** |
| RAGAS Context Recall | **1.000000** |
| Real-user testers | 3 |
| Average user-testing rating | **4.0 / 5** |

The final retrieval configuration uses Vector Top-25, BM25 Top-20, Reciprocal Rank Fusion, Cohere rerank-v3.5, and final Top-5 evidence.

The RAGAS run completed successfully in GitHub Actions on 5 October 2026. q01 was evaluated in the approved pilot and was not rerun. The remaining 19 questions consumed exactly the authorized 247 additional Cohere attempts, for 260 provider attempts across the complete frozen 20-question evaluation.

## Corpus

SentinelRAG uses 26 verified sources from NIST, CISA, OWASP, and MITRE ATT&CK:

- 17 PDF documents
- 8 HTML sources
- 1 structured MITRE ATT&CK dataset

The complete source inventory is in [data/sources_manifest.csv](data/sources_manifest.csv).

## Architecture

### Offline ingestion

    Authoritative PDF / HTML / MITRE STIX sources
        -> extraction and conservative cleaning
        -> structure-aware recursive chunking
        -> ~350 tokens/chunk + ~60-token overlap
        -> deterministic chunk IDs and metadata
        -> multilingual-e5-small passage embeddings
        -> ChromaDB vector index + BM25 lexical index

The final evaluation index contains 7,570 chunks in both ChromaDB and BM25.

### Online query path

    Authenticated Streamlit user
        -> E5 query embedding
        -> Chroma Top-25 + BM25 Top-20
        -> Reciprocal Rank Fusion
        -> Cohere rerank-v3.5
        -> final Top-5 evidence
        -> Cohere command-r7b-12-2024
        -> grounded answer + citations + visible evidence

Production query embeddings are served by a separate Railway service using a prebuilt OpenVINO FP16 E5 artifact. This isolates embedding-model memory from the Streamlit application.

See [architecture.md](architecture.md) for the full design rationale and alternatives considered.

## Why these choices

### Chunking

Cybersecurity guidance often contains multi-step procedures and technical identifiers. Very large chunks reduce retrieval precision; very small chunks can separate an instruction from its explanation. Structure-aware recursive splitting at roughly 350 tokens with 60-token overlap balances focused retrieval with context preservation.

### Embeddings

`intfloat/multilingual-e5-small` is retrieval-oriented, supports separate query/passage representations, has a compact 384-dimensional output, and can run on CPU. Its multilingual capability also keeps future Arabic-query support possible without changing the architecture.

### Vector database

ChromaDB fits the actual corpus size. It provides persistence, metadata, cosine search, and simple Python integration. FAISS would require more metadata/persistence plumbing; Elasticsearch/OpenSearch or a managed vector database would add unnecessary infrastructure for a 7,570-chunk corpus.

### Hybrid retrieval

Semantic E5 retrieval handles paraphrases, while BM25 is strong for exact identifiers such as ATT&CK IDs, CVEs, protocol names, and acronyms. RRF combines the rankings without pretending BM25 and vector scores share the same scale.

### Reranking and generation

Cohere rerank-v3.5 provides a dedicated relevance stage without loading another local model. command-r7b-12-2024 receives only the final five evidence passages and is instructed not to invent facts, procedures, sources, or citations.

## Retrieval evaluation

The project uses 30 manually verified Golden Questions. A question is a Recall@5 hit when at least one labeled gold chunk appears in the final reranked Top-5 evidence.

Baseline with Vector Top-20:

- 24 / 30 hits
- 80.00%
- did **not** satisfy the strict greater-than-80% requirement

Final with Vector Top-25:

- 25 / 30 hits
- **83.33%**
- requirement **passed**

The Golden labels were not changed to manufacture the improvement.

## RAGAS evaluation

The frozen 20-question set was scored on:

- Faithfulness
- Answer Relevancy
- Context Precision
- Context Recall

| Metric | Valid / Expected | Mean |
|---|---:|---:|
| Faithfulness | 20 / 20 | 0.996429 |
| Answer Relevancy | 20 / 20 | 0.912540 |
| Context Precision | 20 / 20 | 0.940694 |
| Context Recall | 20 / 20 | 1.000000 |

Full report: [docs/ragas_report.md](docs/ragas_report.md)

The RAGAS sample is a deterministic subset of the project's development Golden Set, not an independent held-out benchmark.

## Interface and authentication

The Streamlit UI includes:

- shared-password authentication
- logout support
- custom questions
- grounded answers
- native citation metadata
- exactly five final evidence passages
- source IDs
- page or ATT&CK section information
- rerank scores
- evidence text

Secrets are read from environment variables and are not hard-coded.

## Real-user testing

Three real users tested authentication, question-answer flow, evidence presentation, and usability.

- successful logins: 3 / 3
- successful Q&A sessions: 3 / 3
- successful logout/new-login cycles: 3 / 3
- average rating: 4.0 / 5
- authentication failures: 0

Full report: [docs/user_testing.md](docs/user_testing.md)

## Deployment

SentinelRAG is deployed on Railway as two services:

1. **sentinel-rag-capstone** — public Streamlit application
2. **sentinel-embed** — private OpenVINO E5 query-embedding service

Public URL:

https://sentinel-rag-capstone-production.up.railway.app

## Local development

Requirements:

- Python 3.11
- Cohere API key
- prebuilt ChromaDB and BM25 indexes in `data/index`

Install:

    python -m venv .venv
    pip install -r requirements-runtime.txt

Create a `.env` file from `.env.example` and set:

    COHERE_API_KEY=...
    APP_PASSWORD=...

For local embeddings:

    EMBEDDING_PROVIDER=local

Run:

    python -m streamlit run app.py

## Repository structure

    app.py                         Streamlit UI
    domain.md                     Domain and source rationale
    architecture.md               Architecture and design justifications
    ADR.md                        One-page architecture decision record
    cost_analysis.md              1K / 10K / 100K cost scenarios
    docs/user_testing.md          Three-user testing report
    docs/ragas_report.md          Final 20-question RAGAS report
    data/sources_manifest.csv     Verified source inventory
    data/eval/                    Golden questions and evaluation evidence
    data/index/                   Persistent ChromaDB and BM25 indexes
    src/                          Retrieval, reranking, generation, auth
    scripts/                      Ingestion and evaluation scripts
    tests/                        Validation and evaluation tests
    embedding_service.py          OpenVINO embedding microservice

## Safety and limitations

SentinelRAG is a defensive cybersecurity knowledge assistant. It does not autonomously contain incidents or replace an organization's incident-response plan.

Important limitations:

- answers are limited by the indexed corpus
- relevant evidence can still be missed
- cybersecurity guidance changes over time
- public guidance cannot capture every organization's policies or legal obligations
- grounded generation can still summarize imperfectly
- the current single-worker embedding service would require scaling work for heavy burst concurrency

## Submission checklist

- [x] Public GitHub repository
- [x] Live Railway demo
- [x] Domain documentation
- [x] Architecture documentation with written justification
- [x] 26 high-quality sources
- [x] Full ingestion pipeline
- [x] Hybrid vector + BM25 retrieval
- [x] Cohere reranking
- [x] 30 Golden Questions
- [x] Recall@5 above 80%: 83.33%
- [x] Streamlit interface
- [x] Simple authentication
- [x] Three real-user tests
- [x] RAGAS report on 20 questions
- [x] Cost analysis for 1K, 10K, and 100K users
- [x] One-page ADR
