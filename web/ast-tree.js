export const CATEGORIES = [
  ["decl", "оголошення"], ["stmt", "оператор"], ["expr", "вираз"],
  ["var", "змінна"], ["const", "константа"], ["group", "список"],
];

const NODE_H = 26;
const ROW_GAP = 10;
const LEVEL_GAP = 46;
const DURATION = 380;
const FONT = '500 12px "JetBrains Mono", Menlo, monospace';
const SMALL_FONT = '600 10.5px "JetBrains Mono", Menlo, monospace';

const ctx = document.createElement("canvas").getContext("2d");
function textWidth(text, font = FONT) {
  ctx.font = font;
  return ctx.measureText(text).width;
}

function splitLabel(name) {
  const i = name.indexOf(" ");
  return i < 0 ? [name, ""] : [name.slice(0, i), name.slice(i + 1)];
}

export class AstTree {
  constructor(host, { onSelect, onHover } = {}) {
    this.host = host;
    this.onSelect = onSelect || (() => {});
    this.onHover = onHover || (() => {});
    this.root = null;
    this.selected = null;
    this.nextId = 0;

    this.svg = d3.select(host).append("svg").attr("class", "tree");
    this.viewport = this.svg.append("g");
    this.linkLayer = this.viewport.append("g");
    this.nodeLayer = this.viewport.append("g");
    this.tooltip = d3.select(host).append("div").attr("class", "tree-tooltip");

    this.zoom = d3.zoom().scaleExtent([0.08, 2.5])
      .on("zoom", (e) => this.viewport.attr("transform", e.transform));
    this.svg.call(this.zoom).on("dblclick.zoom", null);
  }

  setData(data) {
    if (!data) { this.clear(); return; }
    const prev = this.root;
    this.root = d3.hierarchy(data);
    const total = this.root.descendants().length;
    this.root.each((d) => {
      d.id = ++this.nextId;
      d._children = d.children;
      d.box = this.measure(d.data);
    });
    if (total > 45) this.root.each((d) => { if (d.depth >= 3) d.children = null; });
    this.root.x0 = 0; this.root.y0 = 0;
    this.selected = null;
    this.nodeLayer.selectAll("*").remove();
    this.linkLayer.selectAll("*").remove();
    this.update(this.root);
    if (!prev) this.fit(false); else this.fit(true);
    return total;
  }

  clear() {
    this.root = null;
    this.nodeLayer.selectAll("*").remove();
    this.linkLayer.selectAll("*").remove();
  }

  measure(data) {
    const role = data.role ? data.role + ": " : "";
    const [kind, detail] = splitLabel(data.name);
    const roleW = textWidth(role);
    const kindW = textWidth(kind + (detail ? " " : ""));
    const detailW = textWidth(detail);
    const typeW = data.ctype ? textWidth(data.ctype, SMALL_FONT) + 12 : 0;
    const width = 24 + roleW + kindW + detailW + (typeW ? typeW + 8 : 0) + 10;
    return { role, kind, detail, roleW, kindW, detailW, typeW, width };
  }

  layout() {
    d3.tree().nodeSize([NODE_H + ROW_GAP, 1])(this.root);
    const widest = [];
    this.root.each((d) => { widest[d.depth] = Math.max(widest[d.depth] || 0, d.box.width); });
    const offset = [0];
    for (let i = 1; i < widest.length; i++) offset[i] = offset[i - 1] + widest[i - 1] + LEVEL_GAP;
    this.root.each((d) => { d.px = offset[d.depth]; d.py = d.x; });
  }

  linkPath(s, t) {
    const x0 = s.px + s.box.width, y0 = s.py, x1 = t.px, y1 = t.py, mx = (x0 + x1) / 2;
    return `M${x0},${y0} C${mx},${y0} ${mx},${y1} ${x1},${y1}`;
  }

  update(source) {
    this.layout();
    const nodes = this.root.descendants();
    const links = this.root.links();
    const t = this.svg.transition().duration(DURATION).ease(d3.easeCubicOut);
    const from = { px: source.px0 ?? source.px ?? 0, py: source.py0 ?? source.py ?? 0, box: source.box };

    const node = this.nodeLayer.selectAll("g.node").data(nodes, (d) => d.id);
    const enter = node.enter().append("g")
      .attr("class", "node")
      .attr("transform", `translate(${from.px},${from.py})`)
      .attr("opacity", 0)
      .on("click", (e, d) => this.handleClick(d))
      .on("mouseenter", (e, d) => { this.onHover(d.data); this.showTooltip(e, d); })
      .on("mousemove", (e, d) => this.showTooltip(e, d))
      .on("mouseleave", () => { this.onHover(null); this.tooltip.style("opacity", 0); });

    enter.append("rect").attr("class", "node-bg")
      .attr("y", -NODE_H / 2).attr("height", NODE_H).attr("rx", 7)
      .attr("width", (d) => d.box.width);
    enter.append("circle").attr("class", "node-dot")
      .attr("cx", 12).attr("r", 4.5)
      .attr("fill", (d) => `var(--c-${d.data.category})`);
    const label = enter.append("text").attr("x", 22);
    label.append("tspan").attr("class", "t-role").text((d) => d.box.role);
    label.append("tspan").attr("class", "t-kind").text((d) => d.box.kind + (d.box.detail ? " " : ""));
    label.append("tspan").attr("class", "t-detail").text((d) => d.box.detail);

    const chip = enter.filter((d) => d.data.ctype).append("g").attr("class", "type-chip")
      .attr("transform", (d) => `translate(${d.box.width - d.box.typeW - 8},0)`);
    chip.append("rect").attr("y", -8).attr("height", 16).attr("rx", 4).attr("width", (d) => d.box.typeW);
    chip.append("text").attr("x", 6).text((d) => d.data.ctype);

    const more = enter.append("g").attr("class", "more");
    more.append("rect").attr("y", -8).attr("height", 16).attr("rx", 8);
    more.append("text");

    const merged = enter.merge(node);
    merged.transition(t)
      .attr("transform", (d) => `translate(${d.px},${d.py})`)
      .attr("opacity", 1);

    merged.select("g.more")
      .style("display", (d) => (d._children && !d.children ? null : "none"))
      .attr("transform", (d) => `translate(${d.box.width + 4},0)`);
    merged.select("g.more rect").attr("width", (d) => (d._children ? 14 + String(d._children.length).length * 7 : 0));
    merged.select("g.more text")
      .attr("x", (d) => (d._children ? (14 + String(d._children.length).length * 7) / 2 : 0))
      .text((d) => (d._children ? "+" + d._children.length : ""));
    merged.classed("selected", (d) => d === this.selected);

    node.exit().transition(t)
      .attr("transform", `translate(${source.px},${source.py})`)
      .attr("opacity", 0).remove();

    const link = this.linkLayer.selectAll("path.link").data(links, (d) => d.target.id);
    const linkEnter = link.enter().append("path").attr("class", "link")
      .attr("d", () => this.linkPath(from, from));
    link.merge(linkEnter).transition(t).attr("d", (d) => this.linkPath(d.source, d.target));
    link.exit().transition(t).attr("d", () => this.linkPath(source, source)).remove();

    this.root.each((d) => { d.px0 = d.px; d.py0 = d.py; });
    this.markPath();
  }

  handleClick(d) {
    if (d._children) d.children = d.children ? null : d._children;
    this.selected = d;
    this.onSelect(d.data);
    this.update(d);
  }

  markPath() {
    const onPath = new Set(this.selected ? this.selected.ancestors() : []);
    this.linkLayer.selectAll("path.link").classed("active", (l) => onPath.has(l.target));
  }

  showTooltip(event, d) {
    const [x, y] = d3.pointer(event, this.host);
    const data = d.data;
    const kids = d._children ? d._children.length : 0;
    this.tooltip.html(`
      <div class="tt-kind">${escapeHtml(data.kind)}</div>
      ${data.role ? `<div class="tt-row">поле батька: <b>${escapeHtml(data.role)}</b></div>` : ""}
      <div class="tt-row">${data.end > data.line ? `рядки <b>${data.line}–${data.end}</b>` : `рядок <b>${data.line}</b>`}${data.ctype ? ` · тип <b>${escapeHtml(data.ctype)}</b>` : ""}</div>
      ${kids ? `<div class="tt-row">дітей: <b>${kids}</b>${d.children ? "" : " (згорнуто)"}</div>` : ""}`);
    const box = this.host.getBoundingClientRect();
    const left = Math.min(x + 16, box.width - 290);
    this.tooltip.style("left", `${Math.max(8, left)}px`).style("top", `${y + 14}px`).style("opacity", 1);
  }

  fit(animate = true) {
    if (!this.root) return;
    const nodes = this.root.descendants();
    const minX = d3.min(nodes, (d) => d.px), maxX = d3.max(nodes, (d) => d.px + d.box.width + 30);
    const minY = d3.min(nodes, (d) => d.py - NODE_H / 2), maxY = d3.max(nodes, (d) => d.py + NODE_H / 2);
    const { width, height } = this.host.getBoundingClientRect();
    const pad = 28;
    const ideal = Math.min(1.1, (width - pad * 2) / (maxX - minX), (height - pad * 2 - 40) / (maxY - minY));
    const scale = Math.max(0.55, ideal);
    const clamped = scale > ideal;
    const tx = pad - minX * scale;
    const ty = clamped ? pad + 16 - minY * scale : (height - 40 - (maxY + minY) * scale) / 2;
    const transform = d3.zoomIdentity.translate(tx, ty).scale(scale);
    (animate ? this.svg.transition().duration(DURATION) : this.svg).call(this.zoom.transform, transform);
  }

  expandAll() {
    if (!this.root) return;
    this.root.each((d) => { if (d._children) d.children = d._children; });
    this.update(this.root);
    setTimeout(() => this.fit(), DURATION);
  }

  collapseToFunctions() {
    if (!this.root) return;
    this.root.each((d) => { if (d._children) d.children = d.depth < 1 ? d._children : null; });
    this.update(this.root);
    setTimeout(() => this.fit(), DURATION);
  }

  highlightLine(line) {
    this.nodeLayer.selectAll("g.node").classed("linked", (d) => line != null && d.data.line === line && d.depth > 0);
  }

  search(query) {
    if (!this.root) return 0;
    const q = query.trim().toLowerCase();
    const matches = new Set();
    if (q) {
      const all = [];
      (function collect(n) { all.push(n); (n._children || []).forEach(collect); })(this.root);
      for (const d of all) {
        const hay = `${d.data.name} ${d.data.kind} ${d.data.ctype || ""}`.toLowerCase();
        if (hay.includes(q)) matches.add(d);
      }
      for (const n of all) {
        if (n._children && n._children.some((c) => hasMatch(c, matches))) n.children = n._children;
      }
      this.update(this.root);
    }
    this.nodeLayer.selectAll("g.node").classed("match", (d) => matches.has(d));
    return matches.size;
  }
}

function hasMatch(node, matches) {
  if (matches.has(node)) return true;
  return (node._children || []).some((c) => hasMatch(c, matches));
}

export function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
