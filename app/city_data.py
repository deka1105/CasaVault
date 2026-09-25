"""Philadelphia L&I records, read from the City's open data.

CARFAX is credible because its events come from parties with no stake in the
sale — repair shops, insurers, the DMV. This module is the equivalent here.

Two rules in statutes.yaml depend on facts no lease ever states:

  no_rental_license            the most common successful defense in
                               Philadelphia landlord-tenant court
  open_violations_over_30_days the Safe Healthy Homes Act bar

Until now both landed in "needs facts" forever, and the app told the user to
go and look them up. The City publishes them, free and unauthenticated, so
they can be answered automatically — by a source that owes nothing to either
the landlord's or the tenant's account of events.

The derived facts use the exact names already in app/extraction_schema.py and
already referenced by statutes.yaml conditions, so a city_record VaultEvent
flows through adjudicate_vault() with no changes to the rules engine, the
statute table or the schema.

Honesty constraint that shapes the whole module: **absence of a record is not
proof of absence.** A property missing from business_licenses may be
unlicensed, or may be recorded under a different address string, or may be
owner-occupied and not require a licence. So a missing record yields no fact
at all (the rule stays "needs facts"); only a record we actually found can
assert something.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

CARTO_SQL = "https://phl.carto.com/api/v2/sql"

# The City API is a nice-to-have on a page the user is waiting for, so it gets
# a short leash. A slow lookup must never hold up the vault.
TIMEOUT_SECONDS = 8.0

# Street-type spellings, normalized to the abbreviations the City uses.
# Confirmed against live rows: "3617 SPRING GARDEN ST", "1519 Spring Garden St".
_STREET_TYPES = {
    "STREET": "ST",
    "AVENUE": "AVE",
    "ROAD": "RD",
    "DRIVE": "DR",
    "BOULEVARD": "BLVD",
    "PLACE": "PL",
    "COURT": "CT",
    "LANE": "LN",
    "TERRACE": "TER",
    "PARKWAY": "PKWY",
    "SQUARE": "SQ",
    "CIRCLE": "CIR",
    "HIGHWAY": "HWY",
}

# Unit designators to strip for a building-level lookup. A rental licence is
# issued to the property, not the apartment, so "#213" must come off before
# matching — but it is kept for display and for unit-level vault records.
_UNIT_PATTERN = re.compile(
    r"[,\s]*(?:#|\b(?:APT|APARTMENT|UNIT|STE|SUITE|FL|FLOOR|RM|ROOM)\b\.?)\s*[\w-]*\s*$",
    re.IGNORECASE,
)

_HOUSE_NUMBER = re.compile(r"^(\d+)(?:-\d+)?\s+(.*)$")

# Hard allowlist. The normalized address is interpolated into a SQL string sent
# to Carto, so anything outside this set is rejected outright rather than
# escaped — a narrow grammar is easier to be sure of than an escaping routine.
_SAFE_ADDRESS = re.compile(r"^[A-Z0-9 ]+$")


class CityDataUnavailable(RuntimeError):
    """The City API could not be reached or returned something unusable.

    Distinct from "we looked and found nothing", which is a real answer.
    Conflating the two would let a network blip read as "no licence on file",
    which is exactly the false accusation this module must never make.
    """


@dataclass
class CityRecord:
    """What the City knows about one address."""

    query_address: str
    address_found: bool = False
    licenses: list[dict[str, Any]] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    unavailable: bool = False
    note: Optional[str] = None

    @property
    def rental_licenses(self) -> list[dict[str, Any]]:
        return [lic for lic in self.licenses if "RENTAL" in str(lic.get("licensetype", "")).upper()]

    @property
    def open_violations(self) -> list[dict[str, Any]]:
        return [v for v in self.violations if str(v.get("violationstatus", "")).upper() == "OPEN"]


def normalize_address(raw: str) -> str:
    """Reduce a typed address to the building-level form the City stores.

    This is the "VIN problem": the same building appears as
    "200 Spring Garden St #213", "200 SPRING GARDEN STREET" and, in the
    violations table, inside a range like "3514-16 Spring Garden St". Getting
    this wrong means looking up the wrong building and reporting someone
    else's violations, so it stays deliberately conservative and
    Philadelphia-specific — do not generalize it to other cities.
    """
    text = (raw or "").upper().strip()
    text = _UNIT_PATTERN.sub("", text)
    # Drop anything after a comma (city/state/zip) — the City matches on the
    # street address alone.
    text = text.split(",")[0]
    text = re.sub(r"[^\w\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    words = [_STREET_TYPES.get(w, w) for w in text.split()]
    # Directionals are recorded without periods.
    words = [re.sub(r"^(N|S|E|W|NE|NW|SE|SW)\.$", r"\1", w) for w in words]
    return " ".join(words).strip()


def split_house_number(normalized: str) -> tuple[Optional[str], str]:
    """Separate "3617" from "SPRING GARDEN ST"."""
    match = _HOUSE_NUMBER.match(normalized)
    if not match:
        return None, normalized
    return match.group(1), match.group(2)


def _address_regex(normalized: str) -> Optional[str]:
    """Postgres regex matching this address, including hyphenated ranges.

    A building recorded as "3514-16 Spring Garden St" must match a search for
    "3514 Spring Garden St", so the house number is allowed an optional
    "-NN" suffix.
    """
    number, street = split_house_number(normalized)
    if not number or not street:
        return None
    if not _SAFE_ADDRESS.match(street) or not number.isdigit():
        logger.warning("refusing to query City data for an unsafe address: %r", normalized)
        return None
    return f"^{number}(-[0-9]+)? {street}"


def _query(sql: str) -> list[dict[str, Any]]:
    try:
        response = httpx.get(CARTO_SQL, params={"q": sql}, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # network, timeout, HTTP error, bad JSON
        raise CityDataUnavailable(str(exc)) from exc
    if "rows" not in payload:
        raise CityDataUnavailable(f"unexpected response shape: {sorted(payload)[:5]}")
    return payload["rows"]


def fetch_city_record(raw_address: str, limit: int = 50) -> CityRecord:
    """Look an address up in the City's licence and violation tables.

    Never raises: a City outage produces a record marked `unavailable`, which
    the caller renders as "we couldn't check right now" rather than as a
    finding. That distinction is the same one app/extractor.py draws between
    "the document said nothing" and "the provider was down".
    """
    normalized = normalize_address(raw_address)
    record = CityRecord(query_address=normalized)

    pattern = _address_regex(normalized)
    if not pattern:
        record.note = "That doesn't look like a Philadelphia street address we can look up."
        return record

    escaped = pattern.replace("'", "''")
    try:
        record.licenses = _query(
            "SELECT licensetype, licensenum, licensestatus, address, "
            "initialissuedate, expirationdate FROM business_licenses "
            f"WHERE UPPER(address) ~ '{escaped}' ORDER BY expirationdate DESC LIMIT {limit}"
        )
        record.violations = _query(
            "SELECT address, violationcodetitle, violationstatus, violationdate, "
            "casestatus FROM violations "
            f"WHERE UPPER(address) ~ '{escaped}' ORDER BY violationdate DESC LIMIT {limit}"
        )
    except CityDataUnavailable as exc:
        logger.warning("City open data unavailable for %r: %s", normalized, exc)
        record.unavailable = True
        record.note = "City records couldn't be reached just now. Nothing below is a finding about this property."
        return record

    record.address_found = bool(record.licenses or record.violations)
    if not record.address_found:
        record.note = (
            "No City records found for this address. That isn't proof there are none — "
            "the City may hold them under a different address format."
        )
    return record


def _parse_day(value: Any) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def derive_facts(record: CityRecord, today: Optional[date] = None) -> dict[str, Any]:
    """Turn City records into facts the existing rules engine already knows.

    Emits only what the records actually support:

    * `landlord_rental_license_valid` — True on an Active, unexpired rental
      licence; False when a rental licence exists but is inactive, closed or
      expired. **Omitted entirely when no rental licence row was found**, so
      the rule stays "needs facts" rather than accusing a landlord of being
      unlicensed on the strength of a missing row.
    * `li_violations_open_days` — the longest-running open violation, or 0
      when the address is present in City data with nothing open. Omitted
      when the address wasn't found at all, since "no rows" would otherwise
      read as a clean record.
    """
    if record.unavailable or not record.address_found:
        return {}

    today = today or date.today()
    facts: dict[str, Any] = {}

    rentals = record.rental_licenses
    if rentals:
        def is_current(lic: dict[str, Any]) -> bool:
            if str(lic.get("licensestatus", "")).upper() != "ACTIVE":
                return False
            expiry = _parse_day(lic.get("expirationdate"))
            return expiry is None or expiry >= today

        facts["landlord_rental_license_valid"] = any(is_current(lic) for lic in rentals)

    open_days = [
        (today - day).days
        for v in record.open_violations
        if (day := _parse_day(v.get("violationdate"))) is not None
    ]
    facts["li_violations_open_days"] = max(open_days) if open_days else 0

    return facts
