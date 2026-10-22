"use client";
// Reach: Workday / iCIMS / SmartRecruiters jobs the engine found, fit-gated and wrote a resume for, but cannot submit
// (the form sits behind your own candidate account). One job at a time: open the posting, upload the tailored resume,
// copy each answer from the fill kit (your presets + Fact Bank, the same values the engine types elsewhere), then mark
// it submitted so it is counted and never listed or applied to again.
import { useEffect, useMemo, useState } from "react";
import { Nav } from "../nav";
import { api, get, post, poll } from "@/lib/types";

type Row = { listed: string; ats: string; company: string; title: string; url: string; location: string; posted?: string;
             lane?: string; jd_match?: number; resume: string; salary_range?: [number, number] | null;
             mark: "todo" | "submitted" | "skipped"; marked?: string | null };
type Reach = { rows: Row[]; listed: number; gated: number; by_ats: Record<string, number>; marks: Record<string, number>; write: boolean };
type Kit = { groups: { group: string; fields: [string, string][] }[] };
type Signins = { jobs: number; employers: { host: string; company: string; jobs: number; url: string }[] };
type Desk = { desk: { up: boolean; state: string; queued: number; last: string } | null; open: string;
              results: Record<string, { status: string; detail: string; ts: string }> };

const TABS = [["todo", "To do"], ["submitted", "Submitted"], ["skipped", "Skipped"]] as const;
const file = (p: string) => p.split("/").pop() || p;
const money = (n: number) => "$" + Math.round(n).toLocaleString("en-US");

export default function ReachPage() {
  return <ReachView />;
}

function ReachView() {
  const [data, setData] = useState<Reach | null>(null);
  const [kit, setKit] = useState<Kit | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("todo");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const [copied, setCopied] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const [desk, setDesk] = useState<Desk | null>(null);
  const pull = () => get<Reach>("/api/control/reach?limit=500").then(setData).catch((e) => setMsg(e.message));
  const pullDesk = () => get<Desk>("/api/reach/desk").then(setDesk).catch(() => setDesk(null));
  useEffect(() => {
    pullDesk();
    return poll(pullDesk, 5000);  // the desk beats every 3 s; its result lands within a minute of a fill
  }, []);
  const [signins, setSignins] = useState<Signins | null>(null);
  useEffect(() => { get<Signins>("/api/reach/signins").then(setSignins).catch(() => setSignins(null)); }, []);
  const openSignin = async (e: Signins["employers"][number]) => {
    try {
      await post("/api/reach/open", { url: e.url });
      setMsg(`Opening ${e.host} in the desk. Switch to the desk tab, sign in (or create the account), then use "Fill it in the desk" on its jobs.`);
    } catch (err: any) { setMsg(err.message); }
  };
  const fill = async (r: Row) => {
    setBusy(true);
    try {
      const out = await post<{ desk: string }>("/api/reach/fill", { url: r.url });
      setMsg(out.desk === "up" ? `Queued for the desk: ${r.company}. Watch it fill in the desk tab.`
        : `Queued, but the desk is not running (docker compose -f deploy/bank.compose.yml up -d desk).`);
      pullDesk();
    } catch (e: any) { setMsg(e.message); } finally { setBusy(false); }
  };
  useEffect(() => {
    pull();
    get<Kit>("/api/reach/kit").then(setKit).catch((e) => setMsg(`Fill kit: ${e.message}`));
    return poll(pull, 30000);  // new rows land once per pipeline pass
  }, []);

  const rows = useMemo(() => (data?.rows || []).filter((r) => r.mark === tab
    && (!q || `${r.company} ${r.title} ${r.location} ${r.ats}`.toLowerCase().includes(q.toLowerCase()))), [data, tab, q]);
  const cur = (data?.rows || []).find((r) => r.url === sel) || null;
  useEffect(() => { if (!cur && rows.length) setSel(rows[0].url); }, [rows, cur]);

  const copy = async (k: string, v: string, el?: HTMLElement) => {
    let ok = false;
    try { await navigator.clipboard.writeText(v); ok = true; } catch { /* permission denied: fall back below */ }
    if (!ok) {  // a selected hidden textarea + execCommand works where the async clipboard API is not allowed
      const ta = document.createElement("textarea");
      ta.value = v; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      try { ok = document.execCommand("copy"); } catch { ok = false; }
      ta.remove();
    }
    if (ok) { setCopied(k); setMsg(""); setTimeout(() => setCopied(""), 1200); return; }
    if (el) {  // last resort: leave the value selected, so one Ctrl+C copies it
      const r = document.createRange(); r.selectNodeContents(el);
      const s = window.getSelection(); s?.removeAllRanges(); s?.addRange(r);
    }
    setMsg("This browser blocks copying from pages. The value is selected: press Ctrl+C.");
  };
  const mark = async (r: Row, m: Row["mark"]) => {
    setBusy(true);
    try {
      await post("/api/reach/mark", { url: r.url, mark: m });
      setMsg(m === "submitted" ? `Marked submitted: ${r.company}. It is in your applications and won't be listed again.`
        : m === "skipped" ? `Skipped: ${r.company}.` : `Back to to-do: ${r.company}.`);
      const next = rows.find((x) => x.url !== r.url);
      await pull();
      setSel(next ? next.url : null);
    } catch (e: any) { setMsg(e.message); } finally { setBusy(false); }
  };
  const salary = cur?.salary_range?.length === 2 ? money((cur.salary_range[0] + cur.salary_range[1]) / 2) : null;

  return (
    <main className="page">
      <Nav />
      <header className="hero">
        <h1>Reach list</h1>
        <p>Jobs on Workday, iCIMS and SmartRecruiters. Each one already passed the fit gate and the trust gate and has a resume tailored to its description. These portals put the form behind your own candidate account, so you submit: open the posting, upload the resume, copy the answers, then mark it submitted.
          {" "}Amazon, NVIDIA, Google, Apple, Microsoft and Netflix roles are in <a href="/room/listen#bigtech">Discover</a>.</p>
      </header>
      {msg && <p className="note" role="status">{msg}</p>}

      {!!signins?.employers.length && (
        <details className="card" aria-label="Workday sign-ins">
          <summary><b>Workday sign-ins</b> <small className="dim">{signins.employers.length} employers · {signins.jobs} jobs · one account per employer, most jobs first</small></summary>
          <p className="dim small">1. <a href={desk?.open || "http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale"} target="_blank" rel="noreferrer">Open the desk ↗</a> in another tab.
            2. Press "Open in desk" for an employer: its site opens there at Sign In. 3. Sign in or create the account in the desk (your password stays with you; the engine never types it). The login is kept, so this is once per employer.</p>
          <table className="apps">
            <thead><tr><th>Employer</th><th>Jobs</th><th>Site</th><th></th></tr></thead>
            <tbody>
              {signins.employers.map((e) => (
                <tr key={e.host}>
                  <td><b>{e.company}</b></td><td>{e.jobs}</td>
                  <td className="mono small"><a href={e.url} target="_blank" rel="noreferrer">{e.host}</a></td>
                  <td><button className="btn" disabled={!data?.write} onClick={() => openSignin(e)}>Open in desk</button></td>
                </tr>))}
            </tbody>
          </table>
        </details>)}

      <div className="toolbar">
        <div className="seg" role="tablist" aria-label="Status">
          {TABS.map(([k, label]) => (
            <button key={k} role="tab" aria-selected={tab === k} onClick={() => { setTab(k); setSel(null); }}>
              {label}<small>{data?.marks?.[k] ?? 0}</small></button>))}
        </div>
        <input type="search" placeholder="Search company, role, place" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
      </div>
      {data && !data.write && <p className="dim small">Marking is off: the API needs REGEN_API_REACH=1 (bank) or REGEN_API_WRITE=1 (local).</p>}

      <div className={`split ${cur ? "open" : ""}`}>
        <div style={{ overflowX: "auto" }}>
          <table className="apps">
            <thead><tr><th>Listed</th><th>Role</th><th>ATS</th><th>Lane</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.url} aria-selected={r.url === sel} onClick={() => setSel(r.url)} tabIndex={0}
                    onKeyDown={(e) => e.key === "Enter" && setSel(r.url)}>
                  <td className="mono small">{r.listed.slice(5, 16).replace("T", " ")}</td>
                  <td><b>{r.company}</b> · {r.title}<br /><small className="dim">{r.location}</small></td>
                  <td className="small">{r.ats}</td>
                  <td className="small">{r.lane}</td>
                </tr>))}
              {!rows.length && <tr><td colSpan={4} className="dim">{data ? "Nothing here." : "Loading…"}</td></tr>}
            </tbody>
          </table>
        </div>

        {cur && (
          <aside className="detail" aria-label={`${cur.company} ${cur.title}`}>
            <button className="close" onClick={() => setSel(null)} aria-label="Close">×</button>
            <h2>{cur.title}</h2>
            <p className="dim small">{cur.company} · {cur.location} · {cur.ats}{cur.lane ? ` · ${cur.lane} resume` : ""}
              {cur.jd_match != null ? ` · JD match ${cur.jd_match}` : ""}{cur.marked ? ` · marked ${cur.mark} ${cur.marked.slice(5, 16).replace("T", " ")}` : ""}</p>

            {(cur.ats === "workday" || cur.ats === "smartrecruiters") && (<>
              <h3 className="sub">Let the desk fill it</h3>
              <p className="dim small">The desk is a browser on this computer that you sign in to once per employer. The engine fills the form there with your presets and Fact Bank, uploads this resume, and stops at Review for your Submit click.</p>
              <p className="row">
                <button className="btn gold" disabled={!data?.write || busy} onClick={() => fill(cur)}>Fill it in the desk</button>
                <a className="btn" href={desk?.open || "http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale"} target="_blank" rel="noreferrer">Open the desk ↗</a>
                <span className="small" style={{ color: desk?.desk?.up ? "var(--calm)" : "var(--alarm)" }}>
                  desk {desk?.desk?.up ? `${desk.desk.state}${desk.desk.queued ? ` (${desk.desk.queued} queued)` : ""}` : "down"}</span>
              </p>
              {desk?.results?.[cur.url] && <p className="note small">Last fill {desk.results[cur.url].ts.slice(5, 16).replace("T", " ")}: {desk.results[cur.url].detail}</p>}
            </>)}

            <h3 className="sub">1 · Open the posting</h3>
            <p><a className="btn gold" href={cur.url} target="_blank" rel="noreferrer">Open on {cur.ats} ↗</a>
              <span className="dim small"> Sign in or create your candidate account there.</span></p>

            <h3 className="sub">2 · Upload this resume</h3>
            <p className="row">
              <a className="btn" href={api(`/api/resume/${encodeURIComponent(file(cur.resume))}?download=1`)}>Download PDF</a>
              <a className="small" href={api(`/api/resume/${encodeURIComponent(file(cur.resume))}`)} target="_blank" rel="noreferrer">{file(cur.resume)} ↗</a>
            </p>
            <iframe className="pdf" src={api(`/api/resume/${encodeURIComponent(file(cur.resume))}`)} title={`Resume for ${cur.company}`} />

            <h3 className="sub">3 · Copy the answers</h3>
            <p className="dim small">Your presets and Fact Bank, exactly as the engine uses them. Click a value to copy it.</p>
            <dl className="qa">
              <div><dt>Salary for this job</dt>
                <dd><button className="chip" onClick={(e) => copy("salary", salary || "", e.currentTarget)} disabled={!salary}>
                  {salary ? `${salary} (posted range midpoint)` : "No range posted: use the market rate below"}</button>{copied === "salary" && <small> copied</small>}</dd></div>
              {!kit && <div><dt>Fill kit</dt><dd className="dim">Loading…</dd></div>}
              {kit?.groups.map((g) => (
                <details key={g.group} open={g.group === "Contact" || g.group === "Work authorization"}>
                  <summary>{g.group} <small className="dim">({g.fields.length})</small></summary>
                  {g.fields.map(([k, v]) => (
                    <div key={g.group + k}><dt>{k}</dt>
                      <dd><button className="chip" onClick={(e) => copy(g.group + k, v, e.currentTarget)} aria-label={`Copy ${k}: ${v}`}>{v}</button>
                        {copied === g.group + k && <small> copied</small>}</dd></div>))}
                </details>))}
            </dl>

            <h3 className="sub">4 · Mark it</h3>
            <p className="row">
              {cur.mark !== "submitted" && <button className="btn gold" disabled={!data?.write || busy} onClick={() => mark(cur, "submitted")}>I submitted it</button>}
              {cur.mark !== "skipped" && <button className="btn" disabled={!data?.write || busy} onClick={() => mark(cur, "skipped")}>Skip</button>}
              {cur.mark !== "todo" && <button className="btn" disabled={!data?.write || busy} onClick={() => mark(cur, "todo")}>Back to to-do</button>}
            </p>
          </aside>)}
      </div>
    </main>
  );
}
