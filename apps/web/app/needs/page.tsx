"use client";
// Needs you: every job the engine parked, grouped by the question that stopped it, so one answer clears many jobs.
// Answers are stored once (profile/answers.json via POST /api/answers) and reused on every form; jobs whose blocking
// questions are all answerable go back into the queue, and "Apply now" starts a retry pass (or the running loop
// picks them up on its next pass). Legal / attestation items can't be answered here: open the posting to finish.
import { useEffect, useMemo, useState } from "react";
import { Nav } from "../nav";
import { LocalOnly } from "../local-only";
import { PUBLIC } from "@/lib/engine";
import { get, post, type HumanItem } from "@/lib/types";

const LEGAL = /arbitrat|attest|certif|export|citizen|clearance|eeo|gender|race|veteran|disab|transcript|assessment|captcha|bot-check|human check/i;

type Group = { q: string; jobs: HumanItem[]; legal: boolean };

export default function Needs() {
  if (PUBLIC) return <LocalOnly title="Needs you" what="The questions only you can answer, grouped so one answer clears many jobs." />;
  return <NeedsView />;
}

function NeedsView() {
  const [items, setItems] = useState<HumanItem[] | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [done, setDone] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [view, setView] = useState<"question" | "job">("question");

  const pull = () => get<HumanItem[]>("/api/human").then(setItems).catch((e) => setMsg(e.message));
  useEffect(() => { pull(); const t = setInterval(pull, 20000); return () => clearInterval(t); }, []);

  // group by question: O(items x questions)
  const groups = useMemo<Group[]>(() => {
    const m = new Map<string, HumanItem[]>();
    for (const it of items || []) {
      const qs = it.missing?.length ? it.missing : [it.text];
      for (const q of qs) m.set(q, [...(m.get(q) || []), it]);
    }
    return [...m.entries()].map(([q, jobs]) => ({ q, jobs, legal: LEGAL.test(q) }))
      .sort((a, b) => Number(a.legal) - Number(b.legal) || b.jobs.length - a.jobs.length);
  }, [items]);

  const answer = async (g: Group) => {
    const a = (draft[g.q] || "").trim();
    if (!a) return;
    try {
      await post("/api/answers", { job: g.jobs[0].job, question: g.q, answer: a });
      setDone((d) => ({ ...d, [g.q]: a }));
      setMsg(`Saved. ${g.jobs.length} job${g.jobs.length > 1 ? "s" : ""} can go again.`);
    } catch (e: any) { setMsg(e.message); }
  };
  const applyNow = () => post<any>("/api/control/retry", {}).then((r) => setMsg(r.note || "Retry pass started.")).catch((e) => setMsg(e.message));

  const answerable = groups.filter((g) => !g.legal);
  return (
    <main className="page">
      <Nav />
      <header className="hero">
        <h1>Needs you</h1>
        <p>{items ? `${items.length} jobs are waiting on ${groups.length} questions.` : "Loading…"} Answer a question once and every job that asked it goes back in line. Legal and attestation items stay yours: open the posting to finish them.</p>
      </header>
      {msg && <p className="note" role="status">{msg}</p>}
      <div className="toolbar">
        <div className="seg" role="tablist" aria-label="Group by">
          <button role="tab" aria-selected={view === "question"} onClick={() => setView("question")}>By question <small>{groups.length}</small></button>
          <button role="tab" aria-selected={view === "job"} onClick={() => setView("job")}>By job <small>{items?.length || 0}</small></button>
        </div>
        <button className="btn gold" onClick={applyNow}>Apply now ({Object.keys(done).length} answered)</button>
      </div>

      {view === "question" ? (
        <ol className="needs">
          {groups.map((g, i) => (
            <li key={g.q} className={`card need ${g.legal ? "legal" : ""} ${done[g.q] ? "ok" : ""}`} style={{ ["--i" as any]: i }}>
              <div className="need-head">
                <b className="count-pill">{g.jobs.length}</b>
                <p className="q">{g.q}</p>
              </div>
              <ul className="chips">{g.jobs.slice(0, 8).map((j) => <li key={(j.url || j.job) + j.status} className="chip">{j.url ? <a href={j.url} target="_blank" rel="noreferrer noopener">{j.job}</a> : j.job}</li>)}{g.jobs.length > 8 && <li className="chip">+{g.jobs.length - 8}</li>}</ul>
              {g.legal ? (
                <p className="dim small">Yours to decide on the employer’s page (legal / attestation / human check). The form is prepared and the resume is ready.</p>
              ) : done[g.q] ? (
                <p className="small">Answered: <b>{done[g.q]}</b></p>
              ) : (
                <form className="answer-row" onSubmit={(e) => { e.preventDefault(); answer(g); }}>
                  <label className="sr-only" htmlFor={`a${i}`}>Answer</label>
                  <textarea id={`a${i}`} rows={2} placeholder="Your answer (used on every form that asks this)" value={draft[g.q] || ""}
                            onChange={(e) => setDraft({ ...draft, [g.q]: e.target.value })} />
                  <button className="btn" type="submit" disabled={!(draft[g.q] || "").trim()}>Save</button>
                </form>
              )}
            </li>
          ))}
        </ol>
      ) : (
        <ol className="needs">
          {(items || []).map((it) => (
            <li key={(it.url || it.job) + it.status} className="card need">
              <div className="need-head"><b>{it.job}</b><span className="dim small">{it.status}</span></div>
              <ul className="list">{(it.missing?.length ? it.missing : [it.text]).map((q) => <li key={q}>{q}{done[q] && <small>Answered: {done[q]}</small>}</li>)}</ul>
              <p className="row small">{it.url && <a href={it.url} target="_blank" rel="noreferrer noopener">Open posting ↗</a>}</p>
            </li>
          ))}
        </ol>
      )}
      {items && !answerable.length && <p className="dim">Nothing you can answer here right now.</p>}
    </main>
  );
}
