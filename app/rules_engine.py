import logging
from datetime import timedelta
from typing import Any

from sqlmodel import Session, select

from app.condition_eval import UnsafeConditionError, evaluate_condition
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

    if event.event_type == "move_out" and event.facts.get("forwarding_address_provided"):
        rule = table.get_rule("deposit_return_clock")
        if rule and rule.get("status") == "verified":
            due_date = event.occurred_at + timedelta(days=30)
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
