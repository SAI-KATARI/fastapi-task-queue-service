import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# pulling from env so dev and prod don't need code changes, just .env swaps
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://taskuser:taskpass@localhost:5432/taskdb"
)

engine = create_engine(DATABASE_URL)

# autocommit=False means we control when things actually get committed
# autoflush=False keeps things predictable inside request lifecycles
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency — yields a db session per request and closes it
    when the request is done, even if something blows up mid-way.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
