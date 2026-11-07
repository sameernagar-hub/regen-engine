"use client";
// Shadow (11-06): the engine's ignition backup. When a job parks on a question, the engine calls you twice, a timer
// behind each call; if neither call is picked up, Shadow (your AI delegate) picks up and finishes the job as you.
// Backend: engine/shadow.py (a 30 s tick in the answers container). Policy: engine/override.py (the gates treat
// Shadow as you; Shadow stays truthful; it never touches a CAPTCHA). Concept credit: Oto.ai's watching -> autopilot
// handoff (Memory Meets Motion, 2026-08-03).
import Link from "next/link";
import { useEffect, useState } from "react";
import { Nav } from "../nav";
import { get, post, poll } from "@/lib/types";

type Rec = { q: string; a: string | null; from: string };
type Line = { url: string; job: string; question?: string; state: string; by?: string | null; next_s: number | null; open: boolean; ts: string; recommend?: Rec[] };
type Mem = { known: number; by_you: number; entries: { question: string; answer: string; by: string; used: number; submitted?: number; parked_again?: number; moved_forward?: number; overridden?: number; weak?: boolean }[] };
type Who = { applications: Record<string, number>; answers: Record<string, number> };
type State = { mode: "calls" | "always" | "off"; ring_min: number; lines: Line[]; ringing: number; by_shadow: number; by_you: number; who?: Who; memory?: Mem };

const MODES: [State["mode"], string, string][] = [
  ["calls", "Two calls, then Shadow", "The engine calls you twice. No pickup, Shadow takes the job."],
  ["always", "Shadow always", "Shadow answers on the form itself. Nothing waits, nothing rings."],
  ["off", "Only me", "Calls ring, Shadow never picks up. Every question waits for you."],
];
const mmss = (x: number) => `${Math.floor(x / 60)}:${String(Math.floor(x % 60)).padStart(2, "0")}`;

export default function ShadowPage() {
  const [s, setS] = useState<State | null>(null);
  const [msg, setMsg] = useState("");
  const [, tick] = useState(0);
  const [pulled, setPulled] = useState(() => Date.now());

  const pull = () => get<State>("/api/shadow").then((d) => { setS(d); setPulled(Date.now()); }).catch((e) => setMsg(e.message));
  useEffect(() => { pull(); const a = poll(pull, 5000), t = setInterval(() => tick((n) => n + 1), 1000); return () => { a(); clearInterval(t); }; }, []);

  const act = async (path: string, body: object, done: string) => {
    try { await post(path, body); await pull(); setMsg(done); } catch (e: any) { setMsg(e.message); }
  };
  const left = (l: Line) => (l.next_s == null ? null : Math.max(0, l.next_s - (Date.now() - pulled) / 1000));
  const ring = (s?.ring_min ?? 5) * 60;
  const open = (s?.lines || []).filter((l) => l.open), closed = (s?.lines || []).filter((l) => !l.open);
  const c1 = open.filter((l) => l.state === "call 1").length, c2 = open.filter((l) => l.state === "call 2").length;
  const live = s?.mode === "calls";

  return (
    <main className="page shadow-page" data-mode={s?.mode}>
      <Nav />
      <header className="hero">
        <h1>Shadow</h1>
        <p className="shadow-tag">Two calls. Then Shadow.</p>
        <p>When a job stops on a question, the engine calls you, then calls again. If neither call is picked up, Shadow,
          your AI delegate, picks up and finishes the application as you, so the engine never stalls.</p>
      </header>
      {msg && <p className="note" role="status">{msg}</p>}

      <section className="card shadow-ignition" aria-label="Ignition sequence">
        <Ignition wide s={s} c1={c1} c2={c2} parked={open.length} live={live} />
        <Ignition s={s} c1={c1} c2={c2} parked={open.length} live={live} />
      </section>

      <Who who={s?.who} />

      <section className="card">
        <h2>Mode</h2>
        <div className="shadow-modes" role="radiogroup" aria-label="Shadow mode">
          {MODES.map(([m, label, about]) => (
            <button key={m} role="radio" aria-checked={s?.mode === m} className={`shadow-mode${s?.mode === m ? " on" : ""}`}
                    onClick={() => act("/api/shadow", { mode: m }, `Mode: ${label}.`)}>
              <b>{label}</b><span className="dim small">{about}</span>
            </button>))}
        </div>
        <label className="row small shadow-idle">Time between calls
          <input type="number" min={0.5} max={240} step={0.5} defaultValue={s?.ring_min ?? 5} key={s?.ring_min}
                 onBlur={(e) => act("/api/shadow", { ring_min: Number(e.target.value) }, "Ring interval saved.")} /> minutes
        </label>
      </section>

      <section className="card">
        <h2>Ringing now</h2>
        {!s ? <p className="dim">Reading the switchboard…</p> : !open.length ? <p className="dim">No calls. Every parked job is answered or with someone.</p> : (
          <ol className="shadow-lines">
            {open.map((l) => {
              const t = left(l), pct = t == null ? 0 : 1 - t / ring;
              return (
                <li key={l.url} className="shadow-line" data-state={l.state}>
                  <div className="shadow-line-head">
                    <span className="shadow-bulbs" aria-hidden="true"><i className="on" /><i className={l.state === "call 2" ? "on" : ""} /><i /></span>
                    <b>{l.job}</b>
                    <span className="dim small">{l.state} · {t == null ? "" : t > 0 ? `${l.state === "call 1" ? "call 2" : "Shadow"} in ${mmss(t)}` : "next tick"}</span>
                  </div>
                  {l.recommend?.length ? (
                    <ul className="shadow-recs">
                      {l.recommend.map((r, i) => (
                        <li key={i} className={r.a ? "" : "shadow-rec-none"}>
                          <span className="dim small">{r.q}</span>
                          <span className="shadow-rec"><em>Shadow recommends</em> <b>{r.a || "nothing on file: it will not invent one"}</b>
                            <span className="dim small"> · {r.from}</span></span>
                        </li>))}
                    </ul>) : l.question && <p className="dim small shadow-q">{l.question}</p>}
                  <div className="shadow-gauge" aria-hidden="true"><span style={{ width: `${Math.round(pct * 100)}%` }} /></div>
                  <p className="row small">
                    <Link className="btn gold" href="/needs" onClick={() => post("/api/shadow/pickup", { url: l.url, who: "you" }).catch(() => {})}>Pick up</Link>
                    <button className="btn" onClick={() => act("/api/shadow/pickup", { url: l.url, who: "shadow" }, `Shadow took ${l.job}.`)}>Let Shadow take it</button>
                  </p>
                </li>);
            })}
          </ol>)}
      </section>

      <MemoryPanel m={s?.memory} />

      <section className="shadow-policy">
        <div className="card">
          <h2>Shadow answers as you</h2>
          <ul className="small">
            <li>The gates treat Shadow and you as the same person: its answers carry the weight of yours.</li>
            <li>Salary: the middle of the posted range, else your market-rate preset, matched to the form's bands.</li>
            <li>Certifications, start dates, addresses, how you heard about the role: from your presets.</li>
            <li>A question the Fact Bank cannot settle: Shadow writes down what it recommends at call 1, so you see it while
              the calls ring. Nobody picks up, Shadow uses it, remembers it, and never drafts that question again.</li>
            <li>It learns: your answers replace its own, and each remembered answer carries its record (submitted, parked
              again, moved forward, corrected by you).</li>
          </ul>
        </div>
        <div className="card">
          <h2>Shadow never</h2>
          <ul className="small">
            <li>Invents experience, a credential or a fact. If the honest answer is no, it says no.</li>
            <li>Ticks a CAPTCHA or a bot check. Those never ring; they wait for you on the Desk.</li>
            <li>Answers EEO questions with anything but a decline.</li>
          </ul>
        </div>
      </section>

      <section className="card">
        <h2>Picked up</h2>
        {!closed.length ? <p className="dim">Nothing yet.</p> : (
          <ol className="shadow-feed">
            {closed.map((l) => (
              <li key={l.url} data-by={l.by || "none"}>
                <span className="dim small">{l.ts.replace("T", " ").slice(5, 16)}</span>
                <b>{l.by === "shadow" ? "Shadow" : l.by === "you" ? "You" : "Closed"}</b>
                <span>{l.job}</span>
              </li>))}
          </ol>)}
      </section>
    </main>
  );
}

// The ignition sequence: parked piston -> call 1 plug -> call 2 plug -> Shadow cylinder. Wide (a row) on desktop,
// tall (a column) on phones, so the labels stay readable at 375 px; CSS shows one of the two.
function Ignition({ wide = false, s, c1, c2, parked, live }: { wide?: boolean; s: State | null; c1: number; c2: number; parked: number; live: boolean }) {
  const pts = wide ? [[90, 120], [330, 120], [570, 120], [850, 120]] : [[170, 70], [170, 250], [170, 420], [170, 600]];
  const wire = wide ? "M120 120 H 840" : "M170 100 V 590";
  return (
    <svg viewBox={wide ? "0 0 960 230" : "0 0 340 720"} className={wide ? "shadow-wide" : "shadow-tall"} role="img"
         aria-label={`Parked ${parked}, call 1 ringing ${c1}, call 2 ringing ${c2}, Shadow picked up ${s?.by_shadow ?? 0}`}>
      <defs>
        <linearGradient id={wide ? "shadowWireW" : "shadowWireT"} gradientUnits="userSpaceOnUse"
                        x1={wide ? 120 : 170} x2={wide ? 840 : 170} y1={wide ? 120 : 100} y2={wide ? 120 : 590}>
          <stop offset="0" stopColor="#f2c14e" /><stop offset="1" stopColor="#a78bfa" />
        </linearGradient>
      </defs>
      <path d={wire} className="shadow-wire" />
      <path d={wire} pathLength={100} className={`shadow-spark${live && parked ? " on" : ""}`} stroke={`url(#${wide ? "shadowWireW" : "shadowWireT"})`} />
      <g transform={`translate(${pts[0][0]} ${pts[0][1]})`}>
        <rect x="-34" y="-46" width="68" height="92" rx="8" className="shadow-block" />
        <rect x="-24" y="-10" width="48" height="26" rx="4" className="shadow-piston stalled" />
        <Label wide={wide} a="Parked" b={`${parked} waiting`} />
      </g>
      {[{ i: 1, n: 1, k: c1 }, { i: 2, n: 2, k: c2 }].map((p) => (
        <g key={p.n} transform={`translate(${pts[p.i][0]} ${pts[p.i][1]})`} className={`shadow-plug${live && p.k ? " ringing" : ""}`}>
          <circle r="44" className="shadow-plug-halo" />
          <circle r="28" className="shadow-plug-body" />
          <path d="M-6 -12 L4 -2 L-2 2 L6 12" className="shadow-bolt" />
          <Label wide={wide} a={`Call ${p.n}`} b={`${p.k} ringing · ${s ? s.ring_min : "…"} min`} />
        </g>))}
      <g transform={`translate(${pts[3][0]} ${pts[3][1]})`} className={`shadow-cyl${s && s.mode !== "off" ? " armed" : ""}`}>
        <rect x="-40" y="-56" width="80" height="112" rx="10" className="shadow-block shadow-block-s" />
        <rect x="-28" y="-34" width="56" height="30" rx="4" className="shadow-piston" />
        <rect x="-4" y="-4" width="8" height="40" className="shadow-rod" />
        <Label wide={wide} a="Shadow" b={`${s?.by_shadow ?? 0} picked up · you ${s?.by_you ?? 0}`} s />
      </g>
    </svg>
  );
}

function Label({ wide, a, b, s = false }: { wide: boolean; a: string; b: string; s?: boolean }) {
  // wide: under the part; tall: to the right of it
  return wide
    ? <><text y={s ? 84 : 74} className={`shadow-node-label${s ? " shadow-s" : ""}`}>{a}</text><text y={s ? 104 : 94} className="shadow-node-sub">{b}</text></>
    : <><text x="62" y="-4" className={`shadow-node-label shadow-left${s ? " shadow-s" : ""}`}>{a}</text><text x="62" y="18" className="shadow-node-sub shadow-left">{b}</text></>;
}

// Who answered in the last 24 h: the same numbers the supervisor sees (engine/shadow.py oversight()).
function Who({ who }: { who?: Who }) {
  const sub = (by: string) => who?.applications?.[`${by}:SUBMITTED`] || 0;
  const rows: [string, string, number][] = [
    ["you", "You", sub("you")], ["shadow", "Shadow", sub("shadow")], ["engine", "Engine rules", sub("engine")],
  ];
  const max = Math.max(1, ...rows.map((r) => r[2]));
  return (
    <section className="card shadow-who" aria-label="Who answered, last 24 hours">
      <h2>Who cleared the forms <span className="dim small">last 24 h · the supervisor sees the same</span></h2>
      {rows.map(([k, label, n]) => (
        <div key={k} className="shadow-bar" data-by={k}>
          <span>{label}</span>
          <span className="shadow-bar-track"><span style={{ width: `${(n / max) * 100}%` }} /></span>
          <b>{n}</b>
        </div>))}
      <p className="dim small">Answers saved: you {who?.answers?.you || 0} · Shadow {who?.answers?.shadow || 0}</p>
    </section>
  );
}

// Shadow's memory: every question it has seen, the answer, who gave it (you win), and how it went. Learned from
// the ledger every 5 minutes (engine/shadow.py learn()), so the same question is never drafted twice.
function MemoryPanel({ m }: { m?: Mem }) {
  return (
    <section className="card shadow-memory" aria-label="Shadow's memory">
      <h2>Shadow's memory <span className="dim small">{m ? `${m.known} questions known · ${m.by_you} answered by you` : ""}</span></h2>
      {!m?.entries?.length ? <p className="dim">Empty so far. Every answer Shadow gives or learns from you lands here.</p> : (
        <ol className="shadow-mem">
          {m.entries.map((e, i) => (
            <li key={i} data-by={e.by} data-weak={e.weak ? "true" : "false"} style={{ animationDelay: `${Math.min(i, 12) * 40}ms` }}>
              <span className="dim small">{e.question}</span>
              <span><b>{e.answer}</b> <span className={`shadow-chip ${e.by}`}>{e.by === "you" ? "you" : "Shadow"}</span>
                <span className="dim small"> used {e.used} · submitted {e.submitted || 0}{e.moved_forward ? ` · ${e.moved_forward} moved forward` : ""}
                  {e.overridden ? ` · you corrected it ${e.overridden}×` : ""}{e.weak ? " · weak: rethinking" : ""}</span></span>
            </li>))}
        </ol>)}
    </section>
  );
}
