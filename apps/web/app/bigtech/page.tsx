"use client";
// Big tech: the engine also reads the careers portals of Amazon, NVIDIA, Google, Apple, Microsoft and Netflix
// (engine/discovery/bigtech.py), new-grad and early-career searches included. Every role here passed the same title
// filter and fit gate as the rest and has a resume tailored to its description. These portals need your own account,
// so you apply there: open the role, upload its resume.
import { useEffect, useMemo, useState } from "react";
import { Nav } from "../nav";
import { api, get, poll } from "@/lib/types";

type Row = { posted: string; company: string; title: string; url: string; location: string; lane: string; ats: number;
             resume: string; new_grad: boolean };
type Big = { rows: Row[]; sources: string[]; by_company: Record<string, number>; new_grad: number; queries: string[];
             last_run: string | null };

export default function BigTechPage() {
  const [data, setData] = useState<Big | null>(null);
  const [msg, setMsg] = useState("");
  const [co, setCo] = useState<string>("all");
  const [grad, setGrad] = useState(false);
  const [q, setQ] = useState("");
  useEffect(() => {
    const pull = () => get<Big>("/api/control/bigtech").then(setData).catch((e) => setMsg(e.message));
    pull();
    return poll(pull, 60000);  // the pipeline reads these portals at most once an hour
  }, []);
  const rows = useMemo(() => (data?.rows || []).filter((r) => (co === "all" || r.company === co) && (!grad || r.new_grad)
    && (!q || `${r.company} ${r.title} ${r.location} ${r.lane}`.toLowerCase().includes(q.toLowerCase()))), [data, co, grad, q]);

  return (
    <main className="page">
      <Nav />
      <header className="hero">
        <h1>Big tech</h1>
        <p>Besides ~5,500 company job boards, the engine reads the careers portals of the largest employers directly:
          {" "}{data ? data.sources.join(", ") : "…"}. It searches each for software, data, research, support and test roles,
          new grad and early career included, keeps what passes the fit gate, and writes a resume for each one. These portals
          need your own account, so you apply there with the resume ready.</p>
      </header>
      {msg && <p className="note" role="status">{msg}</p>}
      {process.env.NEXT_PUBLIC_REGEN_MODE === "public" && (
        <p className="dim small">Public demo: the portals and searches are the real engine&apos;s; the roles below are demo rows
          (each links to that portal&apos;s public search) with a fictional candidate&apos;s resume.</p>)}

      <section className="card" aria-label="Coverage">
        <p className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          {(data?.sources || []).map((s) => (
            <button key={s} className="chip" aria-pressed={co === s} onClick={() => setCo(co === s ? "all" : s)}
                    title={`Show ${s} roles`}>
              <b>{s}</b> {data?.by_company[s] ?? 0}</button>))}
        </p>
        <p className="dim small">
          {data ? `${data.rows.length} roles with a tailored resume · ${data.new_grad} new grad / early career · `
                  + `${data.sources.length} portals · ${data.queries.length} searches each` : "Loading…"}
          {data?.last_run ? ` · last read ${data.last_run.slice(5).replace("T", " ")}` : ""}</p>
      </section>

      <div className="toolbar">
        <div className="seg" role="tablist" aria-label="Level">
          <button role="tab" aria-selected={!grad} onClick={() => setGrad(false)}>All<small>{data?.rows.length ?? 0}</small></button>
          <button role="tab" aria-selected={grad} onClick={() => setGrad(true)}>New grad<small>{data?.new_grad ?? 0}</small></button>
        </div>
        <input type="search" placeholder="Search company, role, place" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
      </div>

      <div style={{ overflowX: "auto" }}>
        <table className="apps">
          <thead><tr><th>Posted</th><th>Role</th><th>Lane</th><th>ATS</th><th>Resume</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.url + r.resume}>
                <td className="mono small">{r.posted}</td>
                <td><b>{r.company}</b> · <a href={r.url} target="_blank" rel="noreferrer">{r.title} ↗</a>
                  {r.new_grad && <small className="chip" style={{ marginLeft: 6 }}>new grad</small>}
                  <br /><small className="dim">{r.location}</small></td>
                <td className="small">{r.lane}</td>
                <td className="small">{r.ats}%</td>
                <td className="small"><a href={api(`/api/resume/${encodeURIComponent(r.resume)}?download=1`)}>PDF</a></td>
              </tr>))}
            {!rows.length && <tr><td colSpan={5} className="dim">{data ? "Nothing here yet." : "Loading…"}</td></tr>}
          </tbody>
        </table>
      </div>
    </main>
  );
}
