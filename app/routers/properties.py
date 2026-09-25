"""The public address surface — Tier A and Tier B.

Anyone can look up any Philadelphia address here without signing in and
without holding a vault. That is the point: the record belongs to the
property, so it has to be readable by the person deciding whether to move in.

What this surface may and may not expose is decided by **where a fact came
from**, not by who owns it:

  Tier A  City records — licences, violations. Already public, published by
          the City, owing nothing to either the landlord's or the tenant's
          account. Always shown.
  Tier B  De-identified incident history — "a heating repair was reported in
          this building on 14 Mar, resolved 2 Apr". Never a name, never a
          unit, never a vault id.
  Tier C  Anything inside a vault — documents, lease terms, deposit amounts.
          **Never served from here.** It moves only when its holder discloses
          it to a named counterparty.

CARFAX publishes the DMV record, not what the last owner said about the car.
Same rule. tests/test_properties.py asserts no vault id, resident name or
Tier C content can leave this router.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app import city_data
from app.database import get_session
from app.models import Incident, Property, PropertyLink

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/properties", tags=["properties"])

# Below this many tenancies at an address, incident history is withheld: in a
# duplex, "a repair was reported here in March" identifies a person as surely
# as naming them. Buildings large enough to blur the individual still get the
# benefit of a shared record.
MIN_TENANCIES_FOR_HISTORY = 2


def get_or_create_property(address: str, session: Session, zip_code: Optional[str] = None) -> Optional[Property]:
    """Resolve a typed address to the one Property row that represents it."""
    normalized = city_data.normalize_address(address)
    if not normalized:
        return None
    existing = session.exec(
        select(Property).where(Property.address_normalized == normalized)
    ).first()
    if existing:
        # Keep the first display form; later spellings of the same building
        # shouldn't churn it.
        if zip_code and not existing.zip_code:
            existing.zip_code = zip_code
            session.add(existing)
            session.commit()
            session.refresh(existing)
        return existing

    # Display keeps the user's own capitalisation but drops the city/state/zip
    # tail, so "4047 Spring Garden Street, Philadelphia, PA" reads back as
    # "4047 Spring Garden Street" and a unit can be appended cleanly.
    display = (address or "").split(",")[0].strip() or normalized
    prop = Property(address_normalized=normalized, address_display=display, zip_code=zip_code)
    session.add(prop)
    session.commit()
    session.refresh(prop)
    return prop


def _city_payload(record: city_data.CityRecord) -> dict[str, Any]:
    """Shape the City record for display, hedged where the data is silent."""
    rentals = record.rental_licenses
    current = [lic for lic in rentals if str(lic.get("licensestatus", "")).upper() == "ACTIVE"]

    if record.unavailable:
        licence_summary = "City records couldn't be reached just now."
    elif not record.address_found:
        licence_summary = "No City records found for this address."
    elif current:
        licence_summary = "An active rental licence is on file with the City."
    elif rentals:
        licence_summary = "A rental licence is on file, but it is not currently active."
    else:
        # The distinction that keeps this honest: silence is not an accusation.
        licence_summary = (
            "No rental licence found for this address. Not every property needs one — "
            "an owner-occupied home doesn't — and the City may hold it under a different "
            "address format."
        )

    return {
        "queried": record.query_address,
        "found": record.address_found,
        "unavailable": record.unavailable,
        "note": record.note,
        "licence_summary": licence_summary,
        "licences": [
            {
                "type": lic.get("licensetype"),
                "status": lic.get("licensestatus"),
                "issued": lic.get("initialissuedate"),
                "expires": lic.get("expirationdate"),
                "address": lic.get("address"),
            }
            for lic in rentals[:10]
        ],
        "open_violations": [
            {
                "title": v.get("violationcodetitle"),
                "status": v.get("violationstatus"),
                "date": v.get("violationdate"),
                "address": v.get("address"),
            }
            for v in record.open_violations[:10]
        ],
        "violation_count": len(record.violations),
        "open_violation_count": len(record.open_violations),
        "source": "Philadelphia Department of Licenses & Inspections, via the City's open data",
    }


@router.get("/lookup")
def lookup_property(
    address: str = Query(..., min_length=3, max_length=200),
    session: Session = Depends(get_session),
):
    """Everything publicly knowable about an address.

    Works for any Philadelphia address, including one nobody has a record
    for — the City half never depends on this app having been used before.
    """
    record = city_data.fetch_city_record(address)
    normalized = record.query_address

    prop = session.exec(
        select(Property).where(Property.address_normalized == normalized)
    ).first()

    tenancies = 0
    history: list[dict[str, Any]] = []
    withheld = False

    if prop is not None:
        tenancies = len(
            session.exec(select(PropertyLink).where(PropertyLink.property_id == prop.id)).all()
        )
        if tenancies >= MIN_TENANCIES_FOR_HISTORY:
            incidents = session.exec(
                select(Incident)
                .where(Incident.property_id == prop.id)
                .order_by(Incident.reported_at.desc())
            ).all()
            history = [_deidentified(i) for i in incidents[:25]]
        else:
            withheld = True

    return {
        "address": {
            "normalized": normalized,
            "display": prop.address_display if prop else (address or "").strip(),
            "known_to_us": prop is not None,
        },
        "city_record": _city_payload(record),
        "history": history,
        "history_withheld": withheld,
        "history_note": (
            "Repair history is held back until more than one tenancy at an address has "
            "recorded something — in a small building, a single entry identifies a person."
            if withheld
            else None
        ),
    }


def _deidentified(incident: Incident) -> dict[str, Any]:
    """Tier B: the shape of what happened, with the person removed.

    No vault id, no unit, no name, no free-text detail — a description
    written by a resident can name them without meaning to.
    """
    return {
        "category": incident.category,
        "urgency": incident.urgency,
        "affected_essential_service": incident.affects_essential_service,
        "reported": incident.reported_at,
        "work_started": incident.work_started_at,
        "resolved": incident.resolved_at,
        "days_to_resolve": (
            (incident.resolved_at - incident.reported_at).days
            if incident.resolved_at and incident.reported_at
            else None
        ),
    }
