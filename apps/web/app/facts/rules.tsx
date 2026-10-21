"use client";
// The rules, the other half of the fuel (v1.2). Facts say what a resume may claim; rules say what the engine may do.
// Each rule group is a tank whose fuel line feeds the cylinder of the stage it runs in (discover, select, fill,
// submit). Pulses on a line are rule firings: more firings in the event log, more fuel in flight. Pick a tank to list
// its rules. The catalog is read from the modules that run the rules (engine/rules.py), so it cannot drift.
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { get } from "@/lib/types";

type Rule = { id: string; name?: string | null; pattern?: string; source?: string; note?: string; fires?: number;
              status?: string; rejected?: number; seen?: number; since?: string; line?: number };
type Group = { id: string; name: string; stage: string; where: string; about: string; rules: Rule[]; count: number;
               fires: number; live?: Record<string, any> };
type Catalog = { groups: Group[]; recent: { ts: string; group: string; rule: string; job: string }[]; total: number };

const STAGES = ["discover", "select", "fill", "submit"] as const;
const COLOR: Record<string, string> = { title: "#6fb7ff", gate: "#f2c14e", learned: "#ff7eb6", answers: "#7ef0c1",
  safety: "#ff5a5f", override: "#b39dff" };
const CYL_X = (i: number) => 560 + i * 110;  // four cylinders in a row
const TANK_Y = (i: number) => 46 + i * 66;

// how much fuel is in flight: 1 pulse for an idle rule set, up to 5 for thousands of firings (log scale)
const pulses = (fires: number) => Math.max(1, Math.min(5, Math.round(1 + Math.log10(1 + fires) * 1.2)));
const sourceKind = (s = "") => (s.startsWith("preset") ? "preset" : s.split(":")[0]);

export function RulesEngine() {
  const [c, setC] = useState<Catalog | null>(null);
  const [err, setErr] = useState("");
  const [pick, setPick] = useState("gate");
  const [q, setQ] = useState("");

  useEffect(() => {
    const pull = () => get<Catalog>("/api/rules").then(setC).catch((e) => setErr(e.message));
    pull();
    const t = setInterval(pull, 60000);
    return () => clearInterval(t);
  }, []);

  const lines = useMemo(() => (c?.groups || []).map((g, i) => {
    // tank outlet -> over the block -> down into the cylinder's spark plug
    const y0 = TANK_Y(i) + 22, x1 = CYL_X(STAGES.indexOf(g.stage as any)) + (i % 2 ? 9 : -9);
    return { g, i, d: `M 236 ${y0} C ${380 + i * 18} ${y0}, ${x1} ${80 + i * 8}, ${x1} 190` };
  }), [c]);

  if (err) return <section className="card" id="rules"><h2 className="sub">Rules</h2><p className="err">{err}</p></section>;
  if (!c) return <section className="card" id="rules"><h2 className="sub">Rules</h2><p className="dim">Loading the rules…</p></section>;

  const g = c.groups.find((x) => x.id === pick) || c.groups[0];
  const needle = q.trim().toLowerCase();
  const shown = g.rules.filter((r) => !needle || `${r.name || ""} ${r.pattern || ""} ${r.source || ""} ${r.note || ""}`.toLowerCase().includes(needle));
  const maxFire = Math.max(1, ...g.rules.map((r) => r.fires || 0));
  const fed = (s: string) => c.groups.filter((x) => x.stage === s);

  return (
    <section className="card rules" id="rules" aria-label="Rules that drive the engine">
      <h2 className="sub">Rules: the other half of the fuel</h2>
      <p className="dim small">
        Facts say what a resume may claim; rules say what the engine may do. {c.total} rules in {c.groups.length} groups, each read from
        the code that runs it. A tank feeds the stage it runs in; pulses are firings from the event log. Select a tank to list its rules.
      </p>

      <svg viewBox="0 0 1000 470" className="rules-svg" role="img"
           aria-label={`Rule groups feeding the engine: ${c.groups.map((x) => `${x.name} ${x.count} rules, ${x.fires} firings`).join("; ")}`}>
        <defs>
          <linearGradient id="rsteel" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2b3442" /><stop offset="1" stopColor="#141a22" /></linearGradient>
          <filter id="rglow" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="3.5" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>

        {/* fuel lines, then the fuel in flight */}
        {lines.map(({ g: x, d }) => (
          <path key={"l" + x.id} d={d} className={`fuel-line${x.id === pick ? " on" : ""}`} style={{ stroke: COLOR[x.id] }} />
        ))}
        {lines.map(({ g: x, d }) => Array.from({ length: pulses(x.fires) }, (_, k) => {
          const dur = 3.2 + (x.id.length % 3) * 0.6;
          return (
            <circle key={x.id + k} r={x.id === pick ? 5 : 3.6} className="fuel" fill={COLOR[x.id]} filter="url(#rglow)">
              <animateMotion dur={`${dur}s`} begin={`${(k * dur) / pulses(x.fires)}s`} repeatCount="indefinite" path={d} />
            </circle>
          );
        }))}

        {/* tanks: one per rule group, fill level = share of the busiest group's firings */}
        {c.groups.map((x, i) => {
          const max = Math.max(1, ...c.groups.map((y) => y.fires));
          const lvl = x.fires ? 0.15 + 0.85 * (Math.log10(1 + x.fires) / Math.log10(1 + max)) : 0.06;
          return (
            <g key={x.id} className={`tank${x.id === pick ? " on" : ""}`} transform={`translate(20 ${TANK_Y(i)})`} tabIndex={0} role="button"
               aria-pressed={x.id === pick} aria-label={`${x.name}: ${x.count} rules`} onClick={() => setPick(x.id)}
               onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setPick(x.id))}>
              <rect width={216} height={44} rx={10} className="tank-shell" />
              <rect x={3} y={3} width={210 * lvl} height={38} rx={8} fill={COLOR[x.id]} className="tank-fuel" />
              <text x={12} y={19} className="tank-name">{x.name}</text>
              <text x={12} y={35} className="tank-num">{x.count} rules · {x.fires.toLocaleString()} firings</text>
            </g>
          );
        })}

        {/* the engine: four cylinders fire in order; a cylinder glows when a picked group feeds it */}
        <rect x={500} y={180} width={460} height={150} rx={22} className="block" />
        {STAGES.map((s, i) => {
          const x = CYL_X(i), hot = fed(s).some((y) => y.id === pick);
          return (
            <g key={s} className={`cyl${hot ? " hot" : ""}`} style={{ ["--d" as any]: `${i * 0.35}s` }}>
              <rect x={x - 34} y={196} width={68} height={118} rx={10} className="bore" />
              <g className="piston"><rect x={x - 28} y={232} width={56} height={30} rx={6} /><line x1={x} y1={262} x2={x} y2={352} /></g>
              <circle cx={x} cy={196} r={7} className="spark" />
              <text x={x} y={154} className="cyl-label">{s}</text>
              <text x={x} y={170} className="cyl-sub">{fed(s).map((y) => y.name.split(" ")[0]).join(" + ")}</text>
            </g>
          );
        })}
        <g transform="translate(725 400)"><g className="crank"><circle r={30} className="crank-disc" /><rect x={-4} y={-30} width={8} height={60} rx={4} className="crank-arm" /></g></g>
        <line x1={500} y1={400} x2={950} y2={400} className="crank-shaft" />
        <text x={950} y={432} className="cyl-sub end">applications out</text>
      </svg>

      <div className="rules-pick">
        <div>
          <h3 style={{ color: COLOR[g.id] }}>{g.name}</h3>
          <p className="small">{g.about}</p>
          <p className="small dim">Runs in <b>{g.stage}</b> · lives in <code>{g.where}</code>
            {g.live?.clutch && <> · clutch <b>{g.live.clutch}</b> (<Link href="/gearbox">gearbox</Link>)</>}
            {g.live?.saved_answers != null && <> · {g.live.saved_answers} saved answers checked first · firings from the last {g.live.apps_replayed} applications</>}
          </p>
          {g.live?.by_source && (
            <ul className="chips">{Object.entries(g.live.by_source as Record<string, number>).sort((a, b) => b[1] - a[1])
              .map(([k, n]) => <li key={k} className={`chip src-${k.replace(/\W+/g, "-")}`}>{k} {n}</li>)}</ul>)}
        </div>
        <input type="search" placeholder={`Filter ${g.count} rules`} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filter rules" />
      </div>

      <ol className="rule-list">
        {shown.map((r) => (
          <li key={r.id}>
            <div className="rhead">
              <b>{r.name || (r.note ? r.note : r.id)}</b>
              {r.source && <span className={`chip src-${sourceKind(r.source).replace(/\W+/g, "-")}`}>{r.source}</span>}
              {r.status && <span className={`tag ${r.status}`}>{r.status}</span>}
              <span className="usebar" aria-hidden="true"><i style={{ width: `${(100 * (r.fires || 0)) / maxFire}%`, background: COLOR[g.id] }} /></span>
              <small>{(r.fires || 0).toLocaleString()}</small>
            </div>
            {r.pattern && <code className="rpat">{r.pattern}</code>}
            {r.rejected != null && <small className="dim">in {r.rejected} rejected of {r.seen} JDs</small>}
          </li>
        ))}
        {!shown.length && <li className="dim">{g.rules.length ? "No rule matches the filter." : "None yet: the feedback loop proposes phrases after more rejections."}</li>}
      </ol>

      {c.recent.length > 0 && (
        <>
          <h3 className="sub">Latest firings</h3>
          <ul className="ticker">{c.recent.slice(0, 10).map((r, i) => (
            <li key={i}><span className="dot" style={{ background: COLOR[r.group] }} /><small className="dim">{(r.ts || "").slice(5, 16).replace("T", " ")}</small>
              {" "}{r.group === "gate" ? "fit gate skipped" : "filled"} <b>{r.job}</b> <small className="dim">({r.rule})</small></li>))}</ul>
        </>
      )}
    </section>
  );
}
