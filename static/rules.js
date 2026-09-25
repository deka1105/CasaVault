/* The "What we check" page.
 *
 * Loads the real rule list from GET /api/statutes — the same table the app
 * adjudicates against — so this page cannot drift out of date relative to
 * what the product actually does. Draft rules never reach here: the API
 * filters them server-side (app/statutes_loader.py), which is the only place
 * that decision should live.
 *
 * Standalone rather than part of app.js: this page has no vault, no sign-in
 * and no forms, and app.js would throw looking for elements it doesn't have.
 */

const $ = (id) => document.getElementById(id);

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined) continue;
    node.append(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

/* Rules whose citation is a Philadelphia one belong under licensing; the rest
 * are the Pennsylvania deposit rules. Grouped by citation rather than by a
 * hand-kept list of ids, so a new rule lands in the right place on its own. */
function isPhiladelphia(rule) {
  return /Phila/i.test(rule.citation || "");
}

/* A clock rule (the deposit-return deadline) keeps a {deadline} placeholder in
 * its wording that's only filled once your move-out date is known. Show the
 * plain requirement instead of leaking the template at the reader. */
function describe(rule) {
  if (rule.requirement) return rule.requirement;
  if (rule.clock) {
    const parts = [`Applies from: ${rule.clock.replace(/_/g, " ")}`];
    if (rule.requires) parts.push(`Only if: ${rule.requires}`);
    return parts.join(" · ");
  }
  const framing = (rule.party_framing && rule.party_framing.tenant) || rule.detail || "";
  return framing.replace(/\{[^}]*\}/g, "the deadline");
}

function ruleCard(rule) {
  return el("li", { class: "statute" }, [
    el("div", { class: "statute-head" }, [
      el("span", { class: "cite", text: rule.citation }),
      rule.severity ? el("span", { class: "statute-id", text: rule.severity }) : null,
    ]),
    el("p", { text: describe(rule) }),
    // The longer legal explanation, folded away so the page stays scannable.
    rule.detail && rule.detail !== rule.requirement
      ? el("details", { class: "doc-more" }, [
          el("summary", {}, "More detail"),
          el("p", { text: rule.detail }),
        ])
      : null,
  ]);
}

async function render() {
  let rules;
  try {
    const res = await fetch("/api/statutes");
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    rules = await res.json();
  } catch (err) {
    const box = $("rules-error");
    box.textContent = `Couldn't load the rule list just now (${err.message}). Please refresh.`;
    box.hidden = false;
    return;
  }

  const philly = rules.filter(isPhiladelphia);
  const deposit = rules.filter((r) => !isPhiladelphia(r));

  $("rules-deposit").replaceChildren(...deposit.map(ruleCard));
  $("rules-philly").replaceChildren(...philly.map(ruleCard));
  $("rule-count").textContent =
    `${rules.length} rules, grouped below. Each one shows the law it comes from.`;
}

render();
