# CasaVault

**A statute-aware record of a rental relationship** — where every document you upload is checked against Pennsylvania and Philadelphia law, every deadline is tracked automatically, and a grounded agent answers your questions using only your own record and the law.

Built at **LexHack 2026** | Track: Access to Justice & Civic Tech

**Live:** [casavault.vercel.app](https://casavault.vercel.app)

---

## Demo

### Full Workflow

<video src="video/CasaVault_workflow.mp4" controls width="100%"></video>

### Sign-in Flow

<video src="video/CasaVault_login.mp4" controls width="100%"></video>

---

## The Problem

In Philadelphia, **87% of landlords** in housing court have a lawyer. Only **16% of tenants** do. Neither side loses because they're wrong — they lose because they can't prove it.

Philadelphia's Right to Counsel program covers roughly ten zip codes. Every renter outside them walks into court alone, usually with no documentation of the repair requests they made, the notices they received, or the condition of their unit.

## How It Works

One vault per tenancy. Every document goes in — lease, repair requests, notices, inspection photos. Four things happen:

1. **Extract** — Gemini reads each document into a fixed schema. It never judges legality.
2. **Check** — A deterministic rules engine joins extracted facts against 9 verified statutes. Every flag carries the exact section that produced it.
3. **Track** — Events that start statutory clocks (move-out, deposit, repairs) become dated deadlines.
4. **Answer** — A grounded agent answers questions over the vault and statute table only — never from model knowledge.

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

## Key Features

| Feature | What it does |
|---------|-------------|
| **Lease check** | Upload a lease, get findings with citations — file deleted immediately, nothing stored |
| **Address lookup** | Live Philadelphia L&I data: rental licence status + open code violations |
| **Cited flags** | Every issue cites the exact statute section — `68 P.S. 250.511a(a)`, not "this might be a problem" |
| **Three-state adjudication** | Flagged, no issue found, or needs more information — never asserts compliance it can't prove |
| **Grounded agent** | Answers with citations or refuses and routes to a human (Philly Tenant Hotline / PhillyTenant.org) |
| **Incident reporting** | Guided questions, drafted email notice, sent from your own outbox — your mail is the proof |
| **Share link** | Read-only counterparty view — the other side sees findings but can't change anything |
| **Evidence packet** | Print-to-PDF, chronological, every finding with its citation — ready for court |
| **Party toggle** | Same facts, same rules, reframed: tenant view and landlord view |
| **Deadline tracking** | Statutory clocks (deposit return, repair timelines) computed from your events |

## The Agent

The agent is a query interface over your record. It is not an oracle and does not generate legal opinions.

```
"How long does my landlord have to return my deposit?"
  → 30 days from move-out, so by 2026-08-31
    [68 P.S. § 250.512]

"Will I win in court?"
  → I can't answer that. Here's who can:
    Philly Tenant Hotline (267) 443-2500
```

That refusal is the product working, not a limitation. Grounding is enforced structurally — the agent's retrieval surface is the vault and the statute table, nothing else — not by prompt instruction alone. A fabricated citation is caught and downgraded to a refusal before it reaches the user.

## Stack

- **Backend:** FastAPI + SQLite (local) / Neon Postgres (production)
- **Frontend:** Plain HTML/JS, no framework — served as static files
- **Extraction:** Gemini (`google-genai` SDK), schema-constrained output
- **Rules:** 9 verified statutes in YAML, loaded at startup
- **City data:** Philadelphia L&I via Carto API (rental licences + code violations)
- **Storage:** Local disk (dev) / Vercel Blob (production)
- **Auth:** Optional Clerk sign-in (additive, never gates vault access)
- **Deploy:** Vercel (Fluid Compute, Neon Postgres, Blob)

## Running Locally

```bash
git clone https://github.com/deka1105/CasaVault.git
cd CasaVault
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Optional: set GEMINI_API_KEY in .env for extraction + agent
# Get one at https://aistudio.google.com/apikey

uvicorn app.main:app --reload   # http://127.0.0.1:8000
```

## Tests

```bash
pytest -q                  # full suite (114 tests)
pytest -q -k test_name     # single test
```

## What We Check

9 verified rules from Pennsylvania and Philadelphia law:

- **Deposit cap** — 68 P.S. 250.511a(a): first-year max is 2 months' rent
- **Deposit freeze** — 68 P.S. 250.511a(a): drops to 1 month after year 5
- **Deposit waiver void** — 68 P.S. 250.511a(f): any clause waiving deposit rights is void
- **Escrow required** — 68 P.S. 250.511b: deposits over $100 must be in a disclosed escrow account
- **Deposit return clock** — 68 P.S. 250.512: 30 days from move-out with forwarding address
- **No rental licence** — Phila. Code 9-3902: operating without a valid rental licence
- **No Certificate of Rental Suitability** — Phila. Code 9-3903: must be provided at lease signing
- **No Partners in Good Housing** — Phila. Code 9-3903: handbook must be provided at lease signing
- **Open violations 30+ days** — Phila. Code 9-3901: code violations open over 30 days

## Important

This is rights information, not legal advice. Using CasaVault does not make us your lawyer. For advice about your own situation, call the **Philly Tenant Hotline** at **(267) 443-2500** or visit [PhillyTenant.org](https://phillytenant.org).

---

**LexHack 2026** | Built by [Shubham A. D.](https://github.com/deka1105)
