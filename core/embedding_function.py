"""
core/embedding_function.py

Custom embedding function that plugs Google Gemini's embedding model
into ChromaDB's collection interface.

Why this file exists:
ChromaDB doesn't know how to call Gemini out of the box — it only
understands its own EmbeddingFunction interface: a callable class with
a __call__(self, input: list[str]) -> list[list[float]] signature.
This class is the adapter between "text ChromaDB wants embedded" and
"Gemini's embed_content API call."

Without this adapter, ChromaDB would silently fall back to its default
local embedding model — meaning your PDF chunks and your queries would
be embedded in a completely different vector space, producing garbage
similarity scores. This file guarantees BOTH ingestion (vector_store.py)
and retrieval (rag_chain.py) use the exact same embedding model.
"""

import google.generativeai as genai
from chromadb import Documents, EmbeddingFunction, Embeddings
from core.config import settings

# Configure the Gemini SDK once, at import time, using the API key
# from our centralized settings object (never hardcoded here).
genai.configure(api_key=settings.GOOGLE_API_KEY)


class GeminiEmbeddingFunction(EmbeddingFunction):
    """
    Adapts Gemini's embedding API to ChromaDB's EmbeddingFunction
    interface, so ChromaDB can call it transparently whenever
    documents are added to or queried from a collection.
    """
    def __init__(self):
        # Explicit __init__ required by newer ChromaDB versions —
        # satisfies the EmbeddingFunction base class contract and
        # silences the deprecation warning.
        super().__init__()

    def __call__(self, input: Documents) -> Embeddings:
        """
        Called automatically by ChromaDB. Takes a list of raw text
        strings (input) and returns a list of embedding vectors.

        Note: Gemini's embed_content requires a 'task_type' — this
        tells the model HOW to optimize the vector. We default to
        'retrieval_document' here since this function is primarily
        used when ADDING chunks to the store. Queries use a separate
        method below with 'retrieval_query' for asymmetric optimization.
        """
        embeddings = []
        for text in input:
            response = genai.embed_content(
                model=settings.EMBEDDING_MODEL_NAME,
                content=text,
                task_type="retrieval_document",
            )
            embeddings.append(response["embedding"])
        return embeddings


def embed_query(text: str) -> list[float]:
    """
    Separate function (not part of the ChromaDB interface) used
    specifically when embedding a USER'S QUESTION at query time.

    Why this is separate from __call__ above:
    Gemini's embedding model supports 'asymmetric' task types —
    'retrieval_document' vs 'retrieval_query' produce vectors optimized
    for their respective roles. A question ("How do I reset my password?")
    and its answer chunk ("To reset your password, go to Settings...")
    are lexically different but semantically related — task_type tuning
    improves retrieval accuracy by accounting for this asymmetry.
    Using the wrong task_type for queries measurably hurts retrieval quality.
    """
    response = genai.embed_content(
        model=settings.EMBEDDING_MODEL_NAME,
        content=text,
        task_type="retrieval_query",
    )
    return response["embedding"]