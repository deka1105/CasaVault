# CasaVault — Demo Video Script

**Target length:** 3–4 minutes
**URL:** casavault.vercel.app
**Before recording:** Sign in via Clerk so the auth header is already present.
Have 5 test lease PDFs ready in a folder on your desktop.

---

## SCENE 1 — The Problem (voiceover, 20s)

> "In Philadelphia, 87% of landlords in housing court have a lawyer. 16% of
> tenants do. But tenants don't usually lose because they're wrong — they lose
> because they can't prove it. And the law that would protect them is scattered
> across state statutes and city ordinances that nobody reads."

Screen: casavault.vercel.app landing page — "Keep proof of your rental — and
know what the law says."

---

## SCENE 2 — Address Lookup (30s)

> "CasaVault starts with the address, not the paperwork."

**Action:** Type `3127 Kensington Ave` in the address search box. Click "Look it up."

Screen: Property page loads with City records from L&I.

> "This comes straight from Philadelphia's open data — rental licence status
> and code violations. This address has no active rental licence. That's the
> most common successful defence in Philadelphia landlord-tenant court, and
> CasaVault found it automatically."

**Pause** on the licence status and violation summary for 3 seconds.

---

## SCENE 3 — Create a Vault and Upload a Bad Lease (60s)

> "Now let's see what happens when someone actually signs a lease here."

**Action:** Click "Start your record" (or navigate back to landing, click
"Start — it's free"). A new vault is created.

> "This is your vault — a private record of one tenancy."

**Action:** Click the document upload area. Select
`04_major_deposit_overcharge_and_waiver_north_philly.pdf`.

> "This lease is for a unit on North Broad Street. $950 a month rent, but the
> landlord is charging a $2,850 security deposit — three months' rent."

Screen: Upload completes, extraction runs. Wait for findings to populate.

> "CasaVault reads the lease with Gemini, extracts 40 fields, and checks every
> one against 9 verified rules drawn from Pennsylvania and Philadelphia law."

**Action:** Scroll to the Findings panel.

> "Three flags, and every one cites the exact statute."

**Point out each finding:**

> "First — the deposit is over the first-year cap. Pennsylvania law says two
> months maximum. 68 P.S. section 250.511a(a)."
>
> "Second — the lease has a clause that tries to waive your deposit rights.
> That waiver is void by statute. 68 P.S. section 250.511a(f)."
>
> "Third — $2,850 deposit with no escrow bank disclosed. Over $100 must be in
> escrow. 68 P.S. section 250.511b."

---

## SCENE 4 — The Compliant Lease (30s)

> "Now let's upload a compliant lease and see the difference."

**Action:** Create a new vault (or open a pre-seeded vault). Upload
`01_compliant_chestnut_hill.pdf`.

> "This is Chestnut Hill Gardens — $1,450 rent, one month's deposit, escrow at
> Citizens Bank, certificate provided, licence is active."

Screen: Findings panel shows "No issue found" for every rule.

> "Every rule says 'no issue found.' That's not silence — it's the system
> confirming your lease checks out. Before we built three-state adjudication,
> a compliant lease showed nothing at all, which looked like the product did
> nothing."

---

## SCENE 5 — The Worst-Case Lease (45s)

> "Now the worst case. A lease from Kensington."

**Action:** Create a new vault. Upload
`05_major_no_license_no_cert_no_escrow_kensington.pdf`.

Screen: Multiple findings light up.

> "No active rental licence — that alone bars the landlord from collecting rent
> or filing for eviction. Phila. Code section 9-3902."
>
> "No Certificate of Rental Suitability, no Partners in Good Housing handbook.
> Section 9-3903."
>
> "And the deposit — $2,200, no escrow bank disclosed."

**Action:** Toggle to Landlord view.

> "Switch to the landlord's side and every finding reframes. Same facts, same
> rules — but phrased for the other party."

---

## SCENE 6 — Ask the Vault (40s)

> "The grounded agent answers questions from your records and the statute table
> only."

**Action:** (In the North Broad vault with the 3 flags) Type in the Ask box:
`How long does my landlord have to return my deposit?`

> "It answers with the citation: 30 days from move-out, 68 P.S. section
> 250.512."

**Action:** Now type: `Will I win in court?`

Screen: Refusal response appears with hotline handoff.

> "This is the most important thing the agent does — it refuses. 'I can't
> ground that in your records. Here's who can help.' And it gives you the
> Philly Tenant Hotline number."
>
> "That's not a failure. That's the product working. A system that knows what
> it doesn't know is more trustworthy than one that always has an answer."

---

## SCENE 7 — Report a Problem (25s)

> "When something breaks, you need a written record."

**Action:** Scroll to "Report a problem." Fill in:
- What's the problem: **No heat**
- How urgent: **Emergency**
- Date: **today's date**
- Description: **No heat since Tuesday, temperature below 50 degrees**
- Click "Draft notice"

Screen: Email draft appears with subject line, reference number, body.

> "CasaVault drafts the notice. You read it and send it from your own email.
> We never send it for you — your outbox is the proof, and it carries your name,
> a timestamp, and a named recipient."

---

## SCENE 8 — Share and Evidence (20s)

> "When you're ready, share it with the other side."

**Action:** Click "Copy link" next to the share link. Open the share link in a
new tab.

Screen: Counterparty view — same findings, same timeline, no edit controls.

> "Read-only. They can see the findings and the timeline, but they can't change
> anything. And they never learn your vault's write address."

**Action:** Click "Evidence packet."

Screen: Print-friendly HTML page with full timeline and citations.

> "One page. Print to PDF. Every finding with its statute citation and every
> document on the timeline, ready for court."

---

## SCENE 9 — What We Check (10s)

**Action:** Click "What we check" in the nav.

Screen: All 9 verified rules displayed with citations.

> "Nine verified rules. Every one checked against the statute text. Every one
> with the exact citation."

---

## SCENE 10 — Close (15s)

> "CasaVault is rights information, not legal advice. Every answer cites a
> source. Every refusal routes to a human. And every document stays yours."
>
> "Built at LexHack 2026."

Screen: Landing page.

---

## Pre-recording checklist

- [ ] Signed in at casavault.vercel.app (Clerk session active, username visible)
- [ ] 5 test PDFs on desktop in an easy-to-find folder
- [ ] Gemini API keys have available quota (check: create a vault, upload a
      small .txt, confirm extraction populates facts)
- [ ] Screen recording tool set to 1280x800 or 1920x1080
- [ ] Browser zoom at 100%, dark mode OFF (light theme reads better on video)
- [ ] No browser extensions visible in toolbar (distracting)
- [ ] Close all other tabs

## PDF → Expected results quick reference

| PDF | Vault label | Flags triggered |
|-----|-------------|-----------------|
| `01_compliant_chestnut_hill.pdf` | Chestnut Hill | None — all "no issue found" |
| `02_minor_no_certificate_west_philly.pdf` | West Philly | No Certificate (9-3903) |
| `03_minor_no_escrow_fishtown.pdf` | Fishtown | No escrow (250.511b) |
| `04_major_deposit_overcharge_and_waiver.pdf` | North Broad | Deposit over cap (250.511a(a)) + Waiver void (250.511a(f)) + No escrow (250.511b) |
| `05_major_no_license_no_cert_no_escrow.pdf` | Kensington | No licence (9-3902) + No certificate (9-3903) + No escrow (250.511b) |

## Timing summary

| Scene | Content | Duration |
|-------|---------|----------|
| 1 | Problem statement | 20s |
| 2 | Address lookup | 30s |
| 3 | Bad lease upload + 3 flags | 60s |
| 4 | Compliant lease | 30s |
| 5 | Worst-case lease + landlord toggle | 45s |
| 6 | Agent Q&A + refusal | 40s |
| 7 | Report a problem | 25s |
| 8 | Share link + evidence packet | 20s |
| 9 | What we check page | 10s |
| 10 | Closing | 15s |
| **Total** | | **~4 min 55s** |

Trim scenes 4 and 5 if you need to hit 3 minutes. The must-haves for the demo
are: address lookup (scene 2), bad lease with flags (scene 3), agent refusal
(scene 6), and the evidence packet (scene 8).
