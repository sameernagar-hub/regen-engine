"use client";
// Test drive: paste a resume, watch the pipeline turn it into a shortlist. The page is one thing, the pipeline board
// (app/pipeline-board.tsx): six steps that read the resume in the browser, three that search live public boards
// (POST /api/public/try, the same rules as `python -m engine try`), and the two stages only a real run uses. Every
// stage is clickable and opens its full output. Nothing is stored and nothing is applied to.
import { useEffect, useState } from "react";
import { Nav } from "../nav";
import { useTestDrive } from "../try-box";
import { PipelineBoard } from "../pipeline-board";
import { screenResume, type Screen } from "@/lib/screen-input";

const SAMPLE = `Jane Doe, Software Engineer (sample resume)
4+ years building backend and full-stack products.
Skills: Python, FastAPI, PostgreSQL, SQL, React, TypeScript, Next.js, Docker, Kubernetes, AWS, Kafka, Redis, CI/CD
Software Engineer II | Example Co | 2022 - Present
- Built REST APIs and microservices in Python serving 2M requests a day; cut p95 latency 40% with Redis caching
- Shipped a full-stack Next.js dashboard with React and TypeScript; end-to-end tests with Playwright in GitHub Actions
Software Engineer | Sample Labs | 2021 - 2022
- Ran event pipelines on Kafka and PostgreSQL; deployed on AWS with Docker and Kubernetes`;

const DISCLAIMER = "For illustration only. Matches come from automated keyword scoring and can be wrong or out of date; check every posting yourself before you apply. REGEN is not responsible for decisions made from these results.";

const PARTS: [string, string, string, string][] = [
  ["Engine room", "/room", "Every job end to end through the stations.", "#6fb7ff"],
  ["Gearbox", "/gearbox", "Speed in gears; the governor scales the appliers from memory, CPU and timeouts.", "#5ee6b5"],
  ["Shadow", "/shadow", "Your AI delegate: answers forms as you, and holds back when it isn't sure.", "#a78bfa"],
  ["Fact Bank", "/facts", "Every claim a resume may make, and which resumes used it.", "#f2c14e"],
  ["Needs you", "/needs", "Questions only you can answer, grouped so one answer clears many jobs.", "#ff9f43"],
  ["MCP cord", "/mcp", "Plug your AI client in and operate the engine at zero model cost.", "#ff7eb6"],
];

export default function TestDrive() {
  const t = useTestDrive();
  const [runId, setRunId] = useState(0);
  const [runText, setRunText] = useState("");
  const [refused, setRefused] = useState<Extract<Screen, { ok: false }> | null>(null);
  useEffect(() => {  // handed over from /pipeline ("Search live jobs with this resume")
    let handed = "";
    try { handed = sessionStorage.getItem("td-text") || ""; sessionStorage.removeItem("td-text"); } catch { /* storage blocked */ }
    if (handed.trim()) t.setText(handed);
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  const drive = (override?: string) => {
    const body = override ?? t.text;
    if (!body.trim()) return;
    const screened = screenResume(body);  // refused text never reaches the pipeline or the server
    if (!screened.ok) { setRefused(screened); setRunId(0); setRunText(""); return; }
    setRefused(null);
    setRunText(body); setRunId((n) => n + 1);
    t.go(override);
    setTimeout(() => document.getElementById("td-pipe")?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
  };
  const sample = () => { t.setText(SAMPLE); drive(SAMPLE); };
  const running = runId > 0 && t.busy;

  return (
    <main className={`page td${running ? " td-rev" : ""}${refused ? " td-no" : ""}`} id="main">
      <Nav />
      <div className="td-aurora" aria-hidden />
      <header className="td-hero">
        <div className="td-pitch">
          <p className="eyebrow"><span className="brand">Test drive</span><span className="try-live" aria-hidden />live on 40 public job boards</p>
          <h1>Paste a resume. Watch it turn into <em>ten real openings.</em></h1>
          <p className="lede">No black box. The pipeline below runs on your text while you watch: the words it keeps, the
            job title it believes, the thousands of postings it throws out and why, and the ten that survive.</p>
          <ul className="td-facts">
            <li><b>~15 s</b> end to end</li>
            <li><b>0</b> sign-ups</li>
            <li><b>0</b> applications sent</li>
            <li><b>0</b> bytes of your text kept</li>
          </ul>
        </div>
        <form className="td-seat" onSubmit={(e) => { e.preventDefault(); drive(); }}>
          <label htmlFor="td-text">Your resume, as plain text</label>
          <textarea id="td-text" rows={9} value={t.text} onChange={(e) => { t.setText(e.target.value); if (refused) setRefused(null); }} maxLength={50000}
                    aria-invalid={!!refused} aria-describedby={refused ? "td-refused" : undefined}
                    placeholder={"Copy it straight out of your PDF or doc.\n\nJob titles and the work you did matter most."} />
          <div className="td-actions">
            <button type="submit" className="td-ignite" disabled={t.busy || !t.text.trim()}>
              <span className="key" aria-hidden />{t.busy ? "Running…" : "Run the pipeline"}</button>
            <button type="button" className="td-sample" onClick={sample} disabled={t.busy}>No resume handy? Use a sample</button>
          </div>
          {refused && <p className="td-refused" id="td-refused" role="alert"><b>Not accepted.</b> {refused.reason}</p>}
          {!refused && t.err && <p className="td-refused" role="alert"><b>{/^This|^That/.test(t.err) ? "Not accepted." : "The search stalled."}</b> {t.err}</p>}
        </form>
      </header>

      <section className="td-pipe" id="td-pipe" aria-labelledby="td-pipe-h">
        <div className="td-pipe-head">
          <h2 id="td-pipe-h">The pipeline</h2>
          <p className="td-sub">{runId ? "Click any stage to open everything it produced. The board follows the run until you do." :
            "Eleven stages, in the order your resume moves through them. Click one to see what it does; run a resume to see what it does to yours."}</p>
        </div>
        <PipelineBoard text={runText} runId={runId} search={{ busy: t.busy, out: t.out, err: t.err }} />
        <p className="td-fine">{DISCLAIMER} <a href="/pipeline">How the reading works, and the benchmark behind it →</a></p>
      </section>

      <section className="td-glance" aria-labelledby="td-glance-h">
        <h2 id="td-glance-h">Past the test drive</h2>
        <p className="td-sub">A real run keeps going after Rank. Each part is its own page in this demo (the data behind them is synthetic).</p>
        <div className="td-parts">
          {PARTS.map(([name, href, about, tone], i) => <a key={href} href={href} style={{ ["--i" as any]: i, ["--tone" as any]: tone }}><b>{name}</b><span>{about}</span></a>)}
        </div>
      </section>

      <section className="td-own" aria-labelledby="td-own-h">
        <h2 id="td-own-h">Run it on your own machine</h2>
        <p>The same check runs locally with plain Python, no packages needed:</p>
        <pre className="dc-code"><code>{"git clone https://github.com/sameernagar-hub/regen-engine && cd regen-engine\npython -m engine try resume.txt     # a PDF needs: pip install pypdf"}</code></pre>
        <p>Setting up a full run (Docker, your own Fact Bank, real applications with a receipt for each) is covered in the <a href="/docs">Docs</a>.</p>
      </section>
    </main>
  );
}
