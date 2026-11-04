import json
from pathlib import Path
from datetime import datetime, timezone

RETRIEVAL_REPORT = Path("evaluation_report.json")
ANSWER_REPORT = Path("answer_evaluation_report.json")
OUTPUT_REPORT = Path("consolidated_evaluation_report.json")


def load_report(path):
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run the evaluation scripts first."
        )

    return json.loads(path.read_text(encoding="utf-8"))


def main():
    retrieval_report = load_report(RETRIEVAL_REPORT)
    answer_report = load_report(ANSWER_REPORT)

    retrieval_results = {
        item["question"]: item
        for item in retrieval_report["results"]
    }

    answer_results = {
        item["question"]: item
        for item in answer_report["results"]
    }

    all_questions = sorted(
        set(retrieval_results) | set(answer_results)
    )

    combined_results = []

    for question in all_questions:
        retrieval = retrieval_results.get(question, {})
        answer = answer_results.get(question, {})

        combined_results.append({
            "question": question,
            "retrieval": {
                "keyword_coverage": retrieval.get("keyword_coverage"),
                "matched_keywords": retrieval.get("matched_keywords", []),
                "missing_keywords": retrieval.get("missing_keywords", []),
                "expected_source": retrieval.get("expected_source"),
                "source_found": retrieval.get("source_found"),
                "retrieved_chunks": retrieval.get("retrieved_chunks"),
                "distances": retrieval.get("distances", []),
            },
            "answer": {
                "expected_answerable": answer.get("expected_answerable"),
                "refusal_detected": answer.get("refusal_detected"),
                "answerability_passed": answer.get("answerability_passed"),
                "citation_metrics": answer.get("citation_metrics"),
                "sources": answer.get("sources", []),
            },
        })

    source_tests = [
        item for item in combined_results
        if item["retrieval"]["expected_source"] is not None
    ]

    answerable_tests = [
        item for item in combined_results
        if item["answer"]["expected_answerable"] is True
    ]

    keyword_scores = [
        item["retrieval"]["keyword_coverage"]
        for item in answerable_tests
        if item["retrieval"]["keyword_coverage"] is not None
    ]

    citation_scores = [
        item["answer"]["citation_metrics"]["citation_accuracy"]
        for item in answerable_tests
        if item["answer"]["citation_metrics"] is not None
    ]

    summary = {
        "total_tests": len(combined_results),
        "source_retrieval_accuracy": (
            round(
                sum(item["retrieval"]["source_found"] is True
                    for item in source_tests) / len(source_tests),
                2,
            ) if source_tests else None
        ),
        "average_keyword_coverage": (
            round(sum(keyword_scores) / len(keyword_scores), 2)
            if keyword_scores else None
        ),
        "answerability_pass_rate": (
            round(
                sum(item["answer"]["answerability_passed"] is True
                    for item in combined_results
                    if item["answer"]["answerability_passed"] is not None)
                / sum(
                    item["answer"]["answerability_passed"] is not None
                    for item in combined_results
                ),
                2,
            )
            if any(
                item["answer"]["answerability_passed"] is not None
                for item in combined_results
            )
            else None
        ),
        "average_citation_accuracy": (
            round(sum(citation_scores) / len(citation_scores), 2)
            if citation_scores else None
        ),
    }

    final_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "results": combined_results,
    }

    OUTPUT_REPORT.write_text(
        json.dumps(final_report, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n========== CONSOLIDATED EVALUATION ==========")
    print("Total tests:", summary["total_tests"])
    print("Source retrieval accuracy:", summary["source_retrieval_accuracy"])
    print("Average keyword coverage:", summary["average_keyword_coverage"])
    print("Answerability pass rate:", summary["answerability_pass_rate"])
    print("Average citation accuracy:", summary["average_citation_accuracy"])
    print("Report saved:", OUTPUT_REPORT.resolve())
    print("==============================================")


if __name__ == "__main__":
    main()