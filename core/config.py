"""
core/config.py

Centralized configuration management for the RAG engine.

Why this file exists:
Every module in this system (embedding_function, vector_store, rag_chain)
needs access to API keys, model names, and file paths. Instead of each
module calling os.getenv() independently (error-prone, untestable, and
scattered), we define ONE typed Settings object here. Every other file
imports `settings` from this module as the single source of truth.

This is the same pattern used in production systems: a config layer
that fails FAST and LOUD at startup if something is misconfigured,
rather than failing silently three requests deep into a user's session.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """
    Typed application settings, auto-loaded from environment variables
    and/or a local .env file. Pydantic validates types AND presence —
    if GOOGLE_API_KEY is missing, the app refuses to start instead of
    crashing later with a confusing 401 from Google's API.
    """

    # --- API Credentials ---
    # No default value = required. If missing from .env, Pydantic raises
    # a ValidationError immediately on import, not mid-request.
    GOOGLE_API_KEY: str

    # --- Model Configuration ---
    # Centralizing model names here means swapping gemini-1.5-flash for
    # gemini-1.5-pro later is a ONE-LINE change, not a find-and-replace
    # across five files.
    EMBEDDING_MODEL_NAME: str = "models/gemini-embedding-001"
    GENERATION_MODEL_NAME: str = "gemini-1.5-flash"

    # --- Chunking Configuration ---
    # Exposed here (not hardcoded in document_loader.py) because chunk
    # size is a tunable hyperparameter you WILL want to experiment with
    # once you see retrieval quality on real PDFs.
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150

    # --- Retrieval Configuration ---
    # How many chunks to pull from ChromaDB per query. Also a knob
    # you'll tune once rag_chain.py is live.
    TOP_K_RESULTS: int = 4

    # --- Storage Paths ---
    # Path objects (not raw strings) so downstream code can use
    # .exists(), .mkdir(), etc. without re-wrapping in Path() everywhere.
    DATA_DIR: Path = Path("data")
    VECTOR_DB_DIR: Path = Path("vector_db")

    # --- ChromaDB Collection Name ---
    # Named explicitly so multiple document sets could theoretically
    # live in separate collections within the same persistent client.
    COLLECTION_NAME: str = "enterprise_rag_collection"

    # Tells pydantic-settings WHERE to look for the .env file and
    # to ignore any extra vars in the environment it doesn't recognize
    # (prevents crashes if your shell has unrelated env vars set).
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# --- Singleton instance ---
# Imported everywhere else as: from core.config import settings
# Instantiated ONCE at import time — this is what triggers the
# fail-fast validation the moment the app starts.
settings = Settings()

# Ensure required directories exist at startup rather than failing
# later when document_loader.py or vector_store.py tries to write to them.
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)