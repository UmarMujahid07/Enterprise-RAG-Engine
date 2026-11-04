
import json
from pathlib import Path

from core.rag_chain import answer_question
from core.evaluation import evaluate_citations, evaluate_retrieval

USER_ID = 3

REFUSAL_PHRASES = [
    "don't have enough information",
    "do not have enough information",
    "do not contain information",
    "not provided in the excerpts",
    "not mentioned in the provided documents",
    "cannot determine from the provided documents",
]


def is_refusal(answer: str) -> bool:
    answer_lower = answer.lower()
    return any(
        phrase in answer_lower
        for phrase in REFUSAL_PHRASES
    )


def run_evaluation():
    dataset = json.loads(
        Path("evaluation_dataset.json").read_text(encoding="utf-8")
    )

    results = []

    for test in dataset:
        question = test["question"]

        print(f"\nTesting: {question}")

        response = answer_question(
            question=question,
            user_id=USER_ID,
        )

        answer = response["answer"]
        sources = response["sources"]

        refusal = is_refusal(answer)

        citation_metrics = evaluate_citations(
            answer=answer,
            sources=sources,
        )

        expected_answerable = test["answerable"]

        answerability_passed = (
            refusal == (not expected_answerable)
        )
        retrieval_metrics = evaluate_retrieval(
            retrieved_documents=[
                source.get("snippet", "")
                for source in sources
            ],
            expected_keywords=test["expected_keywords"],
        )
        result = {
            "question": question,
            "keyword_coverage": retrieval_metrics["keyword_coverage"],
            "answer": answer,
            "expected_answerable": expected_answerable,
            "refusal_detected": refusal,
            "answerability_passed": answerability_passed,
            "citation_metrics": (
                citation_metrics if expected_answerable else None
            ),
            "retrieval_metrics": retrieval_metrics,
            "sources": sources,
        }

        results.append(result)

        print("Answerability passed:", answerability_passed)
        print("Refusal detected:", refusal)
        print(
            "Citation accuracy:",
            citation_metrics["citation_accuracy"] if expected_answerable else "N/A"
        )
    passed = sum(
        item["answerability_passed"]
        for item in results
    )

    report = {
        "total_tests": len(results),
        "passed_tests": passed,
        "failed_tests": len(results) - passed,
        "results": results,
    }

    Path("answer_evaluation_report.json").write_text(
        json.dumps(report, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n========== ANSWER EVALUATION ==========")
    print("Total tests:", len(results))
    print("Passed:", passed)
    print("Failed:", len(results) - passed)
    print("Report: answer_evaluation_report.json")
    print("=======================================")


if __name__ == "__main__":
    run_evaluation()
