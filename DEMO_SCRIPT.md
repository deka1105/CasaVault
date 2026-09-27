# CasaVault — Demo Video Script

**Target length:** Under 3 minutes
**URL:** casavault.vercel.app
**Before recording:** Sign in via Clerk. Have the North Broad PDF
(`04_major_deposit_overcharge_and_waiver_north_philly.pdf`) ready on desktop.

---

## SCENE 1 — The Problem + Landing (15s)

Screen: casavault.vercel.app landing page.

> "In Philadelphia, 87% of landlords in housing court have a lawyer. Only 16%
> of tenants do. They don't lose because they're wrong — they lose because
> they can't prove it."

**Highlight:** Select the headline text "Keep proof of your rental — and know
what the law says."

---

## SCENE 2 — Address Lookup (20s)

> "CasaVault starts with the address."

**Action:** Type `3127 Kensington Ave` in the search box. Hit "Look it up."

Screen: Property page loads with City records.

> "This comes live from Philadelphia L&I."

**Highlight:** Select the licence status line — the text that says the licence
is **not active** or **expired**.

> "No active rental licence. That's the most common successful defence in
> landlord-tenant court — and CasaVault found it without anyone typing a
> thing."

---

## SCENE 3 — Upload the Bad Lease + Flags (50s)

> "Now someone signs a lease at a different address."

**Action:** Go back to landing. Click "Start — it's free." New vault opens.
Upload `04_major_deposit_overcharge_and_waiver_north_philly.pdf`.

> "North Broad Street. $950 a month rent, but the deposit is $2,850 — three
> months."

Screen: Extraction runs. While waiting:

> "Gemini reads the PDF, extracts 40 fields, and the rules engine checks every
> one against 9 verified statutes."

Findings populate. Scroll to the Findings panel.

**Finding 1 — Deposit over cap:**
**Highlight:** Select the full finding text that mentions the deposit exceeding
the first-year cap.
> "The deposit exceeds the first-year cap. Two months maximum."
**Highlight:** Select the citation text `68 P.S. § 250.511a(a)`.

**Finding 2 — Waiver void:**
**Highlight:** Select the finding text about the waiver clause.
> "The lease tries to waive your deposit rights. That waiver is void by
> statute."
**Highlight:** Select the citation `68 P.S. § 250.511a(f)`.

**Finding 3 — No escrow:**
**Highlight:** Select the finding text about escrow.
> "$2,850 and no escrow bank disclosed."
**Highlight:** Select the citation `68 P.S. § 250.511b`.

> "Every flag cites the exact statute section."

---

## SCENE 4 — Ask the Vault + Refusal (30s)

> "You can ask questions in plain English."

**Action:** Type: `How long does my landlord have to return my deposit?`

Screen: Answer appears.

**Highlight:** Select the part of the answer that says **30 days**.
**Highlight:** Select the citation `68 P.S. § 250.512` in the answer.

> "Answers come from your records and the statute table only."

**Action:** Type: `Will I win in court?`

Screen: Refusal response appears.

**Highlight:** Select the refusal text — "I can't ground that" or similar.
**Highlight:** Select the hotline number `(267) 443-2500`.

> "It refuses — and hands you off to a human. That's the product working."

---

## SCENE 5 — Report a Problem (20s)

> "When something breaks, you need it in writing."

**Action:** Scroll to "Report a problem." Fill in:
- What's the problem: **No heat**
- How urgent: **Emergency**
- Date: **today's date**
- Description: `No heat since Tuesday, below 50 degrees`
- Click "Draft notice"

Screen: Email draft appears.

**Highlight:** Select the **subject line** of the draft (the one with
category | urgency | address | reference number).

> "We draft the notice. You send it from your own email — your outbox is
> the proof."

**Highlight:** Select the **"Send from your email"** button / mailto link.

---

## SCENE 6 — Share + Evidence + Landlord Toggle (25s)

**Action:** Copy the share link. Open in new tab.

Screen: Counterparty view.

**Highlight:** Select the "Counterparty view" label at the top — proving this
is read-only.

> "One read-only link for the other side. They see the findings but can't
> change anything."

**Action:** Click "Evidence packet."

Screen: Print-friendly page.

**Highlight:** Select any one finding row with its statute citation in the
evidence packet — showing the citation carries through to the printout.

> "Print to PDF — every finding with its citation, ready for court."

**Action:** Back in the vault tab, click **Landlord view** toggle.

**Highlight:** Select one finding's text AFTER toggling — it now says "You may
not hold more than..." instead of "Your landlord is holding more than..."

> "Same facts, same rules — reframed for the other party."

---

## SCENE 7 — Close (10s)

Screen: Click "What we check" in the nav. 9 rules visible.

**Highlight:** Drag-select across several rule citations in the list.

> "Nine verified rules. Every answer cites a source. Every refusal routes to
> a human. Built at LexHack 2026."

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

## Highlight cheat sheet (what to select in each scene)

| Scene | What to select with cursor | Why |
|-------|---------------------------|-----|
| 1 | Headline: "Keep proof of your rental..." | Anchors the product's promise |
| 2 | Licence status: "No active rental licence" | The key City data finding |
| 3 | Finding #1 full text | Deposit over first-year cap |
| 3 | Citation: `68 P.S. § 250.511a(a)` | Proves the citation is real |
| 3 | Finding #2 full text | Waiver clause void |
| 3 | Citation: `68 P.S. § 250.511a(f)` | Second citation |
| 3 | Finding #3 full text | No escrow |
| 3 | Citation: `68 P.S. § 250.511b` | Third citation |
| 4 | "30 days" in the agent answer | The grounded answer |
| 4 | Citation: `68 P.S. § 250.512` | Agent cites its source |
| 4 | Refusal text: "I can't ground that..." | The designed refusal |
| 4 | Hotline: `(267) 443-2500` | Handoff to a human |
| 5 | Subject line of drafted notice | Shows the structured format |
| 5 | "Send from your email" link | We don't send it for you |
| 6 | "Counterparty view" label | Proves it's read-only |
| 6 | One citation row in evidence packet | Citations carry to print |
| 6 | Landlord-framed finding text | Same rule, other party's words |
| 7 | Multiple rule citations on /what-we-check | The statute table is the product |

---

## Pre-recording checklist

- [ ] Signed in at casavault.vercel.app (username visible in header)
- [ ] `04_major_deposit_overcharge_and_waiver_north_philly.pdf` on desktop
- [ ] Gemini quota available (test: upload a small .txt, confirm facts populate)
- [ ] 1280x800 or 1920x1080, light theme, 100% zoom
- [ ] No extra tabs or extensions visible
- [ ] Practice the address lookup once to confirm L&I data loads
- [ ] QuickTime screen recording ready (Cmd + Shift + 5)
