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
        context_sections.append(
            f"[Source {i}: {meta['source']}, Page {meta['page']}]\n{chunk}"
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


def answer_question(question: str) -> dict:
    """
    Full RAG pipeline: embed question -> retrieve chunks -> generate
    grounded answer -> return answer + source citations.

    Returns:
        {
            "answer": str,
            "sources": list[dict]  # [{"source": ..., "page": ...}, ...]
        }
    """
    # Step 1: Embed the question using the QUERY-optimized embedding
    # (task_type="retrieval_query"), NOT the document-optimized one.
    # This is the fix for the asymmetry gap flagged back in vector_store.py —
    # we bypass collection.query(query_texts=...) and instead pass a
    # pre-computed embedding directly via query_embeddings.
    query_vector = embed_query(question)

    # Step 2: Retrieve the most relevant chunks using the correct vector.
    results = vector_store.collection.query(
        query_embeddings=[query_vector],
        n_results=settings.TOP_K_RESULTS,
    )

    retrieved_chunks = results["documents"][0]
    retrieved_metadatas = results["metadatas"][0]

    # Edge case: no documents in the store at all yet.
    if not retrieved_chunks:
        return {
            "answer": "No documents have been uploaded yet. Please upload a document first.",
            "sources": [],
        }

    # Step 3: Build the grounded prompt and call Gemini.
    prompt = _build_grounded_prompt(question, retrieved_chunks, retrieved_metadatas)
    response = generation_model.generate_content(prompt)
    response_text = response.text.strip()
    # If the model refused to answer (context didn't actually contain
    # the answer), the retrieved chunks were irrelevant despite being
    # the "closest" vectors found — don't present them to the client
    # as if they were meaningful sources for a non-existent answer.
    REFUSAL_TEXT = "I don't have enough information in the provided documents to answer this."
    sources_to_return = [] if response_text == REFUSAL_TEXT else retrieved_metadatas

    return {
        "answer": response_text,
        "sources": sources_to_return,
    }