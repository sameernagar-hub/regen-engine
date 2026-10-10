"use client";
// The Fact Bank, drawn: every resume line the engine may use, grouped by the role it belongs to, sized by how many
// resumes used it and colored by the lane that used it most. The engine never writes a claim that isn't here.
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Nav } from "../nav";
import { get } from "@/lib/types";

type Fact = { id: string; text: string; role: string | null; uses: number; lanes: Record<string, number>;
              recent: { job: string; url: string; ts: string }[] };
type Bank = { name: string; facts: Fact[]; roles: { id: string; org: string; title: string; where: string; when: string }[];
              projects: { id: string; name: string; when: string; points: string[] }[];
              skills: { id: string; label: string; items: string[] }[]; education: { degree: string; when: string }[];
              awards: string[]; publications: string[]; sources: { date: string; file: string; added: string[] }[];
              resumes_built: number };

const LANE: Record<string, string> = { ai: "#f2c14e", fullstack: "#6fb7ff", backend: "#7ef0c1", frontend: "#ff9f43",
  platform: "#b39dff", data: "#ff7eb6", embedded: "#9be15d", sre: "#5ad1e6", "?": "#7d8796" };
const topLane = (l: Record<string, number>) => Object.entries(l).sort((a, b) => b[1] - a[1])[0]?.[0] || "?";

export default function Facts() {
  const [b, setB] = useState<Bank | null>(null);
  const [focus, setFocus] = useState<Fact | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { get<Bank>("/api/factbank").then(setB).catch((e) => setErr(e.message)); }, []);

  // radial map: roles on the inner ring, their facts fanned around them; O(F) layout
  const map = useMemo(() => {
    if (!b) return null;
    const groups = new Map<string, Fact[]>();
    for (const f of b.facts) groups.set(f.role || "Other", [...(groups.get(f.role || "Other") || []), f]);
    const keys = [...groups.keys()];
    const max = Math.max(1, ...b.facts.map((f) => f.uses));
    const out: { role: string; x: number; y: number; facts: (Fact & { x: number; y: number; r: number })[] }[] = [];
    keys.forEach((k, i) => {
      const a = (i / keys.length) * Math.PI * 2 - Math.PI / 2;
      const fs = groups.get(k)!;
      const span = (Math.PI * 2) / keys.length;
      out.push({
        role: k, x: Math.cos(a) * 150, y: Math.sin(a) * 150,
        facts: fs.map((f, j) => {
          const fa = a - span / 2 + (span * (j + 0.5)) / fs.length;
          const rr = 290 + (j % 2) * 46;
          return { ...f, x: Math.cos(fa) * rr, y: Math.sin(fa) * rr, r: 5 + 13 * Math.sqrt(f.uses / max) };
        }),
      });
    });
    return out;
  }, [b]);

  if (err) return <main className="page"><Nav /><p className="err">{err}</p></main>;
  if (!b || !map) return <main className="page"><Nav /><p className="dim">Loading the Fact Bank…</p></main>;
  const used = b.facts.filter((f) => f.uses).length;

  return (
    <main className="page">
      <Nav />
      <header className="hero">
        <h1>Fact Bank</h1>
        <p>Every claim a resume can make, from your own resumes, LinkedIn and repos. {b.resumes_built} resumes were built from these {b.facts.length} facts; {used} have been used at least once.</p>
      </header>
      <dl className="stats">
        <div><dt>Facts</dt><dd>{b.facts.length}</dd></div>
        <div><dt>Roles</dt><dd>{b.roles.length}</dd></div>
        <div><dt>Projects</dt><dd>{b.projects.length}</dd></div>
        <div><dt>Skill lines</dt><dd>{b.skills.length}</dd></div>
        <div><dt>Resumes built</dt><dd>{b.resumes_built}</dd></div>
      </dl>

      <section className="card mapcard" aria-label="Knowledge map">
        <h2 className="sub">Knowledge map</h2>
        <p className="dim small">Center: you. Inner ring: roles. Outer ring: facts, sized by how often resumes used them, colored by the lane that used them most. Select a fact to read it.</p>
        <svg viewBox="-420 -400 840 800" className="factmap" role="img" aria-label="Facts grouped by role">
          {map.map((g) => g.facts.map((f) => (
            <line key={"l" + f.id} x1={g.x} y1={g.y} x2={f.x} y2={f.y} className="grow" stroke={LANE[topLane(f.lanes)]} strokeOpacity={f.uses ? 0.35 : 0.08} pathLength={1} />
          )))}
          {map.map((g) => <line key={"c" + g.role} x1={0} y1={0} x2={g.x} y2={g.y} stroke="var(--line)" />)}
          <circle r={26} fill="#fff" opacity={0.9} /><text y={4} textAnchor="middle" className="glabel" style={{ fill: "#000", stroke: "none" }}>you</text>
          {map.map((g, i) => (
            <g key={g.role} style={{ ["--i" as any]: i }} className="gnode">
              <circle cx={g.x} cy={g.y} r={14} fill="#f2c14e" />
              <text x={g.x} y={g.y - 20} textAnchor="middle" className="glabel">{g.role.length > 22 ? g.role.slice(0, 21) + "…" : g.role}</text>
            </g>
          ))}
          {map.map((g) => g.facts.map((f) => (
            <circle key={f.id} cx={f.x} cy={f.y} r={f.r} fill={LANE[topLane(f.lanes)]} fillOpacity={f.uses ? 0.9 : 0.25}
                    className="gnode" tabIndex={0} onClick={() => setFocus(f)} onKeyDown={(e) => e.key === "Enter" && setFocus(f)}
                    stroke={focus?.id === f.id ? "#fff" : "none"} strokeWidth={2}>
              <title>{f.id}: {f.uses} resumes</title>
            </circle>
          )))}
        </svg>
        <ul className="chips legend">{Object.entries(LANE).filter(([k]) => k !== "?").map(([k, c]) => <li key={k} className="chip" style={{ color: c }}>{k}</li>)}</ul>
        {focus && (
          <div className="note" role="status">
            <b>{focus.id}</b> · used by {focus.uses} resumes{focus.role ? ` · ${focus.role}` : ""}
            <p>{focus.text}</p>
            {focus.recent.length > 0 && <p className="small dim">Recently in: {focus.recent.map((r, i) => <span key={i}>{i ? ", " : ""}<Link href={`/job?u=${encodeURIComponent(r.url || "")}`}>{r.job}</Link></span>)}</p>}
          </div>
        )}
      </section>

      <section className="card" aria-label="All facts by use">
        <h2 className="sub">Facts by use</h2>
        <ol className="factlist">
          {b.facts.map((f) => (
            <li key={f.id} id={f.id}>
              <div className="fhead"><code>{f.id}</code><span className="usebar"><i style={{ width: `${(100 * f.uses) / Math.max(1, b.facts[0].uses)}%` }} /></span><b>{f.uses}</b></div>
              <p>{f.text}</p>
              <ul className="chips">{Object.entries(f.lanes).map(([l, n]) => <li key={l} className="chip" style={{ color: LANE[l] || LANE["?"] }}>{l} {n}</li>)}</ul>
            </li>
          ))}
        </ol>
      </section>

      <div className="grid2">
        <section className="card"><h2 className="sub">Roles</h2>
          <ul className="list">{b.roles.map((r) => <li key={r.id}><b>{r.title}</b> · {r.org}<small>{r.where} · {r.when}</small></li>)}</ul>
          <h2 className="sub">Education</h2>
          <ul className="list">{b.education.map((e, i) => <li key={i}>{e.degree}<small>{e.when}</small></li>)}</ul>
          <h2 className="sub">Awards & publications</h2>
          <ul className="list">{[...b.awards, ...b.publications].map((a, i) => <li key={i}>{a}</li>)}</ul>
        </section>
        <section className="card"><h2 className="sub">Skills</h2>
          {b.skills.map((s) => <div key={s.id} className="skill"><small className="dim">{s.label}</small><ul className="chips">{s.items.map((x) => <li key={x} className="chip">{x}</li>)}</ul></div>)}
          <h2 className="sub">Where the facts came from</h2>
          <ol className="list">{b.sources.map((s, i) => <li key={i}>{s.file}<small>{s.date} · added {s.added.length}: {s.added.slice(0, 8).join(", ")}{s.added.length > 8 ? "…" : ""}</small></li>)}</ol>
        </section>
      </div>

      <section className="card"><h2 className="sub">Projects</h2>
        <ul className="list">{b.projects.map((p) => <li key={p.id}><b>{p.name}</b><small>{p.when}</small>{p.points.map((x, i) => <small key={i}>• {x}</small>)}</li>)}</ul>
      </section>
    </main>
  );
}
