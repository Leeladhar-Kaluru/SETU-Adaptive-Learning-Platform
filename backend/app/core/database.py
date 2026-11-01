from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# Supabase's session-mode pooler caps the whole project at 15 clients. Each
# process keeps a small pool (API 2+2, worker 1+1 via POOL_SIZE env) so the
# API, the worker, and short-lived scripts never exhaust the shared cap.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={
        "prepare_threshold": None,
        "options": "-c idle_in_transaction_session_timeout=15000",
    },
    pool_pre_ping=True,
    pool_recycle=60,
    pool_size=settings.POOL_SIZE,
    max_overflow=settings.MAX_OVERFLOW,
    pool_timeout=settings.POOL_TIMEOUT,
    pool_use_lifo=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass

def check_db_health() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
            return True
    except Exception:
        return False

