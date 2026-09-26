import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

STATUTES_PATH = Path(os.getenv("STATUTES_PATH", BASE_DIR / "statutes.yaml"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'casavault.db'}")
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", BASE_DIR / "uploads"))

_raw_gemini_keys = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEYS: list[str] = [k.strip() for k in _raw_gemini_keys.split(",") if k.strip()]
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else None
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# Set in production (Vercel Blob) — unset locally, where app/storage.py
# falls back to local disk under UPLOADS_DIR instead.
BLOB_READ_WRITE_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")

# Optional sign-in (Clerk). Unset = the app runs exactly as before, fully
# anonymous — see app/auth.py. CLERK_PUBLISHABLE_KEY is not a secret (it's
# handed to the browser via GET /api/config) but CLERK_SECRET_KEY is.
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")
CLERK_PUBLISHABLE_KEY = os.getenv("CLERK_PUBLISHABLE_KEY")
