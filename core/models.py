"""
core/models.py

SQLAlchemy ORM models — the schema for data stored in the SQL database.

Why this file exists:
Separating table definitions from database connection logic (database.py)
and from business logic (auth.py, main.py) keeps each concern isolated:
if you ever add a new table (e.g. tracking upload history per user),
it's added here, without touching connection setup or auth logic.
"""

from sqlalchemy import Column, Integer, String
from core.database import Base


class User(Base):
    """
    Represents a registered user/tenant of the RAG engine.

    Note: we NEVER store plain-text passwords — only hashed_password,
    populated by auth.py using bcrypt. This table has no
    knowledge of hashing itself; that logic is deliberately kept
    separate (single responsibility).
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # unique=True enforces one account per email at the DATABASE level —
    # not just in application code — so this holds even under concurrent
    # registration attempts (a race condition application code alone
    # can't fully prevent).
    email = Column(String, unique=True, index=True, nullable=False)

    hashed_password = Column(String, nullable=False)