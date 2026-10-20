"use client";
// The gearbox (v1.1): the engine is the crankshaft on the left; the gearbox sets how hard it runs and the feedback
// chain on top carries what rejections taught back into the engine. It is a real constant-mesh box: the layshaft
// turns every main-shaft gear all the time, and the selector collar locks one of them to the output shaft. The gear
// picks the applier range and the scan interval (engine/gearbox.py); the clutch couples the learned rejection phrases
// to the fit gate (engine/feedback/rejections.py). Speeds follow the gear; every tooth stays in mesh because each
// gear's angle is derived from the crankshaft's with the tooth ratio and a mesh phase.
import { useEffect, useMemo, useRef, useState } from "react";
import { Nav } from "../nav";
import { PUBLIC } from "@/lib/engine";
import { get, post } from "@/lib/types";

type Rule = { phrase: string; rejected?: number; seen?: number; rate?: number; lift?: number; p_adj?: number; status: string };
type Box = {
  gear: { gear: string; clutch: string; label: string; appliers: number[]; loop_min: number | null; gears: Record<string, string>; set_at?: string; by?: string };
  fleet: { appliers_up?: number; inbox?: number; claimed?: number; verdict?: string };
  speed: { last_hour: number; last_24h: number };
  outcomes: Record<string, number>;
  feedback: { updated?: string; stats: { rejected?: number; with_jd?: number; baseline_rejection_rate?: number; phrases_tested?: number; positive?: number }; rules: Rule[] };
};

const GEARS: Record<string, { appliers: number[]; loop_min: number | null; label: string }> = {
  N: { appliers: [0, 0], loop_min: null, label: "neutral: engine idles, nothing new is applied" },
  "1": { appliers: [1, 1], loop_min: 10, label: "crawl: one applier, scan every 10 min" },
  "2": { appliers: [1, 3], loop_min: 5, label: "cruise: up to 3 appliers, scan every 5 min" },
  "3": { appliers: [1, 7], loop_min: 3, label: "drive: up to 7 appliers, scan every 3 min" },
  "4": { appliers: [2, 9], loop_min: 2, label: "overdrive: 2-9 appliers, scan every 2 min" },
};
// geometry: module 5 (pitch radius = 5 x teeth), so any two gears here mesh
const M = 5;
const ENGINE = { x: 170, y: 360, n: 22 };
const DRIVE = { x: 170 + 5 * 22 + 5 * 8, y: 360, n: 8 };          // layshaft drive gear, meshed with the crankshaft
const LAY_Y = 360, MAIN_Y = 240;                                   // shafts 120 apart: lay n + main n = 24
const PAIRS = [{ g: "1", x: 470, lay: 6, main: 18 }, { g: "2", x: 640, lay: 9, main: 15 },
               { g: "3", x: 810, lay: 11, main: 13 }, { g: "4", x: 960, lay: 14, main: 10 }];
const RPS: Record<string, number> = { N: 0.12, "1": 0.25, "2": 0.4, "3": 0.55, "4": 0.75 };  // crankshaft turns per second

function gearPath(n: number) {
  const r = M * n, ro = r + 4.5, ri = r - 5, step = (2 * Math.PI) / n, pts: string[] = [];
  for (let i = 0; i < n; i++) {
    const a = i * step;  // tooth i centered at angle a (tooth 0 points along +x)
    for (const [da, rr] of [[-0.5, ri], [-0.28, ri], [-0.16, ro], [0.16, ro], [0.28, ri], [0.5, ri]] as const) {
      const t = a + da * step;
      pts.push(`${(Math.cos(t) * rr).toFixed(2)},${(Math.sin(t) * rr).toFixed(2)}`);
    }
  }
  return `M${pts.join("L")}Z`;
}
// angle of a gear meshed with a driver: theta2 = -(n1/n2) theta1 + (1 + n1/n2) phi + 180/n2, phi = direction 1 -> 2
const meshed = (t1: number, n1: number, n2: number, phi: number) => -(n1 / n2) * t1 + (1 + n1 / n2) * phi + 180 / n2;

function Gear({ id, x, y, n, cls, spokes = true }: { id: string; x: number; y: number; n: number; cls: string; spokes?: boolean }) {
  const d = useMemo(() => gearPath(n), [n]);
  const r = M * n;
  return (
    <g transform={`translate(${x} ${y})`}>
      <g data-gear={id} className={`gear ${cls}`}>
        <path d={d} />
        {spokes && r > 30 && [0, 60, 120].map((a) => <rect key={a} className="spoke" x={-r * 0.62} y={-3} width={r * 1.24} height={6} rx={3} transform={`rotate(${a})`} />)}
        <circle className="bore" r={Math.max(6, r * 0.18)} />
      </g>
    </g>
  );
}

export default function Gearbox() {
  const [box, setBox] = useState<Box | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const svg = useRef<SVGSVGElement>(null);
  const gear = box?.gear.gear || "N";
  const clutch = box?.gear.clutch !== "off";

  useEffect(() => {
    const pull = () => get<Box>("/api/control/gearbox").then(setBox).catch((e) => setMsg(`gearbox unreachable: ${e.message}`));
    pull();
    const t = setInterval(pull, 15000);
    return () => clearInterval(t);
  }, []);

  // one animation clock: the crankshaft angle eases toward the gear's speed (spool up / down), every other gear follows
  const target = useRef(RPS[gear]);
  target.current = RPS[gear] ?? 0.12;
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0, last = performance.now(), theta = 0, speed = 0, fb = 0;
    const els = () => Object.fromEntries(Array.from(svg.current?.querySelectorAll<SVGGElement>("[data-gear]") || []).map((e) => [e.dataset.gear!, e]));
    let map = els();
    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      speed += (target.current - speed) * Math.min(1, dt * 1.6);
      theta += speed * 360 * dt;
      fb += 0.08 * 360 * dt;
      if (!map.engine) map = els();
      const set = (k: string, a: number) => map[k]?.setAttribute("transform", `rotate(${a.toFixed(2)})`);
      set("engine", theta);
      const lay = meshed(theta, ENGINE.n, DRIVE.n, 0);
      set("drive", lay);
      for (const p of PAIRS) {  // every lay gear is on the drive gear's shaft: same angle
        set(`lay${p.g}`, lay);
        set(`main${p.g}`, meshed(lay, p.lay, p.main, -90));
      }
      set("feedback", fb);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  const shift = async (g?: string, c?: "on" | "off") => {
    if (!box || busy) return;
    setBusy(true);
    setMsg("");
    try {
      setBox(await post<Box>("/api/control/gearbox", { ...(g ? { gear: g } : {}), ...(c ? { clutch: c } : {}) }));
      if (PUBLIC) setMsg("Demo: shifting is simulated in this tab on the public site.");
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  const engaged = PAIRS.find((p) => p.g === gear);
  const collarX = engaged ? engaged.x - M * engaged.main - 16 : (PAIRS[1].x + PAIRS[2].x) / 2 - 8;
  const fbStats = box?.feedback.stats || {};
  const active = (box?.feedback.rules || []).filter((r) => r.status === "active").length;
  const proposed = (box?.feedback.rules || []).filter((r) => r.status === "proposed").length;
  const spec = GEARS[gear];
  const ret = "M 1100 118 L 1100 80 L 170 80 L 170 245";

  return (
    <main className={`page gearbox gear-${box ? gear : "loading"}${clutch ? "" : " clutch-out"}`}>
      <Nav />
      <header className="hero">
        <h1>Gearbox</h1>
        <p>The engine turns the crankshaft; the gearbox decides how hard it runs, and the feedback chain carries what
          rejections taught back into the engine. Shift to set the applier range and scan interval. The clutch couples the
          learned rejection phrases to the fit gate. Safety limits are not gears: the daily cap and Ashby's one per pass stay put.</p>
      </header>
      {msg && <p className="note" role="status">{msg}</p>}

      <section className="gb-stage">
        <svg ref={svg} className="gb" viewBox="0 0 1180 520" role="img" aria-label={`Gearbox in gear ${gear}, clutch ${clutch ? "engaged" : "disengaged"}`}>
          <defs>
            <linearGradient id="gbsteel" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#3a4556" /><stop offset=".55" stopColor="#1d2530" /><stop offset="1" stopColor="#11161d" /></linearGradient>
            <filter id="gbglow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          </defs>

          {/* feedback chain: output -> rejection feedback -> clutch -> back into the engine */}
          <path className="chain" d={ret} />
          {clutch && [0, 1, 2, 3, 4].map((k) => (
            <circle key={k} className="pulse" r={5}><animateMotion dur="6s" begin={`${k * 1.2}s`} repeatCount="indefinite" path={ret} /></circle>))}
          <g className="clutch" transform="translate(600 80)">
            <rect className="plate a" x={-22} y={-30} width={10} height={60} rx={3} />
            <rect className="plate b" x={12} y={-30} width={10} height={60} rx={3} />
            <text className="gb-label" y={-42}>clutch {clutch ? "engaged" : "out"}</text>
          </g>
          <line className={`shaft out${gear === "N" ? " idle" : ""}`} x1={1100} y1={MAIN_Y} x2={1100} y2={165} />
          <Gear id="feedback" x={1100} y={165} n={9} cls="fb" />
          <text className="gb-label end" x={1150} y={36}>rejection feedback</text>
          <text className="gb-num end" x={1150} y={58}>{fbStats.rejected ?? "·"} rejections read · {active} rules blocking</text>

          {/* engine */}
          <Gear id="engine" x={ENGINE.x} y={ENGINE.y} n={ENGINE.n} cls="engine-gear" />
          <text className="gb-label" x={ENGINE.x} y={500}>engine (crankshaft)</text>

          {/* gearbox housing, shafts, constant-mesh pairs, selector collar */}
          <rect className="housing" x={292} y={128} width={720} height={330} rx={26} />
          <line className="shaft" x1={DRIVE.x} y1={LAY_Y} x2={1000} y2={LAY_Y} />
          <line className={`shaft out${gear === "N" ? " idle" : ""}`} x1={380} y1={MAIN_Y} x2={1100} y2={MAIN_Y} />
          <Gear id="drive" x={DRIVE.x} y={DRIVE.y} n={DRIVE.n} cls="drive" spokes={false} />
          {PAIRS.map((p) => (
            <g key={p.g} className={`pair${box && gear === p.g ? " on" : ""}`}>
              <Gear id={`lay${p.g}`} x={p.x} y={LAY_Y} n={p.lay} cls="lay" />
              <Gear id={`main${p.g}`} x={p.x} y={MAIN_Y} n={p.main} cls="main" />
              <text className="gb-gear" x={p.x} y={MAIN_Y - M * p.main - 16}>{p.g}</text>
            </g>
          ))}
          {box && <rect className="collar" x={0} y={MAIN_Y - 22} width={16} height={44} rx={4} style={{ transform: `translateX(${collarX}px)` }} />}
          <text className="gb-label" x={652} y={446}>layshaft · every gear turns · the collar picks one</text>
        </svg>

        <div className="gb-controls">
          <div className="shifter" role="radiogroup" aria-label="Gear">
            <svg viewBox="0 0 160 160" aria-hidden="true" className="gate">
              <path d="M40 30 V130 M120 30 V130 M40 80 H120" />
            </svg>
            {(["1", "2", "N", "3", "4"] as const).map((g) => (
              <button key={g} role="radio" aria-checked={gear === g} className={`slot s${g}${gear === g ? " on" : ""}`} disabled={busy}
                      onClick={() => shift(g)} title={GEARS[g].label}>{g}</button>))}
            {box && <span className={`knob k${gear}`} aria-hidden="true" />}
          </div>
          <button className={`clutch-btn${clutch ? " on" : ""}`} disabled={busy} onClick={() => shift(undefined, clutch ? "off" : "on")}
                  aria-pressed={clutch}>
            Clutch {clutch ? "engaged: learned phrases block postings" : "out: base fit gate only"}
          </button>
          <dl className="gauges">
            <div><dt>Gear</dt><dd>{gear}</dd><small>{spec.label}</small></div>
            <div><dt>Appliers</dt><dd>{box?.fleet.appliers_up ?? "·"}</dd><small>range {spec.appliers.join("-")}</small></div>
            <div><dt>Scan every</dt><dd>{spec.loop_min ? `${spec.loop_min}m` : "—"}</dd><small>{gear === "N" ? "idling" : "first-applicant loop"}</small></div>
            <div><dt>Speed</dt><dd>{box?.speed.last_hour ?? "·"}/h</dd><small>{box?.speed.last_24h ?? "·"} in 24 h</small></div>
          </dl>
        </div>
      </section>

      <section className="gb-feedback">
        <h2>What the feedback taught</h2>
        <p className="dim small">
          {fbStats.rejected ?? 0} rejected of {fbStats.with_jd ?? 0} submitted job descriptions (baseline rate {fbStats.baseline_rejection_rate ?? "·"}),
          {" "}{fbStats.phrases_tested ?? 0} phrases tested. A phrase blocks only when it is significant after correcting for every phrase tested
          and never appeared where an OA or interview came back; the rest are watched. {active} active, {proposed} proposed. Updated {box?.feedback.updated || "·"}.
        </p>
        <table>
          <thead><tr><th>phrase</th><th>rejected</th><th>seen</th><th>rate</th><th>lift</th><th>p (adj.)</th><th>status</th></tr></thead>
          <tbody>
            {(box?.feedback.rules || []).map((r) => (
              <tr key={r.phrase} className={r.status}><td>{r.phrase}</td><td>{r.rejected ?? ""}</td><td>{r.seen ?? ""}</td><td>{r.rate ?? ""}</td>
                <td>{r.lift ?? ""}</td><td>{r.p_adj ?? ""}</td><td><span className={`tag ${r.status}`}>{r.status}</span></td></tr>))}
            {!box?.feedback.rules?.length && <tr><td colSpan={7} className="dim">No candidates yet: the feedback container reads the inbox every 30 minutes.</td></tr>}
          </tbody>
        </table>
      </section>
    </main>
  );
}
