# CasaVault — Demo Video Script

**Target length:** Under 3 minutes
**URL:** casavault.vercel.app
**Before recording:** Sign in via Clerk. Have the North Broad PDF
(`04_major_deposit_overcharge_and_waiver_north_philly.pdf`) ready on your
desktop. Pre-seed one vault with the Kensington lease already uploaded so you
don't spend extraction wait time on camera twice.

---

## SCENE 1 — The Problem + Landing (15s)

Screen: casavault.vercel.app landing page.

> "In Philadelphia, 87% of landlords in housing court have a lawyer. Only 16%
> of tenants do. They don't lose because they're wrong — they lose because
> they can't prove it."

---

## SCENE 2 — Address Lookup (20s)

> "CasaVault starts with the address."

**Action:** Type `3127 Kensington Ave` in the search box. Hit "Look it up."

Screen: Property page shows City records — licence status, violations.

> "This comes live from Philadelphia L&I. No active rental licence on file.
> That's the most common successful defence in landlord-tenant court — and
> CasaVault found it without anyone typing a thing."

---

## SCENE 3 — Upload the Bad Lease + Flags (50s)

> "Now someone signs a lease at a different address."

**Action:** Go back to landing. Click "Start — it's free." New vault opens.
Upload `04_major_deposit_overcharge_and_waiver_north_philly.pdf`.

> "North Broad Street. $950 a month rent, but the deposit is $2,850 — three
> months."

Screen: Extraction runs (~15–20s). While waiting:

> "Gemini reads the PDF, extracts 40 fields, and the rules engine checks every
> one against 9 verified statutes."

Findings populate. Scroll to the Findings panel.

> "Three flags. First — the deposit exceeds the first-year cap. Two months
> maximum under Pennsylvania law. 68 P.S. section 250.511a."
>
> "Second — the lease tries to waive your deposit rights. That waiver is void
> by statute."
>
> "Third — $2,850 and no escrow bank disclosed."
>
> "Every flag cites the exact statute section."

---

## SCENE 4 — Ask the Vault + Refusal (30s)

> "You can ask questions in plain English."

**Action:** Type: `How long does my landlord have to return my deposit?`

Screen: Answer appears with citation — 30 days, 68 P.S. 250.512.

> "Answers come from your records and the statute table only — never model
> knowledge."

**Action:** Type: `Will I win in court?`

Screen: Refusal with Philly Tenant Hotline number.

> "It refuses. 'I can't ground that in your records. Here's who can help.'
> That refusal is the product working — a system that knows what it doesn't
> know."

---

## SCENE 5 — Report a Problem (20s)

> "When something breaks, you need it in writing."

**Action:** Scroll to "Report a problem." Select **No heat / Emergency /
today's date**. Type: `No heat since Tuesday, below 50 degrees`. Click "Draft
notice."

Screen: Email draft appears.

> "We draft the notice. You send it from your own email — your outbox is the
> proof."

---

## SCENE 6 — Share + Evidence + Landlord Toggle (25s)

**Action:** Copy the share link. Open in new tab.

Screen: Counterparty view — findings visible, no edit controls.

> "One read-only link for the other side. They see the findings but can't
> change anything."

**Action:** Click "Evidence packet."

Screen: Print-friendly page with full timeline and citations.

> "Print to PDF — every finding with its citation, ready for court."

**Action:** Back in the vault, toggle to **Landlord view**.

> "Same facts, same rules — reframed for the other party."

---

## SCENE 7 — Close (10s)

Screen: Landing page.

> "Every answer cites a source. Every refusal routes to a human. Built at
> LexHack 2026."

---

## Timing summary

| Scene | Content | Time |
|-------|---------|------|
| 1 | Problem + landing | 15s |
| 2 | Address lookup | 20s |
| 3 | Upload bad lease + 3 flags | 50s |
| 4 | Agent Q&A + refusal | 30s |
| 5 | Report a problem | 20s |
| 6 | Share + evidence + landlord toggle | 25s |
| 7 | Close | 10s |
| **Total** | | **2 min 50s** |

---

## Pre-recording checklist

- [ ] Signed in at casavault.vercel.app (username visible in header)
- [ ] `04_major_deposit_overcharge_and_waiver_north_philly.pdf` on desktop
- [ ] Gemini quota available (test: upload a small .txt, confirm facts populate)
- [ ] 1280x800 or 1920x1080, light theme, 100% zoom
- [ ] No extra tabs or extensions visible
- [ ] Practice the address lookup once to confirm L&I data loads

## Quick reference — what appears on screen

| Moment | What you'll see |
|--------|-----------------|
| Address lookup: `3127 Kensington Ave` | No active rental licence, possible violations |
| Upload North Broad PDF | 3 flags: deposit over cap (250.511a(a)), waiver void (250.511a(f)), no escrow (250.511b) |
| Agent: "How long to return my deposit?" | 30 days from move-out, 68 P.S. 250.512 |
| Agent: "Will I win in court?" | Refusal + Philly Tenant Hotline (267) 443-2500 |
| Report: No heat / Emergency | Draft email with subject line and reference number |
| Share link | Read-only counterparty view, no vault ID exposed |
| Evidence packet | Print-friendly timeline + citations |
| Landlord toggle | Same findings, landlord-framed language |
