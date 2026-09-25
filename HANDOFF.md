# Handoff: CasaVault — Clerk bug #3 (still needs a human) + session summary

Updated Sep 25 by Opus 5. Read `CLAUDE.md` first for full project context.
This file covers only what is still *open*.

## Deadline

LexHack 2026, hard submission **Sun Sep 27 2026, 5:00 PM EDT**.
Live at https://casavault.vercel.app. Vercel team `shubham-ad-s-projects`,
project `casavault` (`prj_H5qOmZidImbAO138ZSbyPF8xNG4s`).

A background watcher auto-commits and auto-pushes every file save to
`master`; Vercel auto-deploys new commits on `master` straight to production.
No manual promote needed for a genuinely new commit.

## Blocking for the demo — owner action, not code

1. **Upgrade the Gemini key's tier.** The free tier's 20 requests/day is
   exhausted. Every upload and every `/ask` is one request. The app now
   handles this honestly (says "daily limit reached", distinct from a
   grounded refusal, in ~20s rather than ~140s) but a quota message is not a
   demo. **This is the single highest-value thing to do before Saturday.**
2. **One Clerk sign-in click-through** (below).
3. **A real Philadelphia lease, end to end.** Can't be fabricated; needs a
   real document. PLAN.md gates Saturday night on this.

## Bug #3 — sign-in completes, header still says "Sign in"

Still not reproduced directly (the Claude-in-Chrome extension is not
connected in this environment), but the **mechanism is now identified from
clerk-js 6.34.1's own shipped source**, not guessed:

- The OAuth popup hands the session back by `postMessage`, and the handler
  ends in `setActive({session, redirectUrl})`.
- `setActive`, when given a `redirectUrl`, starts a navigation and then does
  `if (isUnloading()) return;` — deliberately **skipping** the internal step
  (`#eX`) that assigns `clerk.user` / `clerk.session` *and* emits to
  `addListener` subscribers, because the document is expected to be replaced.
- `isUnloading()` flips true on `beforeunload`. So if that navigation starts
  but never completes, the tab is left holding a Clerk instance whose
  `client` HAS the new signed-in session while `clerk.user` is still `null`
  and **no listener will ever fire again**. That is exactly the reported
  symptom.

**Mitigation shipped** (`syncClerkSession()` in `static/app.js`): don't trust
`clerk.user` alone — consult `clerk.client.signedInSessions`, and if a
signed-in session exists that the instance hasn't adopted, call
`setActive({session: id})` **without** a `redirectUrl`. That path skips the
navigation branch and does run the assign-and-emit step. It is re-checked on
`focus`, on `visibilitychange`, and by a poll for 90s after `openSignIn()`.
`mountUserButton` is also wrapped in try/catch so a throw there can't leave
the header with neither control.

**Verified as far as possible without a sign-in**: headless Chrome against
the live page reports `window.Clerk=object`, `clerk.loaded=true`,
`__internal_ClerkUICtor=function`, `clerk.client=present`, `clerk.user=null`,
**zero console errors**. So bugs #1 and #2 remain fixed and the load path is
clean.

**What's left**: open the site, sign in, and confirm the header swaps to the
user button and "Your vaults" appears. If it still doesn't, the mitigation
tells you which hypothesis was right — capture `window.Clerk.client.sessions`
and `window.Clerk.user` from that tab's console.

**Remember**: sign-in is explicitly out of PLAN.md scope and never gates
access. If it resists, cutting the sign-in UI costs nothing — the vault link
is the real access control. Don't let it eat Saturday.

## Fixed this session (don't re-litigate)

Backend: `pytest -q` now runs (root `conftest.py`; it also stops the suite
writing into the dev database); the share link is genuinely read-only (it
used to hand out the vault id, which is the write credential); `storage.persist`
no longer 500s when `UPLOADS_DIR` is outside the project; upload cap lowered
to 4MB to sit under Vercel's 4.5MB edge limit; deadlines deduped and framed
per party; agent and extractor now distinguish quota / outage / refusal;
Gemini SDK retries disabled (140s → 20s on a 429); `party` validated as a
Literal; zip codes validated.

Frontend: rebuilt. Stored XSS removed (no `innerHTML` for server data);
**the grounded agent finally has a UI** — it had none at all, despite being
the flagship feature; dates no longer render a day early (statutory
deadlines were affected); responsive down to 320px; vault creation now takes
a label and zip, which is what makes the RTC check reachable at all;
statute-table browser added.

67 tests green. Screenshots of the rebuilt UI were taken with headless
Chrome and checked; the layout was measured for overflow at 320–900px.

## Still unverified

- Visual check by a human in a real browser (headless screenshots only).
- A successful Clerk sign-in.
- A live extraction success against the deployed app (blocked on quota).
- Devpost write-up / demo video script — not started.
