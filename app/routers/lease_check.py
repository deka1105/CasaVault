import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.condition_eval import (
    UnsafeConditionError,
    evaluate_condition_tristate,
    referenced_facts,
)
from app.documents import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES
from app.extractor import (
    ExtractionRateLimited,
    ExtractionUnavailable,
    ExtractionUnsupported,
    ExtractionUpstreamError,
    classify_extraction_error,
    extract_facts_from_file,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lease-check", tags=["lease-check"])


def _adjudicate_facts(facts: dict, table, party: str = "tenant") -> dict:
    """Run adjudication against extracted facts without touching the database."""
    flagged, passed, unknown = [], [], []

    for rule in table.verified_rules:
        condition = rule.get("condition")
        if not condition:
            continue
        try:
            verdict = evaluate_condition_tristate(condition, facts)
            needed = referenced_facts(condition)
        except UnsafeConditionError:
            logger.exception("bad condition for rule %s", rule.get("id"))
            continue

        entry = {
            "statute_id": rule["id"],
            "citation": rule["citation"],
            "severity": rule.get("severity"),
            "requirement": rule.get("requirement"),
            "detail": rule.get("detail"),
        }

        if verdict is True:
            entry["message"] = (rule.get("party_framing") or {}).get(party)
            flagged.append(entry)
        elif verdict is False:
            passed.append(entry)
        else:
            entry["missing"] = sorted(n for n in needed if facts.get(n) is None)
            entry["next_step"] = rule.get("if_unknown")
            unknown.append(entry)

    return {
        "party": party,
        "counts": {
            "checked": len(flagged) + len(passed) + len(unknown),
            "flagged": len(flagged),
            "passed": len(passed),
            "unknown": len(unknown),
        },
        "flagged": flagged,
        "passed": passed,
        "unknown": unknown,
    }


@router.post("")
async def check_lease(request: Request, file: UploadFile = File(...)):
    """Stateless lease check: extract facts, run adjudication, return results.
    The file is deleted immediately — nothing is stored or persisted."""
    original = file.filename or ""
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext or '(none)'}")

    size = 0
    chunks = []
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large (limit {MAX_UPLOAD_BYTES // (1024 * 1024)}MB)",
            )
        chunks.append(chunk)
    content = b"".join(chunks)

    tmp = None
    try:
        tmp = Path(tempfile.mktemp(suffix=ext))
        tmp.write_bytes(content)

        try:
            facts = extract_facts_from_file(tmp) or {}
            extraction_status = "ok" if facts else "no_facts"
            extraction_message = None if facts else "The document was read but stated none of the facts we check."
        except ExtractionUnavailable:
            return {
                "extraction": {"status": "not_configured", "message": "Automatic reading is not configured."},
                "facts": {},
                "adjudication": None,
            }
        except ExtractionUnsupported:
            return {
                "extraction": {"status": "unsupported_type", "message": "This file type can't be read automatically."},
                "facts": {},
                "adjudication": None,
            }
        except ExtractionRateLimited:
            return {
                "extraction": {"status": "rate_limited", "message": "The daily limit for automatic reading has been reached. Try again tomorrow."},
                "facts": {},
                "adjudication": None,
            }
        except ExtractionUpstreamError:
            return {
                "extraction": {"status": "upstream_error", "message": "The document reader was temporarily unreachable. Try again shortly."},
                "facts": {},
                "adjudication": None,
            }
        except Exception as raw:
            exc = classify_extraction_error(raw)
            logger.exception("lease-check extraction failed: %s", exc)
            return {
                "extraction": {"status": "failed", "message": "The document couldn't be read automatically."},
                "facts": {},
                "adjudication": None,
            }
    finally:
        if tmp and tmp.exists():
            tmp.unlink(missing_ok=True)

    adjudication = _adjudicate_facts(facts, request.app.state.statutes)

    return {
        "extraction": {"status": extraction_status, "message": extraction_message},
        "facts": facts,
        "adjudication": adjudication,
    }
