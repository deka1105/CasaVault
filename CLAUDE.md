# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

The full pipeline is built and live-verified end to end: upload a document →
Gemini extracts facts → rules engine flags them with citations → grounded
agent answers questions over the vault + statute table, citing or refusing.
Also done: share link, counterparty acknowledgement, evidence packet, RTC
zip-check, document upload/download, front end. This is a hackathon build
(LexHack 2026) with a hard submission deadline of **Sun Sep 27, 2026, 5:00 PM
EDT** — read `PLAN.md`'s build-order table before starting any work session
to know what day/gate we're against.

**Gemini free-tier rate limit — read this before doing more live testing.**
The configured key hit `20 requests per day on Free Tier` for
`gemini-3.8-flash` during development (confirmed via a real 429 from the
API, not a guess). Every document upload and every `/ask` call is one
request. This is far too low for the actual demo/judging session, let alone
further dev iteration — **upgrade this key's tier/billing before Saturday's
demo**, or the app will start refusing extractions and agent answers mid-use
with no visible warning to the user (it silently falls back to "safe
refusal" behavior, which will look like a bug, not a quota issue, unless you
know to check server logs for `RateLimitError`).

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
- LLM extraction via Gemini (`google-genai`), schema-constrained output
- Statute rules in YAML (`statutes.yaml`), loaded at startup via `app/statutes_loader.py`
- Agent retrieval scoped to vault rows + rules rows only — no open web/model knowledge

## Current API surface

- `POST /api/vaults`, `GET /api/vaults/{id}`, `GET /api/vaults/by-share-token/{token}`
- `POST /api/vaults/{id}/events` — records a timeline event, then re-runs adjudication (see below)
- `GET /api/vaults/{id}/events` — raw timeline events
- `GET /api/vaults/{id}/flags` — current adjudication result, recomputed from scratch on every event write
- `GET /api/vaults/{id}/deadlines` — statutory clocks started so far (currently just the deposit-return clock)
- `GET /api/statutes` — verified rules only (draft rules never serialize out; see `statutes_loader.StatuteTable.verified_rules`)
- `GET /api/vaults/{id}/rtc-check` — Right to Counsel zip lookup (`app/rtc.py`), shared with the agent's refusal handoff
- `POST /api/vaults/by-share-token/{token}/acknowledge` — counterparty one-click ack; first click wins, sets `Vault.acknowledged_at` once and is idempotent after that
- `GET /api/vaults/{id}/evidence` — server-rendered, print-to-PDF-friendly HTML evidence packet (`app/evidence.py`); no JS, no external assets, chronological with citations
- `POST /api/vaults/{id}/ask` — the grounded agent (`app/agent.py`). Live-verified: refuses on ungroundable questions, refuses on "will I win in court"-style legal conclusions, and answers with a citation when the vault/statute data actually supports it. See the Agent section below for how refusal is enforced in code, not just prompted.
- `POST /api/vaults/{id}/documents` (multipart), `GET /api/vaults/{id}/documents/{event_id}` — real file upload/download, backing `document_upload` events. See below.

## Document uploads (`app/documents.py`, `app/storage.py`, `app/routers/documents.py`)

- The on-disk/durable name is always randomized (`app/documents.py:stored_filename`)
  — the client's filename is never trusted for the path, only for its
  extension (allowlisted: pdf/jpg/jpeg/png/heic/txt/docx) and for display
  (`VaultEvent.original_filename`, used only in the download's
  `Content-Disposition` and in the UI/evidence packet, never as a path).
  Uploads are capped at 15MB (`MAX_UPLOAD_BYTES`).
- This is public-facing (PLAN.md: deploy to a public URL), so treat upload
  handling as attack surface: downloads are always forced to
  `Content-Disposition: attachment` (built manually in
  `documents.py:_content_disposition`, CR/LF/quote-stripped against header
  injection) — never switch an uploaded file to inline serving, since a
  stored .txt/.pdf rendered inline under this origin is a stored-content
  risk.
- Creates a `document_upload` `VaultEvent`, then hands the stored file to
  the extractor (see below), which fills in `facts` on success.
- **Storage backend is abstracted in `app/storage.py`** specifically so this
  app doesn't break on Vercel — see the Vercel deployment section below for
  why and how.

## Deploying to Vercel

The original stack (SQLite file + local `uploads/` disk directory) breaks on
Vercel's ephemeral Functions — nothing guarantees either survives a cold
start or redeploy. Fixed by making both swappable, not by rearchitecting:

- **Database**: `app/database.py` uses SQLite locally (`connect_args`
  applied only when `DATABASE_URL` starts with `sqlite`) and Postgres in
  production. Chosen over Turso (SQLite-hosted) specifically because SQLite
  is single-writer even hosted, a real risk under concurrent serverless
  invocations — Postgres has none of that, and Neon has first-party Vercel
  Marketplace provisioning. **Use Neon's pooled (`-pooler` hostname)
  connection string**, and note `poolclass=NullPool` is set for non-SQLite —
  Neon's pooler already runs PgBouncer in front of Postgres, so SQLAlchemy's
  own pooling on top would just be a redundant second pool.
- **File storage**: `app/storage.py` picks a backend by whether
  `BLOB_READ_WRITE_TOKEN` is set — local disk if not (dev/test default, zero
  external credentials needed), Vercel Blob if so. Storage refs are prefixed
  (`blob:...` vs a bare relative path) so `read()`/`delete()` never have to
  guess which backend wrote a given ref. Uses the **official `vercel` PyPI
  package** (`vercel.blob` — `put`/`get`/`delete`), confirmed to exist and
  inspected directly from its installed source and README (not just a doc
  summary) after an initial web search surfaced a plausible-looking but
  wrong REST endpoint shape. Uploads use `access="private"` and
  `add_random_suffix=False` (the app already generates a unique name).
  `extract_facts_from_file` needed **zero changes** — the upload handler
  still writes the file to a local path first (`storage.save_temp`, which is
  `UPLOADS_DIR`/`/tmp` depending on environment) for the extractor to read,
  and only *then* persists the durable copy (`storage.persist`).
- **Runtime**: no rewrite needed. Vercel's own FastAPI docs confirm
  `app/main.py` exporting `app` is a directly supported zero-config
  entrypoint (no `api/index.py` wrapper), and — importantly — that an
  `app.mount(..., StaticFiles(...))` call is **automatically promoted to CDN
  serving** at build time, provided routes declared before it still reach
  the function. `app/main.py` already does exactly this (API routes
  registered, then the static mount last), so **the front end needs zero
  changes** for Vercel either. `vercel.json` only sets `maxDuration: 120`
  as an explicit safety margin — Fluid Compute's 300s default already
  covers every Gemini call timed this session (~90s max).
- **Provisioning status** (team `shubham-ad-s-projects`, project `casavault`,
  id `prj_H5qOmZidImbAO138ZSbyPF8xNG4s`):
  - ✅ Neon Postgres connected, **live-verified**: table creation, insert, and
    a JSON-column round-trip all succeeded against the real database.
    **Found and fixed a real bug this way**: SQLAlchemy's bare
    `postgresql://` scheme (exactly what Neon's dashboard hands out) silently
    resolves to the `psycopg2` dialect, but this project installs `psycopg`
    (v3) — `ModuleNotFoundError: No module named 'psycopg2'` at engine
    creation. `app/database.py` now rewrites `postgresql://` →
    `postgresql+psycopg://` before calling `create_engine`, so a
    copy-pasted Neon connection string just works without the caller
    needing to know SQLAlchemy driver syntax.
  - ✅ Vercel Blob connected, **private access, live-verified**: a real
    put/get/delete round-trip against the actual store succeeded from
    `app/storage.py`. **Note for next time**: the store must be created with
    "Private" access explicitly — a first attempt defaulted to public, and
    `vercel.blob.put(..., access="private")` correctly rejects that mismatch
    with `Cannot use private access on a public store`. That store was
    deleted and recreated private.
  - ❌ Git repo not yet connected to the Vercel project — `deka1105/CasaVault`
    needs Vercel's own GitHub App installed on it (Project Settings → Git →
    Connect Git Repository); a `create_git_project` API call failed with
    `repo_not_found` for exactly this reason.
  - Creating Vercel storage resources via the MCP/API tools returned `403
    Forbidden: You don't have permission to create the blob` consistently —
    this needs to be done from the dashboard, not automatable from here even
    with team access confirmed elsewhere.
  - ✅ **Deployed and live at https://casavault.vercel.app** — git repo
    connected (Vercel's GitHub App on `deka1105/CasaVault`, production
    branch `master`), deployed, and end-to-end verified against the real
    production URL: vault create/read (Postgres), document upload/download
    (Blob, `source_document_ref` correctly shows the `blob:` prefix, content
    byte-identical on download).
  - **Real bug caught only by testing the actual deployment, not local dev**:
    `UPLOADS_DIR` defaulted to a path under the deployed code directory
    (`/var/task`), which is **read-only** on Vercel —
    `OSError: [Errno 30] Read-only file system`. Local dev never hits this
    because the local filesystem is writable everywhere. Fixed by setting
    `UPLOADS_DIR=/tmp/casavault-uploads` as a project env var (Vercel's
    writable per-invocation scratch space) — `app/storage.py` itself needed
    no code change, since this was purely a missing env var, not a logic
    bug. **If a future deploy throws this same read-only error, check this
    env var is still set before assuming the code regressed.**
  - Note on promotion: redeploying the *same* commit (e.g. after only an
    env var change, no new code) does not automatically move to `target:
    production` / the `casavault.vercel.app` alias — `request_promote`
    also didn't work here (`422`). What worked: `create_deployment` with an
    explicit `deploymentId` (redeploy of the built one) and `target:
    "production"`.
  - LLM extraction/agent were **not** re-tested against this live
    deployment — `GEMINI_API_KEY` was never added to the Vercel project
    (deliberately, to conserve the free-tier daily quota already mostly
    used locally). Add it as a project env var and redeploy to enable.
    Storage/persistence — the actual subject of this fix — is fully proven;
    extraction/agent logic itself was already proven separately, against
    the real Gemini API, earlier this session.

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

## Extraction (`app/extraction_schema.py`, `app/extractor.py`)

- Provider: **Gemini** (`google-genai` SDK), chosen over Anthropic after the
  fact — `.env.example` was originally written for `ANTHROPIC_API_KEY` and
  has since been updated to `GEMINI_API_KEY`. Set it in `.env` to activate
  extraction; get one at https://aistudio.google.com/apikey.
- `ExtractedFacts` (`app/extraction_schema.py`) is the fixed schema — one
  optional field per fact any `statutes.yaml` `condition` string references,
  plus `forwarding_address_provided`. **Keep this in sync with
  statutes.yaml**: a new rule whose condition references a fact not in this
  schema will parse and adjudicate fine, but extraction will never populate
  it, so the rule can only ever fire from manually-entered facts.
- `extract_facts_from_file` (`app/extractor.py`) isolates every
  Gemini-specific call behind one function, using `google-genai`'s
  "Interactions API" (`client.interactions.create`). **Live-verified**: a
  plain-text notice mentioning an expired rental license, no Certificate of
  Rental Suitability, and a $2,400 deposit (2.5 months' rent, year one)
  correctly extracted `deposit_amount`, `deposit_months`, `tenancy_year`,
  `landlord_rental_license_valid`, and `certificate_of_rental_suitability_provided`
  — which then correctly fired all four matching flags via the normal
  upload → extract → adjudicate flow, no test-only shortcuts.
- **`response_format` must be passed alone — do NOT also pass
  `response_mime_type`.** That param is marked `deprecated` in the SDK's own
  source and passing it triggers a legacy validation path that rejects the
  request with `"responseFormat must be set when responseMimeType is set"`
  even though `response_format` *was* set. Caught by a live 400 during
  development; cost real API calls to isolate. If a future SDK upgrade
  reintroduces a `response_mime_type`-shaped API, re-verify against the
  installed package source before using it — see the same lesson in
  `app/agent.py`.
- The request/response shape (content blocks, `response_format`,
  `interaction.output_text`) was checked directly against the **installed
  SDK's own type definitions** (`_gaos/types/interactions/*.py`), not
  documentation — a first pass based on a web-doc summary got three things
  wrong (the `response_mime_type` issue above, content-block field names,
  and manual base64 instead of passing a `Path` straight through). If
  something here ever seems to contradict Gemini's public docs, trust the
  installed package's source over the docs, and trust a live error over
  both.
- `.txt` uploads are sent as an inline text block, not as a "document"
  content block — `DocumentContentMimeType` only recognizes
  `application/pdf` and `text/csv`. `.docx` has no mapping at all and
  raises `ExtractionUnsupported`, caught by the router same as any other
  extraction failure.
- `app/routers/documents.py`'s upload handler calls this after saving the
  file and treats every failure mode the same way: no key configured, an
  unsupported file type (`.docx` has no mapping — Gemini's document
  understanding doesn't take it directly), or any other exception all leave
  `facts={}` rather than failing the upload. The document is always safely
  stored; extraction is strictly best-effort on top of that.
- On successful extraction, the router writes the facts onto the event and
  calls `adjudicate_vault` immediately — no separate "run extraction" step.

## Grounded agent (`app/agent.py`)

- **The model's own `grounded: true` claim is never trusted on its own.**
  `ask_agent` independently checks the model's `citation_value` against this
  vault's actual event ids and the statute table's actual citations
  (`_verify_citation`) before ever returning an answer; an unverifiable
  citation is downgraded to a refusal regardless of what the model said.
  This is what makes grounding structural (PLAN.md: "enforced structurally
  ... not by prompt instruction alone") rather than a request. Test it via
  `tests/test_agent.py::test_ask_with_fabricated_citation_is_refused_despite_model_claiming_grounded`
  — this is the single most important test in this codebase to keep green.
- `_build_context` passes through **every field of every verified rule**,
  not a fixed subset — an earlier version only forwarded `id`/`citation`/
  `detail`/`framing`, which silently broke PLAN.md's own flagship demo
  question ("how long does he have to return my deposit") because
  `deposit_return_clock` keeps its actual content in `clock`/`on_expiry`/
  `requires`, not `detail`. Caught live, against that exact question, before
  being caught by a reviewer or a judge. If a future rule shape adds a new
  field, it's already included — don't reintroduce a subset.
- Context also includes this vault's full timeline + current flags/deadlines,
  filtered to the asking party's framing (`message_tenant` vs
  `message_landlord`, and each rule's `party_framing[party]`) — the same
  underlying fact, one framing at a time, matching the party-neutral design.
- Live-verified refusals: a question with no supporting vault event ("when
  did I first report the leak" with no such event) and a legal-conclusion
  question ("will I win in court") both correctly refuse with a
  PhillyTenant.org/hotline handoff.
- Same fail-safe pattern as extraction: no key, any model-call exception, or
  a failed-verification citation all produce the same safe refusal+handoff
  response — never a 500, never a guess.

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
