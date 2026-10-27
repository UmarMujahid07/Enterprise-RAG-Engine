"""
main.py

FastAPI REST server: public auth endpoints + protected RAG endpoints.

Auth flow: /register -> /login (returns JWT) -> send
"Authorization: Bearer <token>" on /upload-pdf and /query.
get_current_user verifies the token and injects the User; its id
scopes every vector-store read/write to that user's own documents.
"""

import shutil
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status

from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from core.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from core.config import settings
from core.database import Base, engine, get_db
from core.document_loader import load_and_chunk_pdf
from core.models import User
from core.rag_chain import answer_question
from core.vector_store import vector_store

app = FastAPI(
    title="Enterprise RAG Engine",
    description="Multi-tenant document QA powered by Gemini + ChromaDB",
    version="2.0.0",
)

# --- CORS: allow the frontend to communicate with this API ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        # Add your deployed Vercel frontend URL here later.
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# Creates the users table on startup if it doesn't exist (no-op otherwise).
Base.metadata.create_all(bind=engine)


# --- Pydantic schemas ---

class RegisterRequest(BaseModel):
    email: EmailStr  # rejects anything that isn't a valid email (422)
    # Min 8 for basic strength; max 72 because bcrypt only uses the
    # first 72 bytes of a password.
    password: str = Field(min_length=8, max_length=72)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str


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
    total_chunks_in_store: int  # this user's chunks only


class DocumentItem(BaseModel):
    id: str
    filename: str
    chunks_count: int
    pages: list[int]


class DocumentsResponse(BaseModel):
    documents: list[DocumentItem]
    total: int


# --- Public endpoints ---

@app.post("/register", response_model=UserResponse, status_code=201)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Creates an account. Stores only a bcrypt hash, never the password."""
    email = request.email.lower()

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered.")

    new_user = User(
        email=email,
        hashed_password=hash_password(request.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)  # loads the DB-generated id
    return UserResponse(id=new_user.id, email=new_user.email)
@app.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Verifies credentials and issues a JWT.

    Uses the standard OAuth2 password form so Swagger's "Authorize"
    button works. The form's `username` field carries the EMAIL.
    """
    user = db.query(User).filter(User.email == form_data.username.strip().lower()).first()

    # One generic error for "no such user" and "wrong password" so
    # attackers can't enumerate which emails are registered.
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise invalid_credentials

    return TokenResponse(access_token=create_access_token(data={"sub": user.email}))


@app.get("/health")
async def health_check():
    """Public liveness check. Deliberately exposes no tenant data."""
    return {"status": "ok"}


# --- Protected endpoints (valid Bearer token required) ---

@app.get("/me", response_model=UserResponse)
async def read_me(current_user: User = Depends(get_current_user)):
    """Returns the logged-in user. Handy for verifying a token works."""
    return UserResponse(id=current_user.id, email=current_user.email)


@app.get("/documents", response_model=DocumentsResponse)
async def list_user_documents(
    current_user: User = Depends(get_current_user),
):
    """List only the authenticated user's documents."""
    documents = vector_store.list_documents(
        user_id=current_user.id
    )

    return DocumentsResponse(
        documents=documents,
        total=len(documents),
    )



@app.post("/upload-pdf", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Ingests a PDF into the CURRENT USER's private document space."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Path(...).name strips any directory parts a client might smuggle
    # into the filename (e.g. "../../x.pdf"); the UUID prefix prevents
    # collisions between uploads with the same name.
    original_name = Path(file.filename).name
    save_path: Path = settings.DATA_DIR / f"{uuid.uuid4().hex}_{original_name}"

    try:
        with save_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    try:
        chunks, metadatas, ids = load_and_chunk_pdf(str(save_path))

        if not chunks:
            raise HTTPException(
                status_code=422,
                detail="No extractable text found in this PDF (it may be scanned/image-only).",
            )

        # user_id comes from the verified token, never from the client.
        vector_store.add_documents(chunks, metadatas, ids, user_id=current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

    return UploadResponse(
        filename=original_name,
        chunks_added=len(chunks),
        total_chunks_in_store=vector_store.document_count(user_id=current_user.id),
    )


@app.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    current_user: User = Depends(get_current_user),
):
    """Answers a question using ONLY the current user's documents."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        result = answer_question(request.question, user_id=current_user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")

    return QueryResponse(answer=result["answer"], sources=result["sources"])