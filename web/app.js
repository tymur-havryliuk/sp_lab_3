import { AstTree, CATEGORIES, escapeHtml } from "./ast-tree.js";
import { renderGrammar } from "./grammar.js";

const $ = (id) => document.getElementById(id);
const store = {
  get(key) { try { return localStorage.getItem(key); } catch (e) { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch (e) { } },
};

const state = {
  result: null,
  pythonRun: null,
  original: "",
  requestId: 0,
  diagMarks: [],
  hoverLines: [],
  tokenMark: null,
  tokenFilter: "all",
};

const editor = CodeMirror($("editor"), {
  mode: "text/x-csrc",
  lineNumbers: true,
  indentUnit: 4,
  tabSize: 4,
  indentWithTabs: false,
  matchBrackets: true,
  autoCloseBrackets: true,
  styleActiveLine: true,
  gutters: ["diag-gutter", "CodeMirror-linenumbers"],
  extraKeys: {
    "Ctrl-Enter": () => compile(),
    "Cmd-Enter": () => compile(),
    Tab: (cm) => cm.execCommand(cm.somethingSelected() ? "indentMore" : "insertSoftTab"),
  },
});

const pythonViewer = CodeMirror($("python-viewer"), {
  mode: "python", readOnly: true, lineNumbers: true, indentUnit: 4,
});

editor.on("change", () => {
  $("dirty").hidden = editor.getValue() === state.original;
});
editor.on("cursorActivity", () => tree.highlightLine(editor.getCursor().line + 1));

function goToLine(line, col) {
  if (!line) return;
  editor.focus();
  editor.setCursor({ line: line - 1, ch: col ? col - 1 : 0 });
  editor.scrollIntoView({ line: line - 1, ch: 0 }, 120);
}

function scrollEditorToLine(line) {
  const top = editor.charCoords({ line, ch: 0 }, "local").top;
  const info = editor.getScrollInfo();
  if (top < info.top || top > info.top + info.clientHeight - 40) editor.scrollTo(null, top - 40);
}

function setHoverRange(data) {
  editor.operation(() => {
    state.hoverLines.forEach((l) => editor.removeLineClass(l, "background", "line-ast-hover"));
    state.hoverLines = [];
    if (!data || !data.line) return;
    const last = Math.min(data.end || data.line, editor.lineCount());
    for (let l = data.line - 1; l < last; l++) {
      editor.addLineClass(l, "background", "line-ast-hover");
      state.hoverLines.push(l);
    }
  });
  if (data && data.line) scrollEditorToLine(data.line - 1);
}

function showDiagnosticsInEditor(diags) {
  editor.operation(() => {
    editor.clearGutter("diag-gutter");
    state.diagMarks.forEach(({ line, cls }) => editor.removeLineClass(line, "background", cls));
    state.diagMarks = [];
    const byLine = new Map();
    for (const d of diags) {
      if (!d.line || d.line > editor.lineCount()) continue;
      const prev = byLine.get(d.line);
      if (!prev || (prev.severity === "warning" && d.severity === "error")) byLine.set(d.line, d);
    }
    for (const [line, d] of byLine) {
      const marker = document.createElement("div");
      marker.className = `diag-marker ${d.severity}`;
      marker.title = diags.filter((x) => x.line === line).map((x) => x.message).join("\n");
      editor.setGutterMarker(line - 1, "diag-gutter", marker);
      const cls = d.severity === "error" ? "line-error" : "line-warning";
      editor.addLineClass(line - 1, "background", cls);
      state.diagMarks.push({ line: line - 1, cls });
    }
  });
}

const tree = new AstTree($("tree"), {
  onSelect: (data) => goToLine(data.line),
  onHover: (data) => setHoverRange(data),
});
$("legend").innerHTML = CATEGORIES.map(([c, n]) => `<span><i style="background:var(--c-${c})"></i>${n}</span>`).join("");
$("ast-expand").onclick = () => tree.expandAll();
$("ast-collapse").onclick = () => tree.collapseToFunctions();
$("ast-fit").onclick = () => tree.fit();

function setAstHidden(hidden) {
  $("workspace").classList.toggle("ast-hidden", hidden);
  $("panel-ast").classList.toggle("collapsed", hidden);
  $("ast-hide").title = hidden ? "Показати панель" : "Сховати панель";
  requestAnimationFrame(() => {
    editor.refresh();
    if (activeTab() === "python") pythonViewer.refresh();
    if (!hidden) tree.fit(false);
  });
}
$("ast-hide").onclick = (e) => {
  e.stopPropagation();
  setAstHidden(!$("panel-ast").classList.contains("collapsed"));
};
$("panel-ast").addEventListener("click", () => {
  if ($("panel-ast").classList.contains("collapsed")) setAstHidden(false);
});
$("ast-search").addEventListener("input", (e) => {
  const n = tree.search(e.target.value);
  $("search-count").textContent = e.target.value.trim() ? String(n) : "";
});

const EXAMPLE_TITLES = {
  "01_factorial.c": "Факторіал: рекурсія і цикл",
  "02_operators.c": "Складені присвоєння та sizeof",
  "90_semantic_errors.c": "Семантичні помилки",
  "91_syntax_errors.c": "Синтаксичні помилки",
};

async function loadExamples() {
  const files = await (await fetch("/api/examples")).json();
  const option = (f) => `<option value="${f}">${f} — ${EXAMPLE_TITLES[f] || ""}</option>`;
  const good = files.filter((f) => !f.startsWith("9")), bad = files.filter((f) => f.startsWith("9"));
  $("examples").innerHTML =
    `<optgroup label="Програми">${good.map(option).join("")}</optgroup>` +
    (bad.length ? `<optgroup label="Демонстрація помилок">${bad.map(option).join("")}</optgroup>` : "");
  $("examples").onchange = () => loadExample($("examples").value);
  const saved = store.get("example");
  const first = files.includes(saved) ? saved : files[0];
  if (first) {
    $("examples").value = first;
    await loadExample(first);
  }
}

async function loadExample(name) {
  const data = await (await fetch("/api/examples/" + encodeURIComponent(name))).json();
  state.original = data.code;
  store.set("example", name);
  $("file-name").textContent = name;
  editor.setValue(data.code);
  editor.clearHistory();
  $("dirty").hidden = true;
  clearResults();
}
$("reset").onclick = () => { editor.setValue(state.original); clearResults(); };

function clearResults() {
  state.requestId++;
  state.result = null;
  state.pythonRun = null;
  tree.clear();
  $("tree-empty").hidden = false;
  $("node-count").textContent = "0";
  showDiagnosticsInEditor([]);
  renderSteps(null);
  const hint = `<div class="empty-state"><div>Натисніть «Запустити»</div></div>`;
  $("page-output").innerHTML = hint;
  $("token-list").innerHTML = hint;
  $("token-filters").innerHTML = "";
  $("diag-list").innerHTML = hint;
  $("diag-badge").hidden = true;
  pythonViewer.setValue("");
}

async function compile() {
  const id = ++state.requestId;
  $("compile").classList.add("busy");
  let r;
  try {
    const resp = await fetch("/api/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: editor.getValue() }),
    });
    r = await resp.json();
  } catch (err) {
    if (id === state.requestId) toast("Сервер недоступний");
    $("compile").classList.remove("busy");
    return;
  }
  $("compile").classList.remove("busy");
  if (id !== state.requestId) return;
  state.result = r;
  state.pythonRun = null;

  const nodeCount = r.ast ? tree.setData(r.ast) : (tree.clear(), 0);
  $("tree-empty").hidden = !!r.ast;
  $("node-count").textContent = nodeCount;
  tree.highlightLine(editor.getCursor().line + 1);
  if ($("ast-search").value.trim()) $("ast-search").dispatchEvent(new Event("input"));

  showDiagnosticsInEditor(r.diagnostics);
  renderSteps(r, nodeCount);
  renderOutput();
  renderPython(r);
  renderTokens(r.tokens);
  renderDiagnostics(r.diagnostics);

  if (r.ok) runPython(id);
  else if (activeTab() === "output") showTab("diag");
}
$("compile").onclick = compile;

const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100;
  const w = m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? few : many;
  return `${n} ${w}`;
};

const STAGES = ["lexer", "parser", "semantic", "interpreter", "codegen"];

function renderSteps(r, nodeCount = 0) {
  const set = (name, cls, metric = "") => {
    const el = document.querySelector(`.step[data-stage="${name}"]`);
    el.className = "step " + cls;
    el.querySelector(".step-metric").textContent = metric;
  };
  if (!r) {
    STAGES.forEach((s) => set(s, ""));
    return;
  }
  const errs = (stage) => r.diagnostics.filter((d) => d.stage === stage && d.severity === "error").length;
  const warns = (stage) => r.diagnostics.filter((d) => d.stage === stage && d.severity === "warning").length;

  set("lexer", errs("lexer") ? "error" : "ok", errs("lexer") ? "помилка" : String(r.tokens.length));
  if (errs("parser")) set("parser", "error", "помилка");
  else if (errs("lexer")) set("parser", "skipped");
  else set("parser", "ok", String(nodeCount));

  const parsed = !errs("lexer") && !errs("parser");
  if (!parsed) set("semantic", "skipped");
  else if (errs("semantic")) set("semantic", "error", String(errs("semantic")));
  else set("semantic", warns("semantic") ? "warn" : "ok");

  if (!r.ok) {
    set("interpreter", "skipped");
    set("codegen", "skipped");
    return;
  }
  set("interpreter", r.run.error ? "error" : "ok");
  const py = state.pythonRun;
  if (!py) set("codegen", "pending");
  else set("codegen", py.ok && py.output === r.run.output ? "ok" : "error");
}

function activeTab() { return document.querySelector(".tab.active").dataset.tab; }
function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".tab-page").forEach((p) => p.classList.toggle("active", p.id === "page-" + name));
  if (name === "python") pythonViewer.refresh();
  if (name === "grammar" && !$("grammar").dataset.loaded) {
    $("grammar").dataset.loaded = "1";
    renderGrammar($("grammar")).catch(() => { $("grammar").innerHTML = `<div class="all-good">Не вдалося завантажити граматику</div>`; });
  }
  store.set("tab", name);
}
document.querySelectorAll(".tab").forEach((t) => (t.onclick = () => showTab(t.dataset.tab)));

const ICON = (id) => `<svg class="ico"><use href="#i-${id}"/></svg>`;

function terminal(title, body, chips = []) {
  return `<div class="term">
    <div class="term-head">${title}</div>
    <pre>${body}</pre>
    ${chips.length ? `<div class="term-foot">${chips.join("")}</div>` : ""}
  </div>`;
}

function renderOutput() {
  const r = state.result, page = $("page-output");
  if (!r) return;
  if (!r.ok) {
    const errors = r.diagnostics.filter((d) => d.severity === "error");
    page.innerHTML = `<div class="banner err">${ICON("x")}Програму не виконано: ${plural(errors.length, "помилка", "помилки", "помилок")} компіляції</div>
      ${errors.slice(0, 4).map((d) => `<div class="diag error" data-line="${d.line}" data-col="${d.col || 0}">
        <div class="diag-icon">${ICON("x")}</div>
        <div><div class="diag-msg">${escapeHtml(d.message)}</div>
        <div class="diag-meta"><span class="stage-tag">${d.stage}</span>рядок ${d.line}</div></div></div>`).join("")}`;
    bindDiagClicks(page);
    return;
  }
  const run = r.run, py = state.pythonRun;
  const interpOut = run.output ? escapeHtml(run.output) : `<span class="placeholder">(порожній вивід)</span>`;
  const interpChips = run.error
    ? [`<span class="chip err">помилка${run.line ? ` · рядок ${run.line}` : ""}</span>`]
    : [`<span class="chip ok">exit ${run.exit_code}</span>`];
  const interpBody = interpOut + (run.error ? `\n<span class="runtime-error">✗ ${escapeHtml(run.error)}</span>` : "");

  let banner, pyBlock;
  const pyTitle = "Згенерований Python";
  if (!py) {
    banner = `<div class="banner pending">${ICON("cpu")}Запуск згенерованого Python…</div>`;
    pyBlock = terminal(pyTitle, `<span class="placeholder">виконується…</span>`);
  } else {
    const same = py.ok && py.output === run.output;
    banner = same
      ? `<div class="banner ok">${ICON("check")}Вивід Python збігається з інтерпретатором</div>`
      : `<div class="banner err">${ICON("alert")}Вивід Python відрізняється від інтерпретатора</div>`;
    const body = (py.output ? escapeHtml(py.output) : `<span class="placeholder">(порожній вивід)</span>`) +
      (py.error ? `\n<span class="runtime-error">✗ ${escapeHtml(py.error)}</span>` : "");
    pyBlock = terminal(pyTitle, body,
      [py.ok ? `<span class="chip ok">${same ? "✓ збігається" : "виконано"}</span>` : `<span class="chip err">помилка</span>`]);
  }
  page.innerHTML = banner + terminal("Інтерпретатор AST", interpBody, interpChips) + pyBlock;
}

async function runPython(id) {
  let res;
  try {
    const resp = await fetch("/api/run-python", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: editor.getValue() }),
    });
    res = await resp.json();
  } catch (e) {
    res = { ok: false, output: "", error: "сервер недоступний", ms: 0 };
  }
  if (id !== state.requestId) return;
  state.pythonRun = res;
  renderOutput();
  renderSteps(state.result, +$("node-count").textContent);
}

function renderPython(r) {
  pythonViewer.setValue(r.ok ? r.python : "# код не згенеровано: спершу виправте помилки компіляції");
  if (activeTab() === "python") pythonViewer.refresh();
}
$("python-copy").onclick = async () => {
  if (!state.result?.ok) return;
  try { await navigator.clipboard.writeText(state.result.python); toast("Python-код скопійовано"); }
  catch (e) { toast("Не вдалося скопіювати"); }
};
$("python-download").onclick = () => {
  if (!state.result?.ok) return;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([state.result.python], { type: "text/x-python" }));
  a.download = ($("file-name").textContent || "program.c").replace(/\.c$/, "") + ".py";
  a.click();
  URL.revokeObjectURL(a.href);
};

const KEYWORD_TOKENS = new Set(["INT", "FLOAT", "DOUBLE", "CHAR", "VOID", "IF", "ELSE", "WHILE", "DO", "FOR",
  "RETURN", "BREAK", "CONTINUE", "SIZEOF"]);
const PUNCT_TOKENS = new Set(["SEMI", "COMMA", "LPAREN", "RPAREN", "LBRACE", "RBRACE", "LBRACKET", "RBRACKET"]);
const TOKEN_CATS = [
  ["all", "усі", null], ["keyword", "ключові слова", "var(--syn-keyword)"], ["ident", "ідентифікатори", "var(--syn-fn)"],
  ["literal", "літерали", "var(--syn-number)"], ["operator", "оператори", "var(--c-stmt)"], ["punct", "роздільники", "var(--muted)"],
];
function tokenCategory(type) {
  if (KEYWORD_TOKENS.has(type)) return "keyword";
  if (type === "ID") return "ident";
  if (type.endsWith("_CONST") || type === "STRING") return "literal";
  if (PUNCT_TOKENS.has(type)) return "punct";
  return "operator";
}

function renderTokens(tokens) {
  const counts = { all: tokens.length };
  tokens.forEach((t) => { const c = tokenCategory(t.type); counts[c] = (counts[c] || 0) + 1; });
  $("token-filters").innerHTML = TOKEN_CATS.map(([id, name, color]) =>
    `<button class="filter ${state.tokenFilter === id ? "active" : ""}" data-filter="${id}">
      ${color ? `<i style="background:${color}"></i>` : ""}${name}<span class="n">${counts[id] || 0}</span></button>`).join("");
  $("token-filters").querySelectorAll(".filter").forEach((b) => (b.onclick = () => {
    state.tokenFilter = b.dataset.filter;
    renderTokens(tokens);
  }));
  const shown = tokens.map((t, i) => [t, i]).filter(([t]) => state.tokenFilter === "all" || tokenCategory(t.type) === state.tokenFilter);
  $("token-list").innerHTML = `<table class="tokens">
    <thead><tr><th>#</th><th>позиція</th><th>токен</th><th>текст</th></tr></thead>
    <tbody>${shown.map(([t, i]) => `<tr data-i="${i}">
      <td class="pos">${i + 1}</td><td class="pos">${t.line}:${t.col}</td>
      <td><span class="tok-type tok-${tokenCategory(t.type)}">${t.type}</span></td>
      <td class="text">${escapeHtml(t.text)}</td></tr>`).join("")}</tbody></table>`;
  $("token-list").querySelectorAll("tr[data-i]").forEach((row) => {
    const t = tokens[+row.dataset.i];
    row.onmouseenter = () => markToken(t);
    row.onmouseleave = () => markToken(null);
    row.onclick = () => goToLine(t.line, t.col);
  });
}
function markToken(t) {
  if (state.tokenMark) { state.tokenMark.clear(); state.tokenMark = null; }
  if (!t) return;
  const from = { line: t.line - 1, ch: t.col - 1 };
  state.tokenMark = editor.markText(from, { line: from.line, ch: from.ch + t.text.length }, { className: "mark-token" });
  scrollEditorToLine(from.line);
}

const STAGE_NAMES = { lexer: "лексер", parser: "парсер", semantic: "семантика", runtime: "виконання" };

function renderDiagnostics(diags) {
  const errors = diags.filter((d) => d.severity === "error").length;
  const badge = $("diag-badge");
  badge.hidden = diags.length === 0;
  badge.textContent = errors || diags.length;
  badge.classList.toggle("warn", errors === 0);
  $("diag-list").innerHTML = diags.length
    ? diags.map((d) => `<div class="diag ${d.severity}" data-line="${d.line}" data-col="${d.col || 0}">
        <div class="diag-icon">${ICON(d.severity === "error" ? "x" : "alert")}</div>
        <div><div class="diag-msg">${escapeHtml(d.message)}</div>
          <div class="diag-meta"><span class="stage-tag">${STAGE_NAMES[d.stage] || d.stage}</span>
          рядок ${d.line}${d.col ? `, кол. ${d.col}` : ""}</div></div>
      </div>`).join("")
    : `<div class="all-good"><div class="ok-circle">${ICON("check")}</div><div>Помилок немає</div></div>`;
  bindDiagClicks($("diag-list"));
}
function bindDiagClicks(root) {
  root.querySelectorAll(".diag[data-line]").forEach((el) => (el.onclick = () => goToLine(+el.dataset.line, +el.dataset.col)));
}

let toastTimer;
function toast(text) {
  const el = $("toast");
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 1800);
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); compile(); }
});

// ?example=01_factorial.c&tab=grammar&run=1
const params = new URLSearchParams(location.search);
if (params.get("example")) store.set("example", params.get("example"));
const savedTab = params.get("tab") || store.get("tab");
if (savedTab && document.querySelector(`.tab[data-tab="${savedTab}"]`)) showTab(savedTab);
document.fonts.ready.then(loadExamples).then(() => { if (params.get("run")) compile(); });
