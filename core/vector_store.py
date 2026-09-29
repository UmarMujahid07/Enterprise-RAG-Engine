"""
core/vector_store.py

Manages the persistent ChromaDB collection — the single point of
contact between the rest of the application and the vector database.

Why this file exists:
Nothing else in the system should import `chromadb` directly. If
main.py, document_loader.py, or rag_chain.py each initialized their
own ChromaDB client, we'd risk multiple processes/connections fighting
over the same on-disk database, and any change to storage logic
(collection name, embedding function, persistence path) would need to
be updated in multiple places. This file is the single, testable
boundary around the vector database.
"""

import chromadb
from core.config import settings
from core.embedding_function import GeminiEmbeddingFunction


class VectorStore:
    """
    Thin wrapper around a persistent ChromaDB collection. Handles
    client initialization, collection creation/loading, chunk
    insertion, and similarity search.
    """

    def __init__(self):
        # PersistentClient writes to disk at VECTOR_DB_DIR — this is
        # what makes embeddings survive a server restart. Without this,
        # every reboot would mean re-embedding and re-uploading every PDF.
        self.client = chromadb.PersistentClient(path=str(settings.VECTOR_DB_DIR))

        # get_or_create_collection is idempotent: on first run it creates
        # the collection; on every subsequent run (e.g. server restart)
        # it just reconnects to the existing one instead of erroring out.
        self.collection = self.client.get_or_create_collection(
            name=settings.COLLECTION_NAME,
            embedding_function=GeminiEmbeddingFunction(),
        )

    def add_documents(
        self,
        chunks: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        """
        Inserts text chunks into the collection. ChromaDB automatically
        calls GeminiEmbeddingFunction.__call__ on `chunks` internally —
        we never embed manually here, keeping this method a pure
        pass-through to ChromaDB's storage layer.

        Args:
            chunks: Raw text chunks extracted from a document.
            metadatas: Per-chunk metadata (e.g. source filename, page
                number) — critical for citing WHERE an answer came from.
            ids: Unique string ID per chunk (e.g. "filename_page3_chunk2").
                 Required by ChromaDB; reusing an ID overwrites that entry,
                 which we'll rely on later to avoid duplicate re-uploads.
        """
        self.collection.add(
            documents=chunks,
            metadatas=metadatas,
            ids=ids,
        )

    def query(self, query_text: str, n_results: int = None) -> dict:
        """
        Runs a similarity search against the collection.

        Note: we pass query_text here (not a pre-computed embedding).
        ChromaDB will call our embedding_function on it too — but that
        means it uses __call__ (task_type="retrieval_document"), NOT
        our asymmetric embed_query() from Step 2. We accept this minor
        inconsistency for now since ChromaDB's collection-level API
        doesn't cleanly support swapping task types per call; rag_chain.py
        will address this properly by embedding manually if needed.

        Args:
            query_text: The user's natural language question.
            n_results: How many top chunks to retrieve. Defaults to
                settings.TOP_K_RESULTS if not overridden.
        """
        return self.collection.query(
            query_texts=[query_text],
            n_results=n_results or settings.TOP_K_RESULTS,
        )

    def document_count(self) -> int:
        """Utility for debugging/testing — confirms how many chunks
        currently live in the collection."""
        return self.collection.count()


# --- Singleton instance ---
# Imported everywhere else as: from core.vector_store import vector_store
# One shared connection to the persistent DB for the whole app lifecycle.
vector_store = VectorStore()