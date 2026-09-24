# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

FastAPI skeleton is in place (vault + event CRUD, statute loader, agent stub
that always refuses — see below). Extraction, the rules engine, and the real
grounded agent are not implemented yet. This is a hackathon build (LexHack
2026) with a hard submission deadline of **Sun Sep 27, 2026, 5:00 PM EDT** —
read `PLAN.md`'s build-order table before starting any work session to know
what day/gate we're against.

## Commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload   # dev server, http://127.0.0.1:8000
pytest -q                       # full test suite
pytest -q -k test_name          # single test
```

## What CasaVault is

A statute-aware record of a rental relationship. A tenant or small landlord
holds one vault per tenancy; every document/event uploaded is adjudicated
against a Philadelphia/PA statute table, deadlines are tracked automatically,
and a grounded Q&A agent answers only from the vault + statute table — never
from model knowledge. Full pitch, problem statement, and judging rubric are in
`PLAN.md`.

## Architecture (locked)

```
document/event ──> extractor (LLM, schema-bound) ──> facts
                                                       │
                     statute table (YAML) ─────────────┤
                                                       ▼
                                         flags + deadlines + citations
                                                       │
                                    grounded agent ────┘
                                 (retrieval limited to vault + table)
```

Four pipeline stages, each with a distinct responsibility that must not blur:

1. **Extract** — LLM parses a document into a fixed schema. It never judges legality.
2. **Adjudicate** — a deterministic rules engine joins extracted facts against
   `statutes.yaml`. Every flag must carry the statute section that produced it.
3. **Track** — events that start statutory clocks (e.g. move-out) become dated deadlines.
4. **Answer** — a grounded agent queries the vault + statute table only.

The statute table is the product; lease audit, notice checker, deadline
tracker, and the agent are four thin entry points onto one engine.

## Stack

- FastAPI + SQLite (backend), SQLModel for the ORM layer
- Plain HTML/JS front end, no framework — served as static files from `static/`, mounted last in `app/main.py` so it doesn't shadow `/api/*`
- LLM extraction via API, schema-constrained output — not built yet
- Statute rules in YAML (`statutes.yaml`), loaded at startup via `app/statutes_loader.py`
- Agent retrieval scoped to vault rows + rules rows only — no open web/model knowledge

## Current API surface

- `POST /api/vaults`, `GET /api/vaults/{id}`, `GET /api/vaults/by-share-token/{token}`
- `POST /api/vaults/{id}/events` — records a timeline event, then re-runs adjudication (see below)
- `GET /api/vaults/{id}/events` — raw timeline events
- `GET /api/vaults/{id}/flags` — current adjudication result, recomputed from scratch on every event write
- `GET /api/vaults/{id}/deadlines` — statutory clocks started so far (currently just the deposit-return clock)
- `GET /api/statutes` — verified rules only (draft rules never serialize out; see `statutes_loader.StatuteTable.verified_rules`)
- `GET /api/vaults/{id}/rtc-check` — Right to Counsel zip lookup (`app/rtc.py`), shared with the agent stub's handoff
- `POST /api/vaults/by-share-token/{token}/acknowledge` — counterparty one-click ack; first click wins, sets `Vault.acknowledged_at` once and is idempotent after that
- `GET /api/vaults/{id}/evidence` — server-rendered, print-to-PDF-friendly HTML evidence packet (`app/evidence.py`); no JS, no external assets, chronological with citations
- `POST /api/vaults/{id}/ask` — **stub**: always returns a refusal + RTC/hotline handoff, since no grounded retrieval exists yet. Do not make this "helpful" by having it answer from model knowledge — that violates the agent's core constraint in `PLAN.md`. Replace it with real grounding, not a shortcut.

## Front end (`static/`)

Plain HTML/JS, single page, no build step. `app.js` drives everything off
`?vault=<id>` (owner) or `?share=<token>` (read-only counterparty) query
params — the same page renders both modes, gating owner-only controls
(event form, share link) on `state.isOwner`. Facts are entered as a raw JSON
textarea, not a generated form, since fact keys are whatever the current
statute conditions reference — see the "cheap interfaces" note in `PLAN.md`.

## Rules engine (`app/rules_engine.py`, `app/condition_eval.py`)

- `aggregate_facts` merges every `VaultEvent.facts` dict for a vault into one
  fact set (later `recorded_at` wins on key conflicts). Adjudication runs
  against this vault-level view, not a single event in isolation — most
  `condition` strings in `statutes.yaml` reference facts that come from
  different documents (e.g. lease-signing facts vs. move-out facts).
- `condition_eval.evaluate_condition` is a narrow, `ast`-based evaluator
  (and/or/not, comparisons, bare names, literals only — no calls/attributes).
  It also normalizes the statute table's authoring conventions into valid
  Python: `AND`/`OR`/`NOT` → lowercase, and lowercase `true`/`false` →
  `True`/`False`. **If a new statute rule's condition still evaluates wrong,
  check this normalization step before assuming the rule text is broken** —
  bare `true`/`false` silently parsing as unbound names (always false) was
  a real bug caught by `tests/test_rules_engine.py`.
- `adjudicate_vault` only handles rules with a `condition` key. Clock-type
  rules (`type: deadline`, no `condition`) are special-cased per event type
  in `compute_deadlines_for_event` — currently just `deposit_return_clock`,
  gated on the move-out event's `forwarding_address_provided` fact per the
  statute's load-bearing requirement.
- A bad/unparseable condition logs and is skipped, not raised — one broken
  statute row must not take down event creation for every vault.

Not implemented yet: LLM extraction (Fri AM gate — needs an LLM API key,
deliberately deferred; extractor provider not yet chosen), the real
grounded agent.

## `statutes.yaml` conventions

- Rules live under a top-level `rules:` key (a YAML block sequence can't be a
  sibling of the `jurisdiction:` mapping key at the same indentation — the
  file as originally drafted didn't parse; this was fixed in the first commit).
- `status: verified` vs `status: draft` — **draft rules must never render to a
  user.** They exist as tracked TODOs pending a pin cite (see section C,
  habitability, in the file). Any code path that reads this table must filter
  on `status == verified` before surfacing a flag.
- Every rule carries a `citation`. A flag or agent answer with no citation is
  a bug, not a style issue — this is a hard product constraint, not just a
  data-quality nicety.
- `party_framing.tenant` / `party_framing.landlord` — the same rule, two
  wordings, for the tenant-view/landlord-view toggle. One condition, two
  framings; do not fork the rule itself per party.
- `condition` strings are the informal spec for the rules-engine DSL — no
  engine implements them yet, so the first implementation decides the actual
  evaluation syntax.
- `right_to_counsel` block (covered zips, hotline, fallback URL) drives the
  zip-check handoff feature — this is data, not a hardcoded string in app code.

## Scope — LOCKED (see `PLAN.md` for full detail)

**In:** single demo vault (no signup), tenant/landlord view toggle, document
upload → extraction → cited flags, timeline events, deposit/repair deadline
clocks, grounded agent with mandatory citation + explicit refusal,
read-only counterparty share link with timestamped acknowledgement, evidence
packet export (print-to-PDF), RTC zip check → hotline/PhillyTenant.org handoff.

**Out — do not build:** homeownership law (mortgage/HOA/liens/tax appeals),
real auth/accounts/password reset, any jurisdiction beyond Philadelphia/PA,
ungrounded chat, notifications/email/SMS/payments/mobile app, file storage
beyond local disk.

If asked to add something from the "Out" list, flag that it's explicitly
out of scope per `PLAN.md` before implementing it.

## Non-negotiables

- This is rights information, not legal advice — must say so in the UI and any write-up.
- Every flag and every agent claim cites a source (a vault entry or a
  `statutes.yaml` row). No uncited legal conclusion may reach a user.
- The agent refuses rather than guesses, and the refusal routes to a human
  (Philly Tenant Hotline for RTC-covered zips, PhillyTenant.org otherwise).
  This must be enforced structurally (the agent's retrieval surface is
  vault + rules table, nothing else), not by prompt instruction alone.
- Nothing shown in the demo video may be non-functional.

## Cut list — if behind schedule, drop in this order

1. Party toggle (ship tenant view only)
2. Counterparty acknowledgement (share link stays read-only)
3. Inspection photo handling (text events only)
4. Payment events
5. Deadline clocks beyond the deposit-return clock

Never cut: extraction, citations on flags, the agent's refusal path, the
evidence export, the real-lease end-to-end test.
