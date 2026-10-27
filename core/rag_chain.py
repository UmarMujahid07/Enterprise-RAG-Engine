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


def _build_grounded_prompt(question: str, retrieved_chunks: list[str], metadatas: list[dict]) -> str:
    """
    Constructs the final prompt sent to Gemini, combining retrieved
    context with the user's question under strict grounding instructions.

    Why a strict system-style instruction is necessary:
    LLMs are trained to be helpful by default — meaning if the context
    doesn't fully answer the question, they'll often "fill in" using
    their own general knowledge rather than saying "I don't know."
    For an enterprise document QA tool, an answer that SOUNDS confident
    but isn't actually grounded in the source document is worse than no
    answer at all — it's a hallucination risk. This prompt explicitly
    forbids that behavior.
    """
    # Build a numbered context block, tagging each chunk with its
    # source file and page so the model can (and must) cite them.
    context_sections = []
    for i, (chunk, meta) in enumerate(zip(retrieved_chunks, metadatas), start=1):
        
        filename = _display_filename(meta)
        context_sections.append(
            f"[Source {i}: {filename}, Page {meta['page']}]\n{chunk}"
        )

    context_block = "\n\n".join(context_sections)

    prompt = f"""You are a document question-answering assistant. Answer the QUESTION using ONLY the CONTEXT provided below.

Rules:
- If the CONTEXT does not contain enough information to answer, respond exactly: "I don't have enough information in the provided documents to answer this."
- Do NOT use any outside knowledge, even if you know the answer.
- Always cite the source and page number(s) you used, in the format (Source: filename, Page: X).
- Be concise and direct.

CONTEXT:
{context_block}

QUESTION:
{question}

ANSWER:"""
    return prompt


REFUSAL_TEXT = "I don't have enough information in the provided documents to answer this."


def answer_question(question: str, user_id: int) -> dict:
    """
    Full RAG pipeline, scoped to one user's documents:
    embed question -> retrieve THIS user's chunks -> grounded answer.
    """
    # Query-optimized embedding (task_type="retrieval_query").
    query_vector = embed_query(question)

    # Retrieval is filtered to the caller's own chunks only.
    results = vector_store.query(query_vector, user_id=user_id)

    retrieved_chunks = results["documents"][0]
    retrieved_metadatas = results["metadatas"][0]

    # This user hasn't uploaded anything (or has no matching chunks).
    if not retrieved_chunks:
        return {
            "answer": "No documents found. Please upload a document first.",
            "sources": [],
        }

    prompt = _build_grounded_prompt(question, retrieved_chunks, retrieved_metadatas)
    response = generation_model.generate_content(prompt)
    response_text = response.text.strip()

    # No sources on a refusal (retrieved chunks weren't actually used).
    if response_text == REFUSAL_TEXT:
        return {"answer": response_text, "sources": []}

    # Return only source + page. Internal fields like user_id must
    # never leak into API responses.
    
    
    sources = [
        {
            "source": _display_filename(metadata),
            "page": metadata["page"],
            "snippet": chunk,
        }
        for chunk, metadata in zip(
            retrieved_chunks,
            retrieved_metadatas,
        )
    ]


    return {"answer": response_text, "sources": sources}