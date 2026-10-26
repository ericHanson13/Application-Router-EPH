// Sends each PDF in the chosen folder to the local Python server and shows the results.

const folderInput = document.getElementById("folder");
const pickedEl = document.getElementById("picked");
const runBtn = document.getElementById("run");
const summaryEl = document.getElementById("summary");
const approvalEl = document.getElementById("approval");
const groups = {
  PASS: [document.getElementById("passed"), "Passed"],
  FAIL: [document.getElementById("failed"), "Failed"],
  ERROR: [document.getElementById("errors"), "Could not review"],
  WAIT: [document.getElementById("pending"), "Reviewing"],
};

const PARALLEL_REVIEWS = 2;
let pdfs = [];
let results = [];

fetch("/api/status").then((r) => r.json()).then((s) => {
  document.getElementById("key-warning").hidden = s.api_key_set;
});

// Build a DOM element. Text always goes through textContent, so nothing from a PDF is run as HTML.
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "text") node.textContent = v;
    else node.setAttribute(k, v);
  }
  for (const c of children) if (c != null) node.append(c);
  return node;
}

// Path inside the chosen folder, without the folder's own name: "sub/permit.pdf".
function relativePath(file) {
  return file.webkitRelativePath.split("/").slice(1).join("/");
}

function pickPdfs() {
  const all = Array.from(folderInput.files);
  pdfs = all
    .filter((f) => f.name.toLowerCase().endsWith(".pdf"))
    .filter((f) => !relativePath(f).includes("/")) // only PDFs directly in the folder
    .sort((a, b) => relativePath(a).localeCompare(relativePath(b)));
  if (!all.length) {
    pickedEl.textContent = "No folder chosen yet.";
  } else {
    const folder = all[0].webkitRelativePath.split("/")[0];
    pickedEl.textContent = `${folder}: ${pdfs.length} PDF${pdfs.length === 1 ? "" : "s"} found`;
  }
  runBtn.textContent = pdfs.length ? `Review ${pdfs.length} PDF${pdfs.length === 1 ? "" : "s"}` : "Review PDFs";
  runBtn.disabled = pdfs.length === 0;
}

folderInput.addEventListener("change", pickPdfs);

runBtn.addEventListener("click", async () => {
  runBtn.disabled = true;
  folderInput.disabled = true;
  approvalEl.hidden = true;
  for (const [group] of Object.values(groups)) group.querySelectorAll(".card").forEach((c) => c.remove());
  results = new Array(pdfs.length);

  const cards = pdfs.map((f) =>
    el("div", { class: "card" },
      el("h2", {}, el("span", { text: relativePath(f) }), el("span", { class: "badge WAIT", text: "Waiting" }))));
  groups.WAIT[0].append(...cards);
  updateGroups();
  updateSummary();

  let next = 0;
  async function worker() {
    while (next < pdfs.length) {
      const i = next++;
      cards[i].querySelector(".badge").textContent = "Reviewing…";
      results[i] = await reviewOne(pdfs[i]);
      cards[i].remove();
      cards[i] = renderResult(results[i]);
      placeCard(cards[i], i);
      updateGroups();
      updateSummary();
    }
  }
  await Promise.all(Array.from({ length: PARALLEL_REVIEWS }, worker));

  renderApproval();
  runBtn.disabled = false;
  folderInput.disabled = false;
});

function status(r) {
  return r.error ? "ERROR" : r.result;
}

// Put a finished card in its group, keeping the files in name order within the group.
function placeCard(card, index) {
  card.dataset.index = index;
  const group = groups[status(results[index])][0];
  const after = Array.from(group.querySelectorAll(".card")).find((c) => Number(c.dataset.index) > index);
  group.insertBefore(card, after || null);
}

// Show each group that has cards, with its count in the heading.
function updateGroups() {
  for (const [group, title] of Object.values(groups)) {
    const n = group.querySelectorAll(".card").length;
    group.hidden = n === 0;
    group.querySelector(".group-title").textContent = `${title} (${n})`;
  }
}

// The list of passed PDFs to send on for approval. Submitting is only a mock-up for now.
function renderApproval() {
  const passed = results.filter((r) => status(r) === "PASS");
  if (!passed.length) {
    approvalEl.hidden = true;
    return;
  }
  const items = passed.map((r) => {
    const box = el("input", { type: "checkbox" });
    box.checked = true;
    const state = el("span", { class: "muted", text: "Not submitted" });
    return { r, box, state, li: el("li", {}, el("label", {}, box, `Submit for approval: ${r.file}`), state) };
  });
  const submitBtn = el("button", { class: "primary" });
  const refresh = () => {
    const n = items.filter((it) => it.box.checked && !it.box.disabled).length;
    submitBtn.textContent = n ? `Submit ${n} for approval` : "Submit for approval";
    submitBtn.disabled = n === 0;
  };
  items.forEach((it) => it.box.addEventListener("change", refresh));
  submitBtn.addEventListener("click", () => {
    const time = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    for (const it of items.filter((it) => it.box.checked && !it.box.disabled)) {
      it.box.disabled = true;
      it.state.className = "submitted";
      it.state.textContent = `✓ Submitted for approval at ${time}`;
    }
    refresh();
  });
  refresh();

  approvalEl.replaceChildren(
    el("h2", { text: "Ready for approval" }),
    el("p", { class: "muted", text: "These PDFs passed. Choose which ones to submit for approval." }),
    el("ul", { class: "approve-list" }, ...items.map((it) => it.li)),
    submitBtn,
  );
  approvalEl.hidden = false;
}

async function reviewOne(file) {
  const name = relativePath(file);
  try {
    const resp = await fetch(`/api/review?name=${encodeURIComponent(name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/pdf" },
      body: file,
    });
    const data = await resp.json();
    if (!resp.ok) return { file: name, error: data.error || resp.statusText };
    return data;
  } catch (e) {
    return { file: name, error: "Lost contact with the local server. Is it still running?" };
  }
}

function updateSummary() {
  const done = results.filter(Boolean);
  const count = (pred) => done.filter(pred).length;
  const stats = [
    ["Reviewed", `${done.length} / ${pdfs.length}`],
    ["Passed", count((r) => r.result === "PASS")],
    ["Failed", count((r) => r.result === "FAIL")],
    ["Errors", count((r) => r.error)],
  ];
  summaryEl.replaceChildren(...stats.map(([label, n]) => el("div", { class: "stat" }, el("b", { text: String(n) }), label)));
  summaryEl.hidden = false;
}

function pages(list) {
  return list.length ? ` (p${list.join(", ")})` : "";
}

function renderResult(r) {
  const st = status(r);
  const card = el("div", { class: "card" },
    el("h2", {}, el("span", { text: r.file }), el("span", { class: `badge ${st}`, text: st })));

  if (r.error) {
    card.append(el("p", { class: "error", text: r.error }));
    return card;
  }

  const o = r.overview;
  card.append(el("p", { class: "muted", text: o.summary }));

  const problems = [];
  if (!o.is_permit_application) problems.push("No permit application form was found in this PDF.");
  for (const f of o.form_fields.filter((f) => f.required && f.status !== "filled")) {
    problems.push(`Form field "${f.label}" (page ${f.page}) is ${f.status}${f.note ? `: ${f.note}` : ""}`);
  }
  for (const a of o.required_attachments.filter((a) => a.applies !== "no" && !a.satisfied)) {
    problems.push(`Missing attachment: ${a.name}. ${a.evidence}`);
  }
  if (problems.length) {
    card.append(el("div", { class: "missing" },
      el("h3", { text: "What's missing" }),
      el("ul", {}, ...problems.map((p) => el("li", { text: p })))));
  } else {
    card.append(el("p", { class: "all-good", text: "The form is complete and every required attachment is included." }));
  }

  // Failed cards show how many items are correct out of the total, e.g. "Form fields (25/30)".
  const needed = o.required_attachments.filter((a) => a.applies !== "no");
  const requiredFields = o.form_fields.filter((f) => f.required);
  const tally = (good, total) => (st === "FAIL" ? ` (${good}/${total})` : "");

  card.append(details(`Required attachments${tally(needed.filter((a) => a.satisfied).length, needed.length)}`, table(
    ["Attachment", "Status", "Found"],
    o.required_attachments.map((a) => {
      const st = a.applies === "no" ? "Not needed" : a.satisfied ? "Attached" : "Missing";
      const cls = a.applies === "no" ? "" : a.satisfied ? "ok" : "no";
      const note = a.condition ? `Only ${a.condition}. ${a.applies_reason}` : a.evidence;
      return [a.name, [st, cls], note + pages(a.found_on_pages)];
    }))));

  card.append(details(`Form fields${tally(requiredFields.filter((f) => f.status === "filled").length, requiredFields.length)}`, table(
    ["Field", "Page", "Value", "Status"],
    o.form_fields.map((f) => {
      const cls = f.status === "filled" ? "ok" : f.required ? "no" : "";
      const label = f.status === "filled" ? "Filled" : f.required ? f.status : `${f.status} (optional)`;
      return [f.label, String(f.page), f.value || "", [label + (f.note ? ` · ${f.note}` : ""), cls]];
    }))));

  card.append(details("Sections of the PDF", table(
    ["Pages", "Type", "Title"],
    o.sections.map((s) => [
      s.start_page === s.end_page ? `${s.start_page}` : `${s.start_page}-${s.end_page}`,
      s.kind.replace("_", " "),
      s.title,
    ]))));
  return card;
}

function details(title, body) {
  return el("details", {}, el("summary", { text: title }), body);
}

// Rows are arrays of cells; a cell is text, or [text, cssClass].
function table(headers, rows) {
  return el("table", {},
    el("tr", {}, ...headers.map((h) => el("th", { text: h }))),
    ...rows.map((row) => el("tr", {}, ...row.map((cell) => {
      const [text, cls] = Array.isArray(cell) ? cell : [cell, ""];
      return el("td", cls ? { class: cls, text } : { text });
    }))));
}
