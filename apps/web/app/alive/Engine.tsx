"use client";
// The living engine (ALIVE Phase 1, docs/ALIVE_PLAN.md §5): the home page's engine block. Five cylinders, one per
// pipeline stage, around a crankcase that breathes at the current gear. Every chip is a real posting, every motion a
// real event from the stream (lib/stream.ts), every part's warmth a real container's heartbeat (/api/control/fleet).
// Nothing is invented: with no events the engine sits still, and a cold part says which container is down.
// Controls (gear, daily cap, Role Keywords) post to the engine and change on screen only when its signal comes back.
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { subscribe } from "@/lib/stream";
import { get, post } from "@/lib/types";
import { empty, foldNarration, foldSignal, type Narration, type Signal, type Spine, type Stage } from "@/lib/spine";
import { Bundle, Chip } from "./Chip";
import { Cylinder, at, slot, CX, CY, R_IN } from "./Cylinder";
import { reducedMotion, schedule, watchVisibility } from "./loop";
import { Seat, SEAT, hasWheel, type Brain } from "./Seat";
import { Captions, caption, type Caption } from "./Captions";

const STATIONS: { stage: Stage; label: string; verb: string; deg: number; role: string }[] = [
  { stage: "listen", label: "Listen", verb: "heard (1 h)", deg: 198, role: "pipeline" },
  { stage: "judge", label: "Judge", verb: "let go", deg: 270, role: "pipeline" },
  { stage: "write", label: "Write", verb: "resumes ready", deg: 342, role: "pipeline" },
  { stage: "apply", label: "Apply", verb: "applying", deg: 54, role: "applier" },
  { stage: "hear", label: "Hear", verb: "replies", deg: 126, role: "feedback" },
];
const DEG = Object.fromEntries(STATIONS.map((s) => [s.stage, s.deg])) as Record<Stage, number>;
const INTAKE: [number, number] = [60, 230];
const EXHAUST: [number, number] = [960, 560];
const TRAY: [number, number] = [CX, 662];
const PER_CYL = 8;
const LISTEN_WINDOW_MS = 60 * 60 * 1000;
// A part is warm while its container beat recently. Appliers beat every 5 s while watching and every 30 s while
// applying, so silence past 15 s (watching) or 40 s (applying) means it is down: a stopped idle applier goes cold in
// ~20 s with the 5 s fleet poll (bench V9 measured 37 s with one flat 35 s limit). The engine's own 120 s threshold
// drives restarts and is not changed here.
const WARM_S: Record<string, (state: string) => number> = { applier: (st) => (st === "applying" ? 40 : 15) };
const BREATH: Record<string, string> = { "1": "4s", "2": "2.5s", "3": "1.5s", "4": "1s" };
const GEARS = ["N", "1", "2", "3", "4"];
const MODES: [string, string][] = [["off", "Off"], ["calls", "Calls"], ["autopilot", "Autopilot"]];
// Parks Shadow may never take: a human check (CAPTCHA / Ashby click) goes straight to your tray, never to the seat.
const HUMAN_CHECK = /captcha|human click|bot.?check|hcaptcha/i;

type Member = { role?: string; up?: boolean; age?: number; state?: string };
type Fleet = { members: Member[]; problems: string[] };
type Cap = { cap_levels: number[]; cap_level: number; cap: number; today: number };
type Ghost = { id: number; kind: "sent" | "parked" | "skip" | "fail" | "seat" | "answer"; from: [number, number]; to: [number, number]; text?: string };
type Pending = { control: "gear" | "cap" | "keywords" | "shadow.mode"; want: string; since: number; error?: string };

/** Parse a ledger ts ("2026-11-10T21:03:05", local time) to epoch ms; NaN when missing. */
const ms = (ts: string | null | undefined) => (ts ? new Date(ts).getTime() : NaN);

/** Warm/cold per role from fleet rows: up by the fleet's own rule, and (appliers) a heartbeat within WARM_S. */
function warmth(members: Member[]): Record<string, boolean> {
  const out: Record<string, boolean> = {};
  for (const m of members) {
    if (!m.role) continue;
    const limit = WARM_S[m.role];
    const ok = !!m.up && (limit === undefined || (m.age ?? 1e9) <= limit(m.state ?? ""));
    out[m.role] = out[m.role] || ok;
  }
  return out;
}

export function Engine() {
  const spine = useRef<Spine>(empty());
  const [, setTick] = useState(0);
  const render = () => schedule(() => setTick((t) => t + 1));
  const [warm, setWarm] = useState<Record<string, boolean> | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const [cap, setCap] = useState<Cap | null>(null);
  const [ab, setAb] = useState<boolean | null>(null);
  const [verified, setVerified] = useState<number | null>(null);
  const [skips, setSkips] = useState(0);
  const [fire, setFire] = useState<Record<string, number>>({});
  const [ghosts, setGhosts] = useState<Ghost[]>([]);
  const [born, setBorn] = useState<Set<string>>(new Set());
  const [pending, setPending] = useState<Pending | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [brain, setBrain] = useState<Brain | null>(null);
  const [captions, setCaptions] = useState<Caption[]>([]);
  const pos = useRef(new Map<string, [number, number]>());
  const gid = useRef(0);
  const still = useRef(false);

  useEffect(() => {
    still.current = reducedMotion();
    const stop = watchVisibility();
    let alive = true;
    const fail = (what: string) => (e: unknown) => { if (alive) setError(`${what}: ${e instanceof Error ? e.message : String(e)}`); };
    // seed: the last few hundred live events and the current control state, folded exactly like live ones
    Promise.all([get<Narration[]>("/api/narration?limit=300"), get<Signal[]>("/api/signals")]).then(([ns, gs]) => {
      for (const g of gs) foldSignal(spine.current, g);
      for (const n of ns) foldNarration(spine.current, n);
      setSkips(ns.filter((n) => n.kind === "gate.skip").length);
      setCaptions(ns.map(caption).filter((c): c is Caption => !!c).slice(-4).reverse());
      render();
    }).catch(fail("history unavailable"));
    get<Cap>("/api/control/cap").then(setCap).catch(fail("cap unavailable"));
    get<{ ab: boolean }>("/api/control/keywords").then((k) => setAb(k.ab)).catch(fail("keywords unavailable"));
    const pullBrain = () => get<Brain>("/api/shadow/brain").then((b) => { if (alive) setBrain(b); }).catch(fail("Shadow's brain unavailable"));
    pullBrain();
    get<{ verified: number }>("/api/snapshot").then((s) => setVerified(s.verified)).catch(fail("snapshot unavailable"));
    const pollFleet = () => get<Fleet>("/api/control/fleet").then((f) => {
      if (!alive) return;
      setWarm(warmth(f.members)); setProblems(f.problems);
    }).catch((e) => { if (alive) { setWarm({}); setError(`fleet unavailable: every part is drawn cold (${e instanceof Error ? e.message : e})`); } });
    pollFleet();
    const fleetTimer = setInterval(() => { if (!document.hidden) pollFleet(); }, 5000);

    const unsub = subscribe((type, data) => {
      if (type === "snapshot") { setVerified((data as { verified: number }).verified); return; }
      if (type === "signal") {
        const g = data as Signal;
        foldSignal(spine.current, g);
        setPending((p) => (p && p.control === g.kind ? null : p));
        if (g.kind === "cap") get<Cap>("/api/control/cap").then(setCap).catch(fail("cap unavailable"));
        if (g.kind === "shadow.mode") pullBrain();
        if (g.kind === "targeting") get<{ ab: boolean }>("/api/control/keywords").then((k) => setAb(k.ab)).catch(fail("keywords unavailable"));
        render();
        return;
      }
      const n = data as Narration;
      const job = n.job ?? "";
      const from = pos.current.get(job) ?? at(DEG[n.stage] ?? 270, 170);
      schedule(() => {
        foldNarration(spine.current, n);
        const ghost = (kind: Ghost["kind"], to: [number, number], text?: string) =>
          setGhosts((g) => [...g.slice(-11), { id: ++gid.current, kind, from, to, text }]);
        if (n.kind === "submitted") { ghost("sent", EXHAUST); setCap((c) => (c ? { ...c, today: c.today + 1 } : c)); }
        else if (n.kind === "parked") {
          // Shadow's seat takes parked questions while it is on; human checks always go straight to you
          const toSeat = !!spine.current.shadow && spine.current.shadow !== "off" && !HUMAN_CHECK.test(n.detail ?? "");
          ghost(toSeat ? "seat" : "parked", toSeat ? SEAT : TRAY);
        }
        else if (n.kind === "shadow.abstain") setGhosts((g) => [...g.slice(-11), { id: ++gid.current, kind: "parked", from: SEAT, to: TRAY }]);
        else if (n.kind === "shadow.answer") setGhosts((g) => [...g.slice(-11), { id: ++gid.current, kind: "answer", from: SEAT, to: at(DEG.apply, 170) }]);
        const cp = caption(n);
        if (cp) setCaptions((cs) => [cp, ...cs.filter((c) => c.id !== cp.id)].slice(0, 4));
        else if (n.kind === "gate.skip") { ghost("skip", [from[0], from[1] + 90], n.detail ?? undefined); setSkips((s) => s + 1); }
        else if (n.kind === "apply.fail") ghost("fail", from);
        if (n.kind === "discovered" && job) setBorn((b) => new Set(b).add(job));
        if (["discovered", "resume", "apply.start", "shadow.answer", "outcome", "gate.skip"].includes(n.kind ?? "")) {
          const st = n.kind === "gate.skip" ? "judge" : n.stage;
          setFire((f) => ({ ...f, [st]: (f[st] ?? 0) + 1 }));
        }
        setTick((t) => t + 1);
      });
    });
    return () => { alive = false; unsub(); stop(); clearInterval(fleetTimer); };
  }, []);

  // newborn chips render at the intake for one frame, then the transition carries them to their slot
  useEffect(() => {
    if (!born.size) return;
    const t = requestAnimationFrame(() => requestAnimationFrame(() => setBorn(new Set())));
    return () => cancelAnimationFrame(t);
  }, [born]);
  // ghosts live 2.2 s (the skip reason fades over 2 s), then leave
  useEffect(() => {
    if (!ghosts.length) return;
    const t = setTimeout(() => setGhosts((g) => g.slice(1)), still.current ? 900 : 2200);
    return () => clearTimeout(t);
  }, [ghosts]);
  // a control that never hears back from the engine says so instead of spinning forever
  useEffect(() => {
    if (!pending || pending.error) return;
    const t = setTimeout(() => setPending((p) => (p ? { ...p, error: "no confirmation from the engine yet" } : p)), 10000);
    return () => clearTimeout(t);
  }, [pending]);

  const s = spine.current;
  const now = Date.now();
  const layout = (() => {  // cheap (<= 100 chips): recomputed every render, so a stage change always moves its chip
    const by: Record<string, [string, { company: string | null; by: string | null; since: string | null }][]> = {};
    for (const [job, c] of s.chips) {
      if (c.stage === "listen" && now - ms(c.since) > LISTEN_WINDOW_MS) continue;  // heard over an hour ago
      (by[c.stage] ??= []).push([job, c]);
    }
    const chips: { id: string; x: number; y: number; company: string | null; by: string | null }[] = [];
    const extra: Record<string, number> = {};
    const count: Record<string, number> = {};
    for (const st of STATIONS) {
      const list = by[st.stage] ?? [];
      count[st.stage] = list.length;
      const shown = list.slice(-PER_CYL);
      extra[st.stage] = list.length - shown.length;
      shown.forEach(([id, c], i) => {
        const [x, y] = born.has(id) && !still.current ? INTAKE : slot(st.deg, i);
        chips.push({ id, x, y, company: c.company, by: c.by });
      });
    }
    return { chips, extra, count };
  })();
  pos.current = new Map(layout.chips.map((c) => [c.id, [c.x, c.y] as [number, number]]));  // ghosts start where a chip was last drawn

  const heard = Object.values(s.heard).reduce((a, b) => a + b, 0);
  const counts: Record<Stage, number> = { listen: layout.count.listen ?? 0, judge: skips, write: layout.count.write ?? 0,
                                          apply: layout.count.apply ?? 0, hear: heard };
  const cold = (role: string) => warm !== null && !warm[role];
  const gear = s.gear ?? "N";
  const capped = !!cap && cap.today >= cap.cap;
  const breath = gear === "N" || capped ? undefined : BREATH[gear];
  const trayItems = [...s.tray.values()].slice(-3).reverse();
  const coldParts = STATIONS.filter((st) => cold(st.role)).map((st) => st.label);
  const lights = [...new Set([...problems, ...s.problems])];

  const act = async (control: Pending["control"], want: string, path: string, body: object) => {
    setPending({ control, want, since: Date.now() });
    try { await post(path, body); }
    catch (e) { setPending({ control, want, since: Date.now(), error: e instanceof Error ? e.message : String(e) }); }
  };

  return (
    <section className={`alive${capped ? " al-idling" : ""}${hasWheel(s.shadow) ? " al-shadow-wheel" : ""}`} aria-label="The engine, live">
      <svg className="alive-svg" viewBox="0 0 1000 700" preserveAspectRatio="xMidYMid meet" role="group"
           aria-label={`Engine in gear ${gear}. ${coldParts.length ? `Cold: ${coldParts.join(", ")}.` : "All parts warm."}`}>
        <path className="al-intake" d={`M${INTAKE[0] - 30} ${INTAKE[1]} L${at(198, 250)[0] - 10} ${at(198, 250)[1]}`} />
        <text className="al-part-label" x={INTAKE[0] - 8} y={INTAKE[1] - 14}>intake</text>
        <path className="al-exhaust" d={`M${at(54, 250)[0]} ${at(54, 250)[1]} Q ${EXHAUST[0] - 60} ${at(54, 250)[1] + 20} ${EXHAUST[0]} ${EXHAUST[1]}`} />
        <text className="al-part-label al-right" x={EXHAUST[0] + 10} y={EXHAUST[1] + 64}>{verified !== null ? `${verified} sent with proof` : "exhaust"}</text>
        {STATIONS.map((st) => (
          <Cylinder key={st.stage} deg={st.deg} label={st.label} verb={st.verb} count={counts[st.stage]}
                    cold={cold(st.role)} why={`${st.role} container down`} fire={still.current ? 0 : fire[st.stage] ?? 0} />
        ))}
        <g className={`al-crank${warm !== null && !Object.values(warm).some(Boolean) ? " al-cold" : ""}`}
           style={breath ? { ["--breath" as string]: breath } : undefined}>
          <circle className="al-case" cx={CX} cy={CY} r={86} />
          {breath && <circle className="al-ring" cx={CX} cy={CY} r={100} />}
          <circle className={`al-hub${breath ? " al-breathing" : ""}`} cx={CX} cy={CY} r={56} />
          <text className="al-hub-gear" x={CX} y={CY + 4}>{gear}</text>
          <text className="al-hub-sub" x={CX} y={CY + 26}>{capped ? "cap reached · idling" : gear === "N" ? "neutral" : "gear"}</text>
        </g>
        {STATIONS.map((st) => {
          const [bx, by] = at(st.deg, R_IN + 12);  // at the barrel's root, clear of the label
          return <Bundle key={`b${st.stage}`} x={bx} y={by} n={layout.extra[st.stage] ?? 0} />;
        })}
        {layout.chips.map((c) => <Chip key={c.id} {...c} />)}
        {ghosts.map((g) => (
          <g key={g.id} className={`al-ghost al-${g.kind}`}
             style={{ ["--x0" as string]: `${g.from[0]}px`, ["--y0" as string]: `${g.from[1]}px`,
                      ["--x1" as string]: `${g.to[0]}px`, ["--y1" as string]: `${g.to[1]}px` }}>
            <circle r={g.kind === "sent" ? 14 : 10} />
            {g.text && <text y={-16}>{g.text.length > 40 ? g.text.slice(0, 39) + "…" : g.text}</text>}
          </g>
        ))}
        <Seat mode={s.shadow} brain={brain} />
        <g className="al-tray" transform={`translate(${TRAY[0]} ${TRAY[1]})`}>
          <rect x={-170} y={-22} width={340} height={44} rx={22} />
          <text y={5}>{s.tray.size ? `Your turn: ${s.tray.size} waiting` : "Nothing waiting on you"}</text>
        </g>
      </svg>

      <div className="alive-side">
        {(lights.length > 0 || coldParts.length > 0) && (
          <ul className="al-lights" aria-label="Warning lights">
            {coldParts.map((p) => <li key={`c${p}`}>{p} is cold: its container is not beating</li>)}
            {lights.map((p) => <li key={p}>{p}</li>)}
          </ul>
        )}
        <Captions mode={s.shadow} items={captions} />
        {trayItems.length > 0 && (
          <p className="al-tray-list"><Link href="/needs">Your turn</Link>: {trayItems.map((t) => t.company ?? "a posting").join(", ")}
            {s.tray.size > 3 ? ` and ${s.tray.size - 3} more` : ""}</p>
        )}
        <div className="al-drive" aria-label="Drive controls">
          <fieldset className="al-gear-lever">
            <legend>Gear</legend>
            {GEARS.map((g) => (
              <button key={g} type="button" aria-pressed={gear === g} disabled={!!pending && !pending.error}
                      className={pending?.control === "gear" && pending.want === g && !pending.error ? "al-waiting" : ""}
                      onClick={() => g !== gear && act("gear", g, "/api/control/gearbox", { gear: g })}>{g}</button>
            ))}
          </fieldset>
          <fieldset className="al-cap-dial">
            <legend>Daily cap{cap ? `: ${cap.today} / ${cap.cap} today` : ""}</legend>
            {cap && <progress max={cap.cap} value={Math.min(cap.today, cap.cap)} aria-label={`${cap.today} of ${cap.cap} today`} />}
            {(cap?.cap_levels ?? []).map((c, i) => (
              <button key={c} type="button" aria-pressed={cap?.cap_level === i} disabled={!!pending && !pending.error}
                      className={pending?.control === "cap" && pending.want === String(i) && !pending.error ? "al-waiting" : ""}
                      onClick={() => cap?.cap_level !== i && act("cap", String(i), "/api/control/cap", { level: i })}>{c}</button>
            ))}
          </fieldset>
          <fieldset className="al-kw-toggle">
            <legend>Role Keywords</legend>
            {["on", "off"].map((v) => (
              <button key={v} type="button" aria-pressed={s.keywords === v} disabled={!!pending && !pending.error}
                      className={pending?.control === "keywords" && pending.want === v && !pending.error ? "al-waiting" : ""}
                      onClick={() => s.keywords !== v && act("keywords", v, "/api/control/keywords", { on: v === "on" })}>{v}</button>
            ))}
            {ab && <small>A/B test on: each posting's URL decides, this switch waits</small>}
          </fieldset>
          <fieldset className="al-shadow-sel">
            <legend>Shadow</legend>
            {MODES.map(([m, label]) => {
              const on = s.shadow === m || (m === "autopilot" && s.shadow === "always");
              return (
                <button key={m} type="button" aria-pressed={on} disabled={!!pending && !pending.error}
                        className={pending?.control === "shadow.mode" && pending.want === m && !pending.error ? "al-waiting" : ""}
                        onClick={() => !on && act("shadow.mode", m, "/api/shadow", { mode: m })}>{label}</button>
              );
            })}
          </fieldset>
        </div>
        {pending?.error && <p className="alive-error" role="status">{pending.control}: {pending.error}</p>}
        {error && <p className="alive-error" role="status">{error}</p>}
      </div>
    </section>
  );
}
