
import json
from pathlib import Path

from core.config import settings
from core.embedding_function import embed_query
from core.vector_store import vector_store
from core.evaluation import evaluate_retrieval


DATASET_PATH = Path("evaluation_dataset.json")
REPORT_PATH = Path("evaluation_report.json")


def run_evaluation():
    with DATASET_PATH.open("r", encoding="utf-8") as file:
        dataset = json.load(file)

    results = []

    for test in dataset:
        question = test["question"]

        print(f"\nTesting: {question}")

        query_embedding = embed_query(question)

        retrieved = vector_store.query(
            query_embedding=query_embedding,
            user_id=3,
        )

        chunks = retrieved["documents"][0]
        metadata = retrieved["metadatas"][0]

        retrieval_metrics = evaluate_retrieval(
            retrieved_documents=chunks,
            expected_keywords=test["expected_keywords"],
        )

        retrieved_sources = {
            item.get("original_filename")
            for item in metadata
        }

        expected_source = test["expected_source"]

        source_found = (
            expected_source in retrieved_sources
            if expected_source
            else None
        )

        result = {
            "question": question,
            "answerable": test["answerable"],
            "retrieved_chunks": len(chunks),
            "keyword_coverage": retrieval_metrics["keyword_coverage"],
            "matched_keywords": retrieval_metrics["matched_keywords"],
            "missing_keywords": retrieval_metrics["missing_keywords"],
            "expected_source": expected_source,
            "source_found": source_found,
            "distances": retrieved.get("distances", [[]])[0],
        }

        results.append(result)

        print("Keyword coverage:", result["keyword_coverage"])
        print("Source found:", source_found)
        print("Distances:", result["distances"])

    report = {
        "total_tests": len(results),
        "passed_source_tests": sum(
            1 for item in results
            if item["source_found"] is True
        ),
        "results": results,
    }

    REPORT_PATH.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8",
    )

    print("\n========== EVALUATION SUMMARY ==========")
    print("Total tests:", report["total_tests"])
    print("Correct source retrieval:", report["passed_source_tests"])
    print("Report saved:", REPORT_PATH.resolve())
    print("========================================")


if __name__ == "__main__":
    run_evaluation()
