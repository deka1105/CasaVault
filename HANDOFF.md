# Handoff: CasaVault Clerk sign-in — bug #3 (unresolved)

Written by Sonnet 5, mid-debugging-session, for whoever (Opus or otherwise)
picks this up next. Read `CLAUDE.md` first for full project context — this
file only covers the *active* debugging thread, not the whole project.

## Project / deadline

CasaVault — statute-aware tenant/landlord rights record system, PA/Philly.
LexHack 2026, hard deadline **Sun Sep 27 2026, 5:00 PM EDT**. Live at
https://casavault.vercel.app. Vercel team `shubham-ad-s-projects`
(`team_4ZQ0ZjkOfXtsefK0Txbwh08b`), project `casavault`
(`prj_H5qOmZidImbAO138ZSbyPF8xNG4s`).

Deploy mechanics: a background watcher (`day10/GitHub-AutoPush-Analytics`)
auto-commits and auto-pushes every file save to `master`. Vercel's GitHub
integration then auto-deploys new commits on `master` straight to
**production** — no manual promote step needed for a genuinely new commit
(promote-by-hand is only needed when redeploying the *same* build/commit,
e.g. after an env-var-only change).

## What's fixed and confirmed working (don't re-litigate these)

1. **Bug #1 (fixed)**: `clerk.browser.js` loaded via plain `<script src>`
   needs `data-clerk-publishable-key` set on the tag itself — its internal
   auto-init reads that attribute synchronously. Without it, auto-init threw
   and left `window.Clerk` non-constructible. Fixed by setting the attribute
   and using `window.Clerk` directly as the pre-built singleton instead of
   `new window.Clerk(key)`.

2. **Bug #2 (fixed)**: `clerk.load()` needs a `clerkUICtor` option or any UI
   method (`openSignIn`, `mountUserButton`, ...) throws `"Clerk was not
   loaded with Ui components"` from `assertComponentsReady`. Fixed in
   `static/app.js`:
   - `clerkFrontendApiFromPublishableKey()` decodes the publishable key
     (base64) to get Clerk's own Frontend API domain
     (`prepared-monarch-288.clerk.accounts.dev` for this project's dev key).
   - `loadClerkScripts()` loads `@clerk/ui`'s browser bundle from that FAPI
     domain FIRST (`/npm/@clerk/ui@1/dist/ui.browser.js` — this file does
     **not** exist on generic jsdelivr, only on Clerk's own FAPI-as-CDN),
     which sets `window.__internal_ClerkUICtor` as a load-time side effect,
     then loads `clerk.browser.js` (also now from the FAPI domain, content
     confirmed byte-identical to the jsdelivr copy — switching CDN was not
     itself a risk).
   - `initAuth()` calls `await clerk.load({ clerkUICtor: window.__internal_ClerkUICtor })`.
   - **Verified against the actual live-served minified bundle, not docs**:
     grepped clerk.browser.js's own option normalizer
     (`#eQ=e=>{let t=e?.clerkUICtor??e?.clerkUiCtor...}`) and confirmed it
     wires straight into the internal components-ready promise
     (`this.#eW.ui?.ClerkUI&&(this.#eR=Promise.resolve(this.#eW.ui.ClerkUI).then(e=>new e(...)))`).
     Confirmed live: user reports sign-in now actually opens Google's OAuth
     popup and completes.

3. **The "lots of warnings" scare was a false alarm** — the user pasted
   console output tagged `accountchooser:*`, `post_api.js`,
   `accounts.youtube.com/.../cspreport`. That's **Google's own
   account-chooser popup's console**, not ours. All of it (unreachable-code
   warnings, Quirks Mode, Firefox fingerprinting-protection notice, CSP
   nonce blocks, 404s on Google's own CSP report endpoint) is Google-side
   noise unrelated to CasaVault. **If this comes up again, check the
   filenames in the stack trace before assuming it's our bug** — anything
   tagged with a google.com/youtube.com file or `accountchooser` is not
   ours.

## Bug #3 — ACTIVE, UNRESOLVED, NOT YET DIAGNOSED

User confirmed: sign-in via the Google popup **completes successfully**.
But on returning to the `casavault.vercel.app` tab:

- The header's "Sign in" button **stays visible** instead of being hidden
  and replaced by the mounted user button.
- The user reports "a lot of errors and warnings" in that tab's own
  console — **content not yet captured**. Asked the user twice to paste the
  console output specifically from the `casavault.vercel.app` tab (not the
  since-closed Google popup); not yet received in a confirmable form.

**Do not guess a fix without that console output.** This exact session hit
two wrong hypotheses already (an initial "third-party cookies" guess for bug
#1 was disproven by real console output; the accountchooser scare above
would have wasted a fix cycle on the wrong target). The pattern that's
worked all session: read the actual error text or the actual bundle source,
never assume.

### Relevant code — `static/app.js`, `updateAuthUI()` (~line 87-99)

```js
function updateAuthUI() {
  const signedIn = Boolean(clerk && clerk.user);
  qs("sign-in-btn").hidden = signedIn;

  const mount = qs("user-button-mount");
  mount.hidden = !signedIn;
  if (signedIn && !mount.dataset.mounted) {
    clerk.mountUserButton(mount);
    mount.dataset.mounted = "1";
  }

  refreshMyVaults();
}
```

Called once synchronously at the end of `initAuth()`, and again via
`clerk.addListener(() => updateAuthUI())` on every Clerk state change.

### Two live hypotheses — NEITHER confirmed

**(a) `clerk.user` is still falsy when the listener fires.** Note
`sign-in-btn.hidden = signedIn` runs *before* the `mountUserButton` call, so
if the button is still visible, `signedIn` was false at that point — this
points at a timing/sync issue between the OAuth popup closing and this tab's
`Clerk` instance's internal state updating, not at `mountUserButton` itself.

**(b) The popup→main-tab session handshake is throwing.** Clerk syncs
session state back from an OAuth popup via its own
postMessage/polling/cookie mechanism. If that handshake errors (which would
explain "a lot of errors"), `clerk.user` might never populate in the main
tab, leaving both the button and `getAuthHeaders()`/`refreshMyVaults()`
(further down in `app.js` — re-read those in full before changing anything)
stuck treating the session as signed-out even though Clerk's own popup says
otherwise.

### Blocking constraint for whoever picks this up

The Claude-in-Chrome browser extension is **not connected** in this
environment (`tabs_context_mcp` returned "Browser extension is not
connected"). Direct in-browser reproduction from the agent side isn't
currently possible — either get the user to reconnect the extension
(install + restart Chrome) so the agent can reproduce this directly, or keep
requesting exact console-output pastes from the user, explicitly scoped to
the `casavault.vercel.app` tab.

### Suggested first step

Get the actual error text from that tab's console after a completed
sign-in. Likely candidates worth checking once you have it: whether
`clerk.addListener` ever fires a second time post-popup, whether
`clerk.user` is populated at that point (`console.log(clerk.user)` from
devtools is a fine manual check), and whether `mountUserButton` itself
throws (wrap in try/catch with a visible error surface, same pattern
already used for `openSignIn` a few lines up in `app.js`, if it isn't
already surfacing one).

## Other pending items (lower priority than bug #3)

- Visual UI verification in an actual browser has still never been done —
  only functional/curl verification and now this Clerk debugging thread.
- Gemini free-tier 20-req/day limit — upgrade key tier before the real demo.
- Devpost write-up / demo video script — not started.
- Real-lease end-to-end test with an actual Philadelphia lease — needs a
  real document from the user, can't be fabricated.
