"use client";
// The electric drivetrain (11-11, the user's pick "A" after rejecting the piston radial): REGEN drawn as one closed
// circuit. Current leaves the source cells (job boards), passes the inverter (the fit gate, which dumps what it lets
// go to ground), energises the motor's coils (Write, then Apply), turns the output shaft into the flywheel (Sent), and
// replies flow back along the return line to the cells, so the loop is closed. Shadow is a second motor on a clutch:
// it engages when Shadow has the wheel. Parked jobs charge the "Your turn" capacitor.
// Every wire is connected end to end. A wire carries animated current only while the container behind it is warm and
// the engine is in gear; every pulse that runs along it is one real event (discovered, gate.skip, resume, apply.start,
// submitted, parked, shadow.*, outcome). Nothing moves without the engine moving.
import { useEffect, useState, type KeyboardEvent, type ReactNode } from "react";

/** A drivetrain part as a door to its room (Phase 1b): click, Enter or Space opens the drawer (alive/Rooms.tsx). */
const door = (room: string, tab: string | undefined, name: string) => ({
  role: "button", tabIndex: 0, "aria-label": `${name}: open`,
  onClick: () => window.dispatchEvent(new CustomEvent("alive:open", { detail: { room, tab } })),
  onKeyDown: (e: KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); window.dispatchEvent(new CustomEvent("alive:open", { detail: { room, tab } })); } },
});

export type Route = "in" | "dump" | "write" | "apply" | "out" | "seat" | "tray" | "back" | "shadowtray" | "return" | "fail";
export type Pulse = { id: number; route: Route; text?: string };
/** A posting sitting in a stage: it rides that stage's coil as a bead (employer initial; full name on hover). */
export type Bead = { id: string; company: string | null; by: string | null };

const M = { x: 560, y: 300 };  // motor centre
export const ROUTES: Record<Route, string> = {
  in: "M150 300 L262 300",
  dump: "M312 352 L312 462",
  write: "M362 300 C402 300 420 192 476 192",
  apply: "M484 186 C540 146 592 146 640 186",
  out: "M648 192 C700 222 694 300 722 300 L832 300",
  seat: "M640 196 C664 330 604 420 562 452",
  tray: "M646 196 C720 262 762 380 762 462",
  back: "M566 452 C604 400 652 300 644 196",
  shadowtray: "M606 500 L730 500",
  return: "M880 352 L880 560 L96 560 L96 424",
  fail: "M640 190 l14 -18 l-10 2 l12 -20",
};
const WIRES: [Route, string][] = [  // static conductors and the container that powers each (for warm / cold)
  ["in", "pipeline"], ["dump", "pipeline"], ["write", "pipeline"], ["apply", "applier"], ["out", "applier"],
  ["seat", "answers"], ["tray", "applier"], ["back", "answers"], ["shadowtray", "answers"], ["return", "feedback"],
];

/** Cubic Bezier point at t (the Write and Apply coils are single cubics in ROUTES). */
function cubic(d: string, t: number): [number, number] {
  const n = d.match(/-?\d+(\.\d+)?/g)!.map(Number);  // M x0 y0 C x1 y1 x2 y2 x3 y3
  const u = 1 - t;
  const f = (a: number, b: number, c: number, e: number) => u * u * u * a + 3 * u * u * t * b + 3 * u * t * t * c + t * t * t * e;
  return [f(n[0], n[2], n[4], n[6]), f(n[1], n[3], n[5], n[7])];
}

/** Beads spread evenly along a coil; Shadow's (by = shadow) are violet. Each is a real posting in that stage. */
function Beads({ route, beads }: { route: Route; beads: Bead[] }) {
  return (
    <g className={`dt-beads dt-beads-${route}`}>
      {beads.map((b, i) => {
        const [x, y] = cubic(ROUTES[route], (i + 1) / (beads.length + 1));
        const who = b.company ?? "a posting";
        return (
          <g key={b.id} className={`dt-bead${b.by === "shadow" ? " dt-bead-shadow" : ""}`} transform={`translate(${x.toFixed(1)} ${y.toFixed(1)})`}>
            <title>{who}</title>
            <circle r={10} />
            <text y={4}>{who.charAt(0).toUpperCase()}</text>
          </g>
        );
      })}
    </g>
  );
}

/** Under 600 px the circuit turns a quarter so it stacks top to bottom (sources on top, flywheel below). */
function usePortrait(): boolean {
  const [p, setP] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 600px)");
    const on = () => setP(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return p;
}

export type DrivetrainProps = {
  beads?: { write: Bead[]; apply: Bead[] };
  gear: string; speed?: string; warm: (role: string) => boolean; capped: boolean;
  counts: { heard: number; letGo: number; write: number; apply: number; sent: number | null; replies: number; tray: number };
  shadow: string | null; pulses: Pulse[]; fired: Record<string, number>; seat: ReactNode; label: string;
};

/** One-shot pulse: an SVG circle that runs its route once (SMIL animateMotion, started on mount). */
function Spark({ p }: { p: Pulse }) {
  const d = ROUTES[p.route];
  const dur = p.route === "return" ? "2.4s" : p.route === "fail" ? "0.5s" : "1.1s";
  return (
    <g className={`dt-pulse dt-${p.route}`}>
      <circle r={p.route === "out" ? 9 : 6}>
        <animateMotion dur={dur} path={d} fill="freeze" begin="indefinite" calcMode="spline" keyTimes="0;1" keySplines=".4 0 .2 1"
                       ref={(el) => { try { (el as unknown as SVGAnimationElement | null)?.beginElement(); } catch { /* SMIL missing: the pulse sits at the start */ } }} />
      </circle>
      {p.text && <text x={322} y={420} className="dt-dump-text">{p.text.length > 34 ? p.text.slice(0, 33) + "…" : p.text}</text>}
    </g>
  );
}

export function Drivetrain({ gear, speed, warm, capped, counts, shadow, pulses, fired, seat, label, beads }: DrivetrainProps) {
  const portrait = usePortrait();
  const running = gear !== "N" && !capped;
  const engaged = shadow === "autopilot" || shadow === "always";
  const live = (role: string) => running && warm(role);
  const teeth = Array.from({ length: 12 }, (_, i) => i * 30);
  return (
    <svg className={`alive-svg dt${running ? " dt-running" : ""}${engaged ? " dt-engaged" : ""}${portrait ? " dt-portrait" : ""}`}
         viewBox={portrait ? "0 0 600 1000" : "0 0 1000 600"}
         preserveAspectRatio="xMidYMid meet" role="group" aria-label={label}
         style={speed ? { ["--speed" as string]: speed } : undefined}>
      <defs>
        <radialGradient id="dt-core"><stop offset="0" stopColor="#f2c14e" stopOpacity=".55" /><stop offset="1" stopColor="#f2c14e" stopOpacity="0" /></radialGradient>
        <filter id="dt-glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
      </defs>
      {/* portrait: the same circuit turned a quarter; labels turn back upright in CSS (.dt-portrait text) */}
      <g transform={portrait ? "translate(600 0) rotate(90)" : undefined}>

      {/* conductors: a dim copper line, and over it the current (dashes flowing) while its container is warm */}
      {WIRES.map(([r, role]) => (
        <g key={r} className={`dt-wire${live(role) ? " dt-live" : ""}${warm(role) ? "" : " dt-cold"}`}>
          <path d={ROUTES[r]} className="dt-copper" />
          <path d={ROUTES[r]} className="dt-current" />
        </g>
      ))}

      {/* source cells: the boards the scan reads; current starts here */}
      <g className={`dt-cells${warm("pipeline") ? "" : " dt-cold"}`} {...door("garage", "gearbox", "Sources")}>
        {[0, 1, 2, 3].map((i) => (
          <g key={i} transform={`translate(40 ${186 + i * 58})`}>
            <rect width={110} height={48} rx={8} />
            <rect className="dt-charge" x={6} y={6} width={98 * Math.min(1, (counts.heard + 1) / (8 + i * 6))} height={36} rx={5} />
            <rect className="dt-nub" x={110} y={16} width={6} height={16} rx={2} />
          </g>
        ))}
        <text x={95} y={170} className="dt-label">Sources</text>
        <text x={95} y={442} className="dt-count">{counts.heard} heard · 1 h</text>
      </g>

      {/* inverter = the fit gate. What it lets go falls to ground */}
      <g className={`dt-inverter${warm("pipeline") ? "" : " dt-cold"}`} key={`j${fired.judge ?? 0}`}>
        <rect x={262} y={250} width={100} height={102} rx={14} />
        <path d="M282 312 q15 -30 30 0 t30 0" className="dt-sine" />
        <g className="dt-txt"><text x={312} y={240} className="dt-label">Judge</text>
        <text x={312} y={276} className="dt-sub">inverter</text></g>
      </g>
      <g className="dt-ground"><path d="M290 466 h44 M298 474 h28 M306 482 h12" /></g>
      <text x={344} y={470} className="dt-count dt-left">{counts.letGo} let go</text>

      {/* the motor: stator ring with 12 coil teeth, a rotor spinning at gear speed while it is powered */}
      <g className={`dt-motor${warm("applier") ? "" : " dt-cold"}`} {...door("garage", "gearbox", "Motor and gearbox")}>
        <circle cx={M.x} cy={M.y} r={150} fill="url(#dt-core)" className="dt-aura" />
        <circle cx={M.x} cy={M.y} r={128} className="dt-stator" />
        {teeth.map((a) => {
          const hot = (a >= 210 && a <= 240 && (fired.write ?? 0) > 0) || (a >= 300 && a <= 330 && (fired.apply ?? 0) > 0);
          return <rect key={`${a}${hot ? `-${fired.write}-${fired.apply}` : ""}`} className={`dt-tooth${hot ? " dt-hot" : ""}`}
                       x={M.x + 104} y={M.y - 9} width={22} height={18} rx={4} transform={`rotate(${a} ${M.x} ${M.y})`} />;
        })}
        <g className={`dt-rotor${live("applier") || live("pipeline") ? " dt-spin" : ""}`}>
          <circle cx={M.x} cy={M.y} r={74} />
          {[0, 60, 120, 180, 240, 300].map((a) => <rect key={a} x={M.x - 6} y={M.y - 70} width={12} height={46} rx={5} transform={`rotate(${a} ${M.x} ${M.y})`} />)}
          <circle cx={M.x} cy={M.y} r={18} className="dt-hub" />
        </g>
        <g className="dt-txt"><text x={M.x} y={M.y + 6} className="dt-gear">{gear}</text>
        <text x={M.x} y={M.y + 26} className="dt-sub">{capped ? "cap reached" : gear === "N" ? "neutral" : "gear"}</text></g>
      </g>
      <g className="dt-station" key={`w${fired.write ?? 0}`}><circle cx={480} cy={190} r={13} /><g className="dt-txt"><text x={448} y={176} className="dt-label dt-right">Write</text><text x={448} y={154} className="dt-count dt-right dt-keep">{counts.write} resumes</text></g></g>
      <g className="dt-station" key={`a${fired.apply ?? 0}`}><circle cx={644} cy={190} r={13} /><g className="dt-txt"><text x={676} y={176} className="dt-label dt-left">Apply</text><text x={676} y={154} className="dt-count dt-left dt-keep">{counts.apply} applying</text></g></g>

      {/* output shaft and the flywheel: each submission gives it a turn */}
      <rect x={722} y={292} width={110} height={16} rx={6} className={`dt-shaft${live("applier") ? " dt-turning" : ""}`} />
      <g key={`s${counts.sent ?? 0}`} {...door("results", "applications", "Sent")}><g className="dt-fly">
        <circle cx={880} cy={300} r={52} />
        {[0, 45, 90, 135].map((a) => <line key={a} x1={880} y1={252} x2={880} y2={348} transform={`rotate(${a} 880 300)`} />)}
        <circle cx={880} cy={300} r={14} className="dt-hub" />
      </g></g>
      <text x={880} y={226} className="dt-label">Sent</text>
      <text x={880} y={378} className="dt-count dt-gold">{counts.sent ?? "–"} with proof</text>

      {/* return line: replies flow back to the cells, closing the circuit */}
      <text x={300} y={584} className="dt-count">Hear · {counts.replies} replies flow back</text>

      {/* Shadow: a second motor on a clutch under the main one */}
      <g className="dt-clutch"><rect x={540} y={432} width={40} height={6} rx={2} /><rect x={540} y={engaged ? 442 : 450} width={40} height={6} rx={2} /></g>
      <g className={`dt-shadow-motor${engaged ? " dt-on" : ""}${shadow === "off" ? " dt-off" : ""}`} {...door("garage", "shadow", "Shadow brain")}>
        <circle cx={560} cy={500} r={44} />
        <g className={engaged ? "dt-spin dt-rotor-s" : "dt-rotor-s"}>{[0, 90].map((a) => <rect key={a} x={556} y={466} width={8} height={68} rx={4} transform={`rotate(${a} 560 500)`} />)}</g>
      </g>
      <g transform="translate(500 492)">{seat}</g>

      {/* the "Your turn" capacitor: charges with every parked job */}
      <g className={`dt-cap${counts.tray ? " dt-charged" : ""}`} {...door("turn", "needs", "Your turn")}>
        <rect x={736} y={466} width={52} height={8} rx={2} /><rect x={736} y={486} width={52} height={8} rx={2} />
        <text x={810} y={486} className="dt-count dt-left dt-amber dt-keep">{counts.tray ? `Your turn: ${counts.tray}` : "nothing waiting"}</text>
      </g>

      {beads && <Beads route="write" beads={beads.write} />}
      {beads && <Beads route="apply" beads={beads.apply} />}
      {pulses.map((p) => <Spark key={p.id} p={p} />)}
      </g>
    </svg>
  );
}
