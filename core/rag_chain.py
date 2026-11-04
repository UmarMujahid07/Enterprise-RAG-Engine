"""
core/rag_chain.py

The core RAG orchestration logic: retrieval + grounded generation.

Why this file exists:
This is the layer that turns "search" into "question answering."
vector_store.py can find relevant chunks, but a chunk isn't an answer —
we need to hand those chunks to an LLM with strict instructions to
answer ONLY from what was retrieved. Without this constraint, Gemini
will happily use its own training knowledge to fill gaps, which
defeats the entire purpose of RAG: grounding answers in YOUR documents,
not the model's general knowledge (which may be outdated, wrong, or
simply not what the user is asking about).
"""

import google.generativeai as genai
from pydantic_settings import sources
from core.config import settings
from core.embedding_function import embed_query
from core.vector_store import vector_store
# Reuses the same genai.configure() call made in embedding_function.py —
# safe to call again, it's idempotent (just resets the API key config).
genai.configure(api_key=settings.GOOGLE_API_KEY)



import re


def _display_filename(metadata: dict) -> str:
    """Return the original filename when available, with legacy fallback."""
    original_filename = metadata.get("original_filename")
    if original_filename:
        return original_filename

    source = metadata.get("source", "Unknown document")

    # Older chunks store a UUID followed by an underscore and filename.
    return re.sub(r"^[0-9a-fA-F]{32}_", "", source)

# Initialize the generation model once at import time, not per-request —
# avoids re-instantiating this object on every single query.
generation_model = genai.GenerativeModel(settings.GENERATION_MODEL_NAME)




def _build_grounded_prompt(
    question: str,
    retrieved_chunks: list[str],
    metadatas: list[dict],
    conversation_history: list[dict] | None = None,
) -> str:
    """Build a grounded prompt with optional conversation history."""

    context_sections = []

    for i, (chunk, meta) in enumerate(
        zip(retrieved_chunks, metadatas), start=1
    ):
        filename = _display_filename(meta)
        page = meta.get("page", "Unknown")

        context_sections.append(
            f"[Source {i}: {filename}, Page {page}]\n{chunk}"
        )

    context_block = "\n\n".join(context_sections)

    history_block = "No previous conversation."

    if conversation_history:
        history_block = "\n".join(
            f"{message['role'].upper()}: {message['content']}"
            for message in conversation_history
        )

    prompt = f"""You are an enterprise document question-answering assistant.

Your task is to answer the user's question using the provided document excerpts.

CONVERSATION HISTORY:
{history_block}

INSTRUCTIONS:
1. Carefully read ALL the provided document excerpts.
2. Use conversation history to understand follow-up questions and references such as "it", "that", or "explain more".
3. Treat the latest user question as the question you must answer.
4. Conversation history provides context only. Do not treat previous assistant answers as verified facts.
5. Ground factual answers ONLY in the current document excerpts.
6. Combine relevant information from multiple excerpts when necessary.
7. Do not use outside knowledge or invent facts.
8. Cite supporting information using this exact format: (Source: filename, Page: X).
9. If only part of the question can be answered, answer that part and clearly mention what information is missing.
10. Only refuse if the excerpts genuinely contain no information relevant to the question.
11. Use clear headings or bullet points when helpful.

DOCUMENT EXCERPTS:
{context_block}

LATEST USER QUESTION:
{question}

GROUNDED ANSWER:"""

    return prompt


REFUSAL_TEXT = "I don't have enough information in the provided documents to answer this."


def answer_question(
    question: str,
    user_id: int,
    conversation_history: list[dict] | None = None,
) -> dict:
    """
    Full RAG pipeline, scoped to one user's documents:
    embed question -> retrieve THIS user's chunks -> grounded answer.
    """
    # Query-optimized embedding (task_type="retrieval_query").
    query_vector = embed_query(question)

    # Retrieval is filtered to the caller's own chunks only.
    results = vector_store.query(query_vector, user_id=user_id)

    retrieved_chunks = results["documents"][0]
    # Evaluate retrieval quality
    print("\n========== RAG DEBUG ==========")
    print("User ID:", user_id)
    print("Retrieved chunks:", len(retrieved_chunks))
    print("Retrieved metadata:", results["metadatas"][0])
    print("Retrieved distances:", results.get("distances", [[]])[0])
    print("First retrieved chunk:", retrieved_chunks[0][:500] if retrieved_chunks else "NONE")
    print("================================\n")
    retrieved_metadatas = results["metadatas"][0]

    # This user hasn't uploaded anything (or has no matching chunks).
    if not retrieved_chunks:
        return {
            "answer": "No documents found. Please upload a document first.",
            "sources": [],
        }

    prompt = _build_grounded_prompt(
        question,
        retrieved_chunks,
        retrieved_metadatas,
        conversation_history,
    )
    response = generation_model.generate_content(prompt)
    response_text = response.text.strip()

    # No sources on a refusal (retrieved chunks weren't actually used).
    if response_text == REFUSAL_TEXT:
        print("CITED PAGES:", cited_pages)
        print("RETURNED SOURCES:", [(s["source"], s["page"]) for s in sources])
        return {"answer": response_text, "sources": []}

    # Return only source + page. Internal fields like user_id must
    # never leak into API responses.
    
    
   
    
    # Extract all page citations from Gemini's answer.
    citations = re.findall(
        r"\(Source:\s*(.+?)\)",
        response_text,
    )

    cited_pages = set()

    for citation in citations:
        filename_match = re.match(
            r"(.+?),\s*Page\s+(\d+)",
            citation,
        )

        if not filename_match:
            continue

        filename = filename_match.group(1).strip()
        page_numbers = re.findall(
            r"Page\s+(\d+)",
            citation,
        )

        for page_number in page_numbers:
            cited_pages.add((filename, int(page_number)))

    # Return only cited sources, avoiding duplicate pages.
    sources = []
    seen_sources = set()

    for chunk, metadata in zip(retrieved_chunks, retrieved_metadatas):
        filename = _display_filename(metadata)
        page = metadata.get("page")
        source_key = (filename, page)

        if source_key in cited_pages and source_key not in seen_sources:
            sources.append({
                "source": filename,
                "page": page,
                "snippet": chunk,
            })
            seen_sources.add(source_key)

    print("CITED PAGES:", cited_pages)
    print("RETURNED SOURCES:", [(s["source"], s["page"]) for s in sources])

    return {"answer": response_text, "sources": sources}
