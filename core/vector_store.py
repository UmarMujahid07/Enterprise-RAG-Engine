"""
core/vector_store.py

Persistent ChromaDB collection manager with per-user data isolation.

Isolation model: ONE shared collection, but every chunk carries a
`user_id` in its metadata, and every search filters on it. ChromaDB
applies the `where` filter BEFORE ranking by similarity, so a user's
query can never even see another user's chunks.
"""

import chromadb
from core.config import settings
from core.embedding_function import GeminiEmbeddingFunction


class VectorStore:
    def __init__(self):
        # PersistentClient writes to disk, so data survives restarts.
        self.client = chromadb.PersistentClient(path=str(settings.VECTOR_DB_DIR))
        self.collection = self.client.get_or_create_collection(
            name=settings.COLLECTION_NAME,
            embedding_function=GeminiEmbeddingFunction(),
        )

    def add_documents(
        self,
        chunks: list[str],
        metadatas: list[dict],
        ids: list[str],
        user_id: int,
    ) -> None:
        """Stores chunks stamped with the owner's user_id."""
        # Stamp ownership onto every chunk's metadata. Callers can't
        # forget it, because this is the only way chunks get in.
        owned_metadatas = [{**meta, "user_id": user_id} for meta in metadatas]

        # Prefix IDs with the user id so two users uploading identically
        # named files can never overwrite each other's chunks
        # (ChromaDB overwrites on duplicate IDs).
        owned_ids = [f"u{user_id}_{chunk_id}" for chunk_id in ids]

        self.collection.add(
            documents=chunks,
            metadatas=owned_metadatas,
            ids=owned_ids,
        )

    def query(self, query_embedding: list[float], user_id: int, n_results: int = None) -> dict:
        """
        Similarity search restricted to ONE user's chunks.
        Takes a pre-computed query embedding (embed_query from Step 2)
        so the retrieval_query task type is used correctly.
        """
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results or settings.TOP_K_RESULTS,
            where={"user_id": user_id},  # <-- the isolation mechanism
        )

    def document_count(self, user_id: int = None) -> int:
        """Total chunks, or only one user's chunks if user_id is given."""
        if user_id is None:
            return self.collection.count()
        # include=[] fetches IDs only (cheap), then we count them.
        return len(self.collection.get(where={"user_id": user_id}, include=[])["ids"])
    
    def list_documents(self, user_id: int) -> list[dict]:
        """List unique documents belonging to one user."""
        result = self.collection.get(
            where={"user_id": user_id},
            include=["metadatas"],
        )

        documents = {}

        for metadata in result.get("metadatas") or []:
            source = metadata.get("source")

            if not source:
                continue

            if source not in documents:
                documents[source] = {
                    "id": source,
                    "filename": source,
                    "chunks_count": 0,
                    "pages": set(),
                }

            documents[source]["chunks_count"] += 1

            page = metadata.get("page")
            if page is not None:
                documents[source]["pages"].add(page)

        return [
            {
                **document,
                "pages": sorted(document["pages"]),
            }
            for document in sorted(
                documents.values(),
                key=lambda item: item["filename"].lower(),
            )
        ]
    
    def delete_document(self, document_id: str, user_id: int) -> bool:
        """Delete one document's chunks, restricted to its owner."""
        result = self.collection.get(
            where={"$and": [{"user_id": user_id}, {"source": document_id}]},
            include=[],
        )

        chunk_ids = result.get("ids") or []

        if not chunk_ids:
            return False

        self.collection.delete(ids=chunk_ids)
        return True





# Singleton shared by the whole app.
vector_store = VectorStore()