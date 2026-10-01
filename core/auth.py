"""
core/auth.py

Password hashing, JWT token creation/validation, and the current-user
dependency that protects routes.

Why this file exists:
Storing a user in the database isn't security by itself — we
need three more things: a way to hash passwords so a database leak
doesn't expose plain-text credentials, a way to issue a signed token
after successful login that proves identity on later requests (without
re-sending a password every time), and a way for protected endpoints
to verify that token and extract WHO is calling. This file is the
single place all three live, so main.py's routes stay thin.
"""

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.models import User

# CryptContext handles bcrypt hashing/verification. bcrypt is deliberately
# slow (by design) — this makes brute-forcing a stolen password hash
# computationally expensive, unlike fast hashes (MD5/SHA256) which are
# WRONG for passwords specifically because speed helps the attacker.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Tells FastAPI's auto-docs (/docs) where a client should send credentials
# to obtain a token (tokenUrl). This also wires up the "Authorize" button
# in Swagger UI, making the whole auth flow testable from the browser.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def hash_password(password: str) -> str:
    """Hashes a plain-text password before it's ever stored in the DB.
    This is the ONLY place a password should be converted to its stored form."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Checks a login attempt's plain-text password against the stored
    hash. We never decrypt the hash — bcrypt verification re-hashes the
    input and compares hashes, which is why hashing must be one-way."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """
    Creates a signed JWT containing the given data (typically just the
    user's email as the 'sub' / subject claim) and an expiry timestamp.

    Why JWTs instead of server-side sessions?
    A JWT is self-contained and signed — the server can verify it's
    authentic (via SECRET_KEY) without a database lookup or server-side
    session store on every single request. This keeps the API stateless,
    which matters for scaling horizontally (any server instance can
    verify any token, no shared session state needed).
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    # Signing with SECRET_KEY is what makes this tamper-proof: anyone
    # could construct a fake JWT claiming to be another user, but
    # without SECRET_KEY they can't produce a signature that verifies.
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that protected routes will declare as a parameter.
    FastAPI automatically: extracts the Bearer token from the request's
    Authorization header, runs it through this function, and injects
    the resulting User object into the route — all before the route's
    own code even runs.

    Raises 401 if the token is missing, invalid, expired, or doesn't
    correspond to a real user — meaning a protected route's code never
    has to worry about auth failures; by the time it runs, the user
    is guaranteed valid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        # Covers expired tokens, tampered signatures, malformed tokens —
        # all collapse to the same 401, deliberately not revealing WHICH
        # failure occurred (that detail could help an attacker).
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    return user