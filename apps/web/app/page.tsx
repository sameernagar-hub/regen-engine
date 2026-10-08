"use client";
// The engine, watched live. Not a dashboard: one line of stations, a tree of real applications growing from
// "applying" (one stem per resume lane, one bead per proof-backed submission), a narrator, and what needs you.
import { useEffect, useMemo, useState } from "react";
import { PUBLIC, useEngine } from "@/lib/engine";
import { pressable, usePanel } from "@/lib/a11y";
import Link from "next/link";
import { STAGES, get, post, type Application, type HumanItem } from "@/lib/types";

const W = 1200, H = 620, LINE_Y = 470;
const stationX = (i: number) => 120 + i * ((W - 240) / (STAGES.length - 1));
const STAGE_I: Record<string, number> = { listen: 0, judge: 1, write: 2, apply: 3, hear: 4 };
const TONE: Record<string, string> = { win: "#f2c14e", alarm: "#ff5a5f", you: "#ff9f43", quiet: "#7d8796", calm: "#6fb7ff" };
// a fixed, seeded scatter so the board field doesn't jump between renders
const rand = (i: number) => { const x = Math.sin(i * 12.9898) * 43758.5453; return x - Math.floor(x); };

export default function Live() {
  const { snap, apps, lines, pulse, replaying } = useEngine();
  const [lights, setLights] = useState<{ id: number; from: number; to: number; color: string }[]>([]);
  useEffect(() => {  // each event sends a light from the previous station to its own
    if (!pulse) return;
    const to = STAGE_I[pulse.stage] ?? 0, from = Math.max(0, to - 1);
    setLights((l) => [...l.slice(-6), { id: pulse.id, from, to, color: TONE[pulse.tone] || "#6fb7ff" }]);
  }, [pulse]);
  const stars = useMemo(() => Array.from({ length: Math.min(120, Math.round((snap?.boards || 0) / 25)) }, (_, i) => {
    const a = rand(i) * Math.PI * 2, r = 22 + rand(i + 99) * 70;
    return { x: stationX(0) + Math.cos(a) * r, y: LINE_Y - 95 + Math.sin(a) * r * 0.7, d: (rand(i + 7) * 4).toFixed(2) };
  }), [snap?.boards]);
  const [open, setOpen] = useState<Application | null>(null);
  const [human, setHuman] = useState<HumanItem[] | null>(null);

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
    <main className="stage" id="main">
      <a className="skip" href="#text-view">Skip to the text version</a>
      <header className="top">
        <div className="brand">REGEN · LIVE <Link href="/graph" style={{ color: "var(--gold)", marginLeft: 16 }}>memory graph →</Link></div>
        <div className="count">
          <b>{snap?.verified ?? "·"}</b>
          <span>applications sent with proof{snap && !PUBLIC ? ` · ${snap.verified_today} today` : ""}{PUBLIC ? " · names hidden" : ""}</span>
          <span className="mode">{replaying ? "replaying the last week of real activity" : "live"}</span>
        </div>
      </header>

      <svg className="machine" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" role="img"
           aria-label="Pipeline: listening, judging, writing, applying, hearing back; a tree of sent applications by resume lane">
        <defs>
          <linearGradient id="pipe" x1="0" x2="1"><stop offset="0" stopColor="#6fb7ff" stopOpacity=".25" /><stop offset=".75" stopColor="#f2c14e" stopOpacity=".55" /><stop offset="1" stopColor="#6fb7ff" stopOpacity=".25" /></linearGradient>
          <filter id="glow"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>

        {/* listening: one faint point per ~25 boards being watched */}
        <g aria-hidden="true">{stars.map((p, i) => <circle key={i} className="star" cx={p.x} cy={p.y} r={1.4} style={{ animationDelay: `${p.d}s` }} />)}</g>

        {/* the pipeline: five stations on one line, with light flowing along it */}
        <line x1={stationX(0)} x2={stationX(4)} y1={LINE_Y} y2={LINE_Y} stroke="url(#pipe)" strokeWidth={2} />
        <line className="flow" x1={stationX(0)} x2={stationX(4)} y1={LINE_Y} y2={LINE_Y} stroke="#f2c14e" strokeOpacity={.35} strokeWidth={1} aria-hidden="true" />
        {lights.map((l) => (
          <circle key={l.id} r={4.5} cy={LINE_Y} fill={l.color} filter="url(#glow)" aria-hidden="true">
            <animate attributeName="cx" from={stationX(l.from)} to={stationX(l.to)} dur="1.3s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1" />
            <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.15;.8;1" dur="1.5s" fill="freeze" />
          </circle>
        ))}
        {STAGES.map((s, i) => (
          <g key={s.key}>
            <circle cx={stationX(i)} cy={LINE_Y} r={7} fill="#0d1117" stroke={s.key === "apply" ? "#f2c14e" : "#6fb7ff"} strokeWidth={1.5} filter="url(#glow)" />
            {pulse?.stage === s.key && <circle key={pulse.id} className="pulse" cx={stationX(i)} cy={LINE_Y} r={9} fill="none" stroke={s.key === "apply" ? "#f2c14e" : "#6fb7ff"} />}
            <text className="station-label" x={stationX(i)} y={LINE_Y + 32}>{s.verb}</text>
          </g>
        ))}
        <text className="station-label" x={stationX(0)} y={LINE_Y + 50} style={{ fontSize: 11 }}>{snap ? `${snap.boards.toLocaleString()} boards` : ""}</text>

        {/* the tree: trunk from "applying", one stem per lane, one bead per proof-backed application */}
        {lanes.length > 0 && <line className="grow" pathLength={1} x1={ax} x2={ax} y1={LINE_Y - 8} y2={trunkTop} stroke="#f2c14e" strokeOpacity={.5} strokeWidth={2} />}
        {lanes.map(([lane, list], li) => {
          const x = ax + (li - (lanes.length - 1) / 2) * span;
          const top = trunkTop - 20 - list.length * 14;
          return (
            <g key={lane}>
              <path className="grow" pathLength={1} d={`M ${ax} ${trunkTop} Q ${ax} ${trunkTop - 18} ${x} ${trunkTop - 26} L ${x} ${top}`} fill="none" stroke="#f2c14e" strokeOpacity={.35} strokeWidth={1.5} style={{ animationDelay: `${li * 120}ms` }} />
              {list.map((a, bi) => (
                <circle key={a.job} className="bead" cx={x} cy={trunkTop - 34 - bi * 14} r={5} fill="#f2c14e" filter="url(#glow)" style={{ animationDelay: `${600 + li * 120 + bi * 45}ms, ${(bi % 7) * 0.4}s` }}
                        {...pressable(`${PUBLIC ? "" : a.company + ", "}${a.role}, ${lane} lane: open details`, () => setOpen(a))}>
                  <title>{a.company} · {a.role}</title>
                </circle>
              ))}
              <text className="lane-label" x={x} y={top - 30}>{lane}</text>
              <text className="lane-count" x={x} y={top - 15}>{list.length}</text>
            </g>
          );
        })}
      </svg>

      <section id="text-view" className="sr-only" aria-label="Text version">
        <h2>Applications sent with proof, by resume lane</h2>
        {lanes.map(([lane, list]) => (
          <div key={lane}><h3>{lane} ({list.length})</h3>
            <ul>{list.map((a) => <li key={a.job}><button onClick={() => setOpen(a)}>{PUBLIC ? a.role : `${a.company}: ${a.role}`}</button></li>)}</ul>
          </div>
        ))}
      </section>

      <footer className="bottom">
        <div className="narrator" aria-live="polite">
          {lines.map((l, i) => <p key={l.id} className={l.tone} style={{ opacity: .35 + (i + 1) / lines.length * .65 }}>{l.text}</p>)}
        </div>
        {!PUBLIC && snap && snap.waiting > 0 && (
          <button className="waiting" onClick={() => get<HumanItem[]>("/api/human").then(setHuman)}>
            {snap.waiting} {snap.waiting === 1 ? "thing is" : "things are"} waiting on you →
          </button>
        )}
      </footer>

      {open && <Proof a={open} onClose={() => setOpen(null)} />}
      {human && (
        <HumanPanel onClose={() => setHuman(null)}>
          <button className="close" onClick={() => setHuman(null)} aria-label="Close the waiting list">×</button>
          <h2>Waiting on you</h2>
          <div className="sub">Each job's latest state. Bot checks are never bypassed; the resume is ready for each.</div>
          <ul className="list">{human.map((h) => (
            <li key={h.job}>{h.text}<small>{h.job}</small>
              {(h.missing ?? []).map((q) => <AnswerBox key={q} job={h.job} question={q} />)}
            </li>))}
          </ul>
        </HumanPanel>
      )}
    </main>
  );
}

function HumanPanel({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  const ref = usePanel(onClose);
  return <aside className="panel" aria-label="Waiting on you" ref={ref} tabIndex={-1} role="dialog">{children}</aside>;
}

function Proof({ a, onClose }: { a: Application; onClose: () => void }) {
  const ref = usePanel(onClose);
  const file = a.proof?.split(/[\\/]/).pop();
  const facts = a.facts ?? [], answers = a.answers ?? [];
  return (
    <aside className="panel" aria-label={`Details for ${PUBLIC ? a.role : a.company}`} ref={ref} tabIndex={-1} role="dialog">
      <button className="close" onClick={onClose} aria-label="Close details">×</button>
      <h2>{PUBLIC ? a.role : a.company}</h2>
      <div className="sub">{a.role} · {a.lane || "earlier"} lane · {a.ts.replace("T", " ")}</div>
      {PUBLIC && <p style={{ color: "var(--dim)" }}>Sent with a saved confirmation page. On the public view the company, the resume and every answer stay private.</p>}
      {!PUBLIC && file && <img src={`/api/proof/${file}`} alt={`Confirmation page for ${a.company}`} />}
      {facts.length > 0 && (<><h3>BUILT FROM THESE FACTS</h3><div className="chips">{facts.map((f) => <span className="chip" key={f}>{f}</span>)}</div></>)}
      {answers.length > 0 && (<><h3>WHAT THE FORM ASKED, WHAT WE ANSWERED</h3>
        {answers.map(([q, ans], i) => <div className="qa" key={i}><span>{q}</span><span>{ans === "__DECLINE__" ? "declined" : ans === "__ACK__" ? "acknowledged" : ans ?? "—"}</span></div>)}</>)}
    </aside>
  );
}

// Answer once here; the engine saves it to answers.json (with its source), reuses it on every form and re-queues the job.
// Legal, sponsorship and EEO questions are refused by the API: those come from your presets only.
function AnswerBox({ job, question }: { job: string; question: string }) {
  const [text, setText] = useState("");
  const [state, setState] = useState<"idle" | "saving" | "saved" | string>("idle");
  const id = `ans-${job}-${question}`.replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 80);
  const save = async () => {
    setState("saving");
    try { await post("/api/answers", { job, question, answer: text }); setState("saved"); }
    catch (e) { setState(e instanceof Error ? e.message : "could not save"); }
  };
  return (
    <form className="answer" onSubmit={(e) => { e.preventDefault(); if (text.trim()) save(); }}>
      <label htmlFor={id}>{question}</label>
      <textarea id={id} rows={2} value={text} onChange={(e) => setText(e.target.value)} disabled={state === "saved"} />
      <button type="submit" disabled={!text.trim() || state === "saving" || state === "saved"}>
        {state === "saved" ? "Saved, job re-queued" : state === "saving" ? "Saving…" : "Save answer"}
      </button>
      {!["idle", "saving", "saved"].includes(state) && <small role="alert">{state}</small>}
    </form>
  );
}
