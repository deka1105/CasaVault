import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

STATUTES_PATH = Path(os.getenv("STATUTES_PATH", BASE_DIR / "statutes.yaml"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'casavault.db'}")
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", BASE_DIR / "uploads"))
