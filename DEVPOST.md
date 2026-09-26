# CasaVault

**A statute-aware record of a rental relationship — where every document you upload is checked against the law, every deadline is tracked automatically, and a grounded agent answers your questions using only your own records and the statute table.**

Live at [casavault.vercel.app](https://casavault.vercel.app)

---

## Inspiration

Philadelphia's Right to Counsel program covers roughly ten zip codes. Every renter outside them walks into landlord-tenant court alone — usually with no documentation of the repair requests they made, the notices they received, or what their unit looked like when they moved in. At program launch the city cited 87% of landlords with attorney access against 16% of renters. Small landlords with one or two units are frequently unrepresented too.

Neither side loses because they're wrong. They lose because they can't prove it.

The law itself is not the problem. Pennsylvania's deposit-return clock, the rental licence defense, the habitability waiver — these are real, powerful protections. They're just scattered across state statutes and city ordinances, and applying them to your own lease requires knowing they exist, knowing which section says what, and having the documentation to back it up.

Meanwhile, when someone moves to a new address, the only tools available are a credit score and a background check — blunt proxies that tell you nothing about whether someone was actually a good resident, and that lock out anyone with thin credit. The record should belong to the address, the way a CARFAX report belongs to a VIN — surviving every occupant, readable by both sides.

## What it does

CasaVault is a single record per tenancy. Everything goes in — lease, notices, repair requests, inspection photos, payment receipts — and four things happen automatically.

**Look up any Philadelphia address.** Type an address and see what the City has on record: rental licence status, open code violations, violation history. This comes live from Philadelphia L&I's open data, not from anyone telling us the truth. No sign-in, no vault needed.

**Upload documents and we read them.** Upload your lease as a PDF (or photo, or text file) and Gemini extracts facts into a 40-field schema — deposit amounts, lease dates, rent, fees, escrow bank, insurance requirements, buy-out terms, concessions, and more. DocuSign leases, where filled values are invisible to text extraction, go through Gemini's visual document understanding path. A real 25-PDF Philadelphia lease bundle runs through the pipeline with document triage that prioritizes the files that matter for the rules.

**Every finding cites the exact statute.** A deterministic rules engine checks extracted facts against 9 verified rules drawn from Pennsylvania and Philadelphia law:

- Deposit over the first-year cap (68 P.S. 250.511a(a))
- Deposit over the second-year cap (68 P.S. 250.511a(b))
- Deposit frozen after five years of tenancy (68 P.S. 250.511a(d))
- Lease clause waiving deposit-return rights, void by statute (68 P.S. 250.511a(f))
- Deposit over $100 not held in escrow (68 P.S. 250.511b)
- 30-day deposit return clock (68 P.S. 250.512)
- No active rental licence on file (Phila. Code 9-3902)
- Certificate of Rental Suitability not provided at signing (Phila. Code 9-3903)
- Open L&I violations over 30 days (Safe Healthy Homes Act, Phila. Bill No. 250329)

The last two — rental licence and code violations — can now be answered automatically from City records, without anyone typing anything. Before that, both were stuck at "needs facts" forever, because a lease will never tell you whether your landlord has a valid licence.

**Three-state adjudication.** Every rule reports one of three states: flagged (with the citation and party-framed explanation), no issue found, or unknown (a fact it depends on hasn't been recorded yet, with the next step to take). A compliant lease reports "no issue found" — not silence, which reads as "this product did nothing."

**A grounded agent that refuses rather than guesses.** Ask a question in plain English and the agent answers from your vault and the statute table only — never from model knowledge. Every answer must cite a specific vault event or statute row. If it can't ground a claim, it says so and hands off to the Philly Tenant Hotline (for Right to Counsel zips) or PhillyTenant.org (for everyone else). This is enforced in code: the model's citation is independently verified against the vault's actual event IDs and the statute table's actual citations before an answer is ever returned. A fabricated citation is downgraded to a refusal regardless of what the model claimed.

**Report a problem in writing.** Pick the issue, urgency, and date. We draft a written notice addressed to your management office with a reference number. You read it and send it from your own email — we never send it. The notice lands on your timeline as a dated record. Written notice is load-bearing under PA and Philadelphia law, and an email from your own outbox carries a send time, a named recipient, and a copy — provenance from outside this app.

**Evidence packet.** One printable page with your full timeline, all findings with citations, and statutory deadlines. Print to PDF from the browser.

**Share with the other side.** One read-only link for your landlord or tenant. They can see the timeline, findings, and deadlines but cannot edit anything or learn your vault's write credential. First click timestamps their acknowledgement.

**Right to Counsel zip check.** Enter your zip code and find out whether you qualify for a free lawyer in eviction court. If covered: the Philly Tenant Hotline at (267) 443-2500. If not: PhillyTenant.org.

**Sign in required for writes.** Uploading files, adding timeline entries, and reporting problems require a signed-in account (Clerk). Looking up an address and viewing shared records work without one. You can delete something you just added within 10 minutes; after that, it lives in the system permanently.

## How we built it

**Backend:** FastAPI with SQLite locally and Neon Postgres in production (via Vercel Marketplace). SQLModel for the ORM. File storage abstracted behind a backend that picks local disk or Vercel Blob depending on environment.

**Frontend:** Plain HTML and JavaScript, no framework, no build step. Four pages served as static files. Everything from the API is rendered with createElement/textContent — never innerHTML — because the counterparty's data is third-party text on a page the other party loads.

**Extraction:** Gemini (google-genai SDK) with schema-constrained output. A 40-field extraction schema covering lease terms, fees, deposits, insurance, buy-out terms, utilities, occupancy, environmental disclosures, and acknowledgments. Multi-key API rotation to work around free-tier daily quotas — each key gets its own 20/day limit, so three keys means 60 requests before exhaustion.

**Rules engine:** statutes.yaml is the product. Each rule carries a condition (evaluated by a narrow AST-based evaluator supporting and/or/not and comparisons), a citation, party-framed explanations for both sides, and severity. The engine uses Kleene three-valued logic — True, False, or None — so a missing fact and a satisfied rule are never confused.

**Architecture decisions that matter:**

- *Four-stage pipeline.* Extract, adjudicate, track, answer — each with a distinct responsibility that never blurs. The extractor never judges legality. The rules engine never guesses at facts. The agent never makes claims it can't cite.
- *Structural grounding.* The agent's refusal is enforced by code that verifies citations against real data, not by a prompt that asks the model to be honest. The single most important test in the codebase (`test_ask_with_fabricated_citation_is_refused_despite_model_claiming_grounded`) proves this property.
- *Three-tier privacy.* City records (Tier A) are public — they're already public, published by the City. De-identified incident history (Tier B) is shown only when enough tenancies exist at an address to prevent re-identification. Vault contents (Tier C) never leave the vault without the holder's deliberate act.

**Deployment:** Vercel (Hobby plan) with Neon Postgres, Vercel Blob (private access), and Clerk for optional sign-in. FastAPI runs as a Vercel Function with a 300-second timeout. Static files are promoted to CDN serving automatically.

## Challenges we ran into

**DocuSign PDFs hide their data.** A real Philadelphia lease — 25 PDFs, 102 pages, 8.8 MB from a DocuSign envelope — stores filled values as drawing operations, not text or form fields. pypdf reads the deposit line as "The total security deposit is $ , due on or before..." — blank. The dollar amount is only visible when you render the page. Extraction has to go through Gemini's visual document path, and any future optimization that "just pulls the text locally" would silently produce a lease with no deposit and no bank.

**20 requests per day.** The Gemini free tier allows 20 API calls per day, and both extraction and agent queries count. A single 25-PDF lease bundle would exhaust the entire quota. We built document triage (priority/secondary/skip categories based on filename relevance) and multi-key rotation (comma-separated keys, each with its own quota, cycled on 429).

**Vercel's 4.5 MB request body limit.** A real lease bundle is 8.8 MB. Each file has to arrive in its own request, attached to a shared event via a manifest/index protocol, with facts merged across files. The front-end checks the same limit before uploading so users get told immediately.

**The share link wasn't actually read-only.** The original implementation returned the full vault object — including the vault ID, which is the write credential. Anyone holding a "read-only" share link could read the ID from the JSON response and upload documents into someone else's vault. Fixed with a separate schema and a separate router that never exposes the ID.

**innerHTML and stored XSS.** The previous frontend interpolated filenames, notes, citations, and vault labels straight into innerHTML. A filename is chosen by whoever uploads; a share link is opened by the counterparty. Rebuilt everything through createElement/textContent.

**Dates showing one day early.** `new Date("2026-08-31")` is parsed as UTC midnight per spec; `toLocaleDateString` renders it in the viewer's timezone, so everywhere west of UTC it printed August 30th. For a deposit-return deadline, that's not cosmetic — it shows a tenant the wrong expiration date. Fixed by parsing date-only strings as local dates.

**SQLModel never alters existing tables.** `create_all()` creates tables that don't exist but silently ignores new columns on existing tables. Every model field addition required a manual ALTER TABLE against the live Neon database. We eventually added a migration function that runs on cold start.

## Accomplishments we're proud of

The grounded agent's refusal is tested by a case where the model explicitly claims grounded=True with a fabricated citation — and the code catches it and returns a refusal anyway. That test is the single clearest proof that grounding is structural, not aspirational.

A real 25-PDF Philadelphia lease for a professionally managed building runs through the full pipeline — triage, extraction, adjudication — and the rules engine correctly reports "no issue found" for every rule, because the lease is compliant. Before three-state adjudication, that read as silence.

City records from Philadelphia L&I auto-populate the rental licence and code violation facts that a lease will never state, moving two rules from "needs facts" to actual findings without the user lifting a finger.

The incident reporting flow drafts a notice with a subject line, reference number, and body that the user sends from their own email. Written notice from the tenant's own outbox is stronger evidence than a message from an app they signed up for.

114 tests green, including the fabricated-citation test, the share-link credential leak test, and the delete-window enforcement test.

## What we learned

The real lease broke every assumption we started with. DocuSign field values are invisible to text extraction. A compliant lease produces no flags, which reads as "this product did nothing" until you build the third state. 25 files exceed the daily API quota, so triage is not an optimization but a requirement. The most legally interesting clause in the whole bundle (a habitability waiver buried in the master addendum) maps to a rule that's still in draft status because the pin cite hasn't been confirmed.

The agent's refusal is the product, not a failure mode. "Will I win in court?" getting a clear refusal with a hotline number is the demo, not a limitation. Building a system that knows what it doesn't know — and says so honestly — turned out to be harder and more valuable than building one that always has an answer.

City records being free, public, and unauthenticated changed the product's shape more than any single feature. Third-party facts that owe nothing to either side's honesty are what make the address page credible — the same reason CARFAX works.

## What's next

**Address claiming and tiered access.** A landlord or prospective tenant submits documentation to claim an address. Before verification, they see high-level stats: number of prior tenancies, average length of stay, issue counts by category and severity, average resolution time. After approval, they get the full detail. This turns the address page from a City-data viewer into a due-diligence tool that someone checking out an apartment can actually use before signing.

**Resident and owner history with mutual disclosure.** Search a person by name or user ID. Available to landlords on request, requiring an application and consent from the resident. Once both parties approve, full history is visible to both — a two-sided pull, not a publication. This is the mechanism that goes beyond credit scores and background checks: evidence-backed residency history that gives good tenants a way to prove it, and gives landlords something more useful than a number.

**Portable history.** Your record follows you when you move. A new vault at a new address inherits the history you choose to carry forward — the same way your driving record follows you to a new insurer.

**More jurisdictions.** The engine is jurisdiction-agnostic; only the statute table is Philadelphia/PA. Adding New York or Chicago means writing a new YAML file and confirming the citations, not rebuilding the pipeline.

**Verified resident feedback.** De-identified reviews attached to the address, not the person — visible on the public address page once enough tenancies exist to prevent re-identification.

---

Built at LexHack 2026. This is rights information, not legal advice.
