"use client";
// "Try it" quick start. useTestDrive() is the one client for /api/public/try (a Next.js route, lib/tryit.ts), so it
// works the same on the Render demo and on your machine with no Python API behind it. The Test drive page
// (app/test-drive) builds its cockpit on the hook; TryBox is the compact paste box /docs uses.
import { useState } from "react";

export type TryOut = { profile: { lanes: string[]; years: number; senior: boolean; student: boolean; keywords: string[] };
  boards: number; postings: number; passing: number; checked: number; blocked: Record<string, number>;
  top: { company: string; title: string; location: string; url: string; reason: string; match: number; matched: string[]; missing: string[] }[] };

export function useTestDrive() {
  const [text, setText] = useState("");
  const [out, setOut] = useState<TryOut | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const go = async (override?: string) => {
    const body = override ?? text;
    if (!body.trim()) return null;
    setBusy(true); setErr(""); setOut(null);
    try {
      const r = await fetch("/api/public/try", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: body }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || `the test drive stalled: ${r.status}`);
      setOut(j as TryOut);
      return j as TryOut;
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); return null; }
    finally { setBusy(false); }
  };
  return { text, setText, out, err, busy, go };
}

export function TopRoles({ out }: { out: TryOut }) {
  return out.top.length ? (
    <ol className="try-top">{out.top.map((j, i) => (
      <li key={j.url} style={{ ["--i" as any]: i }}>
        <span className="spark" aria-hidden />
        <a href={j.url} target="_blank" rel="noreferrer noopener">{j.company}: {j.title}</a>
        {j.location ? <span className="loc"> {j.location}</span> : null}
        <small>{j.reason}</small>
      </li>))}
    </ol>)
    : <p>No fresh role passed the gate for this resume right now.</p>;
}

/** Compact paste box for /docs. */
export function TryBox() {
  const t = useTestDrive();
  return (
    <div className={`dc-try${t.busy ? " busy" : ""}`}>
      <label htmlFor="dc-try-text">Paste your resume text (nothing is stored):</label>
      <textarea id="dc-try-text" rows={6} value={t.text} onChange={(e) => t.setText(e.target.value)} maxLength={50000}
                placeholder="Paste the text of your resume" />
      <button type="button" onClick={() => t.go()} disabled={t.busy || !t.text.trim()}>{t.busy ? "Scanning sample boards…" : "Show my 10 best roles"}</button>
      {t.err && <p className="alive-error" role="status">{t.err}</p>}
      {t.out && (
        <div className="try-out" role="status">
          <p>Scanned {t.out.boards} public boards, {t.out.postings.toLocaleString()} postings; {t.out.passing} pass.</p>
          <TopRoles out={t.out} />
          <p><small>Nothing was applied to and nothing was saved. The full ride is on the <a href="/test-drive">Test drive</a>.</small></p>
        </div>
      )}
    </div>
  );
}
