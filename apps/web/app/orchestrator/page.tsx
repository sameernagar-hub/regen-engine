"use client";
// The fuel rail (11-23): the agent orchestrator (engine/orchestrator.py) as a common-rail injection system.
//   pump      = the supervisor: one stroke per 15 s tick (the pump pulses when the state file's tick time moves)
//   chamber   = queued tasks waiting for a free lease (one droplet each)
//   rail      = pressure line to every agent; it flows while any task holds a lease
//   injectors = the agents: a firing one sprays (its task holds the lease), a held one shows its valve shut and why
//               (ladder level, budget, pause, backoff), a finished one counts its clean runs today
//   sump      = the dead letter: tasks that used every attempt drip into it
// The supervisor is the only dispatcher: the buttons only write a request (fire once, pause, resume) that the next
// tick acts on.
import { useEffect, useRef, useState } from "react";
import { Nav } from "../nav";
import { get, post, poll } from "@/lib/types";

type Agent = { kind: string; every?: number; at_hour?: number; needs?: number; budget?: number; why?: string;
  paused?: boolean; runs?: number; runs_day?: string };
type Task = { id: string; agent: string; state: string; attempts: number; updated: number; by?: string;
  held?: string | null; result?: string; last_error?: string; payload?: { target?: string } };
type Orch = { ts: number | null; level: number | null; running: number; agents: Record<string, Agent>; open: Task[]; recent: Task[] };
type Mode = "firing" | "held" | "paused" | "dead" | "done" | "idle";

const W = 1120, RAIL_Y = 120, PUMP_X = 90, FIRST_X = 250, SUMP_X = 1040;
const today = () => new Date().toLocaleDateString("en-CA");  // local YYYY-MM-DD, as the engine stamps runs_day
const ago = (t?: number | null) => {
  if (!t) return "never";
  const s = Math.max(0, Date.now() / 1000 - t);
  return s < 90 ? `${Math.round(s)} s ago` : s < 5400 ? `${Math.round(s / 60)} min ago` : `${Math.round(s / 3600)} h ago`;
};
const cadence = (a: Agent) => a.every ? `every ${Math.round(a.every / 3600)} h` : a.at_hour != null ? `daily after ${a.at_hour}:00` : "Shadow's plan / on demand";
const label = (n: string) => n.replace(/^hn$/, "HN boards").replace(/^hn/, "HN").replace(/_/g, " ");

function modeOf(name: string, o: Orch): Mode {
  if (o.agents[name]?.paused) return "paused";
  const open = o.open.filter((t) => t.agent === name);
  if (open.some((t) => t.state === "leased")) return "firing";
  if (open.some((t) => t.state === "held")) return "held";
  const last = o.recent.find((t) => t.agent === name);
  return last?.state === "failed" ? "dead" : last?.state === "done" ? "done" : "idle";
}

export default function FuelRail() {
  const [o, setO] = useState<Orch | null>(null);
  const [pick, setPick] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [stroke, setStroke] = useState(0);  // bumps once per supervisor tick: restarts the pump's CSS stroke
  const lastTick = useRef<number | null>(null);

  useEffect(() => {
    const pull = () => get<Orch>("/api/control/orchestrator").then((x) => {
      if (x.ts && x.ts !== lastTick.current) { lastTick.current = x.ts; setStroke((k) => k + 1); }
      setO(x);
    }).catch((e) => setMsg(`orchestrator unreachable: ${e.message}`));
    pull();
    return poll(pull, 5000);
  }, []);

  const names = Object.keys(o?.agents || {});
  const gap = names.length > 1 ? (SUMP_X - 120 - FIRST_X) / (names.length - 1) : 0;
  const xOf = (i: number) => FIRST_X + i * gap;
  const queued = (o?.open || []).filter((t) => t.state === "queued");
  const dead = (o?.recent || []).filter((t) => t.state === "failed");
  const flowing = (o?.running ?? 0) > 0 || (o?.open || []).some((t) => t.state === "leased");
  const sel = pick && o?.agents[pick] ? pick : null;

  const act = async (action: "run" | "pause" | "resume", agent: string) => {
    if (busy) return;
    setBusy(true);
    setMsg("");
    try {
      const r = await post<Record<string, string>>("/api/control/orchestrator", { action, agent });
      setMsg(action === "run" ? `${label(agent)}: sent to the pump. It fires on the next stroke (≤ 15 s).`
                              : `${label(agent)}: ${action === "pause" ? "pause" : "resume"} sent; the pump applies it on the next stroke.`);
      setO(await get<Orch>("/api/control/orchestrator"));
    } catch (e: any) {
      setMsg(`${label(agent)}: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  const tasks = [...(o?.open || []), ...(o?.recent || [])];
  return (
    <main className="page fr">
      <Nav />
      <header className="hero">
        <h1>Fuel rail</h1>
        <p>The crew that works while you sleep. Every 15 seconds the supervisor kicks the pump and work shoots down the
          rail: HN hiring threads at 7 a.m., outreach drafts right after, reply-rate checks, dead boards brought back to
          life, and Shadow going back for the jobs it parked.</p>
        <p>Gold is firing. Amber means the valve is shut, and hovering tells you why: Shadow hasn't earned that rung yet,
          today's budget is spent, or you paused it. A job that fails three times drops into the sump instead of looping
          forever. Hit any injector to fire it by hand. Nothing gets past the ladder or the kill switch.</p>
      </header>
      {msg && <p className="note" role="status">{msg}</p>}

      <section className="fr-stage">
        <svg className="fr-svg" viewBox={`0 0 ${W} 380`} role="img"
             aria-label={`Fuel rail: ${names.length} agents, ${o?.running ?? 0} firing, ${queued.length} queued, ${dead.length} in the dead letter`}>
          {/* pump: body, piston (one stroke per tick), the chamber of queued droplets */}
          <g className="fr-pump" transform={`translate(${PUMP_X} ${RAIL_Y})`}>
            <rect className="fr-body" x={-46} y={-70} width={92} height={190} rx={14} />
            <g key={stroke} className="fr-piston"><rect x={-30} y={-62} width={60} height={22} rx={5} /><rect className="fr-rod" x={-5} y={-92} width={10} height={32} /></g>
            <rect className="fr-chamber" x={-32} y={-26} width={64} height={128} rx={8} />
            {queued.slice(0, 12).map((t, i) => (
              <circle key={t.id} className="fr-drop q" cx={-16 + (i % 3) * 16} cy={88 - Math.floor(i / 3) * 18} r={6}><title>{label(t.agent)} queued</title></circle>))}
            <text className="fr-cap" y={142}>pump · supervisor</text>
            <text className="fr-small" y={160}>stroke {ago(o?.ts)}</text>
          </g>

          {/* rail: a pressure line from the pump past every injector to the sump */}
          <path className={`fr-rail${flowing ? " flow" : ""}`} d={`M${PUMP_X + 46} ${RAIL_Y} H${SUMP_X}`} />
          {flowing && <path className="fr-rail-core" d={`M${PUMP_X + 46} ${RAIL_Y} H${SUMP_X}`} />}

          {names.map((n, i) => {
            const m: Mode = o ? modeOf(n, o) : "idle", x = xOf(i), a = o!.agents[n];
            const why = o!.open.find((t) => t.agent === n && t.state === "held")?.held;
            const runs = a.runs_day === today() ? a.runs ?? 0 : 0;
            return (
              <g key={n} className={`fr-inj ${m}${sel === n ? " sel" : ""}`} transform={`translate(${x} ${RAIL_Y})`}
                 role="button" tabIndex={0} aria-label={`${label(n)}: ${m}${why ? `, ${why}` : ""}`}
                 onClick={() => setPick(n)} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setPick(n))}>
                <rect className="fr-stem" x={-7} y={0} width={14} height={34} />
                <path className="fr-housing" d="M-20 34 H20 V96 L8 118 H-8 L-20 96 Z" />
                <rect className="fr-valve" x={-12} y={50} width={24} height={8} rx={3} />
                {m === "firing" && <g className="fr-spray">{[0, 1, 2, 3, 4, 5].map((k) => <circle key={k} className={`s s${k}`} cx={0} cy={124} r={3} />)}</g>}
                {m === "held" && <text className="fr-shut" y={150}>valve shut</text>}
                <text className="fr-name" y={-20}>{label(n)}</text>
                <text className="fr-small" y={m === "held" ? 166 : 150}>{runs}/{a.budget} today</text>
                {why && <title>{why}</title>}
              </g>);
          })}

          {/* sump: the dead letter */}
          <g className="fr-sump" transform={`translate(${SUMP_X} ${RAIL_Y})`}>
            <path className="fr-drain" d="M0 0 V120" />
            {dead.length > 0 && <circle className="fr-drop drip" cx={0} cy={10} r={5} />}
            <rect className="fr-tank" x={-44} y={120} width={88} height={96} rx={10} />
            <rect className="fr-level" x={-40} y={212 - Math.min(88, dead.length * 11)} width={80} height={Math.min(88, dead.length * 11)} rx={6} />
            <text className="fr-cap" y={236}>sump · dead letter</text>
            <text className="fr-small" y={254}>{dead.length} failed</text>
          </g>
        </svg>
      </section>

      <section className="fr-panel">
        <dl className="fr-gauges">
          <div><dt>firing</dt><dd>{o?.running ?? "·"}</dd></div>
          <div><dt>queued</dt><dd>{queued.length}</dd></div>
          <div><dt>held</dt><dd>{(o?.open || []).filter((t) => t.state === "held").length}</dd></div>
          <div><dt>Shadow level</dt><dd>{o?.level ?? "·"}</dd></div>
        </dl>
        {sel && o ? (() => {
          const a = o.agents[sel], m = modeOf(sel, o), locked = (a.needs ?? 0) > (o.level ?? 0);
          return (
            <article className={`fr-card ${m}`}>
              <h2>{label(sel)} <span className={`tag ${m}`}>{m}</span></h2>
              <p className="dim small">{a.why}</p>
              <ul>
                <li><span>fires</span>{cadence(a)}</li>
                <li><span>needs</span>{a.needs ? `Shadow level ${a.needs}${locked ? " (locked)" : ""}` : "supervisor, always"}</li>
                <li><span>budget</span>{a.runs_day === today() ? a.runs ?? 0 : 0} of {a.budget} runs today</li>
                <li><span>runs as</span>{a.kind === "proc" ? "a child process with a lease" : "an in-process call"}</li>
              </ul>
              <div className="fr-btns">
                <button className="fr-btn go" disabled={busy || a.paused || locked} onClick={() => act("run", sel)}>Fire once now</button>
                <button className="fr-btn" disabled={busy} onClick={() => act(a.paused ? "resume" : "pause", sel)}>{a.paused ? "Resume" : "Pause"}</button>
              </div>
            </article>);
        })() : <p className="dim small">Pick an injector to see its schedule, budget and controls.</p>}
      </section>

      <section className="fr-tasks">
        <h2>Tasks</h2>
        <table>
          <thead><tr><th>agent</th><th>state</th><th>try</th><th>from</th><th>updated</th><th>detail</th></tr></thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.id}>
                <td>{label(t.agent)}{t.payload?.target ? <span className="dim"> · {t.payload.target}</span> : null}</td>
                <td><span className={`tag ${t.state}`}>{t.state}</span></td>
                <td>{t.attempts}</td><td className="dim">{t.by}</td><td className="dim">{ago(t.updated)}</td>
                <td className="fr-mono">{t.held || t.result || t.last_error || ""}</td>
              </tr>))}
            {o && !tasks.length && <tr><td colSpan={6} className="dim">No tasks yet: the pump strokes every 15 s.</td></tr>}
          </tbody>
        </table>
      </section>
    </main>
  );
}
