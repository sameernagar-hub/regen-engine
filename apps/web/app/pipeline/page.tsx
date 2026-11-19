"use client";
// /pipeline: how the Test drive reads a resume, live. Paste one (or pick a sample), press Run, and watch each step of
// lib/resume-nlp.ts produce its real output in order; then the benchmark that checks it (lib/resume-bench.json, written
// by scripts/resume_bench.py on a held-out set): accuracy, precision, recall, F1, robustness and the confusion matrix.
import { useState } from "react";
import { Nav } from "../nav";
import { PipelineRun, STEPS, famColor } from "../pipeline-run";
import B from "@/lib/resume-bench.json";

const SAMPLES: [string, string][] = [
  ["Account Executive (the bug that started this)", `Jordan Taylor · Chicago, IL
Summary
Account Executive with 5+ years of B2B SaaS sales closing mid-market and enterprise deals.
Skills
MEDDIC, Challenger Sale, cold outbound prospecting, Salesforce CRM, HubSpot, Gong
Experience
Senior Account Executive | Veloce Cloud Software | Chicago, IL
March 2024 – Present
* Achieved 132% of annual quota ($1.45M closed-won ARR); President's Club
* Managed full-cycle enterprise sales for workflow automation software with C-level stakeholders
Sales Development Representative (SDR) | BrightPath Analytics | 2021 – 2022
* Exceeded monthly SQL quota for 11 consecutive months`],
  ["Registered nurse", `Maria Lopez, RN
Experience
Registered Nurse, ICU | Mercy General Hospital | 2020 - Present
- Patient care for critical patients; medication administration and vital signs
- Charted in Epic EHR; triage and care plans with physicians
Licenses
RN, BLS, ACLS`],
  ["Recruiter who hires engineers (trap)", `Riley Adams
Technical Recruiter
Experience
Technical Recruiter | Northwind Software | 2021 - Present
- Full-cycle recruiting for 40 software engineer and backend engineer roles a year
- Sourcing, interview loops with hiring managers, offer letters in Greenhouse`],
  ["Teacher turned developer (hybrid)", `Jordan Reyes
Experience
Software Engineer | Startup Labs | 2023 - Present
- React and TypeScript features, REST APIs in Node.js, unit tests and code reviews
Math Teacher | Lincoln High School | 2014 - 2022
- Lesson plans, curriculum and classroom management for 150 students`],
  ["Not a resume", "Looking for a job. Hard worker, team player, fast learner."],
];

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
const short = (c: string) => c.replace(" / ", "/").replace("engineering (non-software)", "eng (non-sw)").replace("solutions/sales engineering", "solutions").replace("customer success/support", "cust. success").replace("operations/supply chain", "ops/supply").replace("hospitality/retail", "hospitality").replace("hardware/embedded", "hw/embedded").replace("program/project", "program").replace("research/science", "research").replace("finance/accounting", "finance").replace("creative/media", "creative");

export default function Pipeline() {
  const [text, setText] = useState(SAMPLES[0][1]);
  const [runId, setRunId] = useState(0);
  const [done, setDone] = useState(false);
  const run = (t?: string) => { if (t !== undefined) setText(t); setDone(false); setRunId((n) => n + 1); };
  const search = () => { try { sessionStorage.setItem("td-text", text); } catch { /* private mode: the page still works */ } location.href = "/test-drive#td-seat-h"; };
  const maxCell = Math.max(1, ...B.confusion.flat());

  return (
    <main className="page td pl" id="main">
      <Nav />
      <header className="pl-hero">
        <p className="eyebrow"><span className="brand">Resume pipeline</span>how the Test drive reads you</p>
        <h1>From raw text to <em>what kind of role you do</em>, one step at a time.</h1>
        <p>Before any job search, the engine has to know what you do. A salesperson at a software company is a
          salesperson; a nurse is a nurse; a recruiter who hires engineers is a recruiter. This page runs that reading
          live, in your browser, with the same code the Test drive and <code>python -m engine try</code> use.</p>
      </header>

      <section className="pl-lab" aria-labelledby="pl-lab-h">
        <h2 id="pl-lab-h"><span className="n">1</span>Run it on a resume</h2>
        <div className="pl-samples" role="group" aria-label="Sample resumes">
          {SAMPLES.map(([name, t]) => <button key={name} type="button" onClick={() => run(t)} className={text === t ? "on" : ""}>{name}</button>)}
        </div>
        <label htmlFor="pl-text" className="td-sub">Or paste your own. It never leaves this page for this part.</label>
        <textarea id="pl-text" rows={8} value={text} onChange={(e) => setText(e.target.value)} maxLength={50000} />
        <div className="td-actions">
          <button type="button" className="td-ignite" onClick={() => run()} disabled={!text.trim()}><span className="key" aria-hidden />Run the pipeline</button>
          {done && <button type="button" className="td-sample" onClick={search}>Search live jobs with this resume →</button>}
        </div>
        <PipelineRun text={text} runId={runId} onDone={() => setDone(true)} />
      </section>

      <section aria-labelledby="pl-how-h">
        <h2 id="pl-how-h"><span className="n">2</span>What each step does</h2>
        <ol className="pl-explain">
          {STEPS.map((s, i) => <li key={s.key}><b>{i + 1}. {s.name}</b><span>{s.does}</span></li>)}
          <li><b>7. Search</b><span>Every posting title goes through the same tokenizer and phrase matcher, so a job and a resume are labelled from one taxonomy. A posting passes the fit gate only when its family is one of yours; then level, location and freshness checks, then ATS keyword scoring on the job description.</span></li>
        </ol>
      </section>

      <section aria-labelledby="pl-bench-h" className="pl-bench">
        <h2 id="pl-bench-h"><span className="n">3</span>Benchmark: how we know it works</h2>
        <p className="td-sub">Measured on a <b>held-out set</b> of {B.n} resumes across {B.classes} classes (25 role families plus
          “unclassified”), written separately from the {B.dev.n}-resume development set the vocabulary was tuned on, in other
          formats (other header names, “@” role lines, lowercase, one-line pastes, hybrids and traps). Regenerated by
          <code> python scripts/resume_bench.py</code>; the test suite fails if this page’s numbers go stale.</p>
        <div className="pl-tiles">
          {[["Accuracy", pct(B.accuracy)], ["Macro precision", B.macro.precision.toFixed(3)], ["Macro recall", B.macro.recall.toFixed(3)],
            ["Macro F1", B.macro.f1.toFixed(3)], ["Weighted F1", B.weighted.f1.toFixed(3)], ["Posting titles", `${B.titles.correct}/${B.titles.n}`],
            ["Dev set", `${B.dev.correct}/${B.dev.n}`], ["Speed", `${B.ms_per_resume} ms`]].map(([k, v]) => <div key={k}><span>{k}</span><b>{v}</b></div>)}
        </div>
        <h3>Robustness: the same {B.n} resumes, mutated</h3>
        <ul className="pl-rob">{Object.entries(B.robustness as Record<string, number>).map(([k, v], i) => (
          <li key={k} style={{ ["--w" as any]: `${v * 100}%`, ["--k" as any]: i }}><span>{k}</span><i /><b>{pct(v)}</b></li>))}</ul>
        <div className="pl-two">
          <div>
            <h3>Per class</h3>
            <div className="pl-tablewrap"><table className="pl-table">
              <thead><tr><th>class</th><th>precision</th><th>recall</th><th>F1</th><th>n</th></tr></thead>
              <tbody>{B.per_class.map((r) => (
                <tr key={r.class}><td><i style={{ background: famColor(r.class) }} />{r.class}</td><td>{r.precision.toFixed(2)}</td><td>{r.recall.toFixed(2)}</td><td>{r.f1.toFixed(2)}</td><td>{r.support}</td></tr>))}
              </tbody></table></div>
          </div>
          <div>
            <h3>Confusion matrix</h3>
            <p className="td-sub">Rows are the true family, columns the predicted one. Everything on the diagonal is right; any off-diagonal cell is a mistake.</p>
            <div className="pl-cmwrap"><table className="pl-cm" aria-label="Confusion matrix">
              <thead><tr><th />{B.labels.map((l) => <th key={l} title={l}><span>{short(l)}</span></th>)}</tr></thead>
              <tbody>{B.confusion.map((row, r) => (
                <tr key={B.labels[r]}><th title={B.labels[r]}>{short(B.labels[r])}</th>
                  {row.map((v, c) => <td key={c} className={v ? (r === c ? "hit" : "miss") : ""} style={{ ["--a" as any]: v / maxCell }} title={`${B.labels[r]} → ${B.labels[c]}: ${v}`}>{v || ""}</td>)}</tr>))}
              </tbody></table></div>
          </div>
        </div>
        {B.misses.length > 0 && <><h3>Misses</h3><ul className="pl-miss">{(B.misses as { want: string; got: string; start: string }[]).map((m, i) => <li key={i}>expected <b>{m.want}</b>, got <b>{m.got}</b>: {m.start}…</li>)}</ul></>}
        <h3>What these numbers do and don’t say</h3>
        <ul className="pl-caveats">
          <li>The resumes are synthetic and written by the same project, in English. A perfect score here means the method
            holds on these {B.n} formats and traps; it is not a measurement on a random sample of real resumes.</li>
          <li>The development and held-out sets are kept apart: a miss on the held-out set is fixed only with a general
            change (vocabulary or structure), and both sets are re-run after every change.</li>
          <li>Robustness re-runs the held-out set after mutating it (case, line breaks, headers removed, order reversed,
            noise, misleading employer names); the label must not move.</li>
          <li>The classifier is transparent on purpose: every label comes with the phrases that decided it (step 5), so a
            wrong label can be traced to a word, not to a black box.</li>
        </ul>
      </section>
    </main>
  );
}
