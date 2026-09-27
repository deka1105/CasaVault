# CasaVault — Demo Video Script (4 min)

**URL:** casavault.vercel.app
**Have ready:** `04_major_deposit_overcharge_and_waiver_north_philly.pdf` and `01_compliant_chestnut_hill.pdf` on desktop.

---

## SCENE 1 — Intro (15s)

Screen: Landing page, casavault.vercel.app

> "CasaVault is a statute-aware record of your rental. Upload a document —
> we check it against Pennsylvania and Philadelphia law, cite the exact
> statute behind every finding, and refuse to answer anything we can't
> ground in your own records."

---

## SCENE 2 — Sign In (20s)

> "First, secure sign-in through Clerk."

**Action:** Click "Sign in" in the header. Complete the Clerk sign-in flow (email/OTP).

Screen: Header updates — username visible, "Your vaults" appears.

> "Your identity is verified, but signing in is optional. Anyone can check
> a lease or look up an address without an account."

---

## SCENE 3 — Check Your Lease (50s)

> "Let's check a lease — no vault, no account needed. The file is deleted
> the moment we finish reading it."

**Action:** Click "Check your lease" in the nav.

Screen: Upload page with privacy callout.

**Action:** Upload `04_major_deposit_overcharge_and_waiver_north_philly.pdf`. Wait for extraction.

> "Gemini reads the PDF, extracts the facts, and the rules engine checks
> every one against 9 verified statutes."

Screen: Results appear — 3 issues flagged (red), passed rules (green), needs-info (yellow).

> "Three issues. The deposit is three months' rent — the first-year cap is
> two."

**Highlight:** Select the deposit flag and its citation `68 P.S. § 250.511a(a)`.

> "The lease tries to waive your deposit rights. That waiver is void."

**Highlight:** Select the waiver flag and `68 P.S. § 250.511a(f)`.

> "$2,850 and no escrow bank disclosed."

**Highlight:** Select the escrow flag and `68 P.S. § 250.511b`.

> "Every flag cites the exact statute. The green ones tell you what passed.
> The yellow ones tell you what facts are missing."

---

## SCENE 4 — Address Lookup #1 (25s)

**Action:** Click "Home" in the nav. Type `2153 E Cambria St` in the search box. Hit "Look it up."

Screen: Property page — inactive licence, 7 open violations.

> "This comes live from Philadelphia L&I — no one typed this."

**Highlight:** Select the licence status — Inactive.

> "No active rental licence. That alone bars the landlord from collecting
> rent or filing for eviction."

**Highlight:** Select the violations list — plumbing, electrical, smoke alarms, windows.

> "Seven open code violations."

---

## SCENE 5 — Address Lookup #2 + Create Vault (40s)

**Action:** Click "Home." Type `8200 Germantown Ave` in the search box. Hit "Look it up."

Screen: Property page — active licence, no open violations.

> "Different address — active licence, no violations. A clean record."

**Action:** Scroll down to "Keep your own record here." Upload `01_compliant_chestnut_hill.pdf`. Fill in zip `19118`. Click "Start my record here."

> "Now we start a vault. Upload the lease, and the same engine runs — but
> this time everything is saved."

Screen: Vault opens. Extraction runs. Findings panel populates.

> "This lease is compliant. Deposit under the cap, escrow bank disclosed,
> certificate provided. Every rule passed — that's the product working too,
> not just catching problems."

**Highlight:** Select the green "No issue found" findings.

---

## SCENE 6 — Ask This Vault (35s)

> "You can ask questions in plain English."

**Action:** Scroll to "Ask this vault." Type: `How long does my landlord have to return my deposit?`

Screen: Answer appears with citation.

**Highlight:** Select **30 days** in the answer.
**Highlight:** Select the citation `68 P.S. § 250.512`.

> "Grounded in the statute table — not a guess."

**Action:** Type: `Will I win in court?`

Screen: Refusal appears.

**Highlight:** Select the refusal text.
**Highlight:** Select the hotline number `(267) 443-2500`.

> "It refuses — and hands you off to a human. That refusal is the product
> working, not a limitation."

---

## SCENE 7 — Log an Issue (25s)

> "When something breaks, you need it in writing."

**Action:** Scroll to "Report a problem." Fill in:
- Category: **No heat**
- Urgency: **Emergency**
- Date: **today**
- Description: `No heat since Tuesday, below 50 degrees inside`

Click "Draft notice."

Screen: Email draft appears with structured subject line.

**Highlight:** Select the subject line (category | urgency | address | ref #).

> "We draft the notice. You send it from your own email — your outbox is
> your proof."

**Highlight:** Select the "Send from your email" mailto link.

---

## SCENE 8 — Close (10s)

Screen: Click "What we check" in the nav.

> "Nine verified rules. Every answer cites a source. Every refusal routes
> to a human. CasaVault — built at LexHack 2026."

---

## Timing

| Scene | Content | Time |
|-------|---------|------|
| 1 | Intro / landing | 15s |
| 2 | Clerk sign-in | 20s |
| 3 | Check your lease (bad lease, 3 flags) | 50s |
| 4 | Address lookup — 2153 E Cambria St (bad) | 25s |
| 5 | Address lookup — 8200 Germantown Ave (clean) + create vault | 40s |
| 6 | Ask this vault + refusal | 35s |
| 7 | Log an issue | 25s |
| 8 | Close | 10s |
| **Total** | | **4 min 0s** |

---

## Pre-recording checklist

- [ ] Both PDFs on desktop: `04_major...pdf` and `01_compliant...pdf`
- [ ] Gemini quota available (test: upload a small .txt first)
- [ ] 1280x800 or 1920x1080, light mode, 100% zoom
- [ ] No extra tabs or extensions visible
- [ ] Practice both address lookups once to confirm L&I data loads
- [ ] QuickTime ready (Cmd + Shift + 5)
