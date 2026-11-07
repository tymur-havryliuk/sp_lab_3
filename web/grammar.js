import { escapeHtml } from "./ast-tree.js";

const KEYWORDS = new Set(["INT", "FLOAT", "DOUBLE", "CHAR", "VOID", "IF", "ELSE", "WHILE", "DO", "FOR",
  "RETURN", "BREAK", "CONTINUE", "SIZEOF"]);
const LITERALS = new Set(["ID", "INT_CONST", "FLOAT_CONST", "CHAR_CONST", "STRING"]);
const FAKE = { IFX: "if без else", UMINUS: "унарний мінус" };
const ASSOC = { left: "left", right: "right", nonassoc: "nonassoc" };

export async function renderGrammar(host) {
  const g = await (await fetch("/api/grammar")).json();
  const terminals = new Set(g.terminals);
  const s = g.stats;

  const symbol = (name) => {
    if (name === "error") return `<span class="sym-err" title="спеціальний токен відновлення після помилок">error</span>`;
    if (!terminals.has(name)) return `<span class="sym-nt" data-goto="${name}">${name}</span>`;
    const text = escapeHtml(g.texts[name] || name);
    if (KEYWORDS.has(name)) return `<span class="sym-kw" title="${name}">${text}</span>`;
    if (LITERALS.has(name)) return `<span class="sym-lit" title="${name}">${text}</span>`;
    return `<span class="sym-op" title="${name}">'${text}'</span>`;
  };

  const precRows = g.precedence.map((p) => `
    <tr>
      <td class="lvl">${p.level}</td>
      <td><span class="assoc ${ASSOC[p.assoc]}">${p.assoc}</span></td>
      <td>${p.tokens.map((t) => FAKE[t.name]
        ? `<span class="op fake" title="фіктивний токен для %prec: ${FAKE[t.name]}">${t.name}</span>`
        : `<span class="op" title="${t.name}">${escapeHtml(t.text)}</span>`).join("")}</td>
    </tr>`).join("");

  const rules = g.rules.map((r) => `
    <div class="rule" id="rule-${r.lhs}" data-search="${r.lhs} ${r.alternatives.flat().map((n) => g.texts[n] || n).join(" ").toLowerCase()}">
      <div><span class="rule-lhs">${r.lhs}</span></div>
      ${r.alternatives.map((alt, i) => `
        <div class="rule-alt"><span class="bar">${i === 0 ? "→" : "|"}</span>
          ${alt.length ? alt.map(symbol).join(" ") : `<span class="sym-eps">ε</span>`}
        </div>`).join("")}
    </div>`).join("");

  host.innerHTML = `
    <div class="g-section">
      <div class="g-stats">
        <div class="g-stat"><b>${s.productions}</b><span>продукцій</span></div>
        <div class="g-stat"><b>${s.states}</b><span>станів LALR(1)</span></div>
        <div class="g-stat ${s.conflicts === 0 ? "ok" : ""}"><b>${s.conflicts}</b><span>конфліктів</span></div>
      </div>
    </div>
    <div class="g-section">
      <h3 class="g-h">Пріоритети</h3>
      <table class="prec">${precRows}</table>
    </div>
    <details class="g-rules">
      <summary>Усі правила граматики <span class="badge">${g.rules.length}</span></summary>
      <div class="g-filter"><label class="search"><svg class="ico"><use href="#i-search"/></svg>
        <input id="rule-filter" placeholder="Пошук: while, expr, +="></label></div>
      <div id="rules">${rules}</div>
    </details>`;

  host.querySelector("#rule-filter").addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    host.querySelectorAll(".rule").forEach((el) => { el.hidden = q && !el.dataset.search.includes(q); });
  });
  host.addEventListener("click", (e) => {
    const target = e.target.closest("[data-goto]");
    if (!target) return;
    const el = host.querySelector(`#rule-${CSS.escape(target.dataset.goto)}`);
    if (!el) return;
    el.hidden = false;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash");
  });
}
