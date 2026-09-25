from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import DATABASE_URL

_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    # SQLite's driver is single-connection-per-thread by default; FastAPI's
    # threadpool needs check_same_thread=False. Not applicable to Postgres.
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Neon's pooled ("-pooler") connection string already runs PgBouncer in
    # front of Postgres — layering SQLAlchemy's own pool on top of that in a
    # serverless environment (many short-lived function invocations) just
    # adds a second, redundant pool. NullPool opens a fresh connection per
    # checkout and lets Neon's pooler do the actual pooling.
    engine = create_engine(DATABASE_URL, poolclass=NullPool)


def init_db() -> None:
    from app import models  # noqa: F401 — registers tables on SQLModel.metadata

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
