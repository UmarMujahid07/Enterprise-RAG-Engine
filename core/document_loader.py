"""
core/document_loader.py

Page-aware PDF loader and text chunker.

Why this file exists:
Raw PDF text can't go straight into embeddings — two problems need
solving first:
  1. PDFs are structured by page, but pypdf gives you one big string
     per page. If we don't track which page each chunk came from,
     we permanently lose the ability to cite sources later.
  2. Embedding models have token limits, and retrieval quality drops
     on very large chunks (too much unrelated content gets embedded
     into one vector, diluting semantic focus). We need to split text
     into smaller, overlapping windows.

This file solves both: it extracts text PAGE BY PAGE (preserving page
numbers as metadata) and then chunks each page's text using LangChain's
RecursiveCharacterTextSplitter.
"""

from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from core.config import settings


def load_and_chunk_pdf(file_path: str) -> tuple[list[str], list[dict], list[str]]:
    """
    Reads a PDF, extracts text page-by-page, and splits each page's
    text into overlapping chunks.

    Args:
        file_path: Path to the PDF file on disk.

    Returns:
        A tuple of three parallel lists, ready to pass directly into
        VectorStore.add_documents():
          - chunks: the actual text content of each chunk
          - metadatas: {"source": filename, "page": page_number} per chunk
          - ids: unique string ID per chunk (filename_page_chunkindex)
    """
    reader = PdfReader(file_path)
    filename = file_path.split("/")[-1].split("\\")[-1]  # works on Win + Unix paths

    # RecursiveCharacterTextSplitter tries to split on paragraph breaks
    # first, then sentences, then words — preserving semantic boundaries
    # as much as possible rather than cutting mid-sentence at a fixed
    # character count. CHUNK_OVERLAP ensures context isn't lost at the
    # boundary between two chunks (a sentence split across chunk 1's end
    # and chunk 2's start still has surrounding context in both).
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )

    chunks: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    # Process page-by-page (NOT the whole PDF as one string) — this is
    # what lets us attach an accurate page number to every chunk.
    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text()

        # Skip blank/image-only pages — embedding empty strings wastes
        # API calls and pollutes the vector store with useless entries.
        if not page_text or not page_text.strip():
            continue

        page_chunks = splitter.split_text(page_text)

        for chunk_index, chunk_text in enumerate(page_chunks):
            chunks.append(chunk_text)
            metadatas.append({"source": filename, "page": page_number})
            # ID format guarantees uniqueness even across multiple PDFs
            # with the same filename structure, and re-uploading the same
            # file overwrites its old chunks instead of duplicating them.
            ids.append(f"{filename}_page{page_number}_chunk{chunk_index}")

    return chunks, metadatas, ids