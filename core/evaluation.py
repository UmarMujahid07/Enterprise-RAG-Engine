
from typing import Any


def evaluate_retrieval(
    retrieved_documents: list[str],
    expected_keywords: list[str],
) -> dict[str, Any]:
    """
    Lightweight retrieval evaluation using expected keywords.
    Measures keyword coverage across retrieved chunks.
    """

    if not expected_keywords:
        return {
            "keyword_coverage": 0.0,
            "matched_keywords": [],
            "missing_keywords": [],
        }

    combined_text = " ".join(retrieved_documents).lower()

    matched = [
        keyword
        for keyword in expected_keywords
        if keyword.lower() in combined_text
    ]

    missing = [
        keyword
        for keyword in expected_keywords
        if keyword.lower() not in combined_text
    ]

    coverage = len(matched) / len(expected_keywords)

    return {
        "keyword_coverage": round(coverage, 2),
        "matched_keywords": matched,
        "missing_keywords": missing,
    }


def evaluate_citations(
    answer: str,
    sources: list[dict],
) -> dict[str, Any]:
    """Check whether cited pages exist in returned sources."""

    import re

    citations = re.findall(
        r"\(Source:\s*(.+?)\)",
        answer,
    )

    returned_pages = {
        (source.get("source"), source.get("page"))
        for source in sources
    }

    valid_citations = []
    invalid_citations = []

    for citation in citations:
        match = re.match(r"(.+?),\s*Page\s+(\d+)", citation)

        if not match:
            invalid_citations.append(citation)
            continue

        filename = match.group(1).strip()
        pages = re.findall(r"Page\s+(\d+)", citation)

        for page in pages:
            key = (filename, int(page))

            if key in returned_pages:
                valid_citations.append(key)
            else:
                invalid_citations.append(key)

    return {
        "total_citations": len(citations),
        "valid_citations": valid_citations,
        "invalid_citations": invalid_citations,
        "citation_accuracy": (
            round(len(valid_citations) / sum(
                len(re.findall(r"Page\s+\d+", c)) for c in citations
            ), 2)
            if citations else 0.0
        ),
    }
