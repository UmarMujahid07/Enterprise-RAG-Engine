"""
main.py

FastAPI REST server — the public interface to the RAG engine.

Why this file exists:
Every module we built (config, embedding_function, document_loader,
vector_store, rag_chain) is pure Python logic with no way for an
external client (a frontend, Postman, curl) to actually use it. This
file is the thin HTTP layer on top: it accepts file uploads and JSON
questions, calls the underlying pipeline, and returns structured JSON
responses — with proper status codes and error handling so failures
are debuggable instead of raw 500 tracebacks.
"""

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from core.config import settings
from core.document_loader import load_and_chunk_pdf
from core.rag_chain import answer_question
from core.vector_store import vector_store

app = FastAPI(
    title="Enterprise RAG Engine",
    description="Multi-format document QA powered by Gemini + ChromaDB",
    version="1.0.0",
)


# --- Pydantic schemas ---
# Defining explicit request/response models (instead of raw dicts) gives
# FastAPI auto-generated validation AND interactive API docs at /docs —
# a client immediately knows the exact shape of what to send/expect,
# and malformed requests are rejected with a clear 422 before they ever
# reach our business logic.

class QueryRequest(BaseModel):
    question: str


class SourceMetadata(BaseModel):
    source: str
    page: int


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceMetadata]


class UploadResponse(BaseModel):
    filename: str
    chunks_added: int
    total_chunks_in_store: int


@app.post("/upload-pdf", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Accepts a PDF upload, saves it to disk, extracts + chunks its text,
    and inserts the chunks into the persistent vector store.
    """
    # Reject non-PDFs early — fail fast with a clear client error (400)
    # rather than letting pypdf throw a confusing internal exception later.
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Use a UUID prefix to avoid collisions if two users upload files
    # with the same name — each save is guaranteed unique on disk.
    safe_filename = f"{uuid.uuid4().hex}_{file.filename}"
    save_path: Path = settings.DATA_DIR / safe_filename

    # Stream the upload to disk in binary mode. shutil.copyfileobj avoids
    # loading the entire file into memory at once — important for large
    # PDFs, since UploadFile.file is a SpooledTemporaryFile under the hood.
    try:
        with save_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    # Run the ingestion pipeline built in Steps 4 and 3.
    try:
        chunks, metadatas, ids = load_and_chunk_pdf(str(save_path))

        if not chunks:
            raise HTTPException(
                status_code=422,
                detail="No extractable text found in this PDF (it may be scanned/image-only).",
            )

        vector_store.add_documents(chunks, metadatas, ids)
    except HTTPException:
        raise
    except Exception as e:
        # Catch-all for unexpected failures (e.g. a malformed/corrupt PDF)
        # so the client gets a clean 500 with context, not a raw traceback.
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

    return UploadResponse(
        filename=file.filename,
        chunks_added=len(chunks),
        total_chunks_in_store=vector_store.document_count(),
    )


@app.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """
    Accepts a natural language question, runs it through the RAG chain
    (Step 5), and returns a grounded, cited answer.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        result = answer_question(request.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")

    return QueryResponse(answer=result["answer"], sources=result["sources"])


@app.get("/health")
async def health_check():
    """Basic liveness check — confirms the server is up and the vector
    store is reachable, without hitting the Gemini API."""
    return {"status": "ok", "documents_in_store": vector_store.document_count()}