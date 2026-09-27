/* Check your lease — standalone page JS.
 *
 * Uploads a file to POST /api/lease-check, renders findings the same way
 * the vault view does, then forgets everything. No vault, no database,
 * no sign-in.
 */

const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;

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

const FACT_LABELS = {
  monthly_rent: "Monthly rent",
  deposit_amount: "Security deposit",
  deposit_months: "Deposit (months' rent)",
  tenancy_year: "Tenancy year",
  lease_start_date: "Lease starts",
  lease_end_date: "Lease ends",
  lease_term_months: "Lease term (months)",
  property_address: "Address",
  apartment_number: "Unit",
  landlord_name: "Landlord / management",
  deposit_bank_disclosed: "Escrow bank disclosed",
  certificate_of_rental_suitability_provided: "Certificate of Rental Suitability",
  partners_good_housing_provided: "Partners in Good Housing handbook",
  landlord_rental_license_valid: "Rental licence valid",
  clause_waives_deposit_rights: "Deposit waiver clause",
  renter_insurance_required: "Renter's insurance required",
  insurance_minimum_coverage: "Insurance minimum coverage",
  late_fee_amount: "Late fee",
  late_fee_grace_days: "Late fee grace period (days)",
  pet_deposit: "Pet deposit",
  buyout_amount: "Buy-out fee",
  buyout_notice_days: "Buy-out notice (days)",
  utilities_included: "Landlord pays utilities",
  utilities_tenant_pays: "Tenant pays utilities",
  prorated_rent: "Prorated first month",
  move_out_notice_days: "Move-out notice (days)",
  lead_paint_disclosure: "Lead paint disclosure",
  building_year_built: "Year built",
  bed_bug_disclosure_provided: "Bed bug disclosure",
  application_fee: "Application fee",
  admin_fee: "Admin / move-in fee",
  rent_concession_amount: "Rent concession",
  rent_concession_description: "Concession details",
};

function formatFactValue(key, value) {
  if (value === null || value === undefined) return null;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number" && key.includes("amount") || key.includes("rent") || key.includes("fee") || key.includes("deposit") || key.includes("coverage") || key.includes("concession")) {
    return "$" + value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return String(value);
}

function renderFindings(adj) {
  const items = [];

  for (const f of adj.flagged) {
    items.push(
      el("li", { class: "finding flagged" }, [
        el("span", { class: "finding-icon", text: "!" }),
        el("div", {}, [
          el("strong", { text: f.message || f.requirement || f.statute_id }),
          el("p", { class: "cite", text: f.citation }),
          f.detail ? el("p", { class: "hint", text: f.detail }) : null,
        ]),
      ])
    );
  }

  for (const p of adj.passed) {
    items.push(
      el("li", { class: "finding passed" }, [
        el("span", { class: "finding-icon finding-ok", text: "✓" }),
        el("div", {}, [
          el("strong", { text: "No issue found" }),
          el("p", { text: p.requirement || p.statute_id }),
          el("p", { class: "cite", text: p.citation }),
        ]),
      ])
    );
  }

  for (const u of adj.unknown) {
    items.push(
      el("li", { class: "finding unknown" }, [
        el("span", { class: "finding-icon finding-unknown", text: "?" }),
        el("div", {}, [
          el("strong", { text: "Needs more information" }),
          el("p", { text: u.requirement || u.statute_id }),
          el("p", { class: "cite", text: u.citation }),
          u.next_step ? el("p", { class: "hint", text: u.next_step }) : null,
        ]),
      ])
    );
  }

  if (!items.length) {
    items.push(el("li", { class: "empty", text: "No rules could be checked against this document." }));
  }

  $("findings-list").replaceChildren(...items);
}

function renderFacts(facts) {
  const rows = [];
  const ordered = Object.keys(FACT_LABELS);
  for (const key of ordered) {
    const val = formatFactValue(key, facts[key]);
    if (val === null) continue;
    rows.push(
      el("div", { class: "fact-row", style: "display:flex;justify-content:space-between;padding:0.4rem 0;border-bottom:1px solid var(--border);" }, [
        el("span", { text: FACT_LABELS[key], style: "color:var(--ink-faint);font-size:0.88rem;" }),
        el("span", { text: val, style: "font-weight:600;font-size:0.88rem;" }),
      ])
    );
  }

  // Show any extra facts not in FACT_LABELS
  for (const [key, value] of Object.entries(facts)) {
    if (ordered.includes(key)) continue;
    const val = formatFactValue(key, value);
    if (val === null) continue;
    rows.push(
      el("div", { class: "fact-row", style: "display:flex;justify-content:space-between;padding:0.4rem 0;border-bottom:1px solid var(--border);" }, [
        el("span", { text: key.replace(/_/g, " "), style: "color:var(--ink-faint);font-size:0.88rem;" }),
        el("span", { text: val, style: "font-weight:600;font-size:0.88rem;" }),
      ])
    );
  }

  if (!rows.length) {
    rows.push(el("p", { class: "empty", text: "No facts were extracted from this document." }));
  }

  $("facts-summary").replaceChildren(...rows);
}

function showSection(id) {
  $("upload-section").hidden = id !== "upload";
  $("loading-section").hidden = id !== "loading";
  $("results-section").hidden = id !== "results";
}

$("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = $("upload-error");
  errorEl.hidden = true;
  $("general-error").hidden = true;

  const file = $("lease-file").files[0];
  if (!file) return;

  if (file.size > MAX_UPLOAD_BYTES) {
    errorEl.textContent = `This file is ${(file.size / 1024 / 1024).toFixed(1)}MB. The limit is ${MAX_UPLOAD_BYTES / 1024 / 1024}MB.`;
    errorEl.hidden = false;
    return;
  }

  showSection("loading");

  try {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("/api/lease-check", { method: "POST", body: formData });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `${res.status} ${res.statusText}`);
    }

    const data = await res.json();

    if (!data.adjudication) {
      // Extraction failed — show the message
      const msg = (data.extraction && data.extraction.message) || "Could not read this document.";
      $("general-error").textContent = msg;
      $("general-error").hidden = false;
      showSection("upload");
      return;
    }

    const counts = data.adjudication.counts;
    if (counts.flagged > 0) {
      $("results-heading").textContent = `${counts.flagged} issue${counts.flagged === 1 ? "" : "s"} found, ${counts.passed} passed, ${counts.unknown} need more info`;
    } else if (counts.passed > 0) {
      $("results-heading").textContent = `No issues found across ${counts.checked} rules checked`;
    } else {
      $("results-heading").textContent = `${counts.checked} rules checked`;
    }

    renderFindings(data.adjudication);
    renderFacts(data.facts);
    showSection("results");
  } catch (err) {
    $("general-error").textContent = err.message;
    $("general-error").hidden = false;
    showSection("upload");
  }
});
