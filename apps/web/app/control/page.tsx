"use client";
// Control room: start a run with your filters, then watch every stage process it live. The pipeline strip lights the
// step that is running; each applier card shows the jobs in its tabs, the questions it is answering, and results.
// Writes (start, stop, filters) only work on your own machine with REGEN_API_WRITE=1.
import Link from "next/link";
import { useEffect, useState } from "react";
import { Nav } from "../nav";
import { get, post } from "@/lib/types";

type Step = { name: string; status: string; started?: number; finished?: number };
type Applier = { name: string; updated: number; jobs: { job: string; state: string }[]; results: Record<string, number>;
                 answers: { job: string; q: string; a: string }[]; done: boolean; summary?: string };
type State = { run: { running: boolean; params?: Record<string, any>; steps?: Step[]; started?: number; finished?: number };
               run_log: string[]; appliers: Applier[]; queue: number; queue_by_ats: Record<string, number>;
               ashby_open_at: number | null; defaults: Params; write: boolean };
type Params = { days: number; max: number; appliers: number; tabs: number; scan: boolean; newgrad: boolean; feed: boolean;
                ats: string[]; cap: number; dry: boolean };
type Filters = { filters: Record<string, string>; terms: Record<string, string[]>; years_experience: number | null };

const STAGES = [
  { key: "discover", label: "Discover", about: "ATS boards" },
  { key: "newgrad", label: "New-grad leads", about: "resolved to ATS" },
  { key: "feed", label: "GitHub feeds", about: "curated lists" },
  { key: "apply", label: "Gate → Compose → Apply", about: "fit gate, resume, forms" },
];
const ATS = ["greenhouse", "lever", "ashby", "workable"];
const TONE: Record<string, string> = { SUBMITTED: "var(--gold)", "NEEDS YOU": "var(--amber)", FAILED: "var(--alarm)",
                                       SKIPPED: "var(--dim)", filling: "var(--calm)", FLAGGED: "var(--alarm)" };

function ago(t?: number | null) {
  if (!t) return "";
  const s = Math.max(0, Date.now() / 1000 - t);
  return s < 60 ? `${s | 0}s ago` : s < 3600 ? `${(s / 60) | 0}m ago` : `${(s / 3600).toFixed(1)}h ago`;
}

export default function Control() {
  const [st, setSt] = useState<State | null>(null);
  const [p, setP] = useState<Params | null>(null);
  const [f, setF] = useState<Filters | null>(null);
  const [edit, setEdit] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string>("");

  useEffect(() => {
    const pull = () => get<State>("/api/control/state").then((s) => { setSt(s); setP((cur) => cur || s.defaults); }).catch((e) => setMsg(String(e.message)));
    pull();
    get<Filters>("/api/control/filters").then((x) => { setF(x); setEdit(x.filters); }).catch(() => {});
    const t = setInterval(pull, 2000);  // processing view: every 2 s while you watch
    return () => clearInterval(t);
  }, []);

  const start = () => post("/api/control/run", p).then(() => setMsg("Run started.")).catch((e) => setMsg(e.message));
  const stop = () => post("/api/control/stop", {}).then(() => setMsg("Run stopped.")).catch((e) => setMsg(e.message));
  const saveFilters = () => post<Filters>("/api/control/filters", edit).then((x) => { setF(x); setMsg("Filters saved."); }).catch((e) => setMsg(e.message));
  const set = (k: keyof Params, v: any) => setP((x) => (x ? { ...x, [k]: v } : x));

  const running = st?.run.running;
  const steps = st?.run.steps || [];
  const stepOf = (k: string) => steps.find((s) => s.name === k);
  const totals = (st?.appliers || []).reduce<Record<string, number>>((a, ap) => {
    for (const [k, v] of Object.entries(ap.results)) a[k] = (a[k] || 0) + v;
    return a;
  }, {});

  return (
    <main className="page">
      <Nav />
      <header className="hero">
        <h1>Control room</h1>
        <p>Set the filters, start a run, and watch each stage work. Everything here is the same CLI the engine runs; nothing is sent without passing the fit gate and the form airbags.</p>
      </header>
      {msg && <p className="note" role="status">{msg}</p>}

      <section aria-label="Pipeline" className="pipe">
        {STAGES.map((s, i) => {
          const x = stepOf(s.key);
          const cls = x?.status === "running" ? "on" : x?.status === "done" ? "done" : x && x.status !== "waiting" ? "bad" : "";
          return (
            <div key={s.key} className={`pstep ${cls}`} style={{ ["--i" as any]: i }}>
              <b>{s.label}</b><small>{s.about}</small>
              <em>{x ? (x.status === "running" ? `processing · ${ago(x.started)}` : x.status) : "idle"}</em>
              {i < STAGES.length - 1 && <span className={`pflow ${cls === "on" ? "live" : ""}`} aria-hidden />}
            </div>
          );
        })}
      </section>

      <div className="grid2">
        <section className="card" aria-label="Run settings">
          <h2 className="sub">Run</h2>
          {p && (
            <form onSubmit={(e) => { e.preventDefault(); start(); }} className="form">
              <label>Days back <input type="number" min={1} max={14} value={p.days} onChange={(e) => set("days", +e.target.value)} /></label>
              <label>Max jobs <input type="number" min={1} max={200} value={p.max} onChange={(e) => set("max", +e.target.value)} /></label>
              <label>Parallel appliers <input type="number" min={1} max={4} value={p.appliers} onChange={(e) => set("appliers", +e.target.value)} /></label>
              <label>Tabs each <input type="number" min={1} max={5} value={p.tabs} onChange={(e) => set("tabs", +e.target.value)} /></label>
              <label>Daily cap <input type="number" min={1} max={100} value={p.cap} onChange={(e) => set("cap", +e.target.value)} /></label>
              <fieldset><legend>Sources</legend>
                {(["scan", "newgrad", "feed"] as const).map((k) => (
                  <label key={k} className="check"><input type="checkbox" checked={p[k]} onChange={(e) => set(k, e.target.checked)} />{k === "scan" ? "ATS boards" : k === "newgrad" ? "New-grad sites" : "GitHub lists"}</label>
                ))}
              </fieldset>
              <fieldset><legend>ATS</legend>
                {ATS.map((a) => (
                  <label key={a} className="check"><input type="checkbox" checked={p.ats.includes(a)}
                    onChange={(e) => set("ats", e.target.checked ? [...p.ats, a] : p.ats.filter((x) => x !== a))} />{a}</label>
                ))}
              </fieldset>
              <label className="check"><input type="checkbox" checked={p.dry} onChange={(e) => set("dry", e.target.checked)} />Dry run (fill, don’t submit)</label>
              <div className="row">
                <button type="submit" className="btn gold" disabled={!st?.write || running}>Start run</button>
                <button type="button" className="btn" disabled={!st?.write || !running} onClick={stop}>Stop</button>
              </div>
              {!st?.write && <p className="dim small">Read-only: start the API with REGEN_API_WRITE=1 to control runs from here.</p>}
            </form>
          )}
        </section>

        <section className="card" aria-label="Queue">
          <h2 className="sub">Queue</h2>
          <p className="big">{st?.queue ?? "…"}<small> jobs waiting</small></p>
          <ul className="bars">
            {Object.entries(st?.queue_by_ats || {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
              <li key={k}><span>{k}</span><i style={{ width: `${(100 * v) / Math.max(1, st!.queue)}%` }} /><b>{v}</b></li>
            ))}
          </ul>
          {st?.ashby_open_at && <p className="dim small">Ashby paused after a bot-check until {new Date(st.ashby_open_at * 1000).toLocaleString()}.</p>}
          <h2 className="sub">This session</h2>
          <ul className="chips">{Object.entries(totals).map(([k, v]) => <li key={k} className="chip" style={{ color: TONE[k] }}>{k} {v}</li>)}</ul>
        </section>
      </div>

      <section aria-label="Appliers" className="appliers">
        <h2 className="sub">Processing now</h2>
        {!st?.appliers.length && <p className="dim">No applier has run in the last 15 minutes.</p>}
        {st?.appliers.map((a) => (
          <article key={a.name} className={`card applier ${a.done ? "" : "live"}`}>
            <header><b>{a.name}</b><span className="dim small">{a.done ? "finished" : "working"} · {ago(a.updated)}</span></header>
            <ul className="tabs">
              {a.jobs.map((j, i) => (
                <li key={i} style={{ borderColor: TONE[j.state] || "var(--line)" }}>
                  <span>{j.job}</span><b style={{ color: TONE[j.state] || "var(--calm)" }}>{j.state}</b>
                </li>
              ))}
            </ul>
            {a.answers.length > 0 && (
              <details><summary>Latest answers ({a.answers.length})</summary>
                <dl className="qa">{a.answers.map((x, i) => <div key={i}><dt>{x.job} · {x.q}</dt><dd>{x.a}</dd></div>)}</dl>
              </details>
            )}
            {a.summary && <p className="dim small mono">{a.summary}</p>}
          </article>
        ))}
      </section>

      {st?.run_log.length ? (
        <section className="card"><h2 className="sub">Run log</h2><pre className="logbox">{st.run_log.join("\n")}</pre></section>
      ) : null}

      <section className="card" aria-label="Filters">
        <h2 className="sub">Filters</h2>
        <p className="dim small">Titles must match an include term and no exclude term; excluded employers are never applied to. Years gate: {f?.years_experience ?? "?"} years (from your presets). Separate terms with |.</p>
        {f && (["include_titles", "exclude_titles", "exclude_companies"] as const).map((k) => (
          <label key={k} className="filter">
            <span>{k.replace("_", " ")} <small className="dim">({(edit[k] || "").split("|").filter(Boolean).length} terms)</small></span>
            <textarea rows={3} value={edit[k] || ""} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} spellCheck={false} />
          </label>
        ))}
        <button className="btn" disabled={!st?.write} onClick={saveFilters}>Save filters</button>
        <p className="small"><Link href="/applications">See every application →</Link> · <Link href="/facts">Fact Bank →</Link></p>
      </section>
    </main>
  );
}
