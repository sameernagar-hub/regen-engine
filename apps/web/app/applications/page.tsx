"use client";
// Every application the engine touched, newest first. Pick one to see exactly what was sent: the resume PDF,
// every question with the answer given, the Fact Bank entries the resume used, and the proof screenshot.
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Nav } from "../nav";
import { get, type Application } from "@/lib/types";

const STATUSES = ["ALL", "SUBMITTED", "NEEDS YOU", "FAILED", "SKIPPED", "FLAGGED"];
const TONE: Record<string, string> = { SUBMITTED: "var(--gold)", "NEEDS YOU": "var(--amber)", FAILED: "var(--alarm)",
                                       SKIPPED: "var(--dim)", FLAGGED: "var(--alarm)" };
const file = (p?: string | null) => (p ? p.split(/[\\/]/).pop()! : "");

export default function Applications() {
  const [apps, setApps] = useState<Application[]>([]);
  const [status, setStatus] = useState("SUBMITTED");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<Application | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    const pull = () => get<Application[]>("/api/applications?limit=2000").then(setApps).catch((e) => setErr(e.message));
    pull();
    const t = setInterval(pull, 15000);
    return () => clearInterval(t);
  }, []);

  const counts = useMemo(() => apps.reduce<Record<string, number>>((a, x) => ({ ...a, [x.status]: (a[x.status] || 0) + 1 }), {}), [apps]);
  const rows = useMemo(() => {
    const needle = q.toLowerCase();
    return apps.filter((a) => (status === "ALL" || a.status === status) && (!needle || a.job.toLowerCase().includes(needle)));
  }, [apps, status, q]);

  return (
    <main className="page">
      <Nav />
      <header className="hero">
        <h1>Applications</h1>
        <p>What was sent, where, and with which resume. Select a row to see the exact submission.</p>
      </header>
      {err && <p className="err">{err}</p>}
      <div className="toolbar">
        <div className="seg" role="tablist" aria-label="Status">
          {STATUSES.map((s) => (
            <button key={s} role="tab" aria-selected={status === s} onClick={() => setStatus(s)} style={{ color: TONE[s] }}>
              {s} <small>{s === "ALL" ? apps.length : counts[s] || 0}</small>
            </button>
          ))}
        </div>
        <input type="search" placeholder="Search company or role" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
      </div>

      <div className={`split ${sel ? "open" : ""}`}>
        <table className="apps">
          <thead><tr><th>When</th><th>Company</th><th>Role</th><th>Lane</th><th>Status</th></tr></thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.url || a.job} onClick={() => setSel(a)} aria-selected={sel?.job === a.job} tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && setSel(a)}>
                <td className="mono small">{a.ts.slice(5, 16).replace("T", " ")}</td>
                <td>{a.company}</td><td>{a.role}</td><td className="dim">{a.lane || "–"}</td>
                <td><b style={{ color: TONE[a.status] }}>{a.status}</b></td>
              </tr>
            ))}
          </tbody>
        </table>

        {sel && (
          <aside className="detail" aria-label="Submission">
            <button className="close" onClick={() => setSel(null)} aria-label="Close">×</button>
            <h2>{sel.company}</h2>
            <p className="dim">{sel.role} · <b style={{ color: TONE[sel.status] }}>{sel.status}</b> · {sel.ts.replace("T", " ")}</p>
            <p className="row small">
              {sel.url && <a href={sel.url} target="_blank" rel="noreferrer noopener">Posting ↗</a>}
              {sel.url && <Link href={`/job?u=${encodeURIComponent(sel.url)}`}>Full timeline →</Link>}
              {sel.proof && <a href={`/api/proof/${file(sel.proof)}`} target="_blank" rel="noreferrer">Proof ↗</a>}
            </p>
            {sel.detail && sel.status !== "SUBMITTED" && <p className="note">{sel.detail}</p>}
            {sel.resume && (
              <>
                <h3 className="sub">Resume sent</h3>
                <iframe className="pdf" src={`/api/resume/${file(sel.resume)}`} title={`Resume for ${sel.company}`} />
                <a className="small" href={`/api/resume/${file(sel.resume)}`} target="_blank" rel="noreferrer">{file(sel.resume)} ↗</a>
              </>
            )}
            {(sel.answers || []).length > 0 && (
              <>
                <h3 className="sub">Answers submitted ({(sel.answers || []).length})</h3>
                <dl className="qa">{(sel.answers || []).map(([qq, aa], i) => <div key={i}><dt>{qq}</dt><dd>{aa ?? "—"}</dd></div>)}</dl>
              </>
            )}
            {(sel.facts || []).length > 0 && (
              <>
                <h3 className="sub">Fact Bank entries used ({(sel.facts || []).length})</h3>
                <ul className="chips">{(sel.facts || []).map((f) => <li key={f} className="chip"><Link href={`/facts#${f}`}>{f}</Link></li>)}</ul>
              </>
            )}
          </aside>
        )}
      </div>
    </main>
  );
}
