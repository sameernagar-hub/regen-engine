"use client";
// Control room: start a run with your filters, then watch every stage process it live. The pipeline strip lights the
// step that is running; each applier card shows the jobs in its tabs, the questions it is answering, and results.
// Writes (start, stop, filters) only work on your own machine with REGEN_API_WRITE=1.
import Link from "next/link";
import { useEffect, useState } from "react";
import { Nav } from "../nav";
import { LocalOnly } from "../local-only";
import { PUBLIC } from "@/lib/engine";
import { api, get, post } from "@/lib/types";

type Step = { name: string; status: string; started?: number; finished?: number };
type Applier = { name: string; updated: number; jobs: { job: string; state: string }[]; results: Record<string, number>;
                 answers: { job: string; q: string; a: string }[]; done: boolean; summary?: string };
type State = { run: { running: boolean; params?: Record<string, any>; steps?: Step[]; started?: number; finished?: number };
               run_log: string[]; appliers: Applier[]; queue: number; queue_by_ats: Record<string, number>;
               ashby_open_at: number | null; defaults: Params; write: boolean };
type Params = { days: number; max: number; appliers: number; tabs: number; scan: boolean; newgrad: boolean; feed: boolean;
                ats: string[]; cap: number; dry: boolean; loop: number };
type Member = { role: string; host: string; age: number; up: boolean; state?: string; batch?: string | null;
                pass?: number; codes?: number; waiting?: number; services?: Record<string, string> };
type Audit = { ts: string; action: string; target: string; reason?: string; jobs?: number; want?: number };
type Fleet = { members: Member[]; inbox: number; claimed: number; done: number; stale_claims: string[];
               codes_waiting: string[]; gmail_tab_age: number | null; imap_codes?: boolean; problems: string[];
               verdict: string; kill?: string | null; limits?: { min: number; max: number }; audit?: Audit[];
               ledger?: string; containers?: Inventory | null };
type Box = { id: string; name: string; service: string; state: string; status: string; image: string; created: number;
             scaled: boolean; cpu?: number; mem_mb?: number; mem_limit_mb?: number };
type Inventory = { ts: number; age: number; stale?: boolean; project: string; containers: Box[];
                   totals: { running: number; all: number; cpu: number; mem_mb: number } };
type ReachRow = { listed: string; ats: string; company: string; title: string; url: string; location: string;
                  lane?: string; jd_match?: number; resume: string };
type Reach = { rows: ReachRow[]; listed: number; gated: number; by_ats: Record<string, number> };
type Bench = { ts: number | null; results: Record<string, Record<string, any>> };
type Filters = { filters: Record<string, string>; terms: Record<string, string[]>; years_experience: number | null };

const STAGES = [
  { key: "discover", label: "Discover", about: "ATS boards" },
  { key: "newgrad", label: "New-grad leads", about: "resolved to ATS" },
  { key: "feed", label: "GitHub feeds", about: "curated lists" },
  { key: "apply", label: "Gate → Compose → Apply", about: "fit gate, resume, forms" },
];
const ATS = ["greenhouse", "lever", "ashby", "workable", "smartrecruiters", "workday", "icims"];
// one line per benchmark: the headline number (engine/bench.py; full JSON in workspace/bench/latest.json)
const BENCH: [string, string, (r: Record<string, any>) => string][] = [
  ["B1_select", "Selection (lazy heap vs sort)", (r) => `x${r.speedup} (${r.heap_ms} ms vs ${r.sort_ms} ms)`],
  ["B2_answers", "Questions answerable now", (r) => `${r.answerable_pct}% of non-legal (${r.answerable_now})`],
  ["B3_claims", "Batch claims exactly once", (r) => `${r.exactly_once ? "yes" : "NO"}: ${r.unique}/${r.batches}`],
  ["B4_coverage", "JD terms on the resume", (r) => `median ${r.median_coverage_pct}%, ATS read-back ${r.median_ats_readback}`],
  ["B5_rate", "Verified submissions / active hour", (r) => `best ${r.best_per_h}/h` + (r.days ? `, latest day ${(Object.values(r.days).pop() as any)?.per_h ?? "?"}/h` : "")],
  ["B6_codes", "Email-code latency", (r) => r.median_s == null ? `no codes yet (${r.code_timeouts} timeouts)` : `median ${r.median_s}s, p90 ${r.p90_s}s, ${r.code_timeouts} timeouts`],
  ["B7_fitgate", "Fit gate on past rejections", (r) => `catch ${r.catch_rate_pct ?? "-"}%, would block ${r.would_block_ok_pct ?? "-"}% of the rest (${r.submitted_with_jd} JDs)`],
  ["B8_supervisor", "Supervisor decisions (faked Docker)", (r) => `${r.passed}/${r.total} pass` + (r.failed?.length ? `: ${r.failed.join(", ")}` : "")],
  ["B9_api", "API latency", (r) => r.skipped ? "skipped" : `p50 ${r.p50_ms} ms, p95 ${r.p95_ms} ms`],
  ["B10_bus", "Event -> Postgres", (r) => r.skipped ? "skipped" : r.ok ? `${r.latency_ms} ms` : "NOT COPIED"],
];
const uptime = (s: number) => { const x = Date.now() / 1000 - s; return x < 3600 ? `${(x / 60) | 0}m` : x < 86400 ? `${(x / 3600).toFixed(1)}h` : `${(x / 86400).toFixed(1)}d`; };
const TONE: Record<string, string> = { SUBMITTED: "var(--gold)", "NEEDS YOU": "var(--amber)", FAILED: "var(--alarm)",
                                       SKIPPED: "var(--dim)", filling: "var(--calm)", FLAGGED: "var(--alarm)" };

function ago(t?: number | null) {
  if (!t) return "";
  const s = Math.max(0, Date.now() / 1000 - t);
  return s < 60 ? `${s | 0}s ago` : s < 3600 ? `${(s / 60) | 0}m ago` : `${(s / 3600).toFixed(1)}h ago`;
}

export default function Control() {
  if (PUBLIC) return <LocalOnly title="Control room" what="Start runs with your filters and watch every stage process them." />;
  return <ControlView />;
}

function ControlView() {
  const [st, setSt] = useState<State | null>(null);
  const [p, setP] = useState<Params | null>(null);
  const [f, setF] = useState<Filters | null>(null);
  const [edit, setEdit] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string>("");
  const [fl, setFl] = useState<Fleet | null>(null);
  const [rc, setRc] = useState<Reach | null>(null);
  const [bn, setBn] = useState<Bench | null>(null);

  useEffect(() => {
    const pull = () => get<State>("/api/control/state").then((s) => { setSt(s); setP((cur) => cur || s.defaults); }).catch((e) => setMsg(String(e.message)));
    const pullFleet = () => get<Fleet>("/api/control/fleet").then(setFl).catch(() => {});
    pull(); pullFleet();
    const tf = setInterval(pullFleet, 5000);  // heartbeats land every 30-60 s
    const pullSlow = () => { get<Reach>("/api/control/reach").then(setRc).catch(() => {}); get<Bench>("/api/control/bench").then(setBn).catch(() => {}); };
    pullSlow();
    const ts = setInterval(pullSlow, 60000);  // reach rows land once per pipeline pass; benchmarks every few hours
    get<Filters>("/api/control/filters").then((x) => { setF(x); setEdit(x.filters); }).catch(() => {});
    const t = setInterval(pull, 2000);  // processing view: every 2 s while you watch
    return () => { clearInterval(t); clearInterval(tf); clearInterval(ts); };
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
              <label title="0 = one pass. Otherwise rescan every N minutes and apply to jobs that just opened.">Rescan every (min) <input type="number" min={0} max={240} value={p.loop} onChange={(e) => set("loop", +e.target.value)} /></label>
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

      {fl && (
        <section className="card" aria-label="Fleet">
          <h2 className="sub">Fleet <small className="dim">({fl.verdict})</small></h2>
          {fl.kill && <p className="small" role="alert" style={{ color: "var(--alarm)" }}>
            KILL SWITCH ON: {fl.kill}. Everything is stopped until it is cleared (MCP clear_kill, or
            <span className="mono"> supervise --clear</span>).</p>}
          <ul className="chips">
            {Object.entries(fl.members.find((m) => m.role === "supervisor" && m.up)?.services || {}).map(([k, v]) => (
              <li key={k} className="chip" style={{ color: v === "ok" ? "var(--calm)" : "var(--alarm)" }}>{k} {v}</li>))}
            {fl.ledger && <li className="chip">ledger {fl.ledger}</li>}
            {fl.limits && <li className="chip">appliers {fl.limits.min}..{fl.limits.max}</li>}
          </ul>
          <ul className="chips">
            <li className="chip">inbox {fl.inbox}</li><li className="chip">claimed {fl.claimed}</li>
            <li className="chip">done {fl.done}</li>
            <li className="chip" style={{ color: fl.codes_waiting.length ? "var(--amber)" : undefined }}>codes waiting {fl.codes_waiting.length}</li>
            {fl.imap_codes
              ? <li className="chip" style={{ color: "var(--calm)" }}>codes via IMAP</li>
              : <li className="chip" style={{ color: fl.gmail_tab_age == null || fl.gmail_tab_age > 120 ? "var(--alarm)" : "var(--calm)" }}>
                  Gmail tab {fl.gmail_tab_age == null ? "silent" : `posted ${fl.gmail_tab_age}s ago`}</li>}
          </ul>
          <ul className="tabs">
            {fl.members.filter((m) => m.up || m.age < 300).map((m) => (
              <li key={m.role + m.host} style={{ borderColor: m.up ? "var(--calm)" : "var(--alarm)" }}>
                <span>{m.role} · <span className="mono small">{m.host}</span> · {m.state}{m.batch ? ` ${m.batch}` : ""}{m.pass ? ` (pass ${m.pass})` : ""}</span>
                <b style={{ color: m.up ? "var(--calm)" : "var(--alarm)" }}>{m.up ? "up" : "down"} · {m.age}s</b>
              </li>
            ))}
          </ul>
          {fl.problems.map((x) => <p key={x} className="small" style={{ color: "var(--amber)" }}>! {x}</p>)}
          {!!fl.audit?.length && (<>
            <h2 className="sub">Supervisor audit</h2>
            <ul className="tabs">
              {fl.audit.slice().reverse().map((a, i) => (
                <li key={i}><span className="mono small">{a.ts.slice(5, 16).replace("T", " ")}</span>
                  <span>{a.action} {a.target}{a.reason ? ` (${a.reason})` : ""}</span>
                  <b className="dim small">{a.jobs != null ? `${a.jobs} jobs → ${a.want}` : ""}</b></li>))}
            </ul></>)}
        </section>
      )}

      {fl?.containers && (
        <section className="card" aria-label="Containers">
          <h2 className="sub">Containers <small className="dim">({fl.containers.totals.running}/{fl.containers.totals.all} running ·
            CPU {fl.containers.totals.cpu}% · {fl.containers.totals.mem_mb} MiB · {fl.containers.stale ? "STALE " : ""}inventory {fl.containers.age}s old)</small></h2>
          <p className="dim small">What the supervisor sees over the Docker socket (only it holds the socket). It creates and removes appliers; any other service is restarted after 3 failed probes.</p>
          <div style={{ overflowX: "auto" }}>
            <table className="apps">
              <thead><tr><th>Service</th><th>Container</th><th>State</th><th>Up</th><th>CPU</th><th>Memory</th></tr></thead>
              <tbody>
                {fl.containers.containers.map((c) => {
                  const hot = c.mem_limit_mb && c.mem_mb ? c.mem_mb / c.mem_limit_mb : 0;
                  return (
                    <tr key={c.id} style={{ cursor: "default" }}>
                      <td>{c.service}{c.scaled && <small className="dim"> · scaled</small>}</td>
                      <td className="mono small">{c.name}</td>
                      <td style={{ color: c.state === "running" ? "var(--calm)" : "var(--alarm)" }} title={c.status}>{c.state}</td>
                      <td className="small">{c.state === "running" ? uptime(c.created) : c.status}</td>
                      <td className="mono small">{c.cpu != null ? `${c.cpu}%` : "-"}</td>
                      <td className="mono small" style={{ color: hot > 0.85 ? "var(--alarm)" : undefined }}>
                        {c.mem_mb != null ? `${c.mem_mb} MiB` : "-"}{c.mem_limit_mb && hot ? ` / ${c.mem_limit_mb}` : ""}</td>
                    </tr>);
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {rc && (
        <section className="card" aria-label="Reach list">
          <h2 className="sub">Reach list <small className="dim">({rc.listed} ready · {rc.gated} gated out)</small></h2>
          <p className="dim small">Workday, iCIMS and SmartRecruiters jobs go through the same fit gate, trust gate and resume tailoring. The portal needs your own candidate account, so you click submit.
            {" "}{Object.entries(rc.by_ats).map(([k, v]) => `${k} ${v}`).join(" · ")}</p>
          {!rc.rows.length ? <p className="dim small">Nothing listed yet. Rows appear after a pipeline pass finds a fresh posting on these boards.</p> : (
            <div style={{ overflowX: "auto", maxHeight: 420, overflowY: "auto" }}>
              <table className="apps">
                <thead><tr><th>Listed</th><th>Role</th><th>ATS</th><th>Lane</th><th>Resume</th></tr></thead>
                <tbody>
                  {rc.rows.map((r) => (
                    <tr key={r.url} style={{ cursor: "default" }}>
                      <td className="mono small">{r.listed.slice(5, 16).replace("T", " ")}</td>
                      <td><a href={r.url} target="_blank" rel="noreferrer">{r.company} · {r.title}</a><br /><small className="dim">{r.location}</small></td>
                      <td className="small">{r.ats}</td>
                      <td className="small">{r.lane}</td>
                      <td className="small"><a href={api(`/api/resume/${encodeURIComponent(r.resume.split("/").pop() || "")}`)} target="_blank" rel="noreferrer">PDF</a></td>
                    </tr>))}
                </tbody>
              </table>
            </div>)}
        </section>
      )}

      {bn && (
        <section className="card" aria-label="Benchmarks">
          <h2 className="sub">Benchmarks <small className="dim">{bn.ts ? <>(run {ago(bn.ts)}; eval containers rerun them on every commit and every 6 h · <a href="/evals">history</a>)</> : "(not run yet: the supervisor runs them 5 min after it starts)"}</small></h2>
          <ul className="tabs">
            {BENCH.filter(([k]) => bn.results[k]).map(([k, label, fmt]) => {
              const r = bn.results[k];
              let v = "";
              try { v = r.error ? `error: ${r.error}` : fmt(r); } catch { v = JSON.stringify(r).slice(0, 80); }
              return <li key={k}><span><b className="mono small">{k.split("_")[0]}</b> {label}</span><b className="small" style={{ color: r.error ? "var(--alarm)" : "var(--calm)" }}>{v}</b></li>;
            })}
          </ul>
        </section>
      )}

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
