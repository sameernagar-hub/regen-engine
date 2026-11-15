"use client";
// "Try it" paste box, shown on the front page and on /docs. It posts to this site's own /api/public/try (a Next.js
// route, lib/tryit.ts), so it works the same on the Render demo and on your machine, with no Python API behind it.
// Drawn as the engine's intake: a flywheel that idles and spins up while it works, the four stations it runs
// (read, scan, gate, rank) firing in turn, and each passing role arriving like a cylinder firing.
import { useEffect, useState } from "react";

type TryOut = { skills: Record<string, string[]>; boards: number; postings: number; passing: number;
  top: { company: string; title: string; location: string; url: string; reason: string }[]; blocked: Record<string, number> };

const STATIONS = ["Read resume", "Scan boards", "Fit gate", "Rank"];

function Flywheel({ fast }: { fast: boolean }) {
  return (
    <svg className={`try-fly${fast ? " fast" : ""}`} viewBox="0 0 40 40" aria-hidden>
      <circle cx="20" cy="20" r="17" className="rim" />
      <g className="spokes">{[0, 60, 120].map((a) => <line key={a} x1="20" y1="4" x2="20" y2="36" transform={`rotate(${a} 20 20)`} />)}</g>
      <circle cx="20" cy="20" r="5" className="hub" />
    </svg>
  );
}

export function TryBox() {
  const [text, setText] = useState("");
  const [out, setOut] = useState<TryOut | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(-1);  // which station is firing; 4 = all done

  useEffect(() => {  // walk the stations while the request runs (scan is the long one, so it holds there)
    if (!busy) return;
    setStage(0);
    const t = [setTimeout(() => setStage(1), 350), setTimeout(() => setStage(2), 5000)];
    return () => t.forEach(clearTimeout);
  }, [busy]);

  const go = async () => {
    setBusy(true); setErr(""); setOut(null);
    try {
      const r = await fetch("/api/public/try", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body.detail || `try failed: ${r.status}`);
      setOut(body as TryOut); setStage(4);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); setStage(-1); }
    finally { setBusy(false); }
  };
  const share = out && out.postings ? Math.max(2, Math.round((out.passing / out.postings) * 1000) / 10) : 0;

  return (
    <div className={`dc-try${busy ? " busy" : ""}`}>
      <ol className="try-stations" aria-label="What the quick start runs">
        {STATIONS.map((s, i) => (
          <li key={s} className={stage > i || stage === 4 ? "done" : stage === i ? "firing" : ""}>
            <span className="plug" aria-hidden />{s}
          </li>
        ))}
      </ol>
      <label htmlFor="dc-try-text">Paste your resume text (nothing is stored):</label>
      <textarea id="dc-try-text" rows={6} value={text} onChange={(e) => setText(e.target.value)} maxLength={50000}
                placeholder="Paste the text of your resume" />
      <button type="button" onClick={go} disabled={busy || !text.trim()}>
        <Flywheel fast={busy} />{busy ? "Scanning sample boards…" : "Show my 10 best roles"}
      </button>
      {err && <p className="alive-error" role="status">{err}</p>}
      {out && (
        <div className="try-out" role="status">
          <p className="try-skills">Your resume shows: {Object.entries(out.skills).map(([f, w]) => <span key={f} className="try-chip"><b>{f}</b> {w.join(", ")}</span>)}
            {!Object.keys(out.skills).length && "no known skill words"}</p>
          <div className="try-gauge" aria-label={`${out.passing} of ${out.postings} postings pass`}>
            <span style={{ ["--to" as any]: `${Math.min(100, share)}%` }} />
            <small>{out.boards} public boards · {out.postings.toLocaleString()} postings · <b>{out.passing}</b> pass the gate</small>
          </div>
          {out.top.length ? (
            <ol className="try-top">{out.top.map((j, i) => (
              <li key={j.url} style={{ ["--i" as any]: i }}>
                <span className="spark" aria-hidden />
                <a href={j.url} target="_blank" rel="noreferrer noopener">{j.company}: {j.title}</a>
                {j.location ? <span className="loc"> {j.location}</span> : null}
                <small>{j.reason}</small>
              </li>))}
            </ol>)
            : <p>No fresh role passed the gate for this resume right now.</p>}
          <p><small>Blocked by the fit gate: {Object.entries(out.blocked).map(([r, n]) => `${n.toLocaleString()} ${r}`).join(", ") || "none"}. Nothing was applied to and nothing was saved.</small></p>
        </div>
      )}
    </div>
  );
}

/** The front page's quick start: the README's "Try it in a minute", as the engine's intake. */
export function TryPanel() {
  return (
    <section className="try-panel" aria-labelledby="try-h">
      <p className="eyebrow"><span className="brand">Intake</span> try it in a minute<span className="try-live" aria-hidden /></p>
      <h2 id="try-h">Feed it a resume, <em>watch it fire.</em></h2>
      <p>Paste below, or <code>git clone</code> the repo and run <code>python -m engine try resume.txt</code> (a PDF needs <code>pip install pypdf</code>).
        It scans a sample of public boards and shows the 10 best-fitting fresh roles with the reason each passed. No
        database, no Docker, nothing applied, nothing saved.</p>
      <TryBox />
    </section>
  );
}
