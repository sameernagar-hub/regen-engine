"use client";
// One job, end to end: which room touched it, when, with what (Fact Bank entries, JD coverage, ATS read-back,
// every question and the answer sent, proof). Each step links back to its room.
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Nav } from "../nav";
import { get } from "@/lib/types";
import { TONE, when, type Job } from "@/lib/room";

const ROOM: Record<string, string> = { listen: "Discover", judge: "Fit gate", write: "Compose", apply: "Apply", hear: "Inbox" };

function JobView() {
  const url = useSearchParams().get("u") || "";
  const [job, setJob] = useState<Job | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!url) return;
    const pull = () => get<Job>(`/api/job?url=${encodeURIComponent(url)}`).then(setJob).catch((e) => setErr(String(e.message || e)));
    pull();
    const t = setInterval(pull, 10000);  // a job being applied to right now keeps updating
    return () => clearInterval(t);
  }, [url]);
  if (!url) return <p>No job selected. <Link href="/room">Pick one in the engine room</Link>.</p>;
  if (err) return <p className="err">Couldn’t load this job ({err}).</p>;
  if (!job) return <p className="dim">Loading…</p>;
  const [company, ...rest] = job.job.split(" - ");
  return (
    <>
      <header className="hero">
        <h1>{company}</h1>
        <p>{rest.join(" - ")}</p>
        <a href={job.url} target="_blank" rel="noreferrer noopener" className="dim">Posting ↗</a>
      </header>
      <ol className="timeline">
        {job.events.map((e) => {
          const d = e.data, cov = d.coverage, ats = cov?.ats;
          return (
            <li key={e.id} style={{ borderColor: TONE[e.tone || "quiet"] }}>
              <div className="tl-head">
                {e.stage && <Link href={`/room/${e.stage}`} className="tag">{ROOM[e.stage] || e.stage}</Link>}
                <time>{when(e.ts)}</time>
                {e.status && <b style={{ color: TONE[e.tone || "quiet"] }}>{e.status}</b>}
              </div>
              {e.text && <p>{e.text}</p>}
              {e.kind === "resume" && (
                <div className="facts">
                  {d.lane && <p>Lane <b>{d.lane}</b>{ats && <> · ATS read-back <b>{ats.score}%</b></>}{cov && <> · {cov.on_resume?.length}/{cov.jd_terms_you_have?.length} JD terms on the page</>}</p>}
                  {cov?.missing_from_resume?.length > 0 && <p className="dim">Not on this page (in your bank): {cov.missing_from_resume.join(", ")}</p>}
                  <p className="dim">Facts used: {(d.facts || []).flatMap(([r, f]: [string, string[]]) => f.map((x) => x)).join(", ")}</p>
                </div>
              )}
              {e.answers.length > 0 && (
                <details>
                  <summary>{e.answers.length} questions answered</summary>
                  <dl className="qa">{e.answers.map(([q, a], i) => <div key={i}><dt>{q}</dt><dd>{String(a)}</dd></div>)}</dl>
                </details>
              )}
              {d.proof && <a className="dim" href={`/api/proof/${String(d.proof).split("/").pop()}`} target="_blank" rel="noreferrer">Proof screenshot ↗</a>}
            </li>
          );
        })}
      </ol>
    </>
  );
}

export default function JobPage() {
  return (
    <main className="page">
      <Nav />
      <p className="crumbs"><Link href="/room">Engine room</Link> / job</p>
      <Suspense fallback={<p className="dim">Loading…</p>}><JobView /></Suspense>
    </main>
  );
}
