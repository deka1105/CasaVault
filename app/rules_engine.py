import logging
from datetime import timedelta
from typing import Any

from sqlmodel import Session, select

from app.condition_eval import (
    UnsafeConditionError,
    evaluate_condition,
    evaluate_condition_tristate,
    referenced_facts,
)
from app.models import Deadline, Flag, VaultEvent
from app.statutes_loader import StatuteTable

logger = logging.getLogger(__name__)


def aggregate_facts(vault_id: str, session: Session) -> dict[str, Any]:
    """Merge every event's extracted facts into one vault-level view. Later
    events (by recorded_at) win on key conflicts — e.g. a corrected
    deposit_amount recorded after the lease upload should take precedence."""
    events = session.exec(
        select(VaultEvent).where(VaultEvent.vault_id == vault_id).order_by(VaultEvent.recorded_at)
    ).all()
    facts: dict[str, Any] = {}
    for event in events:
        facts.update(event.facts or {})
    return facts


def adjudicate_vault(vault_id: str, session: Session, table: StatuteTable) -> list[Flag]:
    """Re-evaluate every verified, condition-based rule against this vault's
    aggregated facts and replace its flags. Idempotent — safe to call after
    every event write. Clock-type rules (no `condition`) are handled by
    compute_deadlines_for_event instead."""
    facts = aggregate_facts(vault_id, session)

    for existing in session.exec(select(Flag).where(Flag.vault_id == vault_id)).all():
        session.delete(existing)

    new_flags: list[Flag] = []
    for rule in table.verified_rules:
        condition = rule.get("condition")
        if not condition:
            continue
        try:
            fires = evaluate_condition(condition, facts)
        except UnsafeConditionError:
            logger.exception("bad condition in statutes.yaml for rule %s", rule.get("id"))
            continue
        if not fires:
            continue
        framing = rule.get("party_framing", {})
        flag = Flag(
            vault_id=vault_id,
            statute_id=rule["id"],
            severity=rule["severity"],
            citation=rule["citation"],
            message_tenant=framing.get("tenant"),
            message_landlord=framing.get("landlord"),
        )
        session.add(flag)
        new_flags.append(flag)

    session.commit()
    for flag in new_flags:
        session.refresh(flag)
    return new_flags


def compute_deadlines_for_event(event: VaultEvent, session: Session, table: StatuteTable) -> list[Deadline]:
    """Clock rules keyed to a specific event type — currently just the
    deposit-return clock (68 P.S. § 250.512), started by move-out with a
    recorded forwarding address. The forwarding-address condition is
    load-bearing per statutes.yaml: without it, no clock starts."""
    new_deadlines: list[Deadline] = []

    if event.event_type == "move_out" and (event.facts or {}).get("forwarding_address_provided"):
        rule = table.get_rule("deposit_return_clock")
        if rule and rule.get("status") == "verified":
            due_date = event.occurred_at + timedelta(days=30)
            # Correcting a move-out date, or re-recording the forwarding
            # address, used to append a second identical clock — the vault
            # then showed the same statutory deadline twice, with no way to
            # tell which one was real. Unlike flags (rebuilt from scratch on
            # every write by adjudicate_vault), deadlines accumulate, so this
            # has to dedupe explicitly.
            already_tracked = session.exec(
                select(Deadline).where(
                    Deadline.vault_id == event.vault_id,
                    Deadline.statute_id == rule["id"],
                    Deadline.due_date == due_date,
                )
            ).first()
            if already_tracked is None:
                deadline = Deadline(
                    vault_id=event.vault_id,
                    event_id=event.id,
                    statute_id=rule["id"],
                    due_date=due_date,
                    description=rule["party_framing"]["tenant"].format(deadline=due_date.isoformat()),
                )
                session.add(deadline)
                new_deadlines.append(deadline)

    if new_deadlines:
        session.commit()
        for deadline in new_deadlines:
            session.refresh(deadline)
    return new_deadlines


def describe_deadline(deadline: Deadline, table: StatuteTable, party: str) -> str:
    """The deadline's stored `description` is baked at creation time from the
    tenant framing, so a landlord reading their own vault saw "Your landlord
    has until ..." about themselves. Flags already re-frame per party; this
    does the same for clocks, at render time, so no second copy of the text
    has to be persisted (and no new column has to be migrated onto the live
    database — see the SQLModel note in CLAUDE.md).

    Falls back to the stored description whenever the rule or its framing is
    missing, so a deadline never renders blank.
    """
    rule = table.get_rule(deadline.statute_id)
    if not rule or rule.get("status") != "verified":
        return deadline.description
    framing = (rule.get("party_framing") or {}).get(party)
    if not framing:
        return deadline.description
    try:
        return framing.format(deadline=deadline.due_date.isoformat())
    except (KeyError, IndexError):
        # An unexpected placeholder in the statute table must not 500 a read.
        return deadline.description


def build_adjudication_report(
    vault_id: str, session: Session, table: StatuteTable, party: str = "tenant"
) -> dict[str, Any]:
    """Everything the statute table has to say about this vault — not just
    what went wrong.

    A vault holding a fully compliant lease produces no flags, so the findings
    panel rendered empty and read as "this product did nothing". It is in fact
    a result, and for a small landlord it is *the* result: a record showing
    the requirements were met. This reports three states per verified rule:

      flagged   the condition fires — a finding, with its citation
      passed    the condition is definitively false, every fact it depends on
                is recorded, so the rule is affirmatively satisfied
      unknown   a fact the rule depends on has never been recorded, so nothing
                can honestly be said either way — carries `missing` and the
                rule's `if_unknown` next step

    "unknown" is the honest category and the useful one: `no_rental_license`
    is the most common successful defense in Philadelphia landlord-tenant
    court, and a lease never states it, so it lands here every time with a
    prompt to go and check.
    """
    facts = aggregate_facts(vault_id, session)
    flagged: list[dict[str, Any]] = []
    passed: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []

    for rule in table.verified_rules:
        condition = rule.get("condition")
        if not condition:
            continue  # clock rules are tracked as deadlines, not adjudicated here
        try:
            verdict = evaluate_condition_tristate(condition, facts)
            needed = referenced_facts(condition)
        except UnsafeConditionError:
            logger.exception("bad condition in statutes.yaml for rule %s", rule.get("id"))
            continue

        entry = {
            "statute_id": rule["id"],
            "citation": rule["citation"],
            "severity": rule.get("severity"),
            "requirement": rule.get("requirement"),
            "detail": rule.get("detail"),
        }

        if verdict is True:
            # Only a rule that actually fired gets the party_framing, which is
            # phrased as an assertion that the violation happened. Printing
            # that on a satisfied rule states the opposite of the truth.
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
