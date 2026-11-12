"use client";
// The exhaust trail (ALIVE Phase 3, docs/ALIVE_PLAN.md §5): today's submissions as receipts, oldest left, newest
// right. Rebuilt from /api/applications on load (so a reload keeps it) and re-read whenever a `submitted` narration
// arrives, so every puff the engine shows lands here as a row backed by the ledger. Click one to open its proof.
import { useEffect, useRef, useState } from "react";
import { subscribe } from "@/lib/stream";
import { get, type Application } from "@/lib/types";
import type { Narration } from "@/lib/spine";
import { ProofDrawer } from "./ProofDrawer";

const PUBLIC = process.env.NEXT_PUBLIC_REGEN_MODE === "public";

/** Today's date as the ledger writes it (local time, "YYYY-MM-DD"). */
function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function Trail() {
  const [rows, setRows] = useState<Application[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Application | null>(null);
  const [fresh, setFresh] = useState<string | null>(null);
  const strip = useRef<HTMLOListElement>(null);
  const opener = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = (newJob?: string) =>
      get<Application[]>("/api/applications?status=SUBMITTED&limit=300").then((all) => {
        if (!alive) return;
        const day = today();
        setRows(all.filter((a) => (a.ts ?? "").startsWith(day)).sort((a, b) => (a.ts < b.ts ? -1 : 1)));
        setError(null);
        if (newJob) setFresh(newJob);
      }).catch((e) => { if (alive) setError(`trail unavailable: ${e instanceof Error ? e.message : e}`); });
    load();
    const unsub = subscribe((type, data) => {
      if (type !== "narration" || (data as Narration).kind !== "submitted") return;
      const job = (data as Narration).job ?? undefined;
      clearTimeout(timer);  // the application row lands with the event; one re-read covers a burst of submits
      timer = setTimeout(() => load(job), 1200);
    });
    return () => { alive = false; unsub(); clearTimeout(timer); };
  }, []);

  // newest on the right: keep the strip scrolled to its end when a receipt arrives
  useEffect(() => {
    const el = strip.current;
    if (el) el.scrollLeft = el.scrollWidth;
  }, [rows]);
  useEffect(() => {
    if (!fresh) return;
    const t = setTimeout(() => setFresh(null), 1600);
    return () => clearTimeout(t);
  }, [fresh]);

  const close = () => { setOpen(null); opener.current?.focus(); };

  return (
    <section className="al-trail" aria-label="Today's submissions">
      <h2>Exhaust trail <small>{rows ? `${rows.length} sent today, each with proof` : "loading"}</small></h2>
      {error && <p className="alive-error" role="status">{error}</p>}
      {rows && rows.length === 0 && <p className="al-trail-empty">Nothing sent yet today. Each submission lands here as a receipt.</p>}
      {rows && rows.length > 0 && (
        <ol ref={strip}>
          {rows.map((a) => {
            const name = PUBLIC ? `${a.lane ?? "role"} · ${a.role}` : `${a.company} · ${a.role}`;
            return (
              <li key={a.url ?? a.job} className={fresh && fresh === a.url ? "al-fresh" : ""}>
                <button type="button" onClick={(e) => { opener.current = e.currentTarget; setOpen(a); }}
                        aria-label={`${name}, sent ${a.ts.slice(11, 16)}: open proof`}>
                  <span className="al-puff" aria-hidden>{PUBLIC ? (a.lane ?? "·").charAt(0).toUpperCase() : a.company.charAt(0).toUpperCase()}</span>
                  <span className="al-rcpt"><b>{PUBLIC ? a.lane ?? "role" : a.company}</b><time>{a.ts.slice(11, 16)}</time></span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
      {open && <ProofDrawer app={open} publicView={PUBLIC} onClose={close} />}
    </section>
  );
}
