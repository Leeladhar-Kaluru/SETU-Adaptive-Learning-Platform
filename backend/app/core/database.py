from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# Supabase's session-mode pooler caps the whole project at 15 clients. The API
# handles dashboard bursts (profile, documents, paths, study, catalogue in
# parallel) and uploads that hold a connection during the storage save, so give
# it room to breathe: 8 + 4 overflow = 12 worst case, worker typically 1-2,
# all below the 15-client cap. Fail after a short wait instead of queueing
# indefinitely; sync endpoints run in FastAPI's thread pool, so this wait never
# blocks the event loop.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=8,
    max_overflow=4,
    pool_timeout=30,
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

