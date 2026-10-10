"use client";
// Outreach: a short note per recent submission at a tier company or startup, written only from template lines and
// the Fact Bank entries that application's resume used. Nothing is sent from here: "Open in Gmail" opens a prefilled
// draft; you add the recipient (never guessed), edit and send.
import { useEffect, useState } from "react";
import { Nav } from "../nav";
import { LocalOnly } from "../local-only";
import { PUBLIC } from "@/lib/engine";
import { get, post } from "@/lib/types";

type Draft = { company: string; role: string; url: string; ts: string; why: string; lane?: string; subject: string;
               body: string; compose: string; sources: string[]; facts_from?: string };
const WHY: Record<string, string> = { "tier 1": "var(--gold)", "tier 2": "var(--calm)", startup: "#7ef0c1" };

export default function Outreach() {
  if (PUBLIC) return <LocalOnly title="Outreach" what="Truthful notes to recruiters and founders after each application." />;
  return <OutreachView />;
}

function OutreachView() {
  const [ds, setDs] = useState<Draft[] | null>(null);
  const [days, setDays] = useState(7);
  const [msg, setMsg] = useState("");
  const load = () => get<Draft[]>("/api/outreach").then(setDs).catch((e) => setMsg(e.message));
  useEffect(() => { load(); }, []);
  const rebuild = () => post<Draft[]>("/api/outreach/build", { days }).then((d) => { setDs(d); setMsg(`${d.length} drafts built.`); }).catch((e) => setMsg(e.message));
  const copy = (d: Draft) => navigator.clipboard.writeText(`${d.subject}\n\n${d.body}`).then(() => setMsg("Copied."));

  return (
    <main className="page">
      <Nav />
      <header className="hero">
        <h1>Outreach</h1>
        <p>One short note per recent application at a tier company or startup. Every line is a template or a Fact Bank entry that application’s resume used. Nothing is sent from here: open the draft in Gmail, add the recipient, send.</p>
      </header>
      {msg && <p className="note" role="status">{msg}</p>}
      <div className="toolbar">
        <label className="small dim">Submissions from the last <input type="number" min={1} max={30} value={days} onChange={(e) => setDays(+e.target.value)} style={{ width: 64 }} /> days</label>
        <button className="btn gold" onClick={rebuild}>Rebuild drafts</button>
      </div>
      <ol className="needs">
        {(ds || []).map((d) => (
          <li key={d.url} className="card need">
            <div className="need-head">
              <b className="count-pill" style={{ background: WHY[d.why] }}>{d.why === "startup" ? "S" : d.why.slice(-1)}</b>
              <div><b>{d.company}</b><p className="dim small" style={{ margin: 0 }}>{d.role}</p></div>
            </div>
            <p className="small"><b>{d.subject}</b></p>
            <pre className="logbox" style={{ color: "var(--ink)" }}>{d.body}</pre>
            <p className="dim small">Facts: {d.sources.join(", ") || "none"}{d.facts_from === "lane" ? " (lane’s most-used: this resume predates fact logging)" : ""}</p>
            <p className="row small">
              <a className="btn gold" href={d.compose} target="_blank" rel="noreferrer noopener">Open in Gmail ↗</a>
              <button className="btn" onClick={() => copy(d)}>Copy</button>
              <a href={d.url} target="_blank" rel="noreferrer noopener">Posting ↗</a>
            </p>
          </li>
        ))}
      </ol>
      {ds && !ds.length && <p className="dim">No drafts yet. Rebuild after a run.</p>}
    </main>
  );
}
