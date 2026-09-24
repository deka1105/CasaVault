const state = { vaultId: null, shareToken: null, isOwner: true, party: "tenant" };

function qs(id) {
  return document.getElementById(id);
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

function showVaultView() {
  qs("landing").hidden = true;
  qs("vault-view").hidden = false;
}

async function loadVaultById(id) {
  const vault = await api(`/api/vaults/${id}`);
  state.vaultId = vault.id;
  state.shareToken = vault.share_token;
  state.isOwner = true;
  await renderVault(vault);
}

async function loadVaultByShareToken(token) {
  const vault = await api(`/api/vaults/by-share-token/${token}`);
  state.vaultId = vault.id;
  state.shareToken = token;
  state.isOwner = false;
  await renderVault(vault);
}

async function renderVault(vault) {
  showVaultView();
  qs("vault-label").textContent = vault.label || `Vault ${vault.id}`;

  qs("owner-controls").hidden = !state.isOwner;
  qs("event-form-section").hidden = !state.isOwner;
  qs("counterparty-controls").hidden = state.isOwner;

  if (state.isOwner) {
    const shareUrl = `${location.origin}/?share=${vault.share_token}`;
    qs("share-link").href = shareUrl;
    qs("share-link").textContent = shareUrl;
    qs("evidence-link").href = `/api/vaults/${vault.id}/evidence`;
  } else {
    qs("ack-status").textContent = vault.acknowledged_at
      ? `Acknowledged at ${vault.acknowledged_at}`
      : "Not yet acknowledged.";
    qs("acknowledge-btn").disabled = Boolean(vault.acknowledged_at);
  }

  const banner = qs("rtc-banner");
  if (vault.zip_code) {
    try {
      const rtc = await api(`/api/vaults/${vault.id}/rtc-check`);
      banner.hidden = false;
      banner.textContent =
        rtc.route === "hotline"
          ? `This zip is covered by Right to Counsel — call ${rtc.contact}.`
          : `Not an RTC-covered zip — see ${rtc.contact} for help.`;
    } catch {
      banner.hidden = true;
    }
  } else {
    banner.hidden = true;
  }

  await refreshData();
}

async function refreshData() {
  const [events, flags, deadlines] = await Promise.all([
    api(`/api/vaults/${state.vaultId}/events`),
    api(`/api/vaults/${state.vaultId}/flags`),
    api(`/api/vaults/${state.vaultId}/deadlines`),
  ]);
  renderEvents(events);
  renderFlags(flags);
  renderDeadlines(deadlines);
}

function renderEvents(events) {
  const tbody = qs("events-table").querySelector("tbody");
  tbody.innerHTML =
    events
      .map((e) => `<tr><td>${e.occurred_at}</td><td>${e.event_type}</td><td>${e.notes || ""}</td></tr>`)
      .join("") || "<tr><td colspan='3'><em>No events yet.</em></td></tr>";
}

function renderFlags(flags) {
  const tbody = qs("flags-table").querySelector("tbody");
  tbody.innerHTML =
    flags
      .map((f) => {
        const message = state.party === "landlord" ? f.message_landlord : f.message_tenant;
        return `<tr class="severity-${f.severity}"><td>${f.severity}</td><td>${message || f.statute_id}</td><td>${f.citation}</td></tr>`;
      })
      .join("") || "<tr><td colspan='3'><em>No flags yet.</em></td></tr>";
}

function renderDeadlines(deadlines) {
  const tbody = qs("deadlines-table").querySelector("tbody");
  tbody.innerHTML =
    deadlines
      .map((d) => `<tr><td>${d.due_date}</td><td>${d.description}</td><td>${d.resolved ? "resolved" : "open"}</td></tr>`)
      .join("") || "<tr><td colspan='3'><em>No deadlines tracked.</em></td></tr>";
}

function setupPartyToggle() {
  document.querySelectorAll('input[name="party"]').forEach((input) => {
    input.addEventListener("change", (e) => {
      state.party = e.target.value;
      refreshData();
    });
  });
}

function setupCreateVault() {
  qs("create-vault-btn").addEventListener("click", async () => {
    const vault = await api("/api/vaults", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    history.replaceState(null, "", `/?vault=${vault.id}`);
    await loadVaultById(vault.id);
  });
}

function setupOpenVault() {
  qs("open-vault-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const value = qs("open-vault-id").value.trim();
    if (!value) return;
    try {
      await loadVaultById(value);
    } catch {
      await loadVaultByShareToken(value);
    }
  });
}

function setupEventForm() {
  qs("event-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = qs("event-error");
    errorEl.hidden = true;

    let facts = {};
    const raw = qs("event-facts").value.trim();
    if (raw) {
      try {
        facts = JSON.parse(raw);
      } catch {
        errorEl.textContent = "Facts must be valid JSON.";
        errorEl.hidden = false;
        return;
      }
    }

    try {
      await api(`/api/vaults/${state.vaultId}/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_type: qs("event-type").value,
          occurred_at: qs("event-date").value,
          notes: qs("event-notes").value || null,
          facts,
        }),
      });
      qs("event-form").reset();
      await refreshData();
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    }
  });
}

function setupAcknowledge() {
  qs("acknowledge-btn").addEventListener("click", async () => {
    const vault = await api(`/api/vaults/by-share-token/${state.shareToken}/acknowledge`, { method: "POST" });
    qs("ack-status").textContent = `Acknowledged at ${vault.acknowledged_at}`;
    qs("acknowledge-btn").disabled = true;
  });
}

async function init() {
  setupCreateVault();
  setupOpenVault();
  setupEventForm();
  setupAcknowledge();
  setupPartyToggle();

  const params = new URLSearchParams(location.search);
  const shareToken = params.get("share");
  const vaultId = params.get("vault");

  try {
    if (shareToken) {
      await loadVaultByShareToken(shareToken);
    } else if (vaultId) {
      await loadVaultById(vaultId);
    }
  } catch (err) {
    console.error("Failed to load vault from URL", err);
  }
}

init();
