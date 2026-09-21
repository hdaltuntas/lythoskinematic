"use strict";
/* Lythos Kinematic — tarayıcı arayüzü.
 *
 * Formlar sunucunun verdiği şemadan üretilir: alan anahtarları, etiketler,
 * birimler ve varsayılanlar Python tarafında bir kez tanımlanır. Böylece
 * arayüzde ikinci bir etiket kopyası ve çevrilecek ikinci bir metin kümesi
 * oluşmaz; dil değişince şema yeniden alınır ve formlar yeniden çizilir.
 *
 * Girdilerin tamamı tek bir düz nesnede (VALUES) tutulur; kaydedilen JSON da
 * odur, sunucuya giden de.
 */

/* --------------------------------------------------------------- durum */
const S = {
  meta: null,            // /api/meta yanıtı
  values: {},            // tüm alanların güncel değerleri
  module: "screening",   // screening | equilibrium
  view: { screening: "stereonet", equilibrium: "results" },
  screening: null,       // son tarama sonucu
  reportHtml: "",
  equilibrium: null,     // son limit denge sonucu
  boltMatrix: null,
  boltCheck: null,
  selectedRow: 0,
  poll: null,
  plotVersion: 0,        // görsellerin önbelleğe takılmaması için
};

const $ = (id) => document.getElementById(id);
const el = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) node.setAttribute(k, v);
  }
  for (const c of children) if (c) node.append(c);
  return node;
};
const T = (key) => (S.meta && S.meta.strings[key]) || key;

/* ------------------------------------------------------------- sunucu */
async function api(path, body) {
  const options = body === undefined
    ? {}
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const response = await fetch(path, options);
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

function status(message, isError = false) {
  $("statusMsg").textContent = message || "";
  $("statusBar").classList.toggle("error", !!isError);
}

function busy(on, note) {
  $("progressBar").style.width = on ? "65%" : "0";
  if (note !== undefined) status(note);
  for (const id of ["btnScreen", "btnAnalyse", "btnRequired", "btnBolts", "btnBoltCheck", "btnReport"]) {
    const node = $(id);
    if (node) node.disabled = on;
  }
}

/* -------------------------------------------------------- form üretimi */
function fieldNode(field) {
  const id = "f_" + field.key;
  const value = S.values[field.key];

  if (field.kind === "check") {
    const input = el("input", {
      type: "checkbox", id,
      onchange: (e) => { S.values[field.key] = e.target.checked; },
    });
    input.checked = !!value;
    return el("div", { class: "field check" }, input, el("label", { for: id, text: field.label }));
  }

  let input;
  if (field.kind === "select") {
    input = el("select", { id, onchange: (e) => { S.values[field.key] = e.target.value; } });
    for (const option of field.options || []) {
      input.append(el("option", { value: option.value, text: option.label }));
    }
    input.value = value ?? (field.options && field.options[0] && field.options[0].value);
  } else if (field.kind === "text") {
    input = el("input", {
      type: "text", id, placeholder: field.placeholder || "",
      oninput: (e) => { S.values[field.key] = e.target.value; },
    });
    input.value = value ?? "";
  } else {
    input = el("input", {
      type: "number", id, placeholder: field.placeholder || "",
      step: field.step || (field.decimals === 0 ? 1 : Math.pow(10, -(field.decimals ?? 2))),
      min: field.min, max: field.max,
      oninput: (e) => {
        const raw = e.target.value.trim();
        S.values[field.key] = raw === "" ? null : parseFloat(raw);
      },
    });
    input.value = value === null || value === undefined ? "" : value;
  }

  const label = el("label", { for: id }, document.createTextNode(field.label));
  if (field.unit) label.append(el("span", { class: "unit", text: field.unit }));
  return el("div", { class: "field" }, label, input);
}

function groupNode(group) {
  const box = el("fieldset", {}, el("legend", { text: group.title }));
  for (const field of group.fields) box.append(fieldNode(field));
  if (group.note) box.append(el("div", { class: "note", html: group.note }));
  return box;
}

function renderForm(host, groups) {
  host.replaceChildren(...groups.map(groupNode));
}

/* ------------------------------------------------------ süreksizlik tablosu */
function renderJoints() {
  const columns = S.meta.schema.screening.columns;
  $("jointHead").replaceChildren(...columns.map((c) => el("th", { text: c.label })));

  const body = $("jointBody");
  body.replaceChildren();
  S.values.joints.forEach((row, index) => {
    const tr = el("tr", {
      class: index === S.selectedRow ? "selected" : "",
      onclick: () => { S.selectedRow = index; renderJoints(); },
    });
    for (const column of columns) {
      const input = el("input", {
        type: column.kind === "number" ? "number" : "text",
        step: "0.1",
        oninput: (e) => {
          const raw = e.target.value;
          row[column.key] = column.kind === "number" ? (raw === "" ? null : parseFloat(raw)) : raw;
        },
      });
      input.value = row[column.key] ?? "";
      tr.append(el("td", {}, input));
    }
    body.append(tr);
  });
}

/* ------------------------------------------------------------ görünümler */
const VIEWS = {
  screening: [
    ["stereonet", "view_stereonet"],
    ["report", "view_report"],
    ["probability", "view_probability"],
  ],
  equilibrium: [
    ["results", "view_results"],
    ["plot", "view_plot"],
    ["stereonet", "view_stereonet"],
    ["table", "view_table"],
    ["bolts", "view_bolts"],
  ],
};

function renderTabs() {
  const tabs = VIEWS[S.module].filter(
    ([key]) => !(S.module === "equilibrium" && key === "stereonet" &&
                 !(S.equilibrium && S.equilibrium.figures.includes("stereonet"))));
  $("viewTabs").replaceChildren(...tabs.map(([key, label]) =>
    el("button", {
      text: T(label),
      class: S.view[S.module] === key ? "active" : "",
      onclick: () => { S.view[S.module] = key; renderTabs(); renderView(); },
    })));
  if (!tabs.some(([key]) => key === S.view[S.module])) {
    S.view[S.module] = tabs[0][0];
    renderTabs();
  }
}

function placeholder(text) {
  return el("div", { class: "placeholder", text });
}

function plotImage(target, kind) {
  return el("img", { src: `/api/plot?target=${target}&kind=${kind}&v=${S.plotVersion}`, alt: target });
}

function dataTable(columns, rows, options = {}) {
  const head = el("tr", {}, ...columns.map((c) => el("th", { text: c })));
  const body = rows.map((row) => {
    const tr = el("tr", { class: options.criticalRows && options.criticalRows(row) ? "critical" : "" });
    row.forEach((cell, i) => {
      const td = el("td", {});
      if (options.colorColumn === i && options.colors && options.colors[cell]) {
        td.style.background = options.colors[cell];
        td.style.color = "#1b1f24";
      }
      td.textContent = cell;
      tr.append(td);
    });
    return tr;
  });
  return el("table", { class: "data" }, el("thead", {}, head), el("tbody", {}, ...body));
}

function renderView() {
  const view = $("view");
  const which = S.view[S.module];

  if (S.module === "screening") {
    if (!S.screening) return view.replaceChildren(placeholder(T("no_screening")));
    if (which === "stereonet") return view.replaceChildren(plotImage("screening", "main"));
    if (which === "report") {
      return view.replaceChildren(el("div", { class: "doc", html: S.reportHtml }));
    }
    return view.replaceChildren(el("div", { class: "doc", html: S.probabilityHtml || "" }));
  }

  if (!S.equilibrium) return view.replaceChildren(placeholder(T("no_results")));
  const result = S.equilibrium;

  if (which === "plot") return view.replaceChildren(plotImage("equilibrium", "main"));
  if (which === "stereonet") return view.replaceChildren(plotImage("equilibrium", "stereonet"));

  if (which === "table") {
    const table = result.table;
    return view.replaceChildren(dataTable(table.columns, table.rows, {
      colorColumn: table.color_column, colors: table.colors,
    }));
  }

  if (which === "bolts") {
    if (S.boltCheck || S.boltMatrix) return view.replaceChildren(boltPane());
    return view.replaceChildren(placeholder(T("no_results")));
  }

  // sonuçlar
  const parts = [kpiRow(result)];
  if (result.warnings.length) {
    parts.push(el("div", { class: "warnings" },
      el("h3", { text: T("warnings") }),
      el("ul", {}, ...result.warnings.map((w) => el("li", { text: w })))));
  }
  parts.push(el("pre", { text: result.summary }));
  view.replaceChildren(...parts);
}

function kpiRow(result) {
  const target = targetFs();
  const good = result.fs !== null && result.fs !== "inf" ? result.fs >= target : true;
  return el("div", { class: "kpi" },
    el("div", { class: "card " + (good ? "good" : "bad") },
      el("small", { text: "FS" }), el("b", { text: result.fs_text })),
    el("div", { class: "card" },
      el("small", { text: T("mode") }), el("b", { text: T("mode_" + result.mode) })));
}

function targetFs() {
  const key = { wedge: "FS_target", planar: "p_FS", toppling: "t_FS" }[S.values.mode_eq || currentMode()];
  return parseFloat(S.values[key]) || 1.5;
}

function boltPane() {
  const parts = [];
  if (S.boltMatrix) {
    const { lengths, rows, best } = S.boltMatrix;
    const head = el("tr", {}, el("th", { text: `${T("spacing")} \\ ${T("length")}` }),
      ...lengths.map((L) => el("th", { text: String(L) })));
    const body = rows.map((row) => el("tr", {},
      el("th", { text: row.spacing.toFixed(2) }),
      ...row.cells.map((cell, i) => {
        const isBest = best && best.spacing === row.spacing && best.length === lengths[i];
        const text = cell.fs === null ? "—" : (cell.fs === "inf" ? "∞" : cell.fs.toFixed(2));
        return el("td", {
          class: (cell.ok ? "ok" : "no") + (isBest ? " best" : ""),
          text: text + (cell.ok ? "*" : ""),
          onclick: () => {
            S.values.b_s_sel = row.spacing;
            S.values.b_L_sel = lengths[i];
            runBoltCheck();
          },
        });
      })));
    parts.push(el("table", { class: "matrix" }, el("thead", {}, head), el("tbody", {}, ...body)));
    parts.push(el("div", { class: "note", text: T("target_met") }));
    if (best) {
      parts.push(el("div", { class: "kpi" }, el("div", { class: "card good" },
        el("small", { text: T("recommendation") }),
        el("b", { text: `s = ${best.spacing.toFixed(2)} m · L = ${best.length} m` }))));
    }
    parts.push(el("pre", { text: S.boltMatrix.pattern }));
  }
  if (S.boltCheck) {
    parts.unshift(el("div", { class: "kpi" },
      el("div", { class: "card " + (S.boltCheck.adequate ? "good" : "bad") },
        el("small", { text: T("bolt_check") }), el("b", { text: S.boltCheck.verdict })),
      el("div", { class: "card" }, el("small", { text: "FS" }),
        el("b", { text: S.boltCheck.fs === null ? "—" : Number(S.boltCheck.fs).toFixed(3) }))));
    parts.push(dataTable(S.boltCheck.table.columns, S.boltCheck.table.rows));
    parts.push(el("pre", { text: S.boltCheck.summary }));
  }
  return el("div", {}, ...parts);
}

/* ------------------------------------------------------------- eylemler */
function currentMode() {
  return $("mode").value || "wedge";
}

async function runScreening() {
  busy(true, T("running"));
  try {
    const data = await api("/api/screen", { values: S.values });
    if (!data.ok) throw new Error(data.error);
    S.screening = data.result;
    S.reportHtml = data.report_html;
    S.plotVersion += 1;
    S.view.screening = S.view.screening === "probability" ? "probability" : "stereonet";
    renderTabs(); renderView();
    status(`${data.result.n_critical} / ${data.result.n_items} ${T("critical_of")} — ${data.result.summary}`);
    startPolling();
  } catch (error) {
    status(`${T("error")}: ${error.message}`, true);
  } finally {
    busy(false);
  }
}

async function runHandoff() {
  try {
    const data = await api("/api/handoff", {});
    if (!data.ok) throw new Error(data.error);
    Object.assign(S.values, data.values);
    $("mode").value = data.mode;
    switchModule("equilibrium");
    renderEquilibriumForm();
    status(data.message);
    await runEquilibrium();
  } catch (error) {
    status(`${T("error")}: ${error.message}`, true);
  }
}

async function runEquilibrium() {
  busy(true, T("running"));
  try {
    const data = await api("/api/equilibrium", { mode: currentMode(), values: S.values });
    S.equilibrium = data;
    S.boltMatrix = S.boltCheck = null;
    S.plotVersion += 1;
    renderTabs(); renderView();
    status(`FS = ${data.fs_text}`);
  } catch (error) {
    S.equilibrium = null;
    renderView();
    status(`${T("error")}: ${error.message}`, true);
  } finally {
    busy(false);
  }
}

async function runRequired() {
  busy(true, T("running"));
  try {
    const data = await api("/api/required", { mode: currentMode(), values: S.values });
    if (!data.ok) throw new Error(data.error);
    Object.assign(S.values, data.changed || {});
    renderEquilibriumForm();
    status(data.message);
    if (Object.keys(data.changed || {}).length) await runEquilibrium();
  } catch (error) {
    status(`${T("error")}: ${error.message}`, true);
  } finally {
    busy(false);
  }
}

async function runBolts() {
  busy(true, T("running"));
  try {
    const data = await api("/api/bolts", { mode: currentMode(), values: S.values });
    if (!data.ok) throw new Error(data.error);
    S.view.equilibrium = "bolts";
    renderTabs();
    startPolling();
  } catch (error) {
    busy(false);
    status(`${T("error")}: ${error.message}`, true);
  }
}

async function runBoltCheck() {
  busy(true, T("running"));
  try {
    const data = await api("/api/bolt-check", {
      mode: currentMode(), values: S.values,
      spacing: parseFloat(S.values.b_s_sel) || parseFloat(S.values.b_smin) || 1.0,
      length: parseFloat(S.values.b_L_sel) || 6.0,
    });
    if (!data.ok) throw new Error(data.error);
    S.boltCheck = data;
    S.view.equilibrium = "bolts";
    renderTabs(); renderView();
    status(`${data.verdict} — FS = ${Number(data.fs).toFixed(3)} (${data.utilisation}%)`);
  } catch (error) {
    status(`${T("error")}: ${error.message}`, true);
  } finally {
    busy(false);
  }
}

async function downloadReport() {
  busy(true, T("running"));
  try {
    const response = await fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target: S.module }),
    });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || response.statusText);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = el("a", { href: url, download: `lythos_${S.module}.pdf` });
    document.body.append(link); link.click(); link.remove();
    URL.revokeObjectURL(url);
    status(T("report") + " ✓");
  } catch (error) {
    status(`${T("error")}: ${error.message}`, true);
  } finally {
    busy(false);
  }
}

/* --------------------------------------------------- arka plan yoklaması */
function startPolling() {
  if (S.poll) return;
  S.poll = setInterval(async () => {
    let state;
    try {
      state = await api("/api/state");
    } catch {
      return;
    }
    S.probabilityHtml = state.probability_html;
    if (S.module === "screening" && S.view.screening === "probability") renderView();

    if (state.job === "running") return;
    clearInterval(S.poll); S.poll = null;
    busy(false);

    if (state.job === "error") {
      status(`${T("error")}: ${state.error}`, true);
      return;
    }
    if (state.kind === "bolts" && state.has_bolt_matrix) {
      S.boltMatrix = await api("/api/bolts");
      if (S.boltMatrix.best) {
        S.values.b_s_sel = S.boltMatrix.best.spacing;
        S.values.b_L_sel = S.boltMatrix.best.length;
      }
      renderView();
    }
    if (state.note) status(state.note);
  }, 400);
}

/* ------------------------------------------------------------- yerleşim */
function switchModule(name) {
  S.module = name;
  $("paneScreeningInputs").hidden = name !== "screening";
  $("paneEquilibriumInputs").hidden = name !== "equilibrium";
  for (const button of document.querySelectorAll("nav.modules button")) {
    button.classList.toggle("active", button.dataset.module === name);
  }
  renderTabs(); renderView();
}

function renderEquilibriumForm() {
  const mode = currentMode();
  const groups = S.meta.schema.equilibrium[mode].groups
    .concat(mode === "toppling" ? [] : S.meta.schema.bolts.groups)
    .concat(S.meta.schema.report.groups);
  renderForm($("equilibriumForm"), groups);
  $("btnBolts").disabled = mode === "toppling";
  $("btnBoltCheck").disabled = mode === "toppling";
}

function applyMeta(meta) {
  S.meta = meta;
  document.documentElement.lang = meta.language.toLowerCase();

  $("tagline").textContent = T("tagline");
  $("lblLanguage").textContent = T("language");
  $("btnOpen").textContent = T("open");
  $("btnSave").textContent = T("save");
  $("btnReport").textContent = T("report");
  $("tabScreening").textContent = T("tab_screening");
  $("tabEquilibrium").textContent = T("tab_equilibrium");
  $("lblJoints").textContent = T("joints");
  $("btnAddRow").textContent = T("add_row");
  $("btnDelRow").textContent = T("del_row");
  $("btnScreen").textContent = T("run_screening");
  $("btnHandoff").textContent = T("handoff");
  $("btnHandoff").title = T("handoff_tip");
  $("lblMode").textContent = T("mode");
  $("btnAnalyse").textContent = T("run_equilibrium");
  $("btnRequired").textContent = T("required");
  $("btnBolts").textContent = T("bolts");
  $("btnBoltCheck").textContent = T("bolt_check");

  const language = $("language");
  language.replaceChildren(...meta.languages.map((code) =>
    el("option", { value: code, text: code })));
  language.value = meta.language;

  const mode = $("mode");
  const previous = mode.value;
  mode.replaceChildren(...["wedge", "planar", "toppling"].map((key) =>
    el("option", { value: key, text: T("mode_" + key) })));
  mode.value = previous || "wedge";

  renderForm($("screeningForm"), meta.schema.screening.groups);
  renderJoints();
  renderEquilibriumForm();
  renderTabs(); renderView();
  status(T("ready"));
}

async function setLanguage(code) {
  const meta = await api("/api/language", { lang: code });
  applyMeta(meta);
  if (S.screening) await runScreening();
  if (S.equilibrium) await runEquilibrium();
}

/* ------------------------------------------------------------ kaydet / aç */
function saveInputs() {
  const blob = new Blob([JSON.stringify({ format: "lythos-kinematic", version: 1, ...S.values }, null, 2)],
    { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = el("a", { href: url, download: "lythos_inputs.json" });
  document.body.append(link); link.click(); link.remove();
  URL.revokeObjectURL(url);
  status(T("saved"));
}

function openInputs(file) {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      if (!data || typeof data !== "object") throw new Error(T("bad_file"));
      Object.assign(S.values, data);
      if (!Array.isArray(S.values.joints)) S.values.joints = S.meta.schema.screening.joints;
      renderForm($("screeningForm"), S.meta.schema.screening.groups);
      renderJoints();
      renderEquilibriumForm();
      status(T("loaded"));
    } catch (error) {
      status(`${T("error")}: ${error.message}`, true);
    }
  };
  reader.readAsText(file);
}

/* ------------------------------------------------------------------ tema */
function toggleTheme() {
  const dark = document.documentElement.getAttribute("data-theme") === "dark";
  document.documentElement.setAttribute("data-theme", dark ? "light" : "dark");
  try {
    localStorage.setItem("lythos-theme", dark ? "light" : "dark");
  } catch { /* özel pencerede depolama kapalı olabilir */ }
}

function restoreTheme() {
  let stored = null;
  try {
    stored = localStorage.getItem("lythos-theme");
  } catch { /* yoksay */ }
  if (stored) document.documentElement.setAttribute("data-theme", stored);
}

/* ------------------------------------------------------------- başlangıç */
async function start() {
  restoreTheme();
  const meta = await api("/api/meta");
  S.values = JSON.parse(JSON.stringify(meta.defaults));
  applyMeta(meta);

  $("language").addEventListener("change", (e) => setLanguage(e.target.value));
  $("btnTheme").addEventListener("click", toggleTheme);
  $("btnSave").addEventListener("click", saveInputs);
  $("btnOpen").addEventListener("click", () => $("fileInput").click());
  $("fileInput").addEventListener("change", (e) => {
    if (e.target.files[0]) openInputs(e.target.files[0]);
    e.target.value = "";
  });
  $("btnReport").addEventListener("click", downloadReport);
  $("btnScreen").addEventListener("click", runScreening);
  $("btnHandoff").addEventListener("click", runHandoff);
  $("btnAnalyse").addEventListener("click", runEquilibrium);
  $("btnRequired").addEventListener("click", runRequired);
  $("btnBolts").addEventListener("click", runBolts);
  $("btnBoltCheck").addEventListener("click", runBoltCheck);
  $("mode").addEventListener("change", () => { renderEquilibriumForm(); });
  $("btnAddRow").addEventListener("click", () => {
    S.values.joints.push({ label: "J" + (S.values.joints.length + 1), dip: 45, dipdir: 180, std: 2.5 });
    renderJoints();
  });
  $("btnDelRow").addEventListener("click", () => {
    if (S.values.joints.length > 1) {
      S.values.joints.splice(S.selectedRow, 1);
      S.selectedRow = Math.max(0, S.selectedRow - 1);
      renderJoints();
    }
  });
  for (const button of document.querySelectorAll("nav.modules button")) {
    button.addEventListener("click", () => switchModule(button.dataset.module));
  }
}

start().catch((error) => status("Error: " + error.message, true));
