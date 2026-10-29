"use client";
// Maintenance (v1.2; "the oil change" in the engine picture): the daily clean-up of what applications leave behind.
// The tank holds the engine's working data; every leftover the supervisor measures (expired files, old code and alert
// mail, Docker cache, closed postings, an applier whose browser has grown) floats in it as a dot, and the tank darkens
// as health falls. A clean-up (engine/oilchange.py, every 24 h or sooner when something fills up) plays each step as
// it happens: clear expired files, tidy the inbox, free machine space, refresh the job queue, health check. From the
// click until the run ends the page polls every second and holds each step on screen for at least MIN_MS.
import { useEffect, useMemo, useRef, useState } from "react";
import { Nav } from "../nav";
import { PUBLIC } from "@/lib/engine";
import { get, post, poll } from "@/lib/types";

type Stage = { name: string; secs?: number; removed?: number; freed_mb?: number; error?: string; skipped?: string; [k: string]: any };
type Run = { started: number; finished?: number; by?: string; stages: Stage[]; freed_mb?: number; removed?: number };
type Oil = {
  life: number | null; wear: Record<string, number>; contaminants: Record<string, any>; limits: Record<string, number>;
  interval_h: number; change_at: number; stages: string[]; running: boolean; stage: string | null; run: Run | null;
  last_change: number | null; next_due: number | null; inspected: number | null; requested: boolean; history: Run[]; now: number;
};

const STAGES = ["drain", "filter", "flush", "refill", "check"] as const;
// stage names stay the engine's (engine/oilchange.py); what each one does is said in job-search terms
const ABOUT: Record<string, [string, string]> = {
  drain: ["Clear expired files", "tailored resumes, job-description copies, logs and old batches past their keep-by date are deleted; proof screenshots are shrunk, never lost"],
  filter: ["Tidy the inbox", "verification-code emails (2 days+) and job-alert emails (7 days+) move to Gmail's Bin, undoable for 30 days; starred mail is never touched"],
  flush: ["Free machine space", "unused Docker cache is cleared, and an applier whose browser has grown is restarted between applications"],
  refill: ["Refresh the job queue", "postings older than 45 days, and jobs already applied to or ruled out, leave the queue so only live openings remain"],
  check: ["Health check", "measure everything again and record the new health score"],
};
// which leftover each stage clears, and the dot color it has in the tank
const KIND: Record<string, { stage: string; label: string; color: string }> = {
  workspace_mb: { stage: "drain", label: "Expired files", color: "#9aa7b8" },
  old_mail: { stage: "filter", label: "Old code and job-alert mail", color: "#ff7a6b" },
  build_cache_gb: { stage: "flush", label: "Docker cache", color: "#6fb7ff" },
  applier_mb: { stage: "flush", label: "Applier memory", color: "#b18cff" },
  stale_queue: { stage: "refill", label: "Stale postings", color: "#5ee6b5" },
};
// the engine is a metaphor; this is what each part means for a job search
const GLOSSARY: [string, string][] = [
  ["Oil", "the engine's working data: queue, resumes, mail, cache. Clean oil means applications go out fast and nothing stale is picked."],
  ["Oil change", "this page: the daily clean-up of leftovers that slow the engine down."],
  ["Health (oil life)", "100% right after a clean-up; it falls with time and with whichever leftover is closest to its limit."],
  ["Cylinders and pistons", "the seven working views (Live, Control, Applications, Needs you, Reach, Outreach, Evals); a firing piston is that view doing work."],
  ["Fuel", "your Fact Bank: every resume line is burned from a fact you can prove."],
  ["Gears", "speed: how many appliers run at once and how often job boards are scanned."],
  ["Clutch", "whether lessons learned from rejections are allowed to change which jobs are applied to."],
  ["Wiring", "the memory graph linking you, applications, companies, facts and outcomes."],
  ["MCP cord", "where your AI assistant plugs in to operate the engine."],
];
const MIN_MS = 2800;  // each stage stays on screen at least this long, however fast the server ran it

// a believable dirty engine for the public site (no supervisor there): numbers are illustrative
const DEMO: Oil = {
  life: 18, wear: { age: 64, workspace_mb: 41, old_mail: 82, build_cache_gb: 76, stale_queue: 33 },
  contaminants: { workspace_files: 212, workspace_mb: 164, mail: { codes: 141, alerts: 105 }, old_mail: 246, build_cache_gb: 4.6,
                  build_cache_total_gb: 9.1, dangling_images: 3, queue: 1580, stale_queue: 99, foreign_stopped: [], bloated: [] },
  limits: { workspace_mb: 400, build_cache_gb: 6, old_mail: 300, stale_queue: 300, applier_mb: 1400 }, interval_h: 24, change_at: 10,
  stages: [...STAGES], running: false, stage: null, run: null, last_change: null, next_due: null, inspected: null, requested: false,
  history: [], now: 0,
};

// oil color: fresh amber at life 100, sludge at 0
const mix = (a: number[], b: number[], t: number) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
const oilColor = (life: number) => { const [r, g, b] = mix([240, 182, 76], [44, 30, 14], Math.min(1, Math.max(0, (100 - life) / 100))); return `rgb(${r},${g},${b})`; };

// deterministic scatter inside the sump (so particles do not jump on every poll)
function rand(seed: number) { let s = seed; return () => ((s = (s * 16807) % 2147483647) / 2147483647); }
const PAN = { top: 332, bottom: 428, left: 160, right: 520 }, PLUG = { x: 340, y: 432 }, FILTER = { x: 700, y: 250 }, DRUM = { x: 1000, y: 470 };

const ago = (t?: number | null, now = Date.now() / 1000) => {
  if (!t) return "never";
  const s = Math.max(0, now - t);
  return s < 90 ? `${Math.round(s)} s ago` : s < 5400 ? `${Math.round(s / 60)} min ago` : s < 172800 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} d ago`;
};
const until = (t?: number | null, now = Date.now() / 1000) => {
  if (!t) return "now";
  const s = t - now;
  return s <= 0 ? "due now" : s < 5400 ? `in ${Math.round(s / 60)} min` : `in ${(s / 3600).toFixed(1)} h`;
};
const when = (t?: number) => (t ? new Date(t * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "");

export default function OilChange() {
  const [oil, setOil] = useState<Oil | null>(null);
  const [msg, setMsg] = useState("");
  const [sim, setSim] = useState<string | null>(null);  // the public site plays the change locally
  // real time: from the click until the run ends the page polls every second; every stage the server reports
  // (running now, or finished between two polls) is queued and shown in order for at least MIN_MS
  const [shown, setShown] = useState<string | null>(null);
  const fast = useRef(false), kick = useRef<() => void>(() => {});
  const queue = useRef<string[]>([]), seen = useRef(new Set<string>()), runKey = useRef<number | null>(null);
  const shownRef = useRef<string | null>(null), since = useRef(0), asked = useRef(0), before = useRef<number | null>(null);
  const latest = useRef<Oil | null>(null);

  useEffect(() => {
    if (PUBLIC) { setOil(DEMO); return; }
    let stop = () => {};
    const busy = (o: Oil) => o.running || o.requested || !!asked.current || !!shownRef.current || queue.current.length > 0;
    const pull = () => get<Oil>("/api/control/oilchange").then((o) => {
      latest.current = o;
      // the run to show: the one running now, or the one that finished since you asked
      const run = o.running ? o.run : asked.current && o.history?.[0] && o.history[0].started >= asked.current - 5 ? o.history[0] : null;
      if (run && run.started !== runKey.current) { runKey.current = run.started; seen.current = new Set(); if (before.current == null) before.current = o.life; }
      if (run) {
        for (const n of [...run.stages.map((s) => s.name), ...(o.running && o.stage ? [o.stage] : [])])
          if (!seen.current.has(n)) { seen.current.add(n); queue.current.push(n); }
        if (!o.running) asked.current = 0;
      }
      setOil(o);
      const f = busy(o);
      if (f !== fast.current) { fast.current = f; stop(); stop = poll(pull, f ? 1000 : 15000); }
    }).catch((e) => setMsg(`maintenance status unreachable: ${e.message}`));
    kick.current = () => { fast.current = true; stop(); stop = poll(pull, 1000); };
    pull();
    stop = poll(pull, 15000);
    // the stage player: hold each stage MIN_MS, and keep the one the server is still running on screen
    const t = setInterval(() => {
      const cur = shownRef.current, o = latest.current;
      if (cur && Date.now() - since.current < MIN_MS) return;
      if (cur && !queue.current.length && o?.running && o.stage === cur) return;
      const next = queue.current.shift() ?? null;
      if (next !== cur) {
        shownRef.current = next; since.current = Date.now(); setShown(next);
        if (!next) before.current = null;
      }
    }, 200);
    return () => { stop(); clearInterval(t); };
  }, []);

  const stage = sim || shown;
  const idx = stage ? STAGES.indexOf(stage as any) : -1;
  const doneStages: string[] = stage ? STAGES.slice(0, idx) : (oil?.history?.[0]?.stages || []).map((s) => s.name);
  // health: the old reading until the tank is refilled on screen, then the new one
  const life = sim ? (idx >= 3 ? 96 : oil?.life ?? 100) : shown && idx < 3 && before.current != null ? before.current : oil?.life ?? 100;
  const color = oilColor(life);
  // sump level: low while drained (drain .. flush), rising on refill
  const level = stage === "drain" || stage === "filter" || stage === "flush" ? 0.06 : 0.82;
  const oilTop = PAN.bottom - level * (PAN.bottom - PAN.top);

  // particles: up to 46, shared out by how much each contaminant has used of its limit
  const particles = useMemo(() => {
    const wear = oil?.wear || {};
    const kinds = Object.keys(KIND).filter((k) => (wear[k] || 0) > 0);
    const total = kinds.reduce((a, k) => a + wear[k], 0);
    const n = Math.round(46 * Math.min(1, total / 220));
    const r = rand(7);
    const out: { k: string; x: number; y: number; s: number; d: number }[] = [];
    kinds.forEach((k) => {
      const m = Math.max(1, Math.round((n * wear[k]) / (total || 1)));
      for (let i = 0; i < m; i++) out.push({ k, x: PAN.left + 30 + r() * (PAN.right - PAN.left - 60), y: PAN.top + 18 + r() * 70, s: 2.5 + r() * 3.5, d: r() * -6 });
    });
    return out;
  }, [oil?.wear]);

  const ask = async () => {
    setMsg("");
    if (PUBLIC) {  // demo: play every stage for 2.6 s
      let i = 0;
      setSim(STAGES[0]);
      const t = setInterval(() => { i += 1; if (i >= STAGES.length) { clearInterval(t); setSim(null); setOil({ ...DEMO, life: 97, wear: { age: 0, workspace_mb: 1, old_mail: 0, build_cache_gb: 8, stale_queue: 0 } }); } else setSim(STAGES[i]); }, 2600);
      return;
    }
    try {
      asked.current = Date.now() / 1000; before.current = oil?.life ?? null;
      kick.current();  // poll every second from now on, so no stage is missed
      setOil(await post<Oil>("/api/control/oilchange", {}));
      setMsg("Clean-up requested: the supervisor starts it within 15 seconds, and each step plays here as it runs.");
    } catch (e: any) { setMsg(e.message); }
  };

  const c = oil?.contaminants || {};
  const now = oil?.now || Date.now() / 1000;
  const due = oil ? life <= oil.change_at : false;
  const gaugeA = -120 + (240 * life) / 100;  // needle angle
  const rows: [string, string, string, number][] = [  // key, label, amount, wear %
    ["age", "Since last clean-up", oil?.last_change ? ago(oil.last_change, now) : "never cleaned", oil?.wear.age ?? 0],
    ["workspace_mb", "Expired files", `${c.workspace_files ?? "·"} files · ${c.workspace_mb ?? "·"} MB of ${oil?.limits.workspace_mb ?? 400}`, oil?.wear.workspace_mb ?? 0],
    ["old_mail", "Old code and job-alert mail", c.mail?.skipped ? c.mail.skipped : `${c.mail?.codes ?? "·"} code · ${c.mail?.alerts ?? "·"} alert of ${oil?.limits.old_mail ?? 300}`, oil?.wear.old_mail ?? 0],
    ["build_cache_gb", "Unused Docker cache", `${c.build_cache_gb ?? "·"} GB of ${oil?.limits.build_cache_gb ?? 6} · ${c.dangling_images ?? 0} dangling images`, oil?.wear.build_cache_gb ?? 0],
    ["stale_queue", "Closed or stale postings in the queue", `${c.stale_queue ?? "·"} of ${c.queue ?? "·"} queued (limit ${oil?.limits.stale_queue ?? 300})`, oil?.wear.stale_queue ?? 0],
    ["applier_mb", "Appliers using too much memory", (c.bloated || []).length ? c.bloated.map((b: any) => `${b.name} ${b.mem_mb} MB`).join(", ") : `none over ${oil?.limits.applier_mb ?? 1400} MB`, oil?.wear.applier_mb ?? 0],
  ];
  const lastRun = oil?.running ? oil.run : oil?.history?.[0];

  return (
    <main className={`page oc${stage ? ` oc-run oc-st-${stage}` : ""}${due ? " oc-due" : ""}`} style={{ ["--oil" as any]: color }}>
      <Nav />
      <header className="hero">
        <h1>Maintenance</h1>
        <p>Every application leaves something behind: a tailored resume, a copy of the job description, a verification-code
          email, a job-alert email, a posting that has since closed. Left alone, they slow the search down and stale jobs
          creep back into the queue. The engine measures these leftovers every five minutes and clears them once a day,
          sooner when one fills up (in the engine picture, this is the oil change). Your Fact Bank, your answers, the
          application log with its proof, and starred mail are never touched.</p>
      </header>
      {msg && <p className="note" role="status">{msg}</p>}

      <section className="oc-stage">
        <svg className="oc-svg" viewBox="0 0 1180 560" role="img"
             aria-label={`Engine health ${life} percent${stage ? `, clean-up running: ${ABOUT[stage]?.[0] ?? stage}` : ""}`}>
          <defs>
            <linearGradient id="ocsteel" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#3a4556" /><stop offset=".55" stopColor="#1d2530" /><stop offset="1" stopColor="#11161d" /></linearGradient>
            <linearGradient id="ocfilter" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#1b4f8a" /><stop offset=".45" stopColor="#3d8ee0" /><stop offset="1" stopColor="#163e6d" /></linearGradient>
            <linearGradient id="ocold" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#3b2f22" /><stop offset=".45" stopColor="#5e4b33" /><stop offset="1" stopColor="#2b2219" /></linearGradient>
            <clipPath id="ocpan"><path d={`M${PAN.left - 20} ${PAN.top} H${PAN.right + 20} L${PAN.right - 20} ${PAN.bottom} H${PAN.left + 20} Z`} /></clipPath>
            <filter id="ocglow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          </defs>

          {/* oil circulation: sump -> pump -> filter -> gallery -> back down to the sump */}
          <path id="occirc" className="oc-circ" d={`M ${PAN.right - 40} ${PAN.bottom - 20} C 600 420 640 380 ${FILTER.x} ${FILTER.y + 92} L ${FILTER.x} ${FILTER.y - 88} L ${FILTER.x - 40} 152 L 150 152 L 150 ${PAN.top + 20}`} />
          {!stage && [0, 1, 2, 3, 4, 5].map((k) => (
            <circle key={k} className="oc-drop" r={4.5}><animateMotion dur="7s" begin={`${-k * 1.15}s`} repeatCount="indefinite"><mpath href="#occirc" /></animateMotion></circle>))}

          {/* engine block: three heads, the crank turning, the filler cap */}
          <g className="oc-block">
            {[200, 300, 400].map((x) => <rect key={x} className="oc-head" x={x} y={58} width={80} height={46} rx={10} />)}
            <path className="oc-case" d="M140 100 H540 V332 H140 Z" />
            {Array.from({ length: 6 }, (_, f) => <rect key={f} className="oc-fin" x={150} y={116 + f * 14} width={380} height={4} rx={2} />)}
            <g transform="translate(340 250)"><g className="oc-crank">
              <circle r={52} className="oc-crank-web" /><rect x={-8} y={-48} width={16} height={40} rx={6} className="oc-crank-pin" /><circle r={11} className="oc-crank-bore" />
            </g></g>
            <rect className="oc-cap" x={456} y={40} width={30} height={20} rx={5} />
            <text className="oc-label" x={340} y={36}>REGEN</text>
          </g>

          {/* refill jug: tips over the filler cap on refill */}
          <g className="oc-jug" transform="translate(520 -10)">
            <path d="M0 10 H54 V70 H0 Z" className="oc-jug-body" /><rect x={8} y={0} width={20} height={14} rx={3} className="oc-jug-body" />
            <text className="oc-tiny" x={27} y={46}>live jobs</text>
          </g>
          <path className="oc-pour" d="M 470 34 L 470 330" />

          {/* the sump: oil, a wave on top, particles of every contaminant */}
          <path className="oc-pan" d={`M${PAN.left - 20} ${PAN.top} H${PAN.right + 20} L${PAN.right - 20} ${PAN.bottom} H${PAN.left + 20} Z`} />
          <g clipPath="url(#ocpan)">
            <rect className="oc-oil" x={PAN.left - 30} y={oilTop} width={PAN.right - PAN.left + 60} height={PAN.bottom - oilTop + 10} />
            <path className="oc-wave" d={`M ${PAN.left - 60} ${oilTop} q 25 -6 50 0 t 50 0 t 50 0 t 50 0 t 50 0 t 50 0 t 50 0 t 50 0 t 50 0 t 50 0 V ${oilTop + 8} H ${PAN.left - 60} Z`} />
            {particles.map((p, i) => (
              <circle key={i} className={`oc-p k-${KIND[p.k].stage}`} cx={p.x} cy={Math.max(p.y, oilTop + 6)} r={p.s} fill={KIND[p.k].color}
                      style={{ animationDelay: `${p.d}s`, ["--dx" as any]: `${(KIND[p.k].stage === "filter" ? FILTER.x : KIND[p.k].stage === "flush" ? DRUM.x : PLUG.x) - p.x}px`,
                               ["--dy" as any]: `${(KIND[p.k].stage === "filter" ? FILTER.y : KIND[p.k].stage === "flush" ? DRUM.y : 520) - p.y}px` }} />))}
          </g>
          <text className="oc-label" x={340} y={PAN.bottom + 2} dy={-8}>working data</text>

          {/* drain plug, the dark stream and the catch tray */}
          <rect className="oc-plug" x={PLUG.x - 10} y={PLUG.y - 4} width={20} height={12} rx={3} />
          <path className="oc-stream" d={`M ${PLUG.x} ${PLUG.y + 8} C ${PLUG.x + 6} 470 ${PLUG.x - 4} 490 ${PLUG.x} 508`} />
          <path className="oc-tray" d={`M ${PLUG.x - 80} 506 H ${PLUG.x + 80} L ${PLUG.x + 66} 536 H ${PLUG.x - 66} Z`} />
          <text className="oc-tiny" x={PLUG.x} y={552}>expired files</text>

          {/* filter mount and two canisters: the old one leaves for the Bin, the new one screws in */}
          <rect className="oc-mount" x={FILTER.x - 58} y={FILTER.y - 108} width={116} height={20} rx={5} />
          <g className="oc-filter old">
            <rect x={FILTER.x - 44} y={FILTER.y - 88} width={88} height={180} rx={18} fill="url(#ocold)" />
            {Array.from({ length: 7 }, (_, k) => <line key={k} x1={FILTER.x - 30 + k * 10} y1={FILTER.y - 70} x2={FILTER.x - 30 + k * 10} y2={FILTER.y + 74} />)}
            <text className="oc-tiny dark" x={FILTER.x} y={FILTER.y + 6}>{life < 50 ? "full" : "inbox"}</text>
          </g>
          <g className="oc-filter new">
            <rect x={FILTER.x - 44} y={FILTER.y - 88} width={88} height={180} rx={18} fill="url(#ocfilter)" />
            {Array.from({ length: 7 }, (_, k) => <line key={k} x1={FILTER.x - 30 + k * 10} y1={FILTER.y - 70} x2={FILTER.x - 30 + k * 10} y2={FILTER.y + 74} />)}
            <text className="oc-tiny" x={FILTER.x} y={FILTER.y + 6}>tidy</text>
          </g>
          <text className="oc-label" x={FILTER.x} y={FILTER.y - 118}>inbox filter</text>

          {/* where things go: Gmail's Bin (undoable for 30 days) and the Docker sludge drum */}
          <g className="oc-bin" transform="translate(840 430)">
            <path d="M0 0 H110 L100 96 H10 Z" /><rect x={-6} y={-12} width={122} height={12} rx={4} />
            <text className="oc-tiny" x={55} y={44}>Gmail Bin</text>
            <text className="oc-num" x={55} y={66}>{c.old_mail ?? 0} mails</text>
          </g>
          <path className="oc-flushline" d={`M ${PAN.right + 4} ${PAN.top + 60} C 760 420 860 360 ${DRUM.x} ${DRUM.y - 40}`} />
          <g className="oc-drum" transform={`translate(${DRUM.x - 50} ${DRUM.y - 40})`}>
            <rect width={100} height={110} rx={12} /><line x1={0} y1={36} x2={100} y2={36} /><line x1={0} y1={74} x2={100} y2={74} />
            <text className="oc-tiny" x={50} y={26}>Docker</text>
            <text className="oc-num" x={50} y={60}>{c.build_cache_gb ?? 0} GB</text>
            <text className="oc-tiny" x={50} y={98}>cache</text>
          </g>

          {/* oil-life gauge */}
          <g transform="translate(1040 190)" className="oc-gauge">
            <path className="oc-arc" d="M -95 55 A 110 110 0 1 1 95 55" />
            <path className="oc-arc red" d="M -95 55 A 110 110 0 0 1 -108 -20" />
            <g style={{ transform: `rotate(${gaugeA}deg)` }} className="oc-needle"><line x1={0} y1={0} x2={0} y2={-92} /><circle r={9} /></g>
            <text className="oc-life" y={44}>{oil?.life == null && !sim ? "·" : `${Math.round(life)}%`}</text>
            <text className="oc-tiny" y={66}>health</text>
          </g>
        </svg>

        <aside className="oc-side">
          <ol className="oc-steps" aria-label="Clean-up steps">
            {STAGES.map((s, i) => {
              const res = (sim ? undefined : lastRun?.stages.find((x) => x.name === s));
              const state = stage === s ? "on" : doneStages.includes(s) ? "done" : "wait";
              return (
                <li key={s} className={`oc-step ${state}`}>
                  <span className="oc-dot">{state === "done" ? "✓" : i + 1}</span>
                  <div><b>{ABOUT[s][0]}</b><small>{ABOUT[s][1]}</small>
                    {res && <em>{res.error ? `error: ${res.error}` : res.skipped ? res.skipped :
                      s === "check" ? `health ${res.life_before ?? "·"}% → ${res.life_after ?? "·"}%` :
                      `${res.removed ?? 0} removed${res.freed_mb ? ` · ${res.freed_mb} MB freed` : ""}`}</em>}
                  </div>
                </li>);
            })}
          </ol>
          <button className="oc-btn" onClick={ask} disabled={!!stage || !!oil?.requested}>
            {stage ? `${ABOUT[stage]?.[0] ?? stage}…` : oil?.requested ? "Requested: starting…" : PUBLIC ? "Play a clean-up" : "Clean up now"}
          </button>
          <dl className="oc-facts">
            <div><dt>Next clean-up</dt><dd>{due ? "due now" : until(oil?.next_due, now)}</dd><small>every {oil?.interval_h ?? 24} h, or when health falls to {oil?.change_at ?? 10}%</small></div>
            <div><dt>Last clean-up</dt><dd>{ago(oil?.last_change, now)}</dd><small>{oil?.history?.[0] ? `${oil.history[0].freed_mb ?? 0} MB, ${oil.history[0].removed ?? 0} items` : "none yet"}</small></div>
          </dl>
        </aside>
      </section>

      <section className="oc-grid">
        <div className="oc-card">
          <h2>What is slowing the engine</h2>
          <p className="dim small">Each line shows how close a leftover is to its limit; the fullest one (or the time since the last clean-up) sets the health score.
            Inspected {ago(oil?.inspected, now)}.</p>
          <ul className="oc-rows">
            {rows.map(([k, label, amount, w]) => (
              <li key={k}>
                <span className="oc-swatch" style={{ background: KIND[k]?.color || "#f2c14e" }} />
                <div className="oc-row-text"><b>{label}</b><small>{amount}</small></div>
                <div className="oc-bar" aria-label={`${Math.round(w)} percent`}><i style={{ width: `${Math.min(100, w)}%` }} className={w >= 90 ? "hot" : w >= 60 ? "warm" : ""} /></div>
                <span className="oc-pct">{Math.round(w)}%</span>
              </li>))}
          </ul>
          {!!(c.foreign_stopped || []).length && (
            <p className="dim small">Left alone (other projects&apos; stopped containers, yours to decide): {c.foreign_stopped.join(", ")}.</p>)}
        </div>
        <div className="oc-card">
          <h2>Clean-up history</h2>
          <ul className="oc-hist">
            {(oil?.history || []).map((h) => (
              <li key={h.started}>
                <time>{when(h.started)}</time>
                <span>{h.freed_mb ?? 0} MB freed · {h.removed ?? 0} items</span>
                <small>{h.by} · health {h.stages.find((s) => s.name === "check")?.life_before ?? "·"}% → {h.stages.find((s) => s.name === "check")?.life_after ?? "·"}%</small>
              </li>))}
            {!oil?.history?.length && <li className="dim">No clean-up yet. The first runs when health reaches {oil?.change_at ?? 10}% or when you ask.</li>}
          </ul>
        </div>
      </section>

      <section className="oc-card oc-key">
        <h2>How to read the engine</h2>
        <p className="dim small">REGEN is drawn as an engine because a job search runs like one: fuel in, work done in
          cycles, speed you can shift, upkeep so it keeps running. Each part stands for one thing:</p>
        <dl>
          {GLOSSARY.map(([t, d]) => <div key={t}><dt>{t}</dt><dd>{d}</dd></div>)}
        </dl>
      </section>
    </main>
  );
}
