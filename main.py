
"""
main.py

FastAPI REST API for the Enterprise RAG Engine.

Features:
- User registration and JWT authentication
- User-specific document management
- PDF upload and ingestion
- Document-grounded question answering
- Persistent multi-turn conversations
"""

# ============================================================
# 1. STANDARD LIBRARY IMPORTS
# ============================================================

import shutil
import uuid

from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic


# ============================================================
# 2. THIRD-PARTY IMPORTS
# ============================================================

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

from pydantic import BaseModel, EmailStr, Field

from sqlalchemy.orm import Session


# ============================================================
# 3. INTERNAL PROJECT IMPORTS
# ============================================================

from core.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

from core.config import settings
from core.database import Base, engine, get_db
from core.document_loader import load_and_chunk_pdf

from core.models import User, Conversation, Message

from core.rag_chain import answer_question
from core.vector_store import vector_store


# ============================================================
# 4. APPLICATION CONFIGURATION
# ============================================================

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
MAX_DOCUMENTS_PER_USER = 20

app = FastAPI(
    title="Enterprise RAG Engine",
    description=(
        "Multi-tenant document QA powered by "
        "Gemini, ChromaDB, and persistent conversations."
    ),
    version="2.1.0",
)


# ============================================================
# 5. CORS CONFIGURATION
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ============================================================
# 6. RATE LIMITING
# ============================================================

_RATE_LIMIT_WINDOW_SECONDS = 60

_rate_limit_events: dict[
    tuple[str, str],
    deque[float]
] = defaultdict(deque)


def rate_limit(max_requests: int):
    """Apply a per-IP, per-endpoint sliding-window rate limit."""

    def dependency(request: Request) -> None:
        client_ip = (
            request.client.host
            if request.client is not None
            else "unknown"
        )

        key = (client_ip, request.url.path)

        now = monotonic()
        events = _rate_limit_events[key]

        while (
            events
            and now - events[0] >= _RATE_LIMIT_WINDOW_SECONDS
        ):
            events.popleft()

        if len(events) >= max_requests:
            retry_after = max(
                1,
                int(
                    _RATE_LIMIT_WINDOW_SECONDS
                    - (now - events[0])
                ),
            )

            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded. "
                    f"Try again in {retry_after} seconds."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        events.append(now)

    return dependency


# ============================================================
# 7. DATABASE INITIALIZATION
# ============================================================

# User, Conversation, and Message models must be imported
# before creating tables.

Base.metadata.create_all(bind=engine)


# ============================================================
# 8. PYDANTIC SCHEMAS
# ============================================================

# ---------- Authentication schemas ----------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str


# ---------- Document schemas ----------

class SourceMetadata(BaseModel):
    source: str
    page: int
    snippet: str


class UploadResponse(BaseModel):
    filename: str
    chunks_added: int
    total_chunks_in_store: int


class DocumentItem(BaseModel):
    id: str
    filename: str
    chunks_count: int
    pages: list[int]


class DocumentsResponse(BaseModel):
    documents: list[DocumentItem]
    total: int


# ---------- Conversation schemas ----------

class CreateConversationRequest(BaseModel):
    title: str | None = None


class ConversationSummary(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    sources: list[SourceMetadata] | None = None
    created_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageResponse]


# ---------- RAG query schemas ----------

class QueryRequest(BaseModel):
    question: str
    conversation_id: int | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceMetadata]
    conversation_id: int


# ============================================================
# 9. PUBLIC AUTHENTICATION ENDPOINTS
# ============================================================

@app.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new user."""

    email = request.email.lower()

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered.",
        )

    new_user = User(
        email=email,
        hashed_password=hash_password(request.password),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserResponse(
        id=new_user.id,
        email=new_user.email,
    )


@app.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(10))],
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Authenticate a user and issue a JWT."""

    user = (
        db.query(User)
        .filter(
            User.email == form_data.username.strip().lower()
        )
        .first()
    )

    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if (
        not user
        or not verify_password(
            form_data.password,
            user.hashed_password,
        )
    ):
        raise invalid_credentials

    access_token = create_access_token(
        data={"sub": user.email}
    )

    return TokenResponse(
        access_token=access_token,
    )


# ============================================================
# 10. PUBLIC HEALTH ENDPOINT
# ============================================================

@app.get("/health")
async def health_check():
    """Public application health check."""

    return {"status": "ok"}


# ============================================================
# 11. PROTECTED USER ENDPOINTS
# ============================================================

@app.get(
    "/me",
    response_model=UserResponse,
)
async def read_me(
    current_user: User = Depends(get_current_user),
):
    """Return the currently authenticated user."""

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
    )


# ============================================================
# 12. DOCUMENT MANAGEMENT ENDPOINTS
# ============================================================

@app.get(
    "/documents",
    response_model=DocumentsResponse,
)
async def list_user_documents(
    current_user: User = Depends(get_current_user),
):
    """List only the authenticated user's documents."""

    documents = vector_store.list_documents(
        user_id=current_user.id,
    )

    return DocumentsResponse(
        documents=documents,
        total=len(documents),
    )


@app.delete("/documents/{document_id}")
async def delete_user_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a document belonging to the authenticated user."""

    deleted = vector_store.delete_document(
        document_id=document_id,
        user_id=current_user.id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    return {
        "message": "Document deleted successfully.",
        "document_id": document_id,
    }


# ============================================================
# 13. CONVERSATION MANAGEMENT ENDPOINTS
# ============================================================

@app.post(
    "/conversations",
    response_model=ConversationSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    request: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new conversation for the authenticated user."""

    title = (request.title or "New conversation").strip()

    conversation = Conversation(
        user_id=current_user.id,
        title=title[:200] or "New conversation",
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


@app.get(
    "/conversations",
    response_model=list[ConversationSummary],
)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the authenticated user's conversations."""

    conversations = (
        db.query(Conversation)
        .filter(
            Conversation.user_id == current_user.id
        )
        .order_by(Conversation.updated_at.desc())
        .all()
    )

    return conversations


@app.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetail,
)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve a conversation and its messages."""

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": conversation.messages,
    }


# ============================================================
# 14. PDF UPLOAD ENDPOINT
# ============================================================

@app.post(
    "/upload-pdf",
    response_model=UploadResponse,
    dependencies=[Depends(rate_limit(10))],
)
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload and ingest a PDF into the user's document space."""

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )

    original_name = Path(file.filename).name

    # Check uploaded file size.
    file.file.seek(0, 2)
    upload_size = file.file.tell()
    file.file.seek(0)

    if upload_size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="PDF exceeds the 10 MB upload limit.",
        )

    # Enforce per-user document limit.
    existing_documents = vector_store.list_documents(
        user_id=current_user.id,
    )

    if len(existing_documents) >= MAX_DOCUMENTS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=(
                "Document limit reached (20 documents per user). "
                "Delete a document before uploading another."
            ),
        )

    save_path = (
        settings.DATA_DIR
        / f"{uuid.uuid4().hex}_{original_name}"
    )

    try:
        with save_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    try:
        chunks, metadatas, ids = load_and_chunk_pdf(
            str(save_path)
        )

        for metadata in metadatas:
            metadata["document_id"] = save_path.name
            metadata["original_filename"] = original_name

        if not chunks:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No extractable text found in this PDF "
                    "(it may be scanned/image-only)."
                ),
            )

        vector_store.add_documents(
            chunks,
            metadatas,
            ids,
            user_id=current_user.id,
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process PDF: {str(e)}",
        )

    return UploadResponse(
        filename=original_name,
        chunks_added=len(chunks),
        total_chunks_in_store=vector_store.document_count(
            user_id=current_user.id
        ),
    )


# ============================================================
# 15. RAG QUERY + MULTI-TURN CONVERSATION ENDPOINT
# ============================================================

@app.post(
    "/query",
    response_model=QueryResponse,
    dependencies=[Depends(rate_limit(10))],
)
async def query_documents(
    request: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Answer a question using the user's documents.

    Conversation history is loaded from SQLite and supplied
    to the RAG pipeline for contextual follow-up questions.
    """

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    # --------------------------------------------------------
    # A. Load existing conversation or create a new one
    # --------------------------------------------------------

    if request.conversation_id is not None:

        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.id == request.conversation_id,
                Conversation.user_id == current_user.id,
            )
            .first()
        )

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

    else:
        conversation = Conversation(
            user_id=current_user.id,
            title=question[:60],
        )

        db.add(conversation)
        db.flush()

    # --------------------------------------------------------
    # B. Load the previous 10 messages
    # --------------------------------------------------------

    previous_messages = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation.id
        )
        .order_by(
            Message.created_at.desc(),
            Message.id.desc(),
        )
        .limit(10)
        .all()
    )

    # Restore chronological order.
    previous_messages.reverse()

    conversation_history = [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in previous_messages
    ]

    # --------------------------------------------------------
    # C. Generate a grounded answer using RAG
    # --------------------------------------------------------

    try:
        result = answer_question(
            question,
            user_id=current_user.id,
            conversation_history=conversation_history,
        )

        # ----------------------------------------------------
        # D. Save the user's question
        # ----------------------------------------------------

        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=question,
        )

        db.add(user_message)

        # ----------------------------------------------------
        # E. Save the assistant's answer and citations
        # ----------------------------------------------------

        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=result["answer"],
            sources=result["sources"],
        )

        db.add(assistant_message)

        # Update conversation title if it is still the default.
        if conversation.title == "New conversation":
            conversation.title = question[:60]

        conversation.updated_at = datetime.now(timezone.utc)

        # Commit both messages together.
        db.commit()

        return QueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            conversation_id=conversation.id,
        )

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate answer: {str(e)}",
        )
