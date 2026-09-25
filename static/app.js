/* CasaVault front end — plain HTML/JS, no build step.
 *
 * Two modes off the query string, one page:
 *   ?vault=<id>    owner: full read/write
 *   ?share=<token> counterparty: read-only
 *
 * Owner and counterparty read from DIFFERENT API surfaces. The share view
 * never learns the vault id, because the vault id IS the write credential
 * (see app/routers/share.py). Read-only is a property of which endpoints
 * this page can reach, not of which buttons it hides.
 */

const state = {
  vaultId: null,
  shareToken: null,
  party: "tenant",
  vault: null,
};

let clerk = null;

const $ = (id) => document.getElementById(id);
const isOwner = () => Boolean(state.vaultId);

/* --- DOM building -------------------------------------------------------
 * Everything rendered from server data is built with createElement and
 * textContent. The previous version assembled rows with innerHTML and
 * interpolated notes, filenames, citations and vault labels straight in —
 * all attacker-controlled (a filename is chosen by whoever uploads, and a
 * share link is opened by the *other* party), so any of them could inject
 * script into the counterparty's session. Never reintroduce innerHTML here.
 */

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.startsWith("on")) node.addEventListener(key.slice(2).toLowerCase(), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined) continue;
    node.append(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

function replaceChildren(node, children) {
  node.replaceChildren(...[].concat(children).filter(Boolean));
}

function emptyRow(colspan, message) {
  return el("tr", {}, el("td", { colspan: String(colspan), class: "empty", text: message }));
}

function showError(node, message) {
  node.textContent = message;
  node.hidden = false;
}

function clearError(node) {
  node.textContent = "";
  node.hidden = true;
}

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

function formatDate(value) {
  if (!value) return "";
  const raw = String(value);

  // A calendar date is not an instant. new Date("2026-08-31") is parsed as
  // UTC midnight per the spec, and toLocaleDateString then renders it in the
  // viewer's zone — so everywhere west of UTC it printed the PREVIOUS day.
  // In a record whose whole purpose is proving what happened when, that is
  // not cosmetic: the 30-day deposit clock (68 P.S. § 250.512) was being
  // shown to tenants as expiring a day earlier than the statute allows.
  // Date-only strings must therefore be constructed in local time; full
  // timestamps (created_at, acknowledged_at) are real instants and stay as-is.
  const parts = DATE_ONLY.exec(raw);
  const date = parts
    ? new Date(Number(parts[1]), Number(parts[2]) - 1, Number(parts[3]))
    : new Date(raw);

  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/* --- API ---------------------------------------------------------------- */

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    let detail = body.detail;
    // FastAPI validation errors arrive as a list of objects; flatten so the
    // UI never prints "[object Object]" at the user.
    if (Array.isArray(detail)) detail = detail.map((d) => d.msg || String(d)).join("; ");
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return res.status === 204 ? null : res.json();
}

/** Path to this vault's data, on whichever surface the current mode uses. */
function vaultPath(suffix = "") {
  return isOwner()
    ? `/api/vaults/${encodeURIComponent(state.vaultId)}${suffix}`
    : `/api/vaults/by-share-token/${encodeURIComponent(state.shareToken)}${suffix}`;
}

/* --- optional sign-in (Clerk) -------------------------------------------
 * Sign-in never gates access — the vault id / share token remain the actual
 * access control. It only lets a creator find their own vaults later.
 * If /api/config reports no publishable key, none of this runs.
 */

function loadScript(src, attrs = {}) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.crossOrigin = "anonymous";
    for (const [key, value] of Object.entries(attrs)) script.setAttribute(key, value);
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Failed to load script: ${src}`));
    document.head.appendChild(script);
  });
}

// pk_{test|live}_<base64(frontendApiDomain + "$")>. That domain also proxies
// npm for Clerk's own packages, which is where @clerk/ui's browser bundle
// lives — it is not on generic jsdelivr.
function clerkFrontendApiFromPublishableKey(publishableKey) {
  const base64Part = publishableKey.replace(/^pk_(test|live)_/, "");
  const padded = base64Part + "=".repeat((4 - (base64Part.length % 4)) % 4);
  return atob(padded).replace(/\$+$/, "");
}

function loadClerkScripts(publishableKey) {
  // Two load-order requirements, both confirmed against the shipped bundle:
  //   1. clerk.browser.js auto-initializes as it executes, reading
  //      data-clerk-publishable-key off its own <script> tag. Without the
  //      attribute it throws internally and leaves window.Clerk unusable.
  //   2. @clerk/ui must finish loading FIRST — it sets
  //      window.__internal_ClerkUICtor as a side effect, and clerk.load()
  //      needs that or every UI method throws "not loaded with Ui components".
  const fapi = clerkFrontendApiFromPublishableKey(publishableKey);
  return loadScript(`https://${fapi}/npm/@clerk/ui@1/dist/ui.browser.js`).then(() =>
    loadScript(`https://${fapi}/npm/@clerk/clerk-js@6/dist/clerk.browser.js`, {
      "data-clerk-publishable-key": publishableKey,
    })
  );
}

/* Recovery for the "signed in, but the header still says Sign in" case.
 *
 * Derived by reading clerk.browser.js's own source, not guessed. Its OAuth
 * popup handshake ends in `setActive({session, redirectUrl})`; setActive,
 * when given a redirectUrl, starts a navigation and then does
 * `if (isUnloading()) return;` — deliberately skipping the internal step
 * (#eX) that assigns clerk.user/clerk.session AND emits to addListener
 * subscribers, because the document is expected to be replaced by the
 * navigation. If that navigation does not actually complete, the tab is left
 * holding a Clerk instance whose client HAS the new signed-in session while
 * clerk.user is still null and no listener will ever fire again.
 *
 * So: consult the client's sessions rather than clerk.user alone, and if a
 * signed-in session exists that the instance hasn't adopted, call setActive
 * WITHOUT a redirectUrl — that path skips the navigation branch and does run
 * the assign-and-emit step.
 */
async function syncClerkSession() {
  if (!clerk || clerk.user) return;
  const sessions = clerk.client?.signedInSessions || clerk.client?.sessions || [];
  const active = sessions.find((s) => s.status === "active") || sessions[0];
  if (!active) return;
  try {
    await clerk.setActive({ session: active.id });
  } catch (err) {
    console.error("Clerk session sync failed", err);
  }
  updateAuthUI();
}

async function initAuth() {
  let config;
  try {
    config = await api("/api/config");
  } catch {
    return; // config endpoint unreachable: run fully anonymous
  }
  if (!config.clerk_publishable_key) return;

  try {
    await loadClerkScripts(config.clerk_publishable_key);
    clerk = window.Clerk;
    await clerk.load({ clerkUICtor: window.__internal_ClerkUICtor });
  } catch (err) {
    console.error("Clerk failed to load; continuing without sign-in", err);
    return;
  }

  $("auth-area").hidden = false;
  $("sign-in-btn").addEventListener("click", () => {
    try {
      clerk.openSignIn();
      // The popup hands the session back by postMessage; see syncClerkSession
      // for why that can land without ever updating this tab. Re-check for a
      // while afterwards so the header can't get stuck showing "Sign in".
      pollForSignIn();
    } catch (err) {
      console.error("Clerk openSignIn failed", err);
      showError($("auth-error"), "Sign-in failed to open. See the browser console for details.");
    }
  });

  clerk.addListener(() => updateAuthUI());
  // Returning to this tab after completing sign-in elsewhere is exactly the
  // moment the missed-emit case above becomes visible, so re-check there too.
  window.addEventListener("focus", () => void syncClerkSession());
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) void syncClerkSession();
  });

  updateAuthUI();
}

function pollForSignIn() {
  const deadline = Date.now() + 90_000;
  const tick = async () => {
    if (clerk?.user || Date.now() > deadline) return;
    await syncClerkSession();
    if (!clerk?.user) setTimeout(tick, 1000);
  };
  setTimeout(tick, 1000);
}

function updateAuthUI() {
  const signedIn = Boolean(clerk && clerk.user);
  $("sign-in-btn").hidden = signedIn;

  const mount = $("user-button-mount");
  mount.hidden = !signedIn;
  if (signedIn && !mount.dataset.mounted) {
    try {
      clerk.mountUserButton(mount);
      mount.dataset.mounted = "1";
    } catch (err) {
      // A throw here previously left the header with neither control.
      console.error("Clerk mountUserButton failed", err);
      mount.hidden = true;
      $("sign-in-btn").hidden = false;
    }
  }
  void refreshMyVaults();
}

async function getAuthHeaders() {
  if (clerk && clerk.session) {
    try {
      const token = await clerk.session.getToken();
      if (token) return { Authorization: `Bearer ${token}` };
    } catch {
      /* fall through to anonymous */
    }
  }
  return {};
}

async function refreshMyVaults() {
  const section = $("my-vaults");
  const onLanding = !$("landing").hidden;
  if (!clerk || !clerk.user || !onLanding) {
    section.hidden = true;
    return;
  }
  try {
    const vaults = await api("/api/vaults/mine", { headers: await getAuthHeaders() });
    replaceChildren(
      $("my-vaults-list"),
      vaults.length
        ? vaults.map((v) =>
            el("li", {}, el("a", { href: `/?vault=${encodeURIComponent(v.id)}`, text: v.label || `Vault ${v.id.slice(0, 8)}` }))
          )
        : el("li", { class: "empty", text: "No vaults yet — create one to get started." })
    );
    section.hidden = false;
  } catch {
    section.hidden = true;
  }
}

/* --- views -------------------------------------------------------------- */

function showLanding() {
  $("landing").hidden = false;
  $("vault-view").hidden = true;
  void refreshMyVaults();
}

function showVaultView() {
  $("landing").hidden = true;
  $("my-vaults").hidden = true;
  $("vault-view").hidden = false;
}

async function loadVaultById(id) {
  const vault = await api(`/api/vaults/${encodeURIComponent(id)}`);
  state.vaultId = vault.id;
  state.shareToken = null;
  state.vault = vault;
  await renderVault();
}

async function loadVaultByShareToken(token) {
  const vault = await api(`/api/vaults/by-share-token/${encodeURIComponent(token)}`);
  state.vaultId = null; // the share surface never yields it, by design
  state.shareToken = token;
  state.vault = vault;
  // The counterparty is the other side of the same rules, so open on the
  // opposite framing by default.
  state.party = "landlord";
  const landlordRadio = document.querySelector('input[name="party"][value="landlord"]');
  if (landlordRadio) landlordRadio.checked = true;
  await renderVault();
}

async function renderVault() {
  const vault = state.vault;
  showVaultView();

  $("vault-label").textContent = vault.label || (isOwner() ? `Vault ${state.vaultId.slice(0, 8)}` : "Shared vault");
  $("vault-mode").textContent = isOwner() ? "You hold this vault" : "Shared with you · read-only";
  $("vault-created").textContent = vault.created_at ? `Opened ${formatDate(vault.created_at)}` : "";

  $("owner-controls").hidden = !isOwner();
  $("event-form-section").hidden = !isOwner();
  $("ask-section").hidden = !isOwner();
  $("counterparty-controls").hidden = isOwner();

  if (isOwner()) {
    const shareUrl = `${location.origin}/?share=${encodeURIComponent(vault.share_token)}`;
    const link = $("share-link");
    link.href = shareUrl;
    link.textContent = shareUrl;
    renderAskSuggestions();
  } else {
    $("ack-status").textContent = vault.acknowledged_at
      ? `Acknowledged ${formatDate(vault.acknowledged_at)}`
      : "You have not acknowledged this record yet.";
    $("acknowledge-btn").disabled = Boolean(vault.acknowledged_at);
    $("share-evidence-link").href = `${vaultPath("/evidence")}?party=${state.party}`;
  }
  updateEvidenceLink();
  await Promise.all([renderRtcBanner(), refreshData()]);
}

function updateEvidenceLink() {
  const link = isOwner() ? $("evidence-link") : $("share-evidence-link");
  link.href = `${vaultPath("/evidence")}?party=${encodeURIComponent(state.party)}`;
}

async function renderRtcBanner() {
  const banner = $("rtc-banner");
  if (!state.vault.zip_code) {
    banner.hidden = true;
    return;
  }
  try {
    const rtc = await api(vaultPath("/rtc-check"));
    const covered = rtc.route === "hotline";
    banner.className = covered ? "banner" : "banner banner-caution";
    replaceChildren(banner, [
      el("strong", { text: covered ? "Right to Counsel covers this zip code. " : "This zip is outside Right to Counsel. " }),
      covered
        ? `You may qualify for a free lawyer in eviction court. Call ${rtc.contact}. ${rtc.eligibility || ""}`
        : `Free legal help and self-help guides are at ${rtc.contact}.`,
    ]);
    banner.hidden = false;
  } catch {
    banner.hidden = true;
  }
}

async function refreshData() {
  clearError($("vault-error"));
  try {
    const [events, flags, deadlines] = await Promise.all([
      api(vaultPath("/events")),
      api(vaultPath("/flags")),
      api(vaultPath("/deadlines")),
    ]);
    renderEvents(events);
    renderFindings(flags);
    renderDeadlines(deadlines);
  } catch (err) {
    // Previously this failure was only console.error'd, so a broken vault
    // looked like an empty one.
    showError($("vault-error"), `Could not load this vault: ${err.message}`);
  }
}

function renderEvents(events) {
  const tbody = $("events-table").querySelector("tbody");
  if (!events.length) {
    replaceChildren(tbody, emptyRow(5, "Nothing recorded yet."));
    return;
  }
  replaceChildren(
    tbody,
    events.map((e) => {
      const facts = Object.entries(e.facts || {});
      return el("tr", {}, [
        el("td", { class: "num", text: formatDate(e.occurred_at) }),
        el("td", {}, el("strong", { text: e.event_type.replace(/_/g, " ") })),
        el("td", { text: e.notes || "" }),
        el(
          "td",
          {},
          facts.length
            ? facts.map(([k, v]) => el("div", { class: "cite", text: `${k}: ${v}` }))
            : el("span", {
                class: "empty",
                // An uploaded document with no facts means extraction found
                // nothing (or could not run) — say so, rather than showing
                // the same blank dash as a hand-logged event that never had
                // facts to begin with. The document itself is stored either way.
                text: e.event_type === "document_upload" ? "nothing extracted" : "—",
              })
        ),
        el(
          "td",
          {},
          e.source_document_ref
            ? el("a", {
                href: `${vaultPath("/documents")}/${e.id}`,
                target: "_blank",
                rel: "noopener",
                text: e.original_filename || "download",
              })
            : ""
        ),
      ]);
    })
  );
}

function framingFor(flag) {
  const primary = state.party === "landlord" ? flag.message_landlord : flag.message_tenant;
  return primary || flag.message_tenant || flag.message_landlord || flag.statute_id;
}

function renderFindings(flags) {
  const list = $("findings-list");
  if (!flags.length) {
    replaceChildren(
      list,
      el("li", { class: "empty", text: "No findings yet. Upload a lease or record what you know and the rules engine runs automatically." })
    );
    return;
  }
  const order = { violation: 0, caution: 1 };
  const sorted = [...flags].sort((a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9));
  replaceChildren(
    list,
    sorted.map((f) =>
      el("li", { class: `finding finding-${f.severity}` }, [
        el("div", { class: "finding-head" }, el("span", { class: "badge", text: f.severity })),
        el("p", { class: "finding-body", text: framingFor(f) }),
        el("span", { class: "cite", text: f.citation }),
      ])
    )
  );
}

function renderDeadlines(deadlines) {
  const tbody = $("deadlines-table").querySelector("tbody");
  if (!deadlines.length) {
    replaceChildren(tbody, emptyRow(3, "No statutory clocks started."));
    return;
  }
  replaceChildren(
    tbody,
    deadlines.map((d) =>
      el("tr", {}, [
        el("td", { class: "num", text: formatDate(d.due_date) }),
        el("td", { text: d.description }),
        el("td", { text: d.resolved ? "resolved" : "open" }),
      ])
    )
  );
}

/* --- the grounded agent -------------------------------------------------- */

const ASK_SUGGESTIONS = {
  tenant: [
    "How long does he have to return my deposit?",
    "What did my landlord fail to give me when I signed?",
    "Will I win in court?",
  ],
  landlord: [
    "How long do I have to return the deposit?",
    "What am I required to give a tenant at signing?",
    "Will I win in court?",
  ],
};

function renderAskSuggestions() {
  replaceChildren(
    $("ask-suggestions"),
    (ASK_SUGGESTIONS[state.party] || []).map((q) =>
      el("button", {
        type: "button",
        class: "chip",
        text: q,
        onclick: () => {
          $("ask-question").value = q;
          $("ask-form").requestSubmit();
        },
      })
    )
  );
}

function renderAnswer(result) {
  const panel = $("ask-answer");
  panel.hidden = false;

  if (result.refusal) {
    // A refusal is the designed behaviour, not an error state (PLAN.md:
    // "That last refusal goes in the demo video. It is the point.") — but an
    // upstream outage is a fault, and the two must not look identical or
    // users learn to distrust a refusal that worked exactly as intended.
    const handoff = result.handoff || {};
    panel.className = "answer answer-refusal";
    replaceChildren(panel, [
      el("div", {
        class: "answer-label",
        text: result.unavailable ? "Agent temporarily unavailable" : "Not answerable from this record",
      }),
      el("p", { class: "answer-text", text: result.refusal }),
      el("div", { class: "handoff" }, [
        el("strong", { text: "Talk to a human: " }),
        handoff.route === "hotline"
          ? `Philly Tenant Hotline, ${handoff.contact}. ${handoff.eligibility || ""}`
          : el("a", { href: handoff.contact || "https://phillytenant.org", target: "_blank", rel: "noopener", text: handoff.contact || "phillytenant.org" }),
      ]),
    ]);
    return;
  }

  panel.className = "answer";
  replaceChildren(panel, [
    el("div", { class: "answer-label", text: "Answer, grounded in this vault" }),
    el("p", { class: "answer-text", text: result.answer }),
    result.citation ? el("span", { class: "cite", text: `Source: ${result.citation}` }) : null,
  ]);
}

function setupAsk() {
  $("ask-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = $("ask-question").value.trim();
    if (!question || !isOwner()) return;

    const btn = $("ask-btn");
    const panel = $("ask-answer");
    btn.disabled = true;
    btn.textContent = "Asking…";
    panel.hidden = false;
    panel.className = "answer";
    replaceChildren(panel, [
      el("div", { class: "answer-label", text: "Working" }),
      el("p", { class: "answer-text" }, [el("span", { class: "spinner" }), " Checking your record and the statute table…"]),
    ]);

    try {
      const result = await api(vaultPath("/ask"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, party: state.party }),
      });
      renderAnswer(result);
    } catch (err) {
      panel.className = "answer answer-refusal";
      replaceChildren(panel, [
        el("div", { class: "answer-label", text: "Could not ask" }),
        el("p", { class: "answer-text", text: err.message }),
      ]);
    } finally {
      btn.disabled = false;
      btn.textContent = "Ask";
    }
  });
}

/* --- statute table ------------------------------------------------------- */

async function renderStatuteTable() {
  let rules;
  try {
    rules = await api("/api/statutes");
  } catch {
    return;
  }
  $("statute-count").textContent = `${rules.length} verified rules`;
  replaceChildren(
    $("statute-list"),
    rules.map((r) =>
      el("li", { class: "statute" }, [
        el("div", { class: "statute-head" }, [
          el("span", { class: "cite", text: r.citation }),
          el("span", { class: "statute-id", text: r.id }),
        ]),
        el("p", { text: (r.party_framing && r.party_framing.tenant) || r.detail || "" }),
      ])
    )
  );
}

/* --- forms --------------------------------------------------------------- */

function setupCreateVault() {
  $("create-vault-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = $("create-error");
    clearError(errorEl);
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const vault = await api("/api/vaults", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(await getAuthHeaders()) },
        body: JSON.stringify({
          label: $("new-vault-label").value.trim() || null,
          zip_code: $("new-vault-zip").value.trim() || null,
        }),
      });
      history.replaceState(null, "", `/?vault=${encodeURIComponent(vault.id)}`);
      state.vaultId = vault.id;
      state.shareToken = null;
      state.vault = vault;
      await renderVault();
    } catch (err) {
      showError(errorEl, err.message);
    } finally {
      btn.disabled = false;
    }
  });
}

function setupOpenVault() {
  $("open-vault-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = $("open-error");
    clearError(errorEl);
    const value = $("open-vault-id").value.trim();
    if (!value) return;
    try {
      await loadVaultById(value);
      history.replaceState(null, "", `/?vault=${encodeURIComponent(value)}`);
    } catch {
      try {
        await loadVaultByShareToken(value);
        history.replaceState(null, "", `/?share=${encodeURIComponent(value)}`);
      } catch {
        showError(errorEl, "No vault found for that id or share token.");
      }
    }
  });
}

function setupPartyToggle() {
  document.querySelectorAll('input[name="party"]').forEach((input) => {
    input.addEventListener("change", async (e) => {
      state.party = e.target.value;
      updateEvidenceLink();
      if (isOwner()) renderAskSuggestions();
      await refreshData();
    });
  });
}

function updateEventFormMode() {
  const isUpload = $("event-type").value === "document_upload";
  $("event-file-label").hidden = !isUpload;
  $("facts-fields").hidden = isUpload;
  $("advanced-facts").hidden = isUpload;
}

function collectStructuredFacts() {
  const facts = {};
  document.querySelectorAll('#facts-fields [name^="fact:"]').forEach((input) => {
    const key = input.name.slice("fact:".length);
    const raw = input.value;
    if (raw === "") return; // not stated — omit rather than assert a value
    facts[key] = input.dataset.factType === "number" ? Number(raw) : raw === "true";
  });
  return facts;
}

async function uploadDocument() {
  const file = $("event-file").files[0];
  if (!file) throw new Error("Choose a file to upload.");
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new Error(`That file is ${(file.size / 1024 / 1024).toFixed(1)}MB. The limit is ${MAX_UPLOAD_BYTES / 1024 / 1024}MB.`);
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("occurred_at", $("event-date").value);
  if ($("event-notes").value) formData.append("notes", $("event-notes").value);

  const res = await fetch(`/api/vaults/${encodeURIComponent(state.vaultId)}/documents`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

/* The document is always stored; reading it is best-effort on top. So an
 * upload that extracted nothing is a success, not an error — but the user
 * still has to be told which of "the document stated nothing we track" and
 * "the daily reading limit ran out" happened, or an empty facts column looks
 * like the product is broken. */
function reportExtraction(info) {
  const note = $("upload-result");
  if (!info || info.status === "ok") {
    note.hidden = true;
    return;
  }
  note.className = info.status === "no_facts" ? "banner" : "banner banner-caution";
  note.textContent = info.message || "The document was stored, but no facts were read from it.";
  note.hidden = false;
}

async function createJsonEvent() {
  const facts = collectStructuredFacts();
  const advancedRaw = $("event-facts-advanced").value.trim();
  if (advancedRaw) Object.assign(facts, JSON.parse(advancedRaw));
  await api(vaultPath("/events"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_type: $("event-type").value,
      occurred_at: $("event-date").value,
      notes: $("event-notes").value || null,
      facts,
    }),
  });
}

// Mirrors MAX_UPLOAD_BYTES in app/documents.py — kept under Vercel's 4.5MB
// request-body limit, which is enforced at the platform edge before the
// request ever reaches the app.
const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;

function setupEventForm() {
  $("event-type").addEventListener("change", updateEventFormMode);
  $("upload-hint").textContent = `PDF, JPG, PNG, HEIC or TXT, up to ${MAX_UPLOAD_BYTES / 1024 / 1024}MB. It is read and adjudicated on upload.`;

  $("event-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = $("event-error");
    clearError(errorEl);
    const btn = $("event-submit");
    const isUpload = $("event-type").value === "document_upload";
    btn.disabled = true;
    btn.textContent = isUpload ? "Reading document…" : "Saving…";

    try {
      if (isUpload) reportExtraction((await uploadDocument()).extraction);
      else await createJsonEvent();
      $("event-form").reset();
      updateEventFormMode();
      await refreshData();
    } catch (err) {
      showError(errorEl, err.message.includes("JSON") ? "Advanced facts must be valid JSON." : err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Add to record";
    }
  });
}

function setupAcknowledge() {
  $("acknowledge-btn").addEventListener("click", async () => {
    const btn = $("acknowledge-btn");
    btn.disabled = true;
    try {
      const vault = await api(vaultPath("/acknowledge"), { method: "POST" });
      state.vault = vault;
      $("ack-status").textContent = `Acknowledged ${formatDate(vault.acknowledged_at)}`;
    } catch (err) {
      showError($("vault-error"), err.message);
      btn.disabled = false;
    }
  });
}

function setupCopyShare() {
  $("copy-share-btn").addEventListener("click", async () => {
    const btn = $("copy-share-btn");
    try {
      await navigator.clipboard.writeText($("share-link").href);
      btn.textContent = "Copied";
      setTimeout(() => (btn.textContent = "Copy link"), 1500);
    } catch {
      btn.textContent = "Copy failed";
      setTimeout(() => (btn.textContent = "Copy link"), 1500);
    }
  });
}

/* --- boot ---------------------------------------------------------------- */

async function init() {
  setupCreateVault();
  setupOpenVault();
  setupEventForm();
  setupAcknowledge();
  setupPartyToggle();
  setupCopyShare();
  setupAsk();
  updateEventFormMode();

  const params = new URLSearchParams(location.search);
  const shareToken = params.get("share");
  const vaultId = params.get("vault");

  try {
    if (shareToken) await loadVaultByShareToken(shareToken);
    else if (vaultId) await loadVaultById(vaultId);
    else showLanding();
  } catch (err) {
    console.error("Failed to load vault from URL", err);
    showLanding();
    showError($("open-error"), `That link did not resolve to a vault: ${err.message}`);
  }

  // Non-blocking: neither should delay first paint of the vault.
  void renderStatuteTable();
  void initAuth();
}

init();
