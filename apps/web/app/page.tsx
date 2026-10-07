"use client";
// The engine, watched live. Not a dashboard: one line of stations, a tree of real applications growing from
// "applying" (one stem per resume lane, one bead per proof-backed submission), a narrator, and what needs you.
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { STAGES, get, type Application, type HumanItem, type Narration, type Snapshot } from "@/lib/types";

const W = 1200, H = 620, LINE_Y = 470;
const stationX = (i: number) => 120 + i * ((W - 240) / (STAGES.length - 1));

export default function Live() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [apps, setApps] = useState<Application[]>([]);
  const [lines, setLines] = useState<Narration[]>([]);
  const [pulse, setPulse] = useState<{ stage: string; id: number } | null>(null);
  const [open, setOpen] = useState<Application | null>(null);
  const [human, setHuman] = useState<HumanItem[] | null>(null);

  const refresh = () => get<Application[]>("/api/applications?status=SUBMITTED&limit=500").then(setApps).catch(() => {});

  useEffect(() => {
    refresh();
    get<Narration[]>("/api/narration?limit=6").then(setLines).catch(() => {});
    const es = new EventSource("/api/stream?after=999999999");  // live only; the replay above already set the scene
    es.addEventListener("snapshot", (m) => setSnap(JSON.parse((m as MessageEvent).data)));
    es.addEventListener("narration", (m) => {
      const n: Narration = JSON.parse((m as MessageEvent).data);
      setLines((l) => [...l.slice(-5), n]);
      setPulse({ stage: n.stage, id: n.id });
      if (n.stage === "apply" && n.tone === "win") refresh();
    });
    get<Snapshot>("/api/snapshot").then(setSnap).catch(() => {});
    return () => es.close();
  }, []);

  // the tree: lanes ordered by size, each a straight stem rising from "applying"
  const lanes = useMemo(() => {
    const by = new Map<string, Application[]>();
    for (const a of apps.filter((a) => a.proof)) {
      const k = a.lane || "earlier";
      by.set(k, [...(by.get(k) || []), a]);
    }
    return [...by.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [apps]);

  const ax = stationX(3), trunkTop = 300, span = Math.min(110, 520 / Math.max(1, lanes.length));

  return (
    <main className="stage">
      <header className="top">
        <div className="brand">REGEN · LIVE <Link href="/graph" style={{ color: "var(--gold)", marginLeft: 16 }}>memory graph →</Link></div>
        <div className="count">
          <b>{snap?.verified ?? "·"}</b>
          <span>applications sent with proof{snap ? ` · ${snap.verified_today} today` : ""}</span>
        </div>
      </header>

      <svg className="machine" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" role="img"
           aria-label="Pipeline: listening, judging, writing, applying, hearing back; a tree of sent applications by resume lane">
        <defs>
          <linearGradient id="pipe" x1="0" x2="1"><stop offset="0" stopColor="#6fb7ff" stopOpacity=".25" /><stop offset=".75" stopColor="#f2c14e" stopOpacity=".55" /><stop offset="1" stopColor="#6fb7ff" stopOpacity=".25" /></linearGradient>
          <filter id="glow"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>

        {/* the pipeline: five stations on one line */}
        <line x1={stationX(0)} x2={stationX(4)} y1={LINE_Y} y2={LINE_Y} stroke="url(#pipe)" strokeWidth={2} />
        {STAGES.map((s, i) => (
          <g key={s.key}>
            <circle cx={stationX(i)} cy={LINE_Y} r={7} fill="#0d1117" stroke={s.key === "apply" ? "#f2c14e" : "#6fb7ff"} strokeWidth={1.5} filter="url(#glow)" />
            {pulse?.stage === s.key && <circle key={pulse.id} className="pulse" cx={stationX(i)} cy={LINE_Y} r={9} fill="none" stroke={s.key === "apply" ? "#f2c14e" : "#6fb7ff"} />}
            <text className="station-label" x={stationX(i)} y={LINE_Y + 32}>{s.verb}</text>
          </g>
        ))}
        <text className="station-label" x={stationX(0)} y={LINE_Y + 50} style={{ fontSize: 11 }}>{snap ? `${snap.boards.toLocaleString()} boards` : ""}</text>

        {/* the tree: trunk from "applying", one stem per lane, one bead per proof-backed application */}
        {lanes.length > 0 && <line x1={ax} x2={ax} y1={LINE_Y - 8} y2={trunkTop} stroke="#f2c14e" strokeOpacity={.5} strokeWidth={2} />}
        {lanes.map(([lane, list], li) => {
          const x = ax + (li - (lanes.length - 1) / 2) * span;
          const top = trunkTop - 20 - list.length * 14;
          return (
            <g key={lane}>
              <path d={`M ${ax} ${trunkTop} Q ${ax} ${trunkTop - 18} ${x} ${trunkTop - 26} L ${x} ${top}`} fill="none" stroke="#f2c14e" strokeOpacity={.35} strokeWidth={1.5} />
              {list.map((a, bi) => (
                <circle key={a.job} className="bead" cx={x} cy={trunkTop - 34 - bi * 14} r={5} fill="#f2c14e" filter="url(#glow)" onClick={() => setOpen(a)}>
                  <title>{a.company} · {a.role}</title>
                </circle>
              ))}
              <text className="lane-label" x={x} y={top - 30}>{lane}</text>
              <text className="lane-count" x={x} y={top - 15}>{list.length}</text>
            </g>
          );
        })}
      </svg>

      <footer className="bottom">
        <div className="narrator" aria-live="polite">
          {lines.map((l, i) => <p key={l.id} className={l.tone} style={{ opacity: .35 + (i + 1) / lines.length * .65 }}>{l.text}</p>)}
        </div>
        {snap && snap.waiting > 0 && (
          <button className="waiting" onClick={() => get<HumanItem[]>("/api/human").then(setHuman)}>
            {snap.waiting} {snap.waiting === 1 ? "thing is" : "things are"} waiting on you →
          </button>
        )}
      </footer>

      {open && <Proof a={open} onClose={() => setOpen(null)} />}
      {human && (
        <aside className="panel" aria-label="Waiting on you">
          <button className="close" onClick={() => setHuman(null)} aria-label="close">×</button>
          <h2>Waiting on you</h2>
          <div className="sub">Each job's latest state. Bot checks are never bypassed; the resume is ready for each.</div>
          <ul className="list">{human.map((h) => <li key={h.job}>{h.text}<small>{h.job}</small></li>)}</ul>
        </aside>
      )}
    </main>
  );
}

function Proof({ a, onClose }: { a: Application; onClose: () => void }) {
  const file = a.proof?.split(/[\\/]/).pop();
  const facts = a.facts ?? [], answers = a.answers ?? [];
  return (
    <aside className="panel" aria-label={`Proof for ${a.company}`}>
      <button className="close" onClick={onClose} aria-label="close">×</button>
      <h2>{a.company}</h2>
      <div className="sub">{a.role} · {a.lane || "earlier"} lane · {a.ts.replace("T", " ")}</div>
      {file && <img src={`/api/proof/${file}`} alt={`Confirmation page for ${a.company}`} />}
      {facts.length > 0 && (<><h3>BUILT FROM THESE FACTS</h3><div className="chips">{facts.map((f) => <span className="chip" key={f}>{f}</span>)}</div></>)}
      {answers.length > 0 && (<><h3>WHAT THE FORM ASKED, WHAT WE ANSWERED</h3>
        {answers.map(([q, ans], i) => <div className="qa" key={i}><span>{q}</span><span>{ans === "__DECLINE__" ? "declined" : ans === "__ACK__" ? "acknowledged" : ans ?? "—"}</span></div>)}</>)}
    </aside>
  );
}
