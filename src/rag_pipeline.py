from src.llm import generate_grounded_response
from src.reranker import rerank_top_evidence
from src.retrieval import hybrid_retrieve


def retrieve_top_evidence(
    question: str,
) -> tuple[list[dict], int]:
    """
    Run the complete retrieval pipeline:

    Vector search + BM25
        -> Reciprocal Rank Fusion
        -> Cohere reranking
        -> final Top-5 evidence
    """
    question = question.strip()

    if not question:
        return [], 0

    candidates = hybrid_retrieve(
        question
    )

    evidence = rerank_top_evidence(
        query=question,
        candidates=candidates,
    )

    return evidence, len(candidates)


def answer_question(
    question: str,
) -> dict:
    """
    Execute the complete SentinelRAG pipeline.
    """
    question = question.strip()

    if not question:
        raise ValueError(
            "Question must not be empty."
        )

    evidence, candidate_count = (
        retrieve_top_evidence(
            question
        )
    )

    generated = generate_grounded_response(
        question=question,
        evidence=evidence,
    )

    return {
        "question": question,
        "answer": generated["answer"],
        "citations": generated[
            "citations"
        ],
        "candidate_count":
            candidate_count,
        "evidence": evidence,
    }
