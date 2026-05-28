from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import settings

# Configurable database path
DATABASE_URL = settings.DATABASE_URL

# For SQLite, we require connect_args={"check_same_thread": False} to run safely across multiple requests
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency provider yielding database sessions, guaranteeing cleanup on teardown."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
