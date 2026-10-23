"use client";
// Discover, as a picture: a panda in a field of glass orbs, one orb per company whose board the engine is reading
// (newest postings first) and six gold orbs for the big-tech portals. The orbs carry no text: hover one and it glows,
// the panda looks at it and lights up, and a card names the company. Left alone the panda reads one orb after another,
// blinks, and settles. The face moves every frame from refs (head turn with parallax, pupils, lids, mouth, ears,
// blush), so React renders only when the data or the hovered orb changes. The loop sleeps when the panda is off screen
// or the tab is hidden. prefers-reduced-motion: no wandering, no blinking, the gaze snaps.
import { useEffect, useMemo, useRef, useState } from "react";
import { get } from "@/lib/types";
import "./discover.css";

type Orb = { company: string; ats: string; title?: string; portal?: boolean };
type Discover = { boards: Record<string, number>; total: number; portals: string[]; orbs: Orb[] };
type Pt = { x: number; y: number };
type Placed = Orb & Pt & { r: number; tone: string };

const W = 1000, H = 480;
const C: Pt = { x: 500, y: 236 };         // centre of the panda's head
const EYE: Pt[] = [{ x: -42, y: -8 }, { x: 42, y: -8 }];  // eyes, head-local
const GOLD = "#f2c14e";
const ATS_TONE: Record<string, string> = { greenhouse: "#5ee6b5", ashby: "#b18cff", lever: "#6fb7ff", workable: "#ff7eb6",
  workday: "#ff9f43", smartrecruiters: "#ffd166", icims: "#9ad1ff", rippling: "#ff8fab", jazzhr: "#c3f584" };
const TONES = [...new Set([GOLD, "#7d8796", ...Object.values(ATS_TONE)])];

const hash = (s: string) => [...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
const clamp = (v: number, a: number) => Math.max(-a, Math.min(a, v));
const SPECKS = Array.from({ length: 40 }, (_, i) => ({ x: hash("x" + i) % W, y: hash("y" + i) % H, r: 0.6 + (hash("r" + i) % 10) / 10,
                                                      d: (hash("d" + i) % 60) / 10 }));

// a furry outline: an ellipse whose edge breaks into soft tufts, fixed so server and client draw the same head
function fur(rx: number, ry: number, n: number, seed: string): string {
  const pts = Array.from({ length: n }, (_, i) => {
    const a = (i / n) * Math.PI * 2, k = 1 + ((hash(seed + i) % 20) - 10) / 700;
    return { x: Math.cos(a) * rx * k, y: Math.sin(a) * ry * k };
  });
  return pts.map((p, i) => {
    const q = pts[(i + 1) % n], m = { x: (p.x + q.x) / 2, y: (p.y + q.y) / 2 };
    return `${i ? "" : `M${m.x.toFixed(1)} ${m.y.toFixed(1)}`}Q${q.x.toFixed(1)} ${q.y.toFixed(1)} ${((q.x + pts[(i + 2) % n].x) / 2).toFixed(1)} ${((q.y + pts[(i + 2) % n].y) / 2).toFixed(1)}`;
  }).join("") + "Z";
}
const HEAD = fur(120, 104, 150, "head"), FLUFF = fur(124, 108, 70, "fluff"), EAR = fur(36, 34, 40, "ear");

function layout(orbs: Orb[]): Placed[] {
  // portals on an inner ring; companies on a golden-angle spiral outside the panda
  const out: Placed[] = [];
  const portals = orbs.filter((o) => o.portal), rest = orbs.filter((o) => !o.portal);
  portals.forEach((o, i) => {
    const a = -Math.PI / 2 + (i / portals.length) * Math.PI * 2 + 0.3;
    out.push({ ...o, x: C.x + Math.cos(a) * 225, y: C.y - 10 + Math.sin(a) * 150, r: 10, tone: GOLD });
  });
  let k = 0;
  for (const o of rest) {
    let p: Pt;
    do {
      const a = k * 2.39996, t = Math.sqrt((k + 6) / (rest.length + 40));
      const j = (hash(o.company + k) % 100) / 100 - 0.5;
      p = { x: C.x + Math.cos(a) * (215 + t * 280 + j * 30), y: C.y + Math.sin(a) * (150 + t * 80 + j * 18) };
      k++;
    } while (((p.x - C.x) / 205) ** 2 + ((p.y - C.y - 30) / 175) ** 2 < 1 || p.x < 22 || p.x > W - 22 || p.y < 20 || p.y > H - 20);
    out.push({ ...o, ...p, r: 5 + (hash(o.company) % 4), tone: ATS_TONE[o.ats] || "#7d8796" });
  }
  return out;
}

const gid = (tone: string) => `pd-g${tone.slice(1)}`;

export function DiscoverPanda() {
  const [data, setData] = useState<Discover | null>(null);
  const [hover, setHover] = useState(-1);
  const orbs = useMemo(() => layout([...(data?.portals || []).map((p) => ({ company: p, ats: "careers portal", portal: true })),
                                     ...(data?.orbs || [])]), [data]);
  const svg = useRef<SVGSVGElement>(null);
  const el = useRef<Record<string, SVGElement | null>>({});
  const orbEls = useRef<(SVGGElement | null)[]>([]);
  const live = useRef({ client: null as Pt | null, hover: -1, orbs: [] as Placed[] });
  live.current.orbs = orbs;
  live.current.hover = hover;
  const ref = (k: string) => (n: SVGElement | null) => { el.current[k] = n; };

  useEffect(() => { get<Discover>("/api/control/discover?n=40").then(setData).catch(() => setData(null)); }, []);

  useEffect(() => {
    const root = svg.current;
    if (!root) return;
    const still = !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const E = el.current, L = live.current;
    // smoothed face state: s = current, every frame it eases toward the goal (different speeds per part)
    const s = { hx: 0, hy: 0, rot: 0, px: [0, 0], py: [0, 0], dil: 1, top: 0.2, bot: 0, smile: 0.2, open: 0, blush: 0, perk: 0 };
    let cur: Pt | null = null, last: Pt | null = null, speed = 0;
    let idle = -1, idleNext = 0, blinkAt = 1200, blinkT = -1, lit = -1, seen = true, visible = !document.hidden;
    let raf = 0, prev = 0;

    const toSvg = (p: Pt) => {
      const m = root.getScreenCTM();
      return m ? new DOMPoint(p.x, p.y).matrixTransform(m.inverse()) : null;
    };
    const light = (i: number) => {
      if (i === lit) return;
      if (lit >= 0) orbEls.current[lit]?.classList.remove("on");
      if (i >= 0) orbEls.current[i]?.classList.add("on");
      lit = i;
    };

    const tick = (now: number) => {
      raf = 0;
      if (!seen || !visible) return;
      const dt = Math.min(0.05, prev ? (now - prev) / 1000 : 0.016);
      prev = now;
      const ease = (rate: number) => 1 - Math.exp(-dt * rate);
      const orbs = L.orbs;

      if (L.client) {
        const p = toSvg(L.client);
        if (p) cur = { x: p.x, y: p.y };
      } else cur = null;
      speed = cur && last ? speed * 0.8 + (Math.hypot(cur.x - last.x, cur.y - last.y) / dt) * 0.2 : speed * 0.9;
      last = cur;

      // what the panda looks at: the hovered orb, else the cursor, else the orb it is reading
      if (!cur && !still && orbs.length && now > idleNext) {
        idle = Math.floor(Math.random() * orbs.length);
        idleNext = now + 1300 + Math.random() * 1500;
      }
      const h = L.hover >= 0 ? orbs[L.hover] : null;
      const target: Pt = h || cur || (idle >= 0 && orbs[idle] && !still ? orbs[idle] : { x: C.x, y: C.y + 160 });
      light(h ? L.hover : cur || still ? -1 : idle);

      const dx = target.x - C.x, dy = target.y - C.y, near = cur ? Math.hypot(cur.x - C.x, cur.y - C.y) < 115 : false;
      const excited = h ? 1 : 0, startled = !h && speed > 2600 ? 1 : 0;

      // goals for the expression
      const g = {
        hx: clamp(dx * 0.05, 14), hy: clamp(dy * 0.05, 10), rot: clamp(dx * 0.014, 7),
        dil: near ? 0.8 : excited ? 1.35 : startled ? 0.75 : 1,
        top: startled ? -0.1 : near ? 0.35 : excited ? 0.02 : cur ? 0.12 : 0.24,
        bot: near ? 0.55 : excited ? 0.22 : 0,
        smile: near ? 1 : excited ? 0.9 : startled ? -0.4 : 0.2,
        open: startled ? 0.75 : excited ? 0.35 : near ? 0.15 : 0,
        blush: near ? 1 : excited ? 0.75 : 0, perk: excited || startled ? 1 : 0,
      };
      const fast = still ? 1 : ease(9), face = still ? 1 : ease(7), eye = still ? 1 : ease(34);
      s.hx += (g.hx - s.hx) * fast; s.hy += (g.hy - s.hy) * fast; s.rot += (g.rot - s.rot) * fast;
      for (const k of ["dil", "top", "bot", "smile", "open", "blush", "perk"] as const) s[k] += (g[k] - s[k]) * face;

      // pupils: each eye aims from its own place in the turned head, so near targets cross the eyes a little
      EYE.forEach((e, i) => {
        const ex = C.x + s.hx * 1.6 + e.x, ey = C.y + s.hy * 1.6 + e.y;
        const vx = target.x - ex, vy = target.y - ey, d = Math.hypot(vx, vy) || 1, k = Math.min(1, d / 170);
        s.px[i] += ((vx / d) * 6.2 * k - s.px[i]) * eye;
        s.py[i] += ((vy / d) * 5.2 * k - s.py[i]) * eye;
      });

      // blinks: every 2.5-6 s, now and then a double
      let blink = 0;
      if (!still) {
        if (blinkT < 0 && now > blinkAt) blinkT = now;
        if (blinkT >= 0) {
          const t = (now - blinkT) / 150;
          blink = t < 1 ? t : t < 2 ? 2 - t : 0;
          if (t >= 2) { blinkT = -1; blinkAt = now + (Math.random() < 0.15 ? 180 : 2500 + Math.random() * 3500); }
        }
      }

      const set = (k: string, a: string, v: string) => E[k]?.setAttribute(a, v);
      set("body", "transform", `translate(${(C.x + s.hx * 0.3).toFixed(2)} ${(C.y + s.hy * 0.25).toFixed(2)})`);
      set("head", "transform", `translate(${(C.x + s.hx).toFixed(2)} ${(C.y + s.hy).toFixed(2)}) rotate(${s.rot.toFixed(2)})`);
      set("face", "transform", `translate(${(s.hx * 0.6).toFixed(2)} ${(s.hy * 0.6).toFixed(2)})`);
      set("earL", "transform", `translate(${(-88 - s.hx * 0.25).toFixed(2)} -78) rotate(${(-s.perk * 9 - s.rot * 0.5).toFixed(2)})`);
      set("earR", "transform", `translate(${(88 - s.hx * 0.25).toFixed(2)} -78) rotate(${(s.perk * 9 - s.rot * 0.5).toFixed(2)})`);
      const top = Math.max(s.top, blink), bot = blink ? Math.max(s.bot, blink * 0.3) : s.bot;
      for (const i of [0, 1]) {
        set(`pupil${i}`, "transform", `translate(${s.px[i].toFixed(2)} ${s.py[i].toFixed(2)})`);
        set(`iris${i}`, "r", (5.6 * s.dil).toFixed(2));
        set(`lidT${i}`, "transform", `translate(0 ${(top * 33).toFixed(2)})`);
        set(`lidB${i}`, "transform", `translate(0 ${(-bot * 33).toFixed(2)})`);
      }
      const cy = 52 - s.smile * 4, dip = 55 + s.smile * 6;
      set("mouth", "d", `M-21 ${cy.toFixed(2)}Q-10 ${dip.toFixed(2)} 0 ${(49 + s.open * 3).toFixed(2)}Q10 ${dip.toFixed(2)} 21 ${cy.toFixed(2)}`);
      set("maw", "ry", (s.open * 12).toFixed(2));
      set("maw", "rx", (7 + s.open * 6).toFixed(2));
      set("tongue", "ry", (s.open * 5).toFixed(2));
      set("tongue", "cy", (58 + s.open * 7).toFixed(2));
      set("blush", "opacity", (0.12 + s.blush * 0.55).toFixed(3));
      if (lit >= 0 && orbs[lit]) {
        const o = orbs[lit];
        set("halo", "transform", `translate(${o.x} ${o.y})`);
        set("halo", "opacity", "1");
        set("catch0", "fill", o.tone); set("catch1", "fill", o.tone);
      } else set("halo", "opacity", "0");
      set("catch0", "opacity", (h ? 0.85 : 0).toString()); set("catch1", "opacity", (h ? 0.85 : 0).toString());

      raf = requestAnimationFrame(tick);
    };
    const wake = () => { if (!raf && seen && visible) { prev = 0; raf = requestAnimationFrame(tick); } };

    const io = new IntersectionObserver(([en]) => { seen = en.isIntersecting; wake(); });
    io.observe(root);
    const vis = () => { visible = !document.hidden; wake(); };
    document.addEventListener("visibilitychange", vis);
    wake();
    return () => { cancelAnimationFrame(raf); io.disconnect(); document.removeEventListener("visibilitychange", vis); };
  }, []);

  // pointer: remember the client point (the frame converts it) and hit-test the orbs for the hover card
  const pick = (e: React.PointerEvent) => {
    live.current.client = { x: e.clientX, y: e.clientY };
    const m = svg.current?.getScreenCTM();
    if (!m) return;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse());
    let best = -1, bd = Infinity;
    orbs.forEach((o, i) => { const d = Math.hypot(o.x - p.x, o.y - p.y) - o.r; if (d < 14 && d < bd) { bd = d; best = i; } });
    if (best !== hover) setHover(best);
  };
  const leave = () => { live.current.client = null; setHover(-1); };
  const card = hover >= 0 ? orbs[hover] : null;

  return (
    <figure className="pd">
      <svg ref={svg} viewBox={`0 0 ${W} ${H}`} role="img" onPointerMove={pick} onPointerDown={pick} onPointerLeave={leave}
           className={card ? "hot" : ""}
           aria-label={`The discover station: a panda watching ${data?.total?.toLocaleString() ?? "thousands of"} job boards and ${data?.portals.length ?? 6} big-tech portals`}>
        <defs>
          {TONES.map((t) => (
            <radialGradient key={t} id={gid(t)} cx="38%" cy="32%" r="70%">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" /><stop offset="22%" stopColor={t} stopOpacity="0.95" />
              <stop offset="75%" stopColor={t} stopOpacity="0.35" /><stop offset="100%" stopColor="#07090d" stopOpacity="0.6" />
            </radialGradient>))}
          <radialGradient id="pd-fur" cx="45%" cy="35%" r="75%">
            <stop offset="0%" stopColor="#fbfaf6" /><stop offset="70%" stopColor="#e9e6de" /><stop offset="100%" stopColor="#bdb8ad" />
          </radialGradient>
          <radialGradient id="pd-black" cx="40%" cy="30%" r="80%">
            <stop offset="0%" stopColor="#2c2c31" /><stop offset="100%" stopColor="#0b0b0d" />
          </radialGradient>
          <radialGradient id="pd-muzzle" cx="50%" cy="30%" r="70%">
            <stop offset="0%" stopColor="#ffffff" /><stop offset="100%" stopColor="#ddd8cd" />
          </radialGradient>
          <radialGradient id="pd-iris" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#0a0604" /><stop offset="45%" stopColor="#2a170b" /><stop offset="85%" stopColor="#5b3518" />
            <stop offset="100%" stopColor="#1a0e06" />
          </radialGradient>
          <radialGradient id="pd-sclera" cx="45%" cy="35%" r="70%">
            <stop offset="0%" stopColor="#fdfcf8" /><stop offset="100%" stopColor="#b9b4aa" />
          </radialGradient>
          <radialGradient id="pd-halo"><stop offset="0%" stopColor="#fff" stopOpacity="0.6" /><stop offset="35%" stopColor={GOLD} stopOpacity="0.35" />
            <stop offset="100%" stopColor={GOLD} stopOpacity="0" /></radialGradient>
          <clipPath id="pd-socket"><circle r="16" /></clipPath>
        </defs>

        {SPECKS.map((p, i) => <circle key={`s${i}`} className="pd-speck" cx={p.x} cy={p.y} r={p.r} style={{ animationDelay: `${p.d}s` }} />)}

        {/* one halo follows whichever orb is lit, so only one soft glow is drawn per frame */}
        <circle ref={ref("halo")} className="pd-halo" r="46" fill="url(#pd-halo)" opacity="0" />

        {orbs.map((o, i) => (
          <g key={o.company + i} className="pd-drift" style={{ ["--d" as any]: `${(hash(o.company) % 40) / 10}s` }}>
            <g ref={(n) => { orbEls.current[i] = n; }} className="pd-orb"
               style={{ transformOrigin: `${o.x}px ${o.y}px`, ["--glow" as any]: o.tone }}>
              <circle cx={o.x} cy={o.y} r={o.r * 1.9} fill={o.tone} opacity="0.1" />
              <circle cx={o.x} cy={o.y} r={o.r} fill={`url(#${gid(o.tone)})`} stroke="#e8edf4" strokeOpacity="0.35" strokeWidth="0.8" />
              <circle className="pd-ring" cx={o.x} cy={o.y} r={o.r + 5} fill="none" stroke={o.tone} strokeWidth="1.2" />
            </g>
          </g>))}

        {/* the panda: shoulders, then a head that turns toward what it watches; face features move further than
            the outline (parallax), which reads as a 3D turn */}
        <g ref={ref("body")} transform={`translate(${C.x} ${C.y})`}>
          {/* white belly, the black band over the shoulders and down the arms, paws resting at the bottom */}
          <ellipse cx="0" cy="215" rx="118" ry="100" fill="url(#pd-fur)" />
          <ellipse cx="0" cy="118" rx="150" ry="46" fill="url(#pd-black)" />
          {[-1, 1].map((k) => (
            <g key={k}>
              <ellipse cx={k * 112} cy="190" rx="44" ry="82" transform={`rotate(${k * 16} ${k * 112} 190)`} fill="url(#pd-black)" />
              <ellipse cx={k * 74} cy="214" rx="34" ry="24" fill="url(#pd-black)" stroke="#ffffff" strokeOpacity="0.08" />
              {[-12, 0, 12].map((t) => <circle key={t} cx={k * 74 + t} cy="204" r="4" fill="#2a2a30" />)}
            </g>))}
        </g>
        <g ref={ref("head")} transform={`translate(${C.x} ${C.y})`}>
          {(["L", "R"] as const).map((s) => (
            <g key={s} ref={ref(`ear${s}`)} transform={`translate(${s === "L" ? -88 : 88} -78)`}>
              <path d={EAR} fill="url(#pd-black)" stroke="#ffffff" strokeOpacity="0.12" />
              <ellipse cx="0" cy="3" rx="17" ry="15" fill="#25252b" />
            </g>))}
          <path d={FLUFF} fill="#e9e6de" opacity="0.45" />
          <path d={HEAD} fill="url(#pd-fur)" />
          <ellipse cx="-24" cy="-62" rx="46" ry="22" fill="#fff" opacity="0.35" />
          <g ref={ref("face")}>
            <g ref={ref("blush")} opacity="0.12">
              {[-1, 1].map((k) => <ellipse key={k} className="pd-blush" cx={k * 74} cy="34" rx="17" ry="10" fill="#ff8fab" />)}
            </g>
            {EYE.map((e, i) => (
              <g key={i} transform={`translate(${e.x} ${e.y})`}>
                {/* the patch slants down and out, like a real panda's */}
                <ellipse cx={i ? 6 : -6} cy="8" rx="31" ry="43" transform={`rotate(${i ? -38 : 38} ${i ? 6 : -6} 8)`} fill="url(#pd-black)" />
                <circle r="17.5" fill="#0b0b0d" />
                <g clipPath="url(#pd-socket)">
                  <circle r="16" fill="url(#pd-sclera)" />
                  <g ref={ref(`pupil${i}`)}>
                    <circle r="11.5" fill="url(#pd-iris)" />
                    <circle ref={ref(`iris${i}`)} r="5.6" fill="#030202" />
                    <circle ref={ref(`catch${i}`)} cx="3.5" cy="3" r="2.4" opacity="0" />
                    <circle cx="-4" cy="-4.5" r="3" fill="#fff" opacity="0.92" />
                    <circle cx="4.5" cy="4" r="1.2" fill="#fff" opacity="0.6" />
                  </g>
                  <ellipse ref={ref(`lidT${i}`)} cx="0" cy="-38" rx="24" ry="22" fill="#0e0e11" />
                  <ellipse ref={ref(`lidB${i}`)} cx="0" cy="38" rx="24" ry="22" fill="#0e0e11" />
                </g>
              </g>))}
            <ellipse cx="0" cy="44" rx="54" ry="38" fill="url(#pd-muzzle)" />
            <ellipse ref={ref("maw")} cx="0" cy="58" rx="7" ry="0" fill="#3a0d14" />
            <ellipse ref={ref("tongue")} cx="0" cy="58" rx="6" ry="0" fill="#ff7a90" />
            <path d="M-15 24Q0 18 15 24Q14 36 0 40Q-14 36 -15 24Z" fill="url(#pd-black)" />
            <ellipse cx="-4" cy="25" rx="5" ry="2.2" fill="#fff" opacity="0.4" />
            <path d="M0 40V49" stroke="#141417" strokeWidth="2.2" strokeLinecap="round" />
            <path ref={ref("mouth")} d="M-21 51Q-10 56 0 49Q10 56 21 51" fill="none" stroke="#141417" strokeWidth="2.4" strokeLinecap="round" />
          </g>
        </g>
      </svg>
      {card && (
        <div className="pd-card" role="status"
             style={{ left: `${(card.x / W) * 100}%`, top: `${(card.y / H) * 100}%`, ["--tone" as any]: card.tone }}
             data-below={card.y < 110 ? "" : undefined}>
          <strong>{card.company}</strong>
          <span>{card.portal ? "big-tech careers portal" : card.ats}</span>
          {card.title && <em>{card.title}</em>}
        </div>)}
      <figcaption className="dim small">
        {data ? `${data.total.toLocaleString()} boards · ${Object.keys(data.boards).length} ATSs · ${data.portals.length} big-tech portals. Hover an orb.`
              : "Connecting to the engine…"}
      </figcaption>
    </figure>
  );
}
