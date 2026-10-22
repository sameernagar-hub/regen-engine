"use client";
// Discover, as a picture: two eyes in a field of orbs, one orb per company whose board the engine is reading (newest
// postings first) and six gold orbs for the big-tech portals. Left alone, each eye wanders to a different orb, as if
// searching two job boards at once, and that orb lights up with its name. Move the cursor and both eyes follow it;
// every orb near the cursor glows and says which company it is. prefers-reduced-motion: no wandering, no blinking.
import { useEffect, useMemo, useRef, useState } from "react";
import { get } from "@/lib/types";
import "./discover.css";

type Orb = { company: string; ats: string; title?: string; portal?: boolean };
type Discover = { boards: Record<string, number>; total: number; portals: string[]; orbs: Orb[] };
type Pt = { x: number; y: number };

const W = 1000, H = 420;
const EYES: Pt[] = [{ x: 430, y: 205 }, { x: 570, y: 205 }];
const RX = 58, RY = 40;  // sclera
const NEAR = 120;        // cursor radius that lights orbs
const ATS_TONE: Record<string, string> = { greenhouse: "#5ee6b5", ashby: "#b18cff", lever: "#6fb7ff", workable: "#ff7eb6",
  workday: "#ff9f43", smartrecruiters: "#ffd166", icims: "#9ad1ff", rippling: "#ff8fab", jazzhr: "#c3f584" };

const hash = (s: string) => [...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
// twinkling specks of dust in the hall, fixed so server and client render the same field
const SPECKS = Array.from({ length: 34 }, (_, i) => ({ x: (hash("x" + i) % W), y: (hash("y" + i) % H), r: 0.6 + (hash("r" + i) % 10) / 10,
                                                      d: (hash("d" + i) % 60) / 10 }));

function layout(orbs: Orb[]): (Orb & Pt & { r: number })[] {
  // portals on an inner ellipse; companies on a golden-angle spiral that skips the eyes' box
  const out: (Orb & Pt & { r: number })[] = [];
  const portals = orbs.filter((o) => o.portal), rest = orbs.filter((o) => !o.portal);
  portals.forEach((o, i) => {
    const a = -Math.PI / 2 + (i / portals.length) * Math.PI * 2 + 0.3;
    out.push({ ...o, x: 500 + Math.cos(a) * 205, y: 210 + Math.sin(a) * 120, r: 9 });
  });
  let k = 0;
  for (const o of rest) {
    let p: Pt;
    do {
      const a = k * 2.39996, t = Math.sqrt((k + 6) / (rest.length + 40));
      const j = (hash(o.company + k) % 100) / 100 - 0.5;
      p = { x: 500 + Math.cos(a) * (190 + t * 300 + j * 30), y: 210 + Math.sin(a) * (110 + t * 95 + j * 18) };
      k++;
    } while ((Math.abs(p.x - 500) < 170 && Math.abs(p.y - 205) < 85) || p.x < 20 || p.x > W - 20 || p.y < 18 || p.y > H - 18);
    out.push({ ...o, ...p, r: 4 + (hash(o.company) % 4) });
  }
  return out;
}

function pupil(eye: Pt, t: Pt | null): Pt {
  if (!t) return { x: 0, y: 0 };
  const dx = t.x - eye.x, dy = t.y - eye.y, d = Math.hypot(dx, dy) || 1, k = Math.min(1, d / 260);
  return { x: (dx / d) * 24 * k, y: (dy / d) * 15 * k };
}

export function DiscoverEyes() {
  const [data, setData] = useState<Discover | null>(null);
  const [cursor, setCursor] = useState<Pt | null>(null);
  const [gaze, setGaze] = useState<[number, number]>([0, 1]);  // idle: which orb each eye looks at
  const [still, setStill] = useState(false);
  const svg = useRef<SVGSVGElement>(null);
  const frame = useRef(0);

  useEffect(() => { get<Discover>("/api/control/discover?n=40").then(setData).catch(() => setData(null)); }, []);
  useEffect(() => {
    const m = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    setStill(!!m?.matches);
  }, []);
  const orbs = useMemo(() => layout([...(data?.portals || []).map((p) => ({ company: p, ats: "careers portal", portal: true })),
                                     ...(data?.orbs || [])]), [data]);
  useEffect(() => {  // idle search: every 1.7 s each eye picks a different orb
    if (cursor || still || orbs.length < 2) return;
    const t = setInterval(() => {
      const a = Math.floor(Math.random() * orbs.length);
      let b = Math.floor(Math.random() * orbs.length);
      if (b === a) b = (b + 1) % orbs.length;
      setGaze(orbs[a].x < orbs[b].x ? [a, b] : [b, a]);  // left eye takes the left orb, so the eyes never cross
    }, 1700);
    return () => clearInterval(t);
  }, [cursor, still, orbs]);

  const move = (e: React.PointerEvent) => {
    const el = svg.current;
    if (!el) return;
    const { clientX, clientY } = e;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      const m = el.getScreenCTM();
      if (!m) return;
      const p = new DOMPoint(clientX, clientY).matrixTransform(m.inverse());
      setCursor({ x: p.x, y: p.y });
    });
  };

  const idle = !cursor && !still && orbs.length > 1;
  const targets: (Pt | null)[] = cursor ? [cursor, cursor] : idle ? [orbs[gaze[0]], orbs[gaze[1]]] : [null, null];
  const lit = new Map<number, number>();  // orb index -> glow 0..1
  if (cursor) orbs.forEach((o, i) => { const d = Math.hypot(o.x - cursor.x, o.y - cursor.y); if (d < NEAR) lit.set(i, 1 - d / NEAR); });
  else if (idle) { lit.set(gaze[0], 1); lit.set(gaze[1], 1); }
  const labelled = [...lit.entries()].sort((a, b) => b[1] - a[1]).slice(0, cursor ? 4 : 2).map(([i]) => i);

  return (
    <figure className="dx">
      <svg ref={svg} viewBox={`0 0 ${W} ${H}`} role="img" onPointerMove={move} onPointerLeave={() => setCursor(null)}
           aria-label={`The discover station: two eyes scanning ${data?.total?.toLocaleString() ?? "thousands of"} job boards and ${data?.portals.length ?? 6} big-tech portals`}>
        <defs>
          <radialGradient id="dx-iris" cx="50%" cy="45%" r="55%">
            <stop offset="0%" stopColor="#ffe08a" /><stop offset="55%" stopColor="#f2c14e" /><stop offset="100%" stopColor="#b9771f" />
          </radialGradient>
          <radialGradient id="dx-white" cx="50%" cy="40%" r="65%">
            <stop offset="0%" stopColor="#f4f7fb" /><stop offset="100%" stopColor="#b9c3d1" />
          </radialGradient>
          <radialGradient id="dx-glass" cx="40%" cy="35%" r="70%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.55" /><stop offset="45%" stopColor="#ffffff" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#07090d" stopOpacity="0.35" />
          </radialGradient>
          <filter id="dx-glow" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="6" /></filter>
          {EYES.map((e, i) => <clipPath key={i} id={`dx-socket-${i}`}><ellipse cx={e.x} cy={e.y} rx={RX} ry={RY} /></clipPath>)}
        </defs>

        {SPECKS.map((s, i) => <circle key={`s${i}`} className="dx-speck" cx={s.x} cy={s.y} r={s.r} style={{ animationDelay: `${s.d}s` }} />)}

        {idle && EYES.map((e, i) => {  // gaze rays: faint dashed lines from each eye to the orb it is reading
          const t = orbs[gaze[i]];
          return <line key={`ray${i}`} className="dx-ray" x1={e.x} y1={e.y} x2={t.x} y2={t.y} />;
        })}

        {orbs.map((o, i) => {
          const g = lit.get(i) ?? 0, tone = o.portal ? "#f2c14e" : ATS_TONE[o.ats] || "#7d8796";
          return (
            <g key={o.company + i} className={`dx-orb${g ? " on" : ""}`} style={{ ["--d" as any]: `${(hash(o.company) % 40) / 10}s` }}>
              {/* a glass orb: misty glow, tinted body, a rim and a highlight; it brightens as the cursor nears */}
              <circle cx={o.x} cy={o.y} r={o.r * (1.8 + g * 2)} fill={tone} opacity={0.08 + g * 0.5} filter="url(#dx-glow)" />
              <circle cx={o.x} cy={o.y} r={o.r * (1 + g * 0.6)} fill={tone} opacity={0.22 + g * 0.6} />
              <circle cx={o.x} cy={o.y} r={o.r * (1 + g * 0.6)} fill="url(#dx-glass)" stroke="#e8edf4" strokeOpacity={0.25 + g * 0.5} strokeWidth="0.8" />
              <circle cx={o.x - o.r * 0.35} cy={o.y - o.r * 0.4} r={o.r * 0.28} fill="#fff" opacity={0.45 + g * 0.5} />
            </g>);
        })}

        {EYES.map((e, i) => {
          const p = pupil(e, targets[i]);
          return (
            <g key={i} className={`dx-eye${still ? "" : " blink"}`} style={{ transformOrigin: `${e.x}px ${e.y}px`, animationDelay: `${i * 0.06}s` }}>
              <ellipse cx={e.x} cy={e.y} rx={RX + 6} ry={RY + 6} fill="none" stroke="#3a4554" strokeWidth="2" />
              <ellipse cx={e.x} cy={e.y} rx={RX} ry={RY} fill="url(#dx-white)" />
              <g clipPath={`url(#dx-socket-${i})`}>
                <g className={cursor ? "dx-pupil fast" : "dx-pupil"} style={{ transform: `translate(${p.x}px, ${p.y}px)` }}>
                  <circle cx={e.x} cy={e.y} r={25} fill="url(#dx-iris)" />
                  <circle cx={e.x} cy={e.y} r={11} fill="#07090d" />
                  <circle cx={e.x - 7} cy={e.y - 8} r={4} fill="#fff" opacity="0.85" />
                </g>
              </g>
            </g>);
        })}

        {labelled.map((i) => {
          const o = orbs[i], left = o.x > W - 170, up = o.y > 40;
          return (
            <g key={`l${i}`} className="dx-label" transform={`translate(${o.x + (left ? -14 : 14)}, ${o.y + (up ? -12 : 22)})`}>
              <text textAnchor={left ? "end" : "start"} className="dx-name">{o.company}</text>
              <text textAnchor={left ? "end" : "start"} y="15" className="dx-ats">
                {cursor ? (o.portal ? "big-tech portal" : `${o.ats}${o.title ? " · " + o.title.slice(0, 34) : ""}`) : `scanning ${o.ats}`}</text>
            </g>);
        })}
      </svg>
      <figcaption className="dim small">
        {data ? `Watching ${data.total.toLocaleString()} boards on ${Object.keys(data.boards).length} ATSs and ${data.portals.length} big-tech portals. `
              : "Connecting to the engine… "}
        Each orb is a company with fresh postings; gold orbs are the big-tech portals. Move your cursor: the eyes follow and every company nearby lights up.
      </figcaption>
    </figure>
  );
}
