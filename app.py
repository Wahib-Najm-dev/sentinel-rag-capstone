import streamlit as st

from src.auth import (
    render_logout_button,
    require_authentication,
)
from src.config import (
    AUTHOR_NAME,
    BM25_TOP_K,
    COHERE_MODEL,
    COHERE_RERANK_MODEL,
    PROJECT_DESCRIPTION,
    PROJECT_NAME,
    TOP_N,
    VECTOR_TOP_K,
)
from src.rag_pipeline import answer_question


st.set_page_config(
    page_title=PROJECT_NAME,
    page_icon=":shield:",
    layout="wide",
)


def _citation_evidence_numbers(
    citations: list[dict],
) -> list[int]:
    numbers = set()

    for citation in citations:
        for evidence_id in citation.get(
            "evidence_ids",
            [],
        ):
            try:
                number = int(
                    evidence_id.split(
                        "_",
                        1,
                    )[1]
                )
            except (
                IndexError,
                ValueError,
            ):
                continue

            numbers.add(number)

    return sorted(numbers)


def _render_grounding_summary(
    result: dict,
) -> None:
    citations = result.get(
        "citations",
        [],
    )

    if not citations:
        st.warning(
            "The model returned no native citation metadata "
            "for this answer."
        )
        return

    evidence_numbers = (
        _citation_evidence_numbers(
            citations
        )
    )

    st.subheader(
        "Grounding"
    )

    if evidence_numbers:
        labels = [
            f"Evidence {number}"
            for number
            in evidence_numbers
        ]

        st.success(
            "Answer grounded in: "
            + " · ".join(labels)
        )
    else:
        st.info(
            "Cohere returned grounded citation spans, "
            "but no evidence IDs were exposed."
        )

    st.caption(
        "Native grounded citation spans: "
        f"{len(citations)}"
    )

    with st.expander(
        "Citation details",
        expanded=False,
    ):
        for index, citation in enumerate(
            citations,
            start=1,
        ):
            cited_text = (
                citation.get("text")
                or "Cited answer span"
            )

            evidence_ids = citation.get(
                "evidence_ids",
                [],
            )

            evidence_label = (
                ", ".join(
                    item.replace(
                        "evidence_",
                        "Evidence ",
                    )
                    for item
                    in evidence_ids
                )
                if evidence_ids
                else "Source metadata unavailable"
            )

            st.markdown(
                f"**{index}. {evidence_label}**"
            )

            st.write(
                cited_text
            )


if not require_authentication():
    st.stop()


render_logout_button()


st.sidebar.header(
    "SentinelRAG"
)

st.sidebar.caption(
    "Evidence-grounded cybersecurity RAG assistant"
)

st.sidebar.markdown(
    f"""
**Retrieval**
- Vector Top-K: `{VECTOR_TOP_K}`
- BM25 Top-K: `{BM25_TOP_K}`
- Final evidence: `{TOP_N}`

**Models**
- LLM: `{COHERE_MODEL}`
- Reranker: `{COHERE_RERANK_MODEL}`
"""
)

st.sidebar.caption(
    f"Author: {AUTHOR_NAME}"
)


st.title(
    "SentinelRAG"
)

st.write(
    PROJECT_DESCRIPTION
)

st.info(
    "Ask questions about SOC operations, incident response, "
    "application security, NIST guidance, CISA guidance, "
    "OWASP guidance, and MITRE ATT&CK evidence contained "
    "in the indexed corpus."
)


with st.form(
    "sentinelrag_question_form",
):
    question = st.text_area(
        "Question",
        height=120,
        placeholder=(
            "Example: What information from logs can help "
            "responders understand the scope and impact of "
            "an active cybersecurity incident?"
        ),
    )

    submitted = st.form_submit_button(
        "Ask SentinelRAG",
        use_container_width=True,
    )


if submitted:
    if not question.strip():
        st.warning(
            "Enter a question before submitting."
        )
    else:
        try:
            with st.spinner(
                "Retrieving, reranking, and generating "
                "an evidence-grounded answer..."
            ):
                result = answer_question(
                    question
                )

            st.session_state[
                "sentinelrag_last_result"
            ] = result

        except Exception:
            st.error(
                "SentinelRAG could not complete the request. "
                "Check the server logs for details."
            )


result = st.session_state.get(
    "sentinelrag_last_result"
)


if result:
    st.divider()

    st.subheader(
        "Answer"
    )

    st.markdown(
        result["answer"]
    )

    _render_grounding_summary(
        result
    )

    st.caption(
        "Hybrid candidates considered before reranking: "
        f"{result['candidate_count']}"
    )

    st.subheader(
        "Retrieved evidence"
    )

    for index, evidence in enumerate(
        result["evidence"],
        start=1,
    ):
        title = (
            evidence.get("title")
            or evidence.get("source_id")
            or "Source"
        )

        with st.expander(
            f"Evidence {index}: {title}",
            expanded=(
                index == 1
            ),
        ):
            col1, col2 = st.columns(
                2
            )

            with col1:
                st.markdown(
                    "**Source ID**"
                )

                st.code(
                    evidence.get(
                        "source_id",
                        "",
                    )
                )

                st.markdown(
                    "**Page**"
                )

                st.write(
                    evidence.get(
                        "page"
                    )
                    if evidence.get(
                        "page"
                    ) is not None
                    else "N/A"
                )

            with col2:
                st.markdown(
                    "**Section**"
                )

                st.write(
                    evidence.get(
                        "section_id"
                    )
                    or "N/A"
                )

                st.markdown(
                    "**Rerank score**"
                )

                score = evidence.get(
                    "rerank_score"
                )

                st.write(
                    f"{score:.4f}"
                    if score is not None
                    else "N/A"
                )

            st.markdown(
                "**Evidence text**"
            )

            st.write(
                evidence.get(
                    "text",
                    "",
                )
            )
