import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine


# -------------------------------------------------------------------
# Environment validation
# -------------------------------------------------------------------

DAH_POSTGRES_URL = os.getenv("DAH_POSTGRES_URL")
DOCMOST_POSTGRES_URL = os.getenv("DOCMOST_POSTGRES_URL")

if not DAH_POSTGRES_URL:
    raise RuntimeError("Missing required env variable: DAH_POSTGRES_URL")

if not DOCMOST_POSTGRES_URL:
    raise RuntimeError("Missing required env variable: DOCMOST_POSTGRES_URL")


# -------------------------------------------------------------------
# Engines
# -------------------------------------------------------------------

# DAH (owned database)
dah_engine: Engine = create_engine(
    DAH_POSTGRES_URL,
    pool_pre_ping=True,
    future=True,
)

# Docmost (external read-only usage)
docmost_engine: Engine = create_engine(
    DOCMOST_POSTGRES_URL,
    pool_pre_ping=True,
    future=True,
)


# -------------------------------------------------------------------
# Session factories
# -------------------------------------------------------------------

DAHSessionLocal = sessionmaker(
    bind=dah_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)

DocmostSessionLocal = sessionmaker(
    bind=docmost_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


# -------------------------------------------------------------------
# Context managers
# -------------------------------------------------------------------

@contextmanager
def get_dah_session():
    """
    Provides a transactional session for DAH database.
    Commits on success, rolls back on exception.
    """
    session = DAHSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_docmost_session():
    """
    Provides a session for Docmost database.
    Intended for read-only operations.
    No automatic commit.
    """
    session = DocmostSessionLocal()
    try:
        yield session
    finally:
        session.close()
