"use client";
// One receipt opened (ALIVE Phase 3): what was sent and the proof it went through. Local build: company, role, lane,
// the proof screenshot (/api/proof), the resume PDF (/api/resume) and every question with the answer given, exactly as
// the ledger row has them. Public build: role and lane only (no employer, answers, resume or screenshot).
// A modal drawer: Esc or the close button closes it, focus stays inside while it is open.
import { useEffect, useRef } from "react";
import { api, type Application } from "@/lib/types";

const file = (p: string) => p.split("/").pop() ?? p;

export function ProofDrawer({ app, publicView, onClose }: { app: Application; publicView: boolean; onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeBtn.current?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); return; }
      if (e.key !== "Tab" || !box.current) return;
      const f = box.current.querySelectorAll<HTMLElement>("a[href], button, iframe, [tabindex]:not([tabindex='-1'])");
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [onClose]);

  const answered = (app.answers ?? []).filter(([, a]) => a !== null && a !== "");
  return (
    <div className="al-drawer-back" onClick={onClose}>
      <div ref={box} className="al-drawer" role="dialog" aria-modal="true" aria-labelledby="al-drawer-title"
           onClick={(e) => e.stopPropagation()}>
        <header>
          <h3 id="al-drawer-title">{publicView ? app.role : `${app.company}: ${app.role}`}</h3>
          <button ref={closeBtn} type="button" className="al-drawer-x" onClick={onClose} aria-label="Close">×</button>
        </header>
        <p className="al-drawer-meta">Sent {app.ts.replace("T", " ").slice(0, 16)}{app.lane ? ` · ${app.lane} resume` : ""}</p>
        {!publicView && (
          <>
            {app.proof ? (
              <figure>
                <img src={api(`/api/proof/${file(app.proof)}`)} alt={`The page after submitting to ${app.company}`} loading="lazy" />
                <figcaption><a href={api(`/api/proof/${file(app.proof)}`)} target="_blank" rel="noreferrer">Proof screenshot ↗</a></figcaption>
              </figure>
            ) : <p className="alive-error">No proof screenshot on disk for this one (it may have been cleaned after 90 days).</p>}
            {app.resume && (
              <p><a href={api(`/api/resume/${file(app.resume)}`)} target="_blank" rel="noreferrer">Resume sent: {file(app.resume)} ↗</a></p>
            )}
            {answered.length > 0 && (
              <details>
                <summary>{answered.length} answers given</summary>
                <dl>{answered.map(([q, a], i) => <div key={i}><dt>{q}</dt><dd>{a}</dd></div>)}</dl>
              </details>
            )}
            {app.url && <p><a href={app.url} target="_blank" rel="noreferrer">The posting ↗</a></p>}
          </>
        )}
      </div>
    </div>
  );
}
