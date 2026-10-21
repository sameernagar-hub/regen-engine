"use client";
// Evals: every benchmark run (B1-B10) the eval containers saved, newest first, with a small trend per metric.
// The supervisor starts one-shot `eval` containers when a commit lands, every 6 h, or on `supervise --eval`.
import { useEffect, useState } from "react";
import { Nav } from "../nav";
import { get, poll } from "@/lib/types";

type Sum = Record<string, any>;
type Run = { ts: number; reason: string | null; sha: string | null; summary: Sum };
type Evals = { runs: Run[]; running: { name: string; state: string; status: string }[] };

// metric key, label, unit, higher is better
const METRICS: [string, string, string, boolean][] = [
  ["answerable_pct", "Questions answerable", "%", true],
  ["coverage_pct", "JD terms on resume", "%", true],
  ["best_per_h", "Best submissions / h", "", true],
  ["code_median_s", "Email-code latency", "s", false],
  ["fit_catch_pct", "Fit gate catch", "%", true],
  ["fit_cost_pct", "Fit gate cost", "%", false],
  ["api_p95_ms", "API p95", "ms", false],
  ["bus_ms", "Event -> Postgres", "ms", false],
];
const when = (s: number) => new Date(s * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

function Spark({ vals }: { vals: (number | null)[] }) {
  const xs = vals.map((v, i) => [i, v] as const).filter(([, v]) => typeof v === "number") as [number, number][];
  if (xs.length < 2) return <span className="dim small">not enough runs</span>;
  const lo = Math.min(...xs.map((p) => p[1])), hi = Math.max(...xs.map((p) => p[1])), w = 120, h = 28;
  const pts = xs.map(([i, v]) => `${(i / (vals.length - 1)) * w},${h - 2 - ((v - lo) / (hi - lo || 1)) * (h - 4)}`).join(" ");
  return <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true"><polyline points={pts} fill="none" stroke="var(--calm)" strokeWidth="1.5" /></svg>;
}

export default function EvalsPage() {
  const [d, setD] = useState<Evals | null>(null);
  const [msg, setMsg] = useState("");
  useEffect(() => {
    const pull = () => get<Evals>("/api/control/evals?n=60").then(setD).catch((e) => setMsg(e.message));
    pull();
    return poll(pull, 20000);
  }, []);
  const runs = d?.runs || [];
  const last = runs[runs.length - 1];
  const live = (d?.running || []).filter((c) => c.state === "running");

  return (
    <main className="page">
      <Nav />
      <header className="hero">
        <h1>Evals</h1>
        <p>Benchmarks B1-B10 measured by one-shot eval containers: on every commit the repo sync pushes, every 6 hours, or when you ask (<code>docker exec deploy-supervisor-1 python -m engine supervise --eval</code>). Each container is bounded, counted and removed when it ends.</p>
      </header>
      {msg && <p className="note" role="status">{msg}</p>}
      <p className="dim small">{live.length ? `Running now: ${live.map((c) => c.name).join(", ")}` : "No eval container running."} {runs.length} runs saved.</p>

      {last && (
        <section className="card" aria-label="Trends">
          <h2 className="sub">Latest <small className="dim">{when(last.ts)} · {last.reason || "scheduled"}{last.sha ? ` · ${last.sha.slice(0, 7)}` : ""} · supervisor {last.summary.supervisor}</small></h2>
          <ul className="tabs">
            {METRICS.map(([k, label, unit]) => (
              <li key={k}><span>{label}</span>
                <span style={{ display: "flex", gap: 12, alignItems: "center" }}>
                  <Spark vals={runs.map((r) => r.summary?.[k] ?? null)} />
                  <b className="small">{last.summary[k] ?? "-"}{last.summary[k] != null ? unit : ""}</b>
                </span></li>))}
          </ul>
        </section>)}

      <section aria-label="Runs" style={{ overflowX: "auto" }}>
        <h2 className="sub">Runs</h2>
        <table className="apps">
          <thead><tr><th>When</th><th>Trigger</th><th>Supervisor</th>{METRICS.map(([k, l]) => <th key={k} className="small">{l}</th>)}<th>Errors</th></tr></thead>
          <tbody>
            {[...runs].reverse().map((r) => (
              <tr key={r.ts}>
                <td className="mono small">{when(r.ts)}</td>
                <td className="small">{r.reason || "scheduled"}{r.sha ? ` ${r.sha.slice(0, 7)}` : ""}</td>
                <td className="small">{r.summary.supervisor === "None/None" ? "-" : r.summary.supervisor}</td>
                {METRICS.map(([k]) => <td key={k} className="small">{r.summary[k] ?? "-"}</td>)}
                <td className="small" style={{ color: r.summary.errors?.length ? "var(--alarm)" : undefined }}>{r.summary.errors?.join(", ") || "none"}</td>
              </tr>))}
            {!runs.length && <tr><td colSpan={METRICS.length + 4} className="dim">{d ? "No runs yet." : "Loading…"}</td></tr>}
          </tbody>
        </table>
      </section>
    </main>
  );
}
