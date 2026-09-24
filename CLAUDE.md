# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status: greenfield

This directory is currently empty except for `PLAN.md` (full project spec) and
`statutes.yaml` (the statute table). No application code, no git repo, no
dependency manifests exist yet. This is a hackathon build (LexHack 2026) with a
hard submission deadline of **Sun Sep 27, 2026, 5:00 PM EDT** — read `PLAN.md`'s
build-order table before starting any work session to know what day/gate we're
against.

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

- FastAPI + SQLite (backend)
- Plain HTML/JS front end, no framework
- LLM extraction via API, schema-constrained output
- Statute rules in YAML (`statutes.yaml`), loaded at startup
- Agent retrieval scoped to vault rows + rules rows only — no open web/model knowledge
- No build tooling exists yet; commands will be added here once the backend scaffold lands

## `statutes.yaml` conventions

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
