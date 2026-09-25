from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import DATABASE_URL

_is_sqlite = DATABASE_URL.startswith("sqlite")

# SQLAlchemy's bare "postgresql://" scheme defaults to the psycopg2 dialect
# for backward compatibility — but this project installs psycopg (v3), which
# needs the "+psycopg" driver suffix. Neon's dashboard (and most Postgres
# hosts) hand out bare "postgresql://" URLs, so normalize it here rather
# than expect every DATABASE_URL to be typed with SQLAlchemy's dialect
# syntax. Caught live: pasting Neon's own connection string as-is raised
# ModuleNotFoundError: No module named 'psycopg2' before this normalization.
_effective_url = DATABASE_URL
if _effective_url.startswith("postgresql://"):
    _effective_url = _effective_url.replace("postgresql://", "postgresql+psycopg://", 1)

if _is_sqlite:
    # SQLite's driver is single-connection-per-thread by default; FastAPI's
    # threadpool needs check_same_thread=False. Not applicable to Postgres.
    engine = create_engine(_effective_url, connect_args={"check_same_thread": False})
else:
    # Neon's pooled ("-pooler") connection string already runs PgBouncer in
    # front of Postgres — layering SQLAlchemy's own pool on top of that in a
    # serverless environment (many short-lived function invocations) just
    # adds a second, redundant pool. NullPool opens a fresh connection per
    # checkout and lets Neon's pooler do the actual pooling.
    engine = create_engine(_effective_url, poolclass=NullPool)


def init_db() -> None:
    from app import models  # noqa: F401 — registers tables on SQLModel.metadata

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
