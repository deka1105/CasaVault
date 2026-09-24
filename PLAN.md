# CasaVault — LexHack 2026

**One-line pitch:** A statute-aware record of a rental relationship — where every
document you upload is adjudicated against Pennsylvania and Philadelphia law, every
deadline is tracked automatically, and an agent answers your questions using only
your own record and the law.

**Track:** Access to Justice & Civic Tech (secondary: Legal Automation)

---

## The problem

Philadelphia's Right to Counsel program covers roughly ten zip codes. Every renter
outside them walks into landlord-tenant court alone, usually with no documentation
of the repair requests they made, the notices they received, or the condition of the
unit when they moved in. At program launch the city cited 87% of landlords with
attorney access against 16% of renters. Small landlords with one or two units are
frequently unrepresented too.

Neither side loses because they're wrong. They lose because they can't prove it.

## Who holds a vault

CasaVault is party-neutral. A tenant or a small landlord can hold one, and both see
the same statute table from their own side — the 30-day deposit return window is a
tenant's right and a landlord's obligation, one rule, two framings.

Homeownership law (mortgages, HOA covenants, contractor liens, tax appeals) is a
separate statute table. The engine is domain-agnostic and would support it; it is
explicitly out of scope for this build.

## The solution

One vault per tenancy. Every artifact goes in — lease, repair requests, notices,
inspection photos, payment receipts. Four things happen:

1. **Extract** — an LLM parses each document into a fixed schema. It never judges legality.
2. **Adjudicate** — a deterministic rules engine joins extracted facts against a
   statute table. Every flag carries the section that produced it.
3. **Track** — events that start statutory clocks become dated deadlines you can see coming.
4. **Answer** — a grounded agent answers questions over the vault and the statute table.

Output: a printable evidence packet, chronological, with citations.

## The agent — grounded, not open-ended

The agent is a query interface over your own record. It is not an oracle and it does
not generate legal opinions.

**Hard constraint:** every claim in an answer must cite either a specific vault entry
or a specific statute row. If it cannot ground a claim in one of those, it says so and
hands off to the Philly Tenant Hotline. This is enforced structurally — the agent's
retrieval surface is the vault and the rules table, nothing else — not by prompt
instruction alone.

    "When did I first report the leak?"
      -> event #7, repair_requested, 2026-03-14, with the photo attached

    "How long does he have to return my deposit?"
      -> 30 days from move-out (2026-08-01), so by 2026-08-31
         [68 P.S. § 250.512]

    "Will I win in court?"
      -> I can't answer that. Here's who can: Philly Tenant Hotline (267) 443-2500

That last refusal goes in the demo video. It is the point, not a limitation.

## Architecture

    document/event ──> extractor (LLM, schema-bound) ──> facts
                                                          │
                            statute table (YAML) ─────────┤
                                                          ▼
                                            flags + deadlines + citations
                                                          │
                                       grounded agent ────┘
                                    (retrieval limited to vault + table)

The statute table is the product. The interfaces are cheap. Lease audit, notice
checker, deadline tracker and agent are four entry points into one engine — which is
why a fifth is configuration, not code.

## Scope — LOCKED

### In
- Single vault, no signup (demo vault + share token)
- Party toggle: tenant view / landlord view over the same rules
- Document upload -> extraction -> flags with citations
- Timeline events: repair request, notice received, inspection, payment, photo
- Statutory deadline tracking on repair + deposit clocks
- Grounded agent with mandatory citation and explicit refusal
- Counterparty read-only share link, one-click timestamped acknowledgement
- Evidence packet export (print-to-PDF of a clean HTML view)
- Right to Counsel zip check -> hotline or PhillyTenant.org handoff

### Out — do not build
- Homeownership law: mortgage, HOA, liens, tax appeals
- Real auth, accounts, password reset
- Any jurisdiction other than Philadelphia / PA
- Ungrounded chat — the agent may not answer from model knowledge
- Notifications, email, SMS, payments, mobile app
- File storage beyond local disk

## Stack

- FastAPI + SQLite
- Plain HTML/JS front end, no framework
- LLM extraction via API, schema-constrained output
- Statute rules in YAML, loaded at startup
- Agent retrieval over vault rows + rules rows only
- Deploy to a public URL by Saturday midday; point the free .xyz domain at it

## Build order (72 hours, deadline Sun Sep 27 5:00 PM EDT)

| When | What | Gate |
|---|---|---|
| Thu night | Schema + statute table verified | Citations confirmed against primary sources |
| Fri AM | Extractor working on one real lease | Structured output, no hallucinated clauses |
| Fri PM | Rules engine + flags with citations | End-to-end on the lease |
| Sat AM | Timeline events + deadline clocks | Repair + deposit clocks correct |
| Sat midday | Grounded agent + refusal path | Cites or refuses, never guesses |
| Sat PM | Share link, acknowledgement, evidence export | **Decision gate: core solid?** |
| Sat night | Real lease from a real Philadelphia renter, end to end | One genuine flag + generated letter |
| Sun AM | Demo video, Devpost write-up | Nothing in the video that isn't working |
| Sun 3 PM | Submit | Hard stop, two hours before deadline |

## Cut list — if behind on Saturday afternoon, drop in this order

1. Party toggle (ship tenant view only)
2. Counterparty acknowledgement (share link stays read-only)
3. Inspection photo handling (text events only)
4. Payment events
5. Deadline clocks beyond the deposit-return clock

Never cut: extraction, citations on flags, the agent's refusal path, the evidence
export, the real-lease test.

## Judging rubric alignment

| Criterion | Weight | How we hit it |
|---|---|---|
| Real-world impact & feasibility | 25% | Named population (renters outside RTC zips + small landlords), real statute, deployable because the model never gives legal advice |
| Technical execution | 25% | Inspectable rules engine, schema-bound extraction, structurally grounded agent, test leases |
| UX & design | 20% | Plain-English output, every flag and answer shows its source, one-page evidence packet |
| Innovation & originality | 15% | "The model extracts, the law adjudicates" — vault as statute-aware timeline; agent that refuses |
| Presentation & documentation | 15% | Real lease in the first 20 seconds; the refusal on camera; limits declared honestly |

## Non-negotiables

- This is rights information, not legal advice. Say it in the UI and the write-up.
- Every flag and every agent claim cites a source. No uncited legal conclusion reaches a user.
- The agent refuses rather than guesses, and the refusal routes to a human.
- Handoff is real: RTC-covered zips -> Philly Tenant Hotline (267) 443-2500;
  everyone else -> PhillyTenant.org.
- Nothing in the demo video that does not work end to end.
