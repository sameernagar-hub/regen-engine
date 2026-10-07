"use client";
// The engine's memory as layers you can open: You -> lanes -> applications -> facts, company, ATS, outcomes.
// Click a node to expand its next layer (it blooms outward); click again to fold it. Facts used by several
// applications stay one shared node, so reused knowledge is visible. Everything comes from /api/graph (evidence only).
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { loadGraph } from "@/lib/engine";

type GNode = { id: string; type: string; label: string; data: Record<string, any> };
type GEdge = { source: string; target: string; type: string; data?: Record<string, any> };
type Pos = { x: number; y: number; a: number; depth: number };

const COLOR: Record<string, string> = {
  You: "#ffffff", Lane: "#f2c14e", Application: "#ffd88a", Company: "#6fb7ff", Fact: "#7ef0c1",
  ATS: "#b39dff", Outcome: "#ff9f43", Question: "#8b96a8",
};
const RING = [0, 170, 330, 500, 640];
const CHILD_TYPES: Record<string, string[]> = {
  You: ["Lane"], Lane: ["Application"], Application: ["Fact", "Company", "ATS", "Outcome"], ATS: ["Application"],
  Fact: ["Application"], Company: ["Application"],
};

export default function Graph() {
  const [g, setG] = useState<{ nodes: GNode[]; edges: GEdge[] } | null>(null);
  const [open, setOpen] = useState<string[]>(["you"]);
  const [hover, setHover] = useState<string | null>(null);
  const [focus, setFocus] = useState<GNode | null>(null);
  const [view, setView] = useState({ x: -560, y: -400, w: 1120, h: 800 });
  const drag = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => { loadGraph().then(setG).catch(() => {}); }, []);

  const byId = useMemo(() => new Map((g?.nodes || []).map((n) => [n.id, n])), [g]);
  const adj = useMemo(() => {
    const m = new Map<string, GEdge[]>();
    for (const e of g?.edges || []) {
      m.set(e.source, [...(m.get(e.source) || []), e]);
      m.set(e.target, [...(m.get(e.target) || []), e]);
    }
    return m;
  }, [g]);

  // lay out visible layers: each opened node places its unplaced children in an arc around its own angle
  const { pos, shown } = useMemo(() => {
    const pos = new Map<string, Pos>();
    const shown: GEdge[] = [];
    if (!g) return { pos, shown };
    pos.set("you", { x: 0, y: 0, a: -Math.PI / 2, depth: 0 });
    for (const id of open) {
      const p = pos.get(id), n = byId.get(id);
      if (!p || !n) continue;
      const kids = (adj.get(id) || []).map((e) => ({ e, other: e.source === id ? e.target : e.source }))
        .filter(({ other }) => CHILD_TYPES[n.type]?.includes(byId.get(other)?.type || ""));
      const fresh = kids.filter(({ other }) => !pos.has(other));
      const depth = Math.min(p.depth + 1, RING.length - 1);
      const spread = depth === 1 ? Math.PI * 2 : Math.min(Math.PI * 0.9, 0.16 * fresh.length + 0.2);
      fresh.forEach(({ other }, i) => {
        const a = depth === 1 ? -Math.PI / 2 + (i / fresh.length) * Math.PI * 2
          : p.a + (fresh.length === 1 ? 0 : (i / (fresh.length - 1) - 0.5) * spread);
        pos.set(other, { x: Math.cos(a) * RING[depth], y: Math.sin(a) * RING[depth], a, depth });
      });
      for (const { e } of kids) shown.push(e);
    }
    return { pos, shown };
  }, [g, open, byId, adj]);

  const lit = useMemo(() => {
    if (!hover) return null;
    return new Set([hover, ...(adj.get(hover) || []).flatMap((e) => [e.source, e.target])]);
  }, [hover, adj]);

  const toggle = (n: GNode) => {
    setFocus(n);
    if (!CHILD_TYPES[n.type]) return;
    setOpen((o) => (o.includes(n.id) ? o.filter((x) => x !== n.id) : [...o, n.id]));
  };

  const onWheel = (ev: React.WheelEvent) => {
    const k = ev.deltaY > 0 ? 1.1 : 0.9;
    setView((v) => ({ x: v.x + (v.w * (1 - k)) / 2, y: v.y + (v.h * (1 - k)) / 2, w: v.w * k, h: v.h * k }));
  };

  if (!g) return <main className="stage"><div className="top"><div className="brand">REGEN · MEMORY</div></div></main>;

  return (
    <main className="stage">
      <header className="top">
        <div className="brand">REGEN · MEMORY <Link href="/" style={{ color: "var(--dim)", marginLeft: 16 }}>← live</Link></div>
        <div className="count"><b style={{ fontSize: 28 }}>{pos.size}</b><span>of {g.nodes.length} nodes open · click to expand a layer</span></div>
      </header>
      <svg className="machine graph" viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} onWheel={onWheel}
           onMouseDown={(e) => (drag.current = { x: e.clientX, y: e.clientY })} onMouseUp={() => (drag.current = null)} onMouseLeave={() => (drag.current = null)}
           onMouseMove={(e) => {
             if (!drag.current) return;
             const s = view.w / (e.currentTarget as SVGSVGElement).clientWidth;
             setView((v) => ({ ...v, x: v.x - (e.clientX - drag.current!.x) * s, y: v.y - (e.clientY - drag.current!.y) * s }));
             drag.current = { x: e.clientX, y: e.clientY };
           }}>
        <defs><filter id="g2"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter></defs>
        {RING.slice(1).map((r) => <circle key={r} r={r} fill="none" stroke="#1b222c" strokeDasharray="2 8" />)}
        {shown.map((e, i) => {
          const a = pos.get(e.source), b = pos.get(e.target);
          if (!a || !b) return null;
          const on = !lit || (lit.has(e.source) && lit.has(e.target));
          return <line key={i} className="flow" x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={COLOR[byId.get(e.target)?.type || ""] || "#3a4554"}
                       strokeOpacity={on ? 0.55 : 0.07} strokeWidth={e.type === "INCLUDES" ? 1 : 1.6} />;
        })}
        {[...pos.entries()].map(([id, p]) => {
          const n = byId.get(id)!; const isOpen = open.includes(id);
          const r = n.type === "You" ? 16 : n.type === "Lane" ? 11 : n.type === "Application" ? 7 : 5;
          const dim = lit && !lit.has(id);
          return (
            <g key={id} className="gnode" style={{ transform: `translate(${p.x}px, ${p.y}px)`, opacity: dim ? 0.18 : 1 }}
               onClick={() => toggle(n)} onMouseEnter={() => setHover(id)} onMouseLeave={() => setHover(null)}>
              <circle r={r} fill={COLOR[n.type] || "#999"} filter="url(#g2)" />
              {isOpen && n.type !== "You" && <circle r={r + 6} fill="none" stroke={COLOR[n.type]} strokeOpacity={.5} />}
              {(n.type !== "Fact" || hover === id) && (
                <text y={-r - 6} textAnchor="middle" className="glabel">{n.type === "Application" ? (n.data.company || n.label) : n.label}</text>
              )}
            </g>
          );
        })}
      </svg>
      <footer className="bottom">
        <div className="narrator legend">
          {Object.entries(COLOR).filter(([t]) => t !== "Question").map(([t, c]) => <span key={t} style={{ color: c, marginRight: 16 }}>● {t}</span>)}
        </div>
      </footer>
      {focus && focus.type !== "You" && (
        <aside className="panel" aria-label={focus.label}>
          <button className="close" onClick={() => setFocus(null)} aria-label="close">×</button>
          <h2>{focus.type === "Application" ? focus.data.company : focus.label}</h2>
          <div className="sub">{focus.type}{focus.type === "Application" ? ` · ${focus.label} · ${focus.data.status}` : ""}</div>
          {focus.data.text && <p style={{ lineHeight: 1.5 }}>{focus.data.text}</p>}
          {focus.data.proof && <img src={`/api/proof/${focus.data.proof}`} alt="confirmation page" />}
          <h3>CONNECTED</h3>
          <ul className="list">{(adj.get(focus.id) || []).map((e, i) => {
            const o = byId.get(e.source === focus.id ? e.target : e.source);
            return o ? <li key={i}><span style={{ color: COLOR[o.type] }}>●</span> {o.type === "Application" ? `${o.data.company} · ${o.label}` : o.label}<small>{e.type}</small></li> : null;
          })}</ul>
        </aside>
      )}
    </main>
  );
}
