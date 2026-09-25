import html
from typing import Any

from app.models import Deadline, Flag, Vault, VaultEvent

_SEVERITY_ORDER = {"violation": 0, "caution": 1}


def _esc(value: Any) -> str:
    return html.escape(str(value)) if value is not None else ""


def render_evidence_packet(
    vault: Vault,
    events: list[VaultEvent],
    flags: list[Flag],
    deadlines: list[Deadline],
    party: str = "tenant",
    document_base: str | None = None,
    deadline_descriptions: dict[int, str] | None = None,
) -> str:
    """Renders a single, self-contained, print-to-PDF-friendly HTML page —
    chronological events, then flags with citations, then open deadlines.
    PLAN.md: 'Output: a printable evidence packet, chronological, with
    citations.' No JS, no external assets — must render identically from a
    saved file, since it will be printed straight from the browser."""

    ordered_events = sorted(events, key=lambda e: e.occurred_at)
    ordered_flags = sorted(flags, key=lambda f: _SEVERITY_ORDER.get(f.severity, 99))
    # One rule, two framings (PLAN.md). The packet used to hardcode
    # message_tenant, so a landlord printing their own vault's evidence got
    # the tenant's side of every finding.
    document_base = document_base or f"/api/vaults/{vault.id}/documents"
    descriptions = deadline_descriptions or {}

    event_rows = "\n".join(
        f"<tr><td>{_esc(e.occurred_at)}</td><td>{_esc(e.event_type)}</td>"
        f"<td>{_esc(e.notes or '')}</td>"
        f"<td><pre>{_esc(_format_facts(e.facts))}</pre></td>"
        f"<td>{_document_link(document_base, e)}</td></tr>"
        for e in ordered_events
    ) or "<tr><td colspan='5'><em>No events recorded.</em></td></tr>"

    flag_rows = "\n".join(
        f"<tr class='severity-{_esc(f.severity)}'><td>{_esc(f.severity)}</td>"
        f"<td>{_esc(_framing(f, party))}</td><td>{_esc(f.citation)}</td></tr>"
        for f in ordered_flags
    ) or "<tr><td colspan='3'><em>No flags.</em></td></tr>"

    deadline_rows = "\n".join(
        f"<tr><td>{_esc(d.due_date)}</td><td>{_esc(descriptions.get(d.id, d.description))}</td>"
        f"<td>{'resolved' if d.resolved else 'open'}</td></tr>"
        for d in deadlines
    ) or "<tr><td colspan='3'><em>No deadlines tracked.</em></td></tr>"

    ack_line = (
        f"Acknowledged by counterparty at {_esc(vault.acknowledged_at)}"
        if vault.acknowledged_at
        else "Not yet acknowledged by counterparty"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CasaVault evidence packet — {_esc(vault.label or vault.id)}</title>
<style>
  body {{ font-family: Georgia, 'Times New Roman', serif; max-width: 800px; margin: 2rem auto; color: #111; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 0; }}
  .disclaimer {{ color: #444; font-size: 0.85rem; margin-top: 0.25rem; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0 2rem; }}
  th, td {{ border: 1px solid #999; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.9rem; vertical-align: top; }}
  th {{ background: #eee; }}
  .severity-violation {{ background: #fdecec; }}
  .severity-caution {{ background: #fff8e1; }}
  pre {{ margin: 0; white-space: pre-wrap; font-size: 0.8rem; }}
  @media print {{ body {{ margin: 0; }} }}
</style>
</head>
<body>
  <h1>CasaVault evidence packet</h1>
  <p class="disclaimer">This is rights information, not legal advice. Vault: {_esc(vault.label or vault.id)} · Jurisdiction: Philadelphia, PA · {_esc(party.title())} view · {ack_line}</p>

  <h2>Timeline</h2>
  <table>
    <thead><tr><th>Date</th><th>Event</th><th>Notes</th><th>Facts</th><th>Document</th></tr></thead>
    <tbody>{event_rows}</tbody>
  </table>

  <h2>Statutory flags</h2>
  <table>
    <thead><tr><th>Severity</th><th>Finding</th><th>Citation</th></tr></thead>
    <tbody>{flag_rows}</tbody>
  </table>

  <h2>Deadlines</h2>
  <table>
    <thead><tr><th>Due</th><th>Description</th><th>Status</th></tr></thead>
    <tbody>{deadline_rows}</tbody>
  </table>
</body>
</html>"""


def _format_facts(facts: dict[str, Any]) -> str:
    return "\n".join(f"{k}: {v}" for k, v in (facts or {}).items()) or "—"


def _framing(flag: Flag, party: str) -> str:
    """Falls back to the other party's wording, then the rule id, so a rule
    authored with only one framing still reads as a sentence rather than a
    bare identifier."""
    primary = flag.message_landlord if party == "landlord" else flag.message_tenant
    secondary = flag.message_tenant if party == "landlord" else flag.message_landlord
    return primary or secondary or flag.statute_id


def _document_link(document_base: str, event: VaultEvent, documents: dict[int, list] | None = None) -> str:
    """Every file attached to the event, not just one.

    A real lease is ~25 documents filed under a single 'lease signed' entry,
    and an evidence packet that listed one of them would misrepresent the
    record it exists to prove. Files the extractor deliberately skipped are
    marked, so the packet never implies a document was read when it wasn't.
    """
    attached = (documents or {}).get(event.id) or []
    if attached:
        return "<br>".join(
            f'<a href="{_esc(document_base)}/{d.id}">{_esc(d.original_filename or "view")}</a>'
            + ("" if d.extraction_status not in ("not_read", "skipped") else " <em>(stored, not read)</em>")
            for d in attached
        )
    if not event.source_document_ref:
        return ""
    label = _esc(event.original_filename or "view")
    return f'<a href="{_esc(document_base)}/{event.id}">{label}</a>'
