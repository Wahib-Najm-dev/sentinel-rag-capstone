# SentinelRAG — Architecture

## 1. Architecture Overview

SentinelRAG is designed as a lightweight, production-oriented Retrieval-Augmented Generation (RAG) system for SOC Operations and Cybersecurity Incident Response.

The architecture separates the project into two major workflows:

1. An offline ingestion pipeline that prepares and indexes authoritative cybersecurity documents.
2. An online query pipeline that retrieves, reranks, and uses the most relevant evidence to generate a grounded answer.

The implementation intentionally avoids heavyweight orchestration frameworks such as LangChain or LlamaIndex so that the retrieval logic, evaluation process, and production behavior remain transparent and reproducible.

---

## 2. High-Level Architecture

```text
OFFLINE PIPELINE

Authoritative cybersecurity documents
        |
        v
PyMuPDF / text extraction
        |
        v
Text cleaning
        |
        v
Structure-aware recursive chunking
        |
        v
~350-token chunks
~60-token overlap
        |
        v
intfloat/multilingual-e5-small
        |
        +----------------------+
        |                      |
        v                      v
Chroma vector index       BM25 lexical index


ONLINE QUERY PIPELINE

User question
        |
        v
E5 query embedding
        |
        +----------------------+
        |                      |
        v                      v
Vector Search Top 20      BM25 Search Top 20
        |                      |
        +----------+-----------+
                   |
                   v
          Reciprocal Rank Fusion
                   |
                   v
          Cohere rerank-v3.5
                   |
                   v
          Top 5 evidence passages
                   |
                   v
      Cohere command-r7b-12-2024
                   |
                   v
Evidence-grounded answer
+ citations
+ source metadata
+ page information
+ relevance scores
+ evidence excerpts