"use client";
// The living engine (ALIVE Phases 1 + 1b, docs/ALIVE_PLAN.md §0a): the home page's engine block, drawn as the electric
// drivetrain (Drivetrain.tsx). Every bead on a coil is a real posting, every pulse a real event from the stream
// (lib/stream.ts), every part's warmth a real container's heartbeat (/api/control/fleet).
// Nothing is invented: with no events the engine sits still, and a cold part says which container is down.
// Controls (gear, daily cap, Role Keywords) post to the engine and change on screen only when its signal comes back.
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { subscribe } from "@/lib/stream";
import { get, post } from "@/lib/types";
import { empty, foldNarration, foldSignal, type Narration, type Signal, type Spine, type Stage } from "@/lib/spine";
import { reducedMotion, schedule, watchVisibility } from "./loop";
import { badge, hasWheel, type Brain } from "./Seat";
import { Drivetrain, type Bead, type Pulse, type Route } from "./Drivetrain";
import { Captions, caption, type Caption } from "./Captions";

// the drivetrain's parts by pipeline stage, and the container that powers each (for the cold-part warning)
const STATIONS: { stage: Stage; label: string; role: string }[] = [
  { stage: "listen", label: "Sources", role: "pipeline" },
  { stage: "judge", label: "Judge", role: "pipeline" },
  { stage: "write", label: "Write", role: "pipeline" },
  { stage: "apply", label: "Apply", role: "applier" },
  { stage: "hear", label: "Hear", role: "feedback" },
];
const BEADS = 8;  // at most this many beads ride a coil; the count says the rest
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
  const [pulses, setPulses] = useState<Pulse[]>([]);
  const [pending, setPending] = useState<Pending | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [brain, setBrain] = useState<Brain | null>(null);
  const [captions, setCaptions] = useState<Caption[]>([]);
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
      schedule(() => {
        foldNarration(spine.current, n);
        const pulse = (route: Route, text?: string) => setPulses((p) => [...p.slice(-23), { id: ++gid.current, route, text }]);
        if (n.kind === "discovered") pulse("in");
        else if (n.kind === "gate.skip") { pulse("dump", n.detail ?? undefined); setSkips((s) => s + 1); }
        else if (n.kind === "resume") pulse("write");
        else if (n.kind === "apply.start") pulse("apply");
        // the gauge re-reads the engine's own count: a local +1 drifted when the stream replayed its backlog (11-13)
        else if (n.kind === "submitted") { pulse("out"); get<Cap>("/api/control/cap").then(setCap).catch(fail("cap unavailable")); }
        else if (n.kind === "parked") {
          // Shadow's motor takes parked questions while it is on; human checks always go straight to you
          const toSeat = !!spine.current.shadow && spine.current.shadow !== "off" && !HUMAN_CHECK.test(n.detail ?? "");
          pulse(toSeat ? "seat" : "tray");
        }
        else if (n.kind === "shadow.abstain") pulse("shadowtray");
        else if (n.kind === "shadow.answer") pulse("back");
        else if (n.kind === "outcome") pulse("return");
        else if (n.kind === "apply.fail") pulse("fail");
        const cp = caption(n);
        if (cp) setCaptions((cs) => [cp, ...cs.filter((c) => c.id !== cp.id)].slice(0, 4));
        if (["discovered", "resume", "apply.start", "shadow.answer", "outcome", "gate.skip"].includes(n.kind ?? "")) {
          const st = n.kind === "gate.skip" ? "judge" : n.stage;
          setFire((f) => ({ ...f, [st]: (f[st] ?? 0) + 1 }));
        }
        setTick((t) => t + 1);
      });
    });
    return () => { alive = false; unsub(); stop(); clearInterval(fleetTimer); };
  }, []);

  // a pulse runs its wire once (<= 2.4 s), then leaves
  useEffect(() => {
    if (!pulses.length) return;
    const t = setTimeout(() => setPulses((p) => p.slice(1)), still.current ? 600 : 2600);
    return () => clearTimeout(t);
  }, [pulses]);
  // a control that never hears back from the engine says so instead of spinning forever
  useEffect(() => {
    if (!pending || pending.error) return;
    const t = setTimeout(() => setPending((p) => (p ? { ...p, error: "no confirmation from the engine yet" } : p)), 10000);
    return () => clearTimeout(t);
  }, [pending]);

  const s = spine.current;
  const now = Date.now();
  // postings per stage (cheap: <= a few hundred chips, recomputed every render so a stage change always moves its bead)
  const layout = (() => {
    const count: Record<string, number> = {};
    const beads: Record<string, Bead[]> = {};
    for (const [job, c] of s.chips) {
      if (c.stage === "listen" && now - ms(c.since) > LISTEN_WINDOW_MS) continue;  // heard over an hour ago
      count[c.stage] = (count[c.stage] ?? 0) + 1;
      (beads[c.stage] ??= []).push({ id: job, company: c.company, by: c.by });
    }
    for (const k of Object.keys(beads)) beads[k] = beads[k].slice(-BEADS);  // newest ride the coil
    return { count, beads };
  })();

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
      <Drivetrain gear={gear} speed={breath} warm={(r) => !cold(r)} capped={capped} shadow={s.shadow} pulses={still.current ? [] : pulses}
                  fired={fire} label={`Engine in gear ${gear}. ${coldParts.length ? `Cold: ${coldParts.join(", ")}.` : "All parts warm."}`}
                  beads={{ write: layout.beads.write ?? [], apply: layout.beads.apply ?? [] }}
                  counts={{ heard: counts.listen, letGo: skips, write: counts.write, apply: counts.apply, sent: verified, replies: heard, tray: s.tray.size }}
                  seat={<g className={`dt-seat${hasWheel(s.shadow) ? " dt-on" : ""}`}>
                    <text className="dt-label dt-right" y={0}>Shadow</text>
                    <text className="dt-count dt-right" y={18}>{s.shadow === "always" ? "autopilot" : s.shadow ?? "mode unknown"}{hasWheel(s.shadow) ? " · engaged" : ""}</text>
                    {badge(brain) && <text className="dt-count dt-right" y={34}>{badge(brain)![0]}</text>}
                  </g>} />

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
