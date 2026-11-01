from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# Supabase's session-mode pooler caps the whole project at 15 clients. Keep each
# process small (API 4 + worker 2 stays well below the cap) and fail fast instead
# of opening the SQLAlchemy default 5 + 10 overflow connections. Sync database
# endpoints run in FastAPI's thread pool, so a short wait here never blocks the
# event loop.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=4,
    max_overflow=0,
    pool_timeout=15,
    pool_use_lifo=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_health() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
            return True
    except Exception:
        return False

