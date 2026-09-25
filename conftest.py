"""Pytest bootstrap.

Two jobs, both of which used to be missing:

1. Put the project root on sys.path. Without a conftest.py here, pytest's
   "prepend" import mode only inserts tests/ — so `from app.main import app`
   raised ModuleNotFoundError and the `pytest -q` documented in CLAUDE.md
   failed outright (only `python -m pytest`, which adds the CWD, worked).
2. Point the suite at a throwaway database and uploads directory. The tests
   previously wrote straight into the dev casavault.db and uploads/ — real
   vaults, events and files accumulating in the same store used for manual
   testing. These env vars must be set before `app.config`/`app.database`
   are imported, since the engine is created at import time.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="casavault-tests-"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP / 'test.db'}")
os.environ.setdefault("UPLOADS_DIR", str(_TMP / "uploads"))
