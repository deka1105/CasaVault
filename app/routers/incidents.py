"""Report an incident, and draft the notice that proves you reported it.

Why this matters more than a form: the vault could already record "I told
them about the leak on 14 March", but that was the resident's own say-so. An
email carries a send time, a named recipient and a copy in the resident's own
mailbox — provenance from outside this app. Written notice is load-bearing
under PA and Philadelphia law, so this turns a diary entry into evidence that
notice was given, and supplies the `reported` timestamp the property's work
history is built from.

Two rules govern the draft:

1. **We never send it.** The user's own mail client does. A notice arriving
   from casavault.app is weaker evidence that the *resident* gave notice, it
   would make this app the sender of a housing dispute, and the copy-to-self
   is automatic when it comes from the resident's own outbox.
2. **The draft states facts and asks for a repair. It makes no legal claim.**
   statutes.yaml has no *verified* rule about repair obligations — the
   habitability rules are still `status: draft` pending a pin cite — so
   citing law here would mean asserting something this project has not
   confirmed, in a letter to a third party. Facts, dates and a reference
   number are strong on their own; the user can add more if they choose.
"""

import logging
import uuid
from datetime import date
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import require_user_id
from app.database import get_session
from app.models import Incident, PropertyLink, Vault, VaultEvent
from app.schemas import IncidentCreate, IncidentDraft, IncidentRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vaults/{vault_id}/incidents", tags=["incidents"])

CATEGORY_LABELS = {
    "heat": "No heat",
    "hot_water": "No hot water",
    "water_leak": "Water leak",
    "electrical": "Electrical problem",
    "pest": "Pests",
    "mold": "Damp or mould",
    "security": "Door, lock or security problem",
    "appliance": "Appliance not working",
    "structural": "Structural problem",
    "other": "Repair needed",
}

URGENCY_LABELS = {"emergency": "EMERGENCY", "urgent": "Urgent", "routine": "Routine"}


def _reference_code() -> str:
    return uuid.uuid4().hex[:6].upper()


def _subject(incident: Incident, address: str, reporter: str) -> str:
    """`issue | urgency | address | name | #ref`

    Issue and urgency lead so the line survives truncation in a crowded
    inbox. The reference code trails so a reply threads back to this
    incident, which is how "work started" and "resolved" get captured later
    without the resident re-entering them.
    """
    parts = [
        CATEGORY_LABELS.get(incident.category, "Repair needed"),
        URGENCY_LABELS.get(incident.urgency, incident.urgency),
        address,
        reporter,
        f"#{incident.reference_code}",
    ]
    return " | ".join(p for p in parts if p)


def _body(incident: Incident, address: str, reporter: str) -> str:
    reported = incident.reported_at or date.today()
    lines = [
        "Hello,",
        "",
        f"I am writing to report a problem at {address} and to ask that it be repaired.",
        "",
        f"Issue: {CATEGORY_LABELS.get(incident.category, 'Repair needed')}",
        f"Reported: {reported.isoformat()}",
        f"Reference: #{incident.reference_code}",
        "",
        incident.summary.strip(),
    ]
    if incident.detail and incident.detail.strip():
        lines += ["", incident.detail.strip()]

    if incident.affects_essential_service:
        lines += [
            "",
            "This is affecting an essential service (heat, water, electricity or the "
            "security of the property).",
        ]
    if incident.previously_reported:
        lines += ["", "I have reported this before and it has not yet been resolved."]

    lines += [
        "",
        "Please confirm you have received this, and let me know when the repair will be "
        "carried out. I am keeping a dated record of this request and of any work done.",
        "",
        "Thank you,",
        reporter or "",
    ]
    return "\n".join(lines)


def build_draft(incident: Incident, address: str, reporter: str, cc: str | None = None) -> IncidentDraft:
    subject = _subject(incident, address, reporter)
    body = _body(incident, address, reporter)

    params = {"subject": subject, "body": body}
    if cc:
        # The resident's copy. Mostly redundant when they send from their own
        # client — it lands in Sent — but an explicit CC survives a client
        # that doesn't keep one, and makes the copy visible to the recipient.
        params["cc"] = cc

    to = (incident.management_email or "").strip()
    mailto = f"mailto:{quote(to)}?{urlencode(params, quote_via=quote)}"
    return IncidentDraft(subject=subject, body=body, to=to or None, cc=cc or None, mailto=mailto)


def _require_vault(vault_id: str, session: Session) -> Vault:
    vault = session.get(Vault, vault_id)
    if vault is None:
        raise HTTPException(status_code=404, detail="vault not found")
    return vault


def _address_for(vault: Vault, session: Session) -> str:
    """Prefer the linked property, fall back to the vault's own label."""
    link = session.exec(
        select(PropertyLink).where(PropertyLink.vault_id == vault.id)
    ).first()
    if link:
        from app.models import Property

        prop = session.get(Property, link.property_id)
        if prop:
            return f"{prop.address_display}{f' {link.unit}' if link.unit else ''}".strip()
    return vault.label or "my home"


@router.post("", response_model=IncidentRead)
async def create_incident(
    vault_id: str,
    payload: IncidentCreate,
    session: Session = Depends(get_session),
    _user: str = Depends(require_user_id),
):
    """Record the incident and return a draft for the user to read and send.

    Returns the draft; it does not send anything. Sending is the user's
    deliberate act in their own mail client.
    """
    vault = _require_vault(vault_id, session)

    link = session.exec(select(PropertyLink).where(PropertyLink.vault_id == vault.id)).first()
    reported = payload.reported_at or date.today()

    incident = Incident(
        vault_id=vault.id,
        property_id=link.property_id if link else None,
        reference_code=_reference_code(),
        category=payload.category,
        urgency=payload.urgency,
        summary=payload.summary.strip(),
        detail=(payload.detail or "").strip() or None,
        affects_essential_service=payload.affects_essential_service,
        previously_reported=payload.previously_reported,
        reported_at=reported,
        management_email=(payload.management_email or "").strip() or None,
        insurance_email=(payload.insurance_email or "").strip() or None,
    )
    session.add(incident)
    session.commit()
    session.refresh(incident)

    # Also a timeline event, so it appears in the vault's history and in the
    # printable evidence packet with no extra plumbing.
    event = VaultEvent(
        vault_id=vault.id,
        event_type="incident_reported",
        occurred_at=reported,
        notes=f"{CATEGORY_LABELS.get(incident.category, 'Repair')} — {incident.summary}"
        f" (ref #{incident.reference_code})",
        facts={},
    )
    session.add(event)
    session.commit()
    session.refresh(event)

    incident.event_id = event.id
    session.add(incident)
    session.commit()
    session.refresh(incident)

    address = _address_for(vault, session)
    reporter = (payload.reporter_name or "").strip()
    draft = build_draft(incident, address, reporter, cc=incident.insurance_email)

    view = IncidentRead.model_validate(incident, from_attributes=True)
    view.draft = draft
    return view


@router.get("", response_model=list[IncidentRead])
def list_incidents(vault_id: str, session: Session = Depends(get_session)):
    _require_vault(vault_id, session)
    incidents = session.exec(
        select(Incident).where(Incident.vault_id == vault_id).order_by(Incident.reported_at.desc())
    ).all()
    return [IncidentRead.model_validate(i, from_attributes=True) for i in incidents]
