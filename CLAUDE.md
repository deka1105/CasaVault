# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

The full pipeline is built and live-verified end to end: upload a document →
Gemini extracts facts → rules engine flags them with citations → grounded
agent answers questions over the vault + statute table, citing or refusing.
Also done: share link, counterparty acknowledgement, evidence packet, RTC
zip-check, document upload/download, front end. **Deployed and verified
live at https://casavault.vercel.app** (Postgres + Blob persistence proven
against the real deployment; see the Vercel deployment section). This is a
hackathon build (LexHack 2026) with a hard submission deadline of **Sun Sep
27, 2026, 5:00 PM EDT** — read `PLAN.md`'s build-order table before starting
any work session to know what day/gate we're against.

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
pytest -q                       # full test suite (67 tests)
pytest -q -k test_name          # single test
```

`conftest.py` at the repo root does two things, both of which were missing
and both of which matter: it puts the project root on `sys.path` (without it
`pytest -q` failed outright with `ModuleNotFoundError: No module named 'app'`
— only `python -m pytest` worked, so the documented command above was
broken), and it points the suite at a throwaway SQLite file and uploads
directory. Before that, running the tests wrote real vaults, events and
uploaded files straight into the dev `casavault.db` and `uploads/`.

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

- `POST /api/vaults`, `GET /api/vaults/{id}`
- `POST /api/vaults/{id}/events` — records a timeline event, then re-runs adjudication (see below)
- `GET /api/vaults/{id}/events` — raw timeline events
- `GET /api/vaults/{id}/flags` — current adjudication result, recomputed from scratch on every event write
- `GET /api/vaults/{id}/deadlines?party=tenant|landlord` — statutory clocks started so far (currently just the deposit-return clock), framed for the asking party
- `GET /api/statutes` — verified rules only (draft rules never serialize out; see `statutes_loader.StatuteTable.verified_rules`)
- `GET /api/vaults/{id}/rtc-check` — Right to Counsel zip lookup (`app/rtc.py`), shared with the agent's refusal handoff
- `/api/vaults/by-share-token/{token}/...` — the **read-only counterparty
  surface**, all of it in `app/routers/share.py`: the vault itself, `/events`,
  `/flags`, `/deadlines`, `/evidence`, `/rtc-check`, `/documents/{event_id}`,
  plus the one write PLAN.md calls for, `POST /acknowledge` (first click wins,
  sets `Vault.acknowledged_at` once, idempotent after that)
- `GET /api/vaults/{id}/evidence?party=tenant|landlord` — server-rendered, print-to-PDF-friendly HTML evidence packet (`app/evidence.py`); no JS, no external assets, chronological with citations
- `POST /api/vaults/{id}/ask` — the grounded agent (`app/agent.py`). Live-verified: refuses on ungroundable questions, refuses on "will I win in court"-style legal conclusions, and answers with a citation when the vault/statute data actually supports it. See the Agent section below for how refusal is enforced in code, not just prompted.
- `POST /api/vaults/{id}/documents` (multipart), `GET /api/vaults/{id}/documents/{event_id}` — real file upload/download, backing `document_upload` events. See below.
- `GET /api/config` — public, non-secret frontend config (currently just `clerk_publishable_key`, `null` if sign-in isn't configured)
- `GET /api/vaults/mine` — requires sign-in (401 otherwise); lists vaults created while signed in as the caller. Registered *before* `/{vault_id}` in `app/routers/vault.py` specifically so `/mine` is never swallowed by the `{vault_id}` path param.

## Optional sign-in (`app/auth.py`, Clerk)

- **Explicitly a scope change from `PLAN.md`** ("Out — do not build: Real auth, accounts"), added on direct user request after initially declining it in favor of UI polish. Kept as additive as possible: `Vault.owner_user_id` is nullable and **never gates access** — the vault's `id`/`share_token` remain the actual access control exactly as designed. Signing in only lets a creator find their own vaults later via `GET /api/vaults/mine` instead of needing to keep the link.
- `get_optional_user_id` (a FastAPI dependency) verifies a Clerk session JWT via the official `clerk-backend-api` Python SDK's `authenticate_request_async` — returns `None` (never raises) whenever `CLERK_SECRET_KEY` is unset, no `Authorization` header is present, or verification fails for any reason. `require_user_id` wraps it to 401 when sign-in is mandatory (only on `/mine`).
- **Verified against the installed SDK's actual types**, not docs — `Requestish` turned out to need only a `.headers` mapping (a plain FastAPI `Request` satisfies it directly), and `RequestState.payload["sub"]` is the Clerk user id. The `vercel:auth` skill's guidance is 100% Next.js/React and doesn't apply to this Python + vanilla-JS stack at all; don't reach for it here.
- **Frontend has no bundler**, so Clerk is loaded via a real jsDelivr CDN entry point the package itself declares (`clerk-js`'s `package.json` → `"jsdelivr": "dist/clerk.browser.js"`, confirmed to be a self-contained UMD bundle that resolves its own chunk files relative to `document.currentScript.src` — verified by installing the package and reading the bundle directly, not assumed). Loaded lazily (`loadClerkScript()` in `app.js`) only when `GET /api/config` reports a publishable key, so zero extra requests when sign-in isn't configured.
- Frontend API: `new Clerk(publishableKey)` → `await clerk.load()` → `clerk.openSignIn()` / `clerk.mountUserButton(node)` / `clerk.addListener(cb)` / `await clerk.session.getToken()`. All verified against `@clerk/clerk-js`'s actual shipped `.d.ts` files.
- **Live-verified as far as possible without a human completing an actual
  sign-in challenge**: a real Clerk application is now connected
  (`CLERK_SECRET_KEY`/`CLERK_PUBLISHABLE_KEY` set on the Vercel project —
  note `CLERK_SECRET_KEY` was already auto-injected for the `development`
  target when Clerk was connected via the dashboard, so it only needed
  setting for `production`/`preview`). `GET /api/config` on the live
  deployment returns the real publishable key. Calling
  `authenticate_request_async` directly against a deliberately garbage
  token returns `AuthStatus.SIGNED_OUT` / `reason: TOKEN_INVALID` — a
  specific rejection, not a crash — proving the secret key is valid and the
  JWKS network round-trip to Clerk's real backend actually works, both
  locally and from the deployed Vercel function (`GET /api/vaults/mine`
  correctly 401s for both no-auth and garbage-token cases on the live
  site). **What's not verified**: an actual successful sign-in — that needs
  a human to click through Clerk's real hosted UI (email/OTP, etc.), which
  isn't something this session can complete unattended. Open
  `casavault.vercel.app`, click Sign in, and confirm "Your vaults" appears
  after — that's the one remaining check.
- **Real bug, caught live via actual browser console output the user
  reported**: clicking "Sign in" did nothing, no visible error. Root cause
  had nothing to do with third-party cookies (the initial hypothesis,
  disproven) — `clerk.browser.js`, when loaded via a plain `<script src>`
  tag, **auto-initializes itself by reading `data-clerk-publishable-key`
  off its own script tag**, synchronously, as it executes. `loadClerkScript()`
  wasn't setting that attribute (it was written assuming the npm
  `new Clerk(key)` constructor pattern instead). The failed auto-init threw
  `Missing publishableKey` internally and left `window.Clerk` in a broken,
  non-constructor state, so the later `new window.Clerk(...)` call threw
  `TypeError: window.Clerk is not a constructor`. Fixed by setting
  `data-clerk-publishable-key` on the script element before appending it,
  and using the resulting `window.Clerk` directly as the pre-initialized
  singleton (`clerk = window.Clerk; await clerk.load();`) instead of trying
  to construct a new instance. **If Clerk ever seems to silently do
  nothing again, check the browser console first** — this class of failure
  (script auto-init succeeding or failing based on a DOM attribute) produces
  no error visible from the Python side at all.
- **Adding `Vault.owner_user_id` broke production vault creation immediately after this deployed** — real, caught live via `get_runtime_errors`, fixed same-session. Root cause, and this generalizes to **any future model field**: `SQLModel.metadata.create_all()` (`app/database.py:init_db`) only creates tables that don't exist yet; it never alters an existing table's columns. Locally this is invisible — the SQLite file gets deleted constantly during dev/testing, so it's always recreated fresh. Against the real, persistent Neon database it silently left the live `vault` table without the new column until a manual `ALTER TABLE vault ADD COLUMN owner_user_id VARCHAR` was run directly. **Any future SQLModel field addition needs the same manual `ALTER TABLE` against the live database before (or immediately after) deploying** — there is no migration tool wired up (Alembic or similar) to do this automatically. Given the deadline, this is an accepted manual step for now, not something to "fix properly" mid-hackathon.

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
  - `GEMINI_API_KEY` is now on the Vercel project too. **Real bug #3, found
    and fixed live**: `vercel.json` had `maxDuration: 120` — more
    conservative than Vercel's own 300s default — and a real extraction
    call on Vercel exceeded it (`Vercel Runtime Timeout Error: Task timed
    out after 120 seconds`, confirmed via `get_runtime_errors`). Bumped to
    `300` (Hobby plan's actual ceiling) and redeployed; a second live
    extraction call then completed **without** timing out — direct proof
    the fix worked, not just a config change taken on faith.
  - That second call still couldn't extract (`facts: {}`) — but the
    *reason* is the same known 20-req/day free-tier limit, confirmed via a
    real 429 in the logs, not a new bug. This is actually a positive
    signal: the fail-safe design worked exactly as intended in production
    — extraction failed cleanly, facts stayed empty, the upload still
    succeeded with a 200, no crash. Extraction/agent logic itself was
    already proven correct against real (successful) Gemini calls earlier
    this session, locally. **A live extraction success against this actual
    deployment is still pending** — needs the key's tier upgraded (or a
    fresh daily quota window) before it can be shown, not more code
    changes.

## The read-only share link (`app/routers/share.py`)

**This was a real access-control bug, not a refactor.** `GET
/api/vaults/by-share-token/{token}` used to return the full `VaultRead`,
including the vault's `id`. The vault id *is* the write credential — every
write route (`POST /events`, `POST /documents`) is addressed by it and
checks nothing else — so anyone holding a "read-only" share link could read
the id out of that JSON response and post events or upload documents into
someone else's vault. The browser hiding the controls (`state.isOwner`) was
the only thing stopping them, and a share link is by definition opened by
the *other* party.

The fix: a separate schema (`VaultShareRead`, which omits `id` and
`share_token`) and a separate router holding every token-addressed route.
Read-only is now a property of which endpoints that surface exposes, not of
which buttons the page renders. Guarded by
`tests/test_share_and_evidence.py::test_share_token_lookup_returns_vault_without_leaking_owner_credential`.

Two consequences worth remembering:
- The shared evidence packet must build document links against
  `/api/vaults/by-share-token/{token}/documents` (`document_base` in
  `app/evidence.py`), or the owner credential ends up embedded in the HTML
  handed to the counterparty.
- The agent (`/ask`) is deliberately **not** on the share surface. It stays
  owner-only, both for scope and to avoid spending the model quota on
  whoever holds a link.

## Front end (`static/`)

Plain HTML/JS, single page, no build step. `app.js` drives everything off
`?vault=<id>` (owner) or `?share=<token>` (counterparty) — the same page
renders both, but they read from *different API surfaces*, and the share mode
never learns the vault id at all (`state.vaultId` stays null; `vaultPath()`
routes to the token surface).

Rules that are load-bearing, not style preferences:

- **Never use `innerHTML` for server data.** Everything rendered from the API
  is built with `createElement`/`textContent` via the `el()` helper. The
  previous version interpolated `notes`, `original_filename`, `citation`,
  `description` and the vault label straight into `innerHTML` — all
  attacker-controlled (a filename is chosen by whoever uploads; a share link
  is opened by the counterparty), so this was a live stored-XSS path into the
  other party's session.
- **Date-only strings must be parsed as local dates.** `new Date("2026-08-31")`
  is parsed as UTC midnight per spec and `toLocaleDateString` then renders it
  in the viewer's zone, so everywhere west of UTC it printed the *previous*
  day. In this product that is not cosmetic: the 30-day deposit clock was
  being shown to tenants as expiring a day earlier than 68 P.S. § 250.512
  actually allows. `formatDate()` handles `YYYY-MM-DD` separately from real
  timestamps; keep that split.
- **`minmax()` floors are wrapped in `min(..., 100%)`** in `style.css`. A bare
  `minmax(300px, 1fr)` never shrinks below 300px and forced the whole page
  wider than a 320px phone screen. Verified by measuring `scrollWidth` vs
  `clientWidth` in same-origin iframes at 320/360/390/414/600/900px — by eye
  it looked fine, because headless Chrome clamps its viewport to 485px.
- The agent panel ("Ask this vault") is owner-only and ships the PLAN.md demo
  questions as one-click chips, including "Will I win in court?" — the
  refusal that is supposed to go in the demo video.

## Gemini client policy (`app/gemini_client.py`)

Both the extractor and the agent build their client here so timeout and retry
policy are identical and set in one place.

**google-genai retries on its own, and its defaults are hostile here**:
verified against the installed package's `types.HttpRetryOptions` field docs
(not the public docs) — 5 attempts, exponential backoff up to 60s per delay,
on a retryable set that includes 408, 429 and every 5xx. Measured effect: an
exhausted daily quota took **2 minutes 19 seconds** to surface its 429. That
is bad twice over — the free tier's cap is a *daily* one, so every retry is
guaranteed waste, and `vercel.json` caps functions at 300s, so a single ask
burning 140s sits close to the ceiling. Disabling SDK retries took the same
call to **20 seconds**.

So: `attempts=1` at the SDK layer, a 120s hard timeout, and retry policy owned
by the application, which can tell a daily quota apart from a transient 5xx.

## Failure taxonomy — say which safe outcome happened

Both the agent and the extractor already failed *safely* (never a guess,
never a 500). What they did not do is say *which* failure it was, and that
distinction is the difference between a user trusting the product and filing
a bug against it:

- `app/agent.py` raises `AgentUnavailable` (no key), `AgentRateLimited`
  (429 — **not retried**, a daily cap cannot clear on retry) or
  `AgentUpstreamError` (5xx/timeout — retried 3× with backoff).
  `AskResponse.unavailable` tells the front end whether this was a fault or
  the designed refusal, which get visibly different treatment.
  A refusal is the product working (PLAN.md: "It is the point"); showing
  "I can't ground that in your vault" when the truth is "Gemini returned 503"
  teaches the user to distrust the thing that was working correctly.
  This was live: a 503 during testing surfaced as "the grounded agent isn't
  configured yet", which was simply false.
- `app/extractor.py` classifies the same way (`ExtractionRateLimited`,
  `ExtractionUpstreamError`), and `app/routers/documents.py` maps every
  outcome through one `_EXTRACTION_OUTCOMES` table onto
  `DocumentUploadRead.extraction` — a **response-only** field, so no new
  model column and therefore no manual `ALTER TABLE` against the live
  database. The upload always succeeds and the document is always stored;
  the UI now says whether extraction found nothing, hit the daily limit, or
  isn't configured.

## Upload size cap

`MAX_UPLOAD_BYTES` is **4MB**, not 15MB, because Vercel Functions cap request
bodies at 4.5MB and enforce it at the platform edge — a larger upload never
reaches this app, so it could never produce our own clean 413. The old 15MB
limit was a promise the deployment could not keep: anything between 4.5MB and
15MB failed with an opaque platform error. The front end checks the same
limit before uploading so the user gets told immediately. Overridable via the
`MAX_UPLOAD_BYTES` env var for a self-hosted run with no such edge limit.

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
  framings; do not fork the rule itself per party. **Both are now mandatory
  on every verified rule**, enforced by
  `tests/test_rules_engine.py::test_every_verified_rule_carries_both_party_framings`.
  Three verified rules (`deposit_freeze_five_years`, `deposit_escrow_required`,
  `open_violations_over_30_days`) previously shipped with none, so every code
  path that renders a flag fell through to the raw rule id — a user was shown
  the literal string `deposit_escrow_required` where a sentence belonged.
  New framings are a plain-English restatement of that rule's own verified
  `detail`; they make no claim the rule did not already make.
- Deadline-type rules keep a `{deadline}` placeholder in their framing that is
  only filled once an event starts the clock. Anything rendering the raw table
  (the statute browser on the landing page) must not print it verbatim — see
  `statuteSummary()` in `static/app.js`, which shows `clock`/`requires` for
  those rules instead.
- Deadlines are framed per party at **render time**
  (`rules_engine.describe_deadline`), not at creation time. `Deadline.description`
  is baked from the tenant framing when the clock starts, so a landlord reading
  their own vault used to be told "Your landlord has until ..." about
  themselves. Doing it at render time avoids persisting a second copy — and
  therefore avoids another manual `ALTER TABLE` against the live database.
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

**Exception, explicitly overridden by direct user request**: optional Clerk
sign-in exists (see the sign-in section above) despite "real auth/accounts"
being on this out-of-scope list. It was flagged as a scope change before
building it. It does not become a general license to add more from this
list without the same kind of explicit ask — still flag before building
anything else here.

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
