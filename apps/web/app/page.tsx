"use client";
// The front door is the engine itself: a radial engine whose parts are the app. Seven cylinders are the working
// views, the crankcase is the engine room, the fuel tank is the Fact Bank (every resume burns facts from it), and the
// ignition harness wires every cylinder to the memory graph. Hover a part and it lights with its live number; click
// and the engine zooms into that part as the page opens. A plain list below the engine does the same for keyboards,
// screen readers and phones.
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { PUBLIC } from "@/lib/engine";
import { get } from "@/lib/types";

type Part = { key: string; href: string; label: string; about: string; tone: string };

const W = 1200, H = 760, CX = 600, CY = 360;
const CYL: Part[] = [  // clockwise from the top, which is also the firing order's starting cylinder
  { key: "live", href: "/live", label: "Live", about: "Watch work flow through the pipeline and the tree of proof-backed applications grow.", tone: "#f2c14e" },
  { key: "control", href: "/control", label: "Control", about: "Start a run with your filters; watch every applier, tab and question as it happens.", tone: "#6fb7ff" },
  { key: "applications", href: "/applications", label: "Applications", about: "Every application with the exact resume, answers and proof that were sent.", tone: "#f2c14e" },
  { key: "needs", href: "/needs", label: "Needs you", about: "Questions only you can answer, grouped so one answer clears many jobs.", tone: "#ff9f43" },
  { key: "reach", href: "/reach", label: "Reach", about: "Workday and iCIMS jobs with a tailored resume and a copy-ready fill kit.", tone: "#b18cff" },
  { key: "outreach", href: "/outreach", label: "Outreach", about: "Truthful notes to recruiters after each application, drafted from your facts.", tone: "#5ee6b5" },
  { key: "evals", href: "/evals", label: "Evals", about: "Benchmarks B1-B10 on every commit: answer rate, JD coverage, fit gate, latency.", tone: "#ff7eb6" },
];
const CORE: Part = { key: "room", href: "/room", label: "Engine room", about: "The five stations (discover, fit gate, compose, apply, inbox) and every job end to end.", tone: "#6fb7ff" };
const FUEL: Part = { key: "facts", href: "/facts", label: "Fact Bank", about: "The fuel: every claim a resume may make, and which resumes burned it.", tone: "#f2c14e" };
const WIRES: Part = { key: "graph", href: "/graph", label: "Memory graph", about: "The wiring: you, lanes, applications, companies, facts and outcomes, connected.", tone: "#5ee6b5" };
const GEARBOX: Part = { key: "gearbox", href: "/gearbox", label: "Gearbox", about: "Shift the engine's speed (appliers, scan rate) and see what rejections taught it, fed back through the clutch.", tone: "#5ee6b5" };
const CORD: Part = { key: "mcp", href: "/mcp", label: "MCP cord", about: "Your AI client plugs in here and operates the engine at zero cost: 35 tools, from memory to the gearbox.", tone: "#5ee6b5" };
const OIL: Part = { key: "oilchange", href: "/oilchange", label: "Maintenance", about: "Clears what applications leave behind (expired files, old code and alert mail, closed postings) so the search stays fast. Shows the engine’s health and each clean-up live.", tone: "#f0b64c" };
const ALL = [...CYL, CORE, GEARBOX, FUEL, WIRES, CORD, OIL];
const FIRING = [0, 2, 4, 6, 1, 3, 5];  // radial engines fire every other cylinder

const ang = (i: number) => -90 + (i * 360) / CYL.length;
const at = (deg: number, r: number) => [CX + Math.cos((deg * Math.PI) / 180) * r, CY + Math.sin((deg * Math.PI) / 180) * r];
const HARNESS = { x: 1010, y: 640 }, TANK = { x: 150, y: 470 }, GBX = { x: 600, y: 696 }, PLUG = { x: 150, y: 150 }, FLT = { x: W - 150, y: 150 };

export default function EngineHome() {
  const router = useRouter();
  const [hot, setHot] = useState<string | null>(null);
  const [launch, setLaunch] = useState<string | null>(null);
  const [stat, setStat] = useState<Record<string, string>>({});
  const [oilLife, setOilLife] = useState(100);
  // public site: the real engine's ledger as of the last release (the demo data behind the pages is synthetic);
  // your machine: live from the ledger
  const [strip, setStrip] = useState({ boards: "~5,500", sent: "220", sentLabel: "applications submitted (as of 10-19)" });

  useEffect(() => {  // one live number per part, from the API on your machine or the proxy dataset on the public site
    const s: Record<string, string> = {};
    const put = (k: string, v: string) => { s[k] = v; setStat({ ...s }); };
    if (!PUBLIC) get<any>("/api/snapshot").then((x) => setStrip({ boards: x.boards.toLocaleString(), sent: String(x.verified), sentLabel: "applications sent with proof" })).catch(() => {});
    get<any>("/api/snapshot").then((x) => { put("live", `${x.verified} sent with proof`); put("applications", `${x.verified} with proof`); put("room", `${x.boards.toLocaleString()} boards + 6 big-tech portals watched`); }).catch(() => {});
    get<any[]>("/api/human").then((x) => put("needs", `${x.length} waiting on you`)).catch(() => {});
    get<any>("/api/control/fleet").then((x) => put("control", `${x.members.filter((m: any) => m.role === "applier" && m.up).length} appliers running`)).catch(() => {});
    get<any>("/api/control/reach?limit=1").then((x) => put("reach", `${x.listed} resumes ready`)).catch(() => {});
    get<any[]>("/api/outreach").then((x) => put("outreach", `${x.length} drafts`)).catch(() => {});
    get<any>("/api/control/evals?n=60").then((x) => put("evals", `${x.runs.length} benchmark runs`)).catch(() => {});
    get<any>("/api/control/gearbox").then((x) => put("gearbox", `gear ${x.gear.gear}, ${x.feedback.stats.rejected ?? 0} rejections read`)).catch(() => {});
    get<any>("/api/control/oilchange").then((x) => { setOilLife(x.life ?? 100); put("oilchange", x.running ? `cleaning up: ${x.stage}` : `health ${Math.round(x.life ?? 100)}%`); }).catch(() => {});
    get<any>("/api/control/mcp").then((x) => put("mcp", `${x.tools.length} tools, bank ${x.servers[0].up ? "up" : "down"}`)).catch(() => {});
    get<any>("/api/factbank").then((x) => { put("facts", `${x.facts.length} facts, ${x.resumes_built} resumes`); put("graph", `${x.roles.length + x.facts.length + x.projects.length}+ nodes`); }).catch(() => {});
  }, []);

  const go = (p: Part) => {
    if (launch) return;
    const still = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (still) return router.push(p.href);
    setLaunch(p.key);
    router.prefetch(p.href);
    setTimeout(() => router.push(p.href), 560);
  };
  const focus = useMemo(() => {  // where the zoom flies to, in SVG units
    if (!launch) return null;
    const i = CYL.findIndex((c) => c.key === launch);
    if (i >= 0) { const [x, y] = at(ang(i), 190); return { x, y }; }
    return launch === "facts" ? TANK : launch === "graph" ? HARNESS : launch === "gearbox" ? GBX : launch === "mcp" ? PLUG : launch === "oilchange" ? FLT : { x: CX, y: CY };
  }, [launch]);
  const part = (p: Part) => ({
    role: "link" as const, tabIndex: 0, "aria-label": `${p.label}: ${p.about}`,
    className: `part${hot === p.key ? " hot" : ""}${launch === p.key ? " launch" : ""}`,
    style: { ["--tone" as any]: p.tone },
    onMouseEnter: () => setHot(p.key), onMouseLeave: () => setHot((h) => (h === p.key ? null : h)),
    onFocus: () => setHot(p.key), onBlur: () => setHot((h) => (h === p.key ? null : h)),
    onClick: () => go(p), onKeyDown: (e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(p); } },
  });
  const info = ALL.find((p) => p.key === hot);

  return (
    <main className={`engine-home${launch ? " launching" : ""}`} id="main">
      <header className="engine-title">
        <p className="eyebrow"><span className="brand">REGEN</span> open-source job engine</p>
        <h1>Be the first application they read, <em>not the 400th.</em></h1>
        <p>REGEN catches roles the hour they go live, writes a resume that only claims what you can prove, applies, and
          keeps a receipt for every submit. Zero model spend. Your machine, your data.</p>
        <ul className="proof-strip" aria-label="Measured in production">
          <li><b>{strip.boards}</b> company boards watched</li><li><b>{strip.sent}</b> {strip.sentLabel}</li><li><b>$0</b> in model costs</li>
        </ul>
        {PUBLIC && <p className="demo-pill" title="Built by scripts/proxy_dataset.py: the real API over a synthetic engine">Interactive demo on synthetic data. Every part of the engine is a door: hover to wake it, click to step inside.</p>}
      </header>

      <svg className="engine" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" aria-label="The REGEN engine. Each part opens a view.">
        <defs>
          <radialGradient id="case" cx=".45" cy=".4" r=".7"><stop offset="0" stopColor="#2b3442" /><stop offset=".7" stopColor="#141a23" /><stop offset="1" stopColor="#0b0f15" /></radialGradient>
          <linearGradient id="barrel" x1="0" x2="1"><stop offset="0" stopColor="#1a212c" /><stop offset=".45" stopColor="#3a4556" /><stop offset="1" stopColor="#141a22" /></linearGradient>
          <linearGradient id="fuel" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stopColor="#f2c14e" stopOpacity=".85" /><stop offset="1" stopColor="#ff9f43" stopOpacity=".45" /></linearGradient>
          <filter id="lit" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>

        <g className="engine-body" style={focus ? { transformOrigin: `${focus.x}px ${focus.y}px` } : undefined}>
          {/* ignition harness: one wire from each spark plug to the memory graph */}
          <g {...part(WIRES)}>
            {CYL.map((c, i) => {
              const [px, py] = at(ang(i), 268);
              const [mx, my] = at(ang(i) + 22, 330);
              return <path key={c.key} className={`wire${hot === c.key ? " live" : ""}`} d={`M ${px} ${py} Q ${mx} ${my} ${HARNESS.x} ${HARNESS.y}`} />;
            })}
            <g transform={`translate(${HARNESS.x} ${HARNESS.y})`}>
              {[[0, 0], [-46, -18], [-30, 30], [34, -34], [48, 14], [10, 44], [-8, -48]].map(([x, y], k, a) => (
                <g key={k}>{k > 0 && <line className="graph-edge" x1={0} y1={0} x2={x} y2={y} />}
                  {k > 1 && <line className="graph-edge" x1={a[k - 1][0]} y1={a[k - 1][1]} x2={x} y2={y} />}
                  <circle className="graph-node" cx={x} cy={y} r={k ? 6 : 10} style={{ animationDelay: `${k * 0.3}s` }} /></g>))}
              <rect className="hit" x={-70} y={-70} width={140} height={140} />
            </g>
            <text className="part-label" x={HARNESS.x} y={HARNESS.y + 84}>Memory graph</text>
          </g>

          {/* fuel tank and line: the Fact Bank feeds the crankcase */}
          <g {...part(FUEL)}>
            <path className="fuel-line" d={`M ${TANK.x + 46} ${TANK.y - 30} C ${TANK.x + 160} ${TANK.y - 40} ${CX - 220} ${CY + 120} ${CX - 92} ${CY + 40}`} />
            <rect className="tank" x={TANK.x - 46} y={TANK.y - 110} width={92} height={190} rx={42} />
            <rect className="tank-fuel" x={TANK.x - 38} y={TANK.y - 40} width={76} height={112} rx={34} />
            <line className="tank-gauge" x1={TANK.x} y1={TANK.y - 96} x2={TANK.x} y2={TANK.y + 66} />
            <text className="part-label" x={TANK.x} y={TANK.y + 112}>Fact Bank</text>
          </g>

          {/* oil filter: the MCP plug's mirror image (same size, height, label offset; its oil line mirrors the cord)
              so the two top corners read as a pair; the window shows the oil life */}
          <g {...part(OIL)}>
            <path className="ocf-line" d={`M ${FLT.x - 22} ${FLT.y + 10} C ${FLT.x - 160} ${FLT.y + 20} ${CX + 200} ${CY - 60} ${CX + 60} ${CY - 20}`} />
            <g transform={`translate(${FLT.x} ${FLT.y + 5}) scale(.5)`}>
              <rect className="ocf-can" x={-32} y={-60} width={64} height={120} rx={14} />
              <rect className="ocf-can" x={-40} y={-74} width={80} height={16} rx={5} />
              {[-18, -6, 6, 18].map((x) => <line key={x} className="ocf-pleat" x1={x} y1={-44} x2={x} y2={44} />)}
              <rect className="ocf-level" x={-24} y={44 - 0.88 * oilLife} width={6} height={0.88 * oilLife} rx={3} />
              <rect className="hit" x={-100} y={-90} width={200} height={200} />
            </g>
            <text className="part-label" x={FLT.x} y={FLT.y + 62}>Maintenance</text>
          </g>

          {/* the MCP cord: your AI client's plug, wired into the crankcase (drawn behind the cylinders) */}
          <g {...part(CORD)}>
            <path id="mcpcord" className="mcp-cord" d={`M ${PLUG.x + 22} ${PLUG.y + 10} C ${PLUG.x + 160} ${PLUG.y + 20} ${CX - 200} ${CY - 60} ${CX - 60} ${CY - 20}`} />
            <circle className="mcp-spark" r={5}><animateMotion dur="2.6s" repeatCount="indefinite" path={`M ${PLUG.x + 22} ${PLUG.y + 10} C ${PLUG.x + 160} ${PLUG.y + 20} ${CX - 200} ${CY - 60} ${CX - 60} ${CY - 20}`} /></circle>
            <g transform={`translate(${PLUG.x} ${PLUG.y})`}>
              <rect className="mcp-plug" x={-22} y={-14} width={44} height={48} rx={8} />
              <rect className="mcp-pin" x={-14} y={-24} width={6} height={12} rx={2} /><rect className="mcp-pin" x={8} y={-24} width={6} height={12} rx={2} />
              <rect className="hit" x={-50} y={-40} width={100} height={100} />
            </g>
            <text className="part-label" x={PLUG.x} y={PLUG.y + 62}>MCP cord</text>
          </g>

          {/* gearbox under the crankcase: the crank drives it down the shaft, feedback climbs back up the dashed line */}
          <g {...part(GEARBOX)}>
            <line className="gbx-shaft" x1={CX - 3} y1={CY + 96} x2={CX - 3} y2={GBX.y - 34} />
            <path className="gbx-return" d={`M ${CX + 30} ${GBX.y - 10} C ${CX + 14} ${GBX.y - 60} ${CX + 5} ${CY + 160} ${CX + 5} ${CY + 98}`} />
            <g transform={`translate(${GBX.x - 24} ${GBX.y})`}><g className="gbx-a">
              {Array.from({ length: 14 }, (_, t) => <rect key={t} className="gbx-gear" x={-4} y={-40} width={8} height={12} rx={2} transform={`rotate(${t * (360 / 14)})`} />)}
              <circle className="gbx-gear" r={30} /><circle cx={0} cy={0} r={7} fill="#0b0f15" /></g></g>
            <g transform={`translate(${GBX.x + 34} ${GBX.y + 4})`}><g className="gbx-b">
              {Array.from({ length: 10 }, (_, t) => <rect key={t} className="gbx-gear" x={-4} y={-29} width={8} height={11} rx={2} transform={`rotate(${t * 36 + 18})`} />)}
              <circle className="gbx-gear" r={20} /><circle cx={0} cy={0} r={5} fill="#0b0f15" /></g></g>
            <rect className="hit" x={GBX.x - 80} y={GBX.y - 50} width={160} height={96} />
            <text className="part-label" x={GBX.x} y={GBX.y + 60}>Gearbox</text>
          </g>

          {/* seven cylinders: barrel with cooling fins, head, spark plug, a piston on the firing order */}
          {CYL.map((c, i) => {
            const a = ang(i), [lx, ly] = at(a, 328);
            return (
              <g key={c.key} {...part(c)}>
                <g transform={`rotate(${a + 90} ${CX} ${CY})`}>
                  <rect className="barrel" x={CX - 30} y={CY - 250} width={60} height={160} rx={6} />
                  {Array.from({ length: 9 }, (_, f) => <rect key={f} className="fin" x={CX - 42} y={CY - 236 + f * 15} width={84} height={5} rx={2} />)}
                  <rect className="head" x={CX - 36} y={CY - 268} width={72} height={24} rx={8} />
                  <rect className="plug" x={CX - 5} y={CY - 286} width={10} height={20} rx={3} />
                  <g className="piston" style={{ animationDelay: `${(FIRING.indexOf(i) / CYL.length) * -1.4}s` }}>
                    <rect x={CX - 24} y={CY - 200} width={48} height={30} rx={4} />
                    <line x1={CX} y1={CY - 172} x2={CX} y2={CY - 100} />
                  </g>
                  <circle className="spark" cx={CX} cy={CY - 288} r={5} style={{ animationDelay: `${(FIRING.indexOf(i) / CYL.length) * -1.4}s` }} />
                  <rect className="hit" x={CX - 46} y={CY - 296} width={92} height={210} />
                </g>
                <text className="part-label" x={lx} y={ly + (ly > CY + 40 ? 28 : ly < CY - 40 ? -14 : 6)}>{c.label}</text>
                {c.key === "needs" && stat.needs && <text className="part-badge" x={lx} y={ly + (ly > CY ? 46 : 8)}>{stat.needs.split(" ")[0]}</text>}
              </g>
            );
          })}

          {/* crankcase: the engine room, turning */}
          <g {...part(CORE)}>
            <circle className="case" cx={CX} cy={CY} r={96} />
            <g className="crank" style={{ transformOrigin: `${CX}px ${CY}px` }}>
              {Array.from({ length: 24 }, (_, t) => { const [x1, y1] = at(t * 15, 70), [x2, y2] = at(t * 15, 84); return <line key={t} className="tooth" x1={x1} y1={y1} x2={x2} y2={y2} />; })}
              <circle className="crank-pin" cx={CX + 34} cy={CY} r={12} />
            </g>
            <circle className="hub" cx={CX} cy={CY} r={44} />
            <text className="hub-text" x={CX} y={CY + 5}>REGEN</text>
          </g>
        </g>
      </svg>

      <aside className={`engine-card${info ? " on" : ""}`} aria-live="polite" style={info ? { ["--tone" as any]: info.tone } : undefined}>
        {info ? (<><b>{info.label}</b><span className="stat">{stat[info.key] || "·"}</span><p>{info.about}</p><small>click to open</small></>)
              : (<><b>Twelve parts, one engine</b><p>Discover, judge, write, apply, hear back. Pick a part.</p></>)}
      </aside>

      <nav className="engine-list" aria-label="Engine parts">
        {ALL.map((p) => (
          <a key={p.key} href={p.href} style={{ ["--tone" as any]: p.tone }} className={hot === p.key ? "hot" : ""}
             onMouseEnter={() => setHot(p.key)} onMouseLeave={() => setHot(null)} onFocus={() => setHot(p.key)} onBlur={() => setHot(null)}
             onClick={(e) => { e.preventDefault(); go(p); }}>{p.label}</a>
        ))}
      </nav>
    </main>
  );
}
