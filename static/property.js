/* The public address page.
 *
 * Anyone can load this for any Philadelphia address, signed in or not,
 * whether or not a record exists here. That is the point: the history
 * belongs to the property, so the person deciding whether to move in has to
 * be able to read it.
 *
 * Everything rendered here arrives already de-identified from
 * app/routers/properties.py — the server decides what may cross onto a public
 * page, not this file. Built with createElement/textContent throughout: the
 * City's violation titles and a resident's address are both third-party text
 * on a page other people load.
 */

const $ = (id) => document.getElementById(id);

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2).toLowerCase(), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined) continue;
    node.append(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})/;

/* Same rule as the vault app: a calendar date is not an instant, and parsing
 * "2026-08-31" as UTC midnight renders it a day early everywhere west of UTC. */
function formatDate(value) {
  if (!value) return "—";
  const raw = String(value);
  const parts = DATE_ONLY.exec(raw);
  const date = parts
    ? new Date(Number(parts[1]), Number(parts[2]) - 1, Number(parts[3]))
    : new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function currentAddress() {
  return new URLSearchParams(location.search).get("a") || "";
}

function goToAddress(address) {
  location.href = `/property/?a=${encodeURIComponent(address)}`;
}

function renderCity(city) {
  const summary = $("city-summary");
  const detail = $("city-detail");

  // An outage and a clean record must never look the same. The server marks
  // which one this is; the page has to keep them apart visually too.
  const tone = city.unavailable
    ? "banner banner-caution"
    : city.licences.some((l) => String(l.status).toUpperCase() === "ACTIVE")
      ? "banner"
      : "banner banner-caution";

  summary.replaceChildren(
    el("div", { class: tone }, [
      el("strong", { text: city.licence_summary }),
      city.open_violation_count
        ? ` ${city.open_violation_count} open code violation${city.open_violation_count === 1 ? "" : "s"} on record.`
        : city.found
          ? " No open code violations on record."
          : "",
    ])
  );

  const blocks = [];

  if (city.licences.length) {
    blocks.push(
      el("h3", { text: "Rental licences", style: "margin-top:1.5rem" }),
      el("div", { class: "table-wrap" }, [
        el("table", {}, [
          el("thead", {}, el("tr", {}, [
            el("th", { text: "Type" }), el("th", { text: "Status" }),
            el("th", { text: "Expires" }), el("th", { text: "On record as" }),
          ])),
          el("tbody", {}, city.licences.map((l) =>
            el("tr", {}, [
              el("td", { text: l.type || "—" }),
              el("td", {}, el("span", {
                class: String(l.status).toUpperCase() === "ACTIVE" ? "badge" : "doc-unread",
                text: l.status || "—",
              })),
              el("td", { class: "num", text: formatDate(l.expires) }),
              el("td", {}, el("span", { class: "cite", text: l.address || "—" })),
            ])
          )),
        ]),
      ])
    );
  }

  if (city.open_violations.length) {
    blocks.push(
      el("h3", { text: "Open violations", style: "margin-top:1.5rem" }),
      el("div", { class: "table-wrap" }, [
        el("table", {}, [
          el("thead", {}, el("tr", {}, [
            el("th", { text: "Date" }), el("th", { text: "Violation" }), el("th", { text: "Status" }),
          ])),
          el("tbody", {}, city.open_violations.map((v) =>
            el("tr", {}, [
              el("td", { class: "num", text: formatDate(v.date) }),
              el("td", { text: v.title || "—" }),
              el("td", { text: v.status || "—" }),
            ])
          )),
        ]),
      ])
    );
  }

  if (city.note) {
    blocks.push(el("p", { class: "home-note", style: "margin-top:1rem", text: city.note }));
  }

  detail.replaceChildren(...blocks);
  $("city-source").textContent = `Source: ${city.source}`;
  $("city-section").hidden = false;
}

function renderHistory(data) {
  const section = $("history-section");
  const tbody = $("history-table").querySelector("tbody");

  if (data.history_withheld) {
    $("history-intro").textContent = data.history_note || "";
    tbody.replaceChildren(
      el("tr", {}, el("td", { colspan: "6", class: "empty", text: "Nothing shown yet." }))
    );
    section.hidden = false;
    return;
  }
  if (!data.history.length) {
    section.hidden = true;
    return;
  }

  $("history-intro").textContent =
    "Repairs residents have recorded here. Names, units and descriptions are left out on purpose.";
  tbody.replaceChildren(
    ...data.history.map((h) =>
      el("tr", {}, [
        el("td", { class: "num", text: formatDate(h.reported) }),
        el("td", {}, [
          el("span", { text: String(h.category).replace(/_/g, " ") }),
          h.affected_essential_service
            ? el("span", { class: "doc-unread", text: "essential service" })
            : null,
        ]),
        el("td", { text: h.urgency }),
        el("td", { class: "num", text: formatDate(h.work_started) }),
        el("td", { class: "num", text: formatDate(h.resolved) }),
        el("td", { class: "num", text: h.days_to_resolve === null ? "—" : String(h.days_to_resolve) }),
      ])
    )
  );
  section.hidden = false;
}

async function load() {
  const address = currentAddress();
  if (!address) {
    location.href = "/#start";
    return;
  }
  $("address-input").value = address;

  let data;
  try {
    const res = await fetch(`/api/properties/lookup?address=${encodeURIComponent(address)}`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `${res.status} ${res.statusText}`);
    }
    data = await res.json();
  } catch (err) {
    $("address-title").textContent = address;
    $("lookup-error").textContent = `Couldn't look that address up: ${err.message}`;
    $("lookup-error").hidden = false;
    return;
  }

  $("address-title").textContent = data.address.display || data.address.normalized;
  $("address-sub").textContent = data.address.known_to_us
    ? "Someone keeps a record at this address."
    : "No one keeps a record here yet.";

  renderCity(data.city_record);
  renderHistory(data);
  $("start-section").hidden = false;
}

function setup() {
  $("address-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const value = $("address-input").value.trim();
    if (value) goToAddress(value);
  });

  $("create-record-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorEl = $("create-error");
    const progressEl = $("create-progress");
    errorEl.hidden = true;
    progressEl.hidden = true;
    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;

    const file = $("record-lease").files[0];
    const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;

    if (file && file.size > MAX_UPLOAD_BYTES) {
      errorEl.textContent = `${file.name} is ${(file.size / 1024 / 1024).toFixed(1)} MB. The limit is 4 MB.`;
      errorEl.hidden = false;
      btn.disabled = false;
      return;
    }

    try {
      progressEl.textContent = "Creating your record…";
      progressEl.hidden = false;

      const res = await fetch("/api/vaults", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          address: currentAddress(),
          unit: $("record-unit").value.trim() || null,
          zip_code: $("record-zip").value.trim() || null,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        let detail = body.detail;
        if (Array.isArray(detail)) detail = detail.map((d) => d.msg || String(d)).join("; ");
        throw new Error(detail || `${res.status} ${res.statusText}`);
      }
      const vault = await res.json();

      if (file) {
        progressEl.textContent = `Uploading ${file.name}…`;
        const formData = new FormData();
        formData.append("file", file);
        formData.append("event_type", "document_upload");
        formData.append("occurred_at", new Date().toISOString().slice(0, 10));
        const manifest = JSON.stringify([file.name]);
        formData.append("manifest", manifest);
        formData.append("index", "0");

        const uploadRes = await fetch(`/api/vaults/${vault.id}/documents`, {
          method: "POST",
          body: formData,
        });
        if (uploadRes.ok) {
          progressEl.textContent = "Reading your lease…";
        }
      }

      location.href = `/?vault=${encodeURIComponent(vault.id)}`;
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
      progressEl.hidden = true;
      btn.disabled = false;
    }
  });

  load();
}

setup();
