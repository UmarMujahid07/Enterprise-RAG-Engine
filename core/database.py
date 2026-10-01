"""
core/database.py

SQLAlchemy engine and session setup for the users database.

Why this file exists:
Up to now, every piece of persistent state (PDFs, embeddings) lived in
ChromaDB. User accounts need a different kind of storage — structured,
relational data (email, hashed password) where ChromaDB (a vector store)
is the wrong tool. This file is the single place that configures HOW we
connect to the SQL database; every other file that needs DB access
imports from here rather than re-configuring its own connection.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from core.config import settings

# The engine manages the actual connection pool to the database file.
# connect_args is SQLite-specific: by default SQLite only allows the
# thread that created a connection to use it, which breaks under
# FastAPI's async request handling (different requests may run on
# different threads). This flag disables that restriction safely for
# our use case (each request gets its own session, never shared).
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# SessionLocal is a factory for creating new DB sessions. We create a
# NEW session per request (see get_db below) rather than one global
# session — this is the standard FastAPI pattern, preventing one
# request's DB state/errors from leaking into another's.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is the class every SQLAlchemy model (like User in models.py)
# will inherit from. It's what lets SQLAlchemy track model definitions
# and generate the actual CREATE TABLE statements from them.
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that provides a database session per request
    and guarantees it's closed afterward, even if an error occurs.

    Why a generator with yield (not a plain return)?
    This pattern lets FastAPI run code AFTER the request finishes
    (the code after `yield`) — specifically, closing the session.
    Without this, sessions would leak and eventually exhaust the
    connection pool under load.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()