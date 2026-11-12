"use client";
// The pulse strip (11-11, the user: "it looks stationary, like a template"): the hero says what the engine is doing
// right now. Three live gauges that count up when the ledger changes (sent today, sent in total, waiting on you) and
// a ticker of the latest real events sliding in. Every number comes from /api/snapshot and its SSE updates; every
// line is a real narration. With nothing happening, the ticker says so instead of looping old lines.
import { useEffect, useRef, useState } from "react";
import { subscribe } from "@/lib/stream";
import { get } from "@/lib/types";
import type { Narration } from "@/lib/spine";

type Snap = { verified: number; verified_today: number; waiting: number; boards: number };

/** A number that rolls to its new value (requestAnimationFrame, ~700 ms); jumps under reduced motion. */
function Roll({ to }: { to: number }) {
  const [n, setN] = useState(to);
  const from = useRef(to);
  useEffect(() => {
    const start = from.current;
    if (start === to || matchMedia("(prefers-reduced-motion: reduce)").matches) { setN(to); from.current = to; return; }
    let raf = 0;
    const t0 = performance.now();
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / 700);
      setN(Math.round(start + (to - start) * (1 - Math.pow(1 - k, 3))));
      if (k < 1) raf = requestAnimationFrame(step); else from.current = to;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [to]);
  return <>{n.toLocaleString()}</>;
}

export function Pulse() {
  const [snap, setSnap] = useState<Snap | null>(null);
  const [bump, setBump] = useState<Record<string, number>>({});
  const [lines, setLines] = useState<Narration[]>([]);
  const prev = useRef<Snap | null>(null);

  useEffect(() => {
    const take = (s: Snap) => {
      const p = prev.current;
      if (p) setBump((b) => ({ ...b, ...(s.verified_today !== p.verified_today ? { today: Date.now() } : {}),
                                     ...(s.waiting !== p.waiting ? { waiting: Date.now() } : {}),
                                     ...(s.boards !== p.boards ? { boards: Date.now() } : {}) }));
      prev.current = s;
      setSnap(s);
    };
    get<Snap>("/api/snapshot").then(take).catch(() => {});
    get<Narration[]>("/api/narration?limit=6").then((r) => setLines(r.slice(-3).reverse())).catch(() => {});
    return subscribe((type, data) => {
      if (type === "snapshot") take(data as Snap);
      else if (type === "narration") setLines((l) => [data as Narration, ...l].slice(0, 3));
    });
  }, []);

  const quiet = lines[0]?.ts ? Date.now() - new Date(lines[0].ts).getTime() > 10 * 60 * 1000 : false;
  const gauge = (key: string, label: string, value: number | undefined, tone: string) => (
    <div className={`al-gauge al-${tone}`} key={`${key}${bump[key] ?? 0}`} data-bump={bump[key] ? "1" : undefined}>
      <b>{value === undefined ? "–" : <Roll to={value} />}</b>
      <span>{label}</span>
    </div>
  );
  return (
    <section className="al-pulse" aria-label="Right now">
      <div className="al-gauges">
        {gauge("today", "sent today", snap?.verified_today, "gold")}
        {gauge("total", "sent with proof", snap?.verified, "ink")}
        {gauge("waiting", "waiting on you", snap?.waiting, "amber")}
        {gauge("boards", "boards watched", snap?.boards, "calm")}
      </div>
      <ol className="al-ticker" aria-live="polite" aria-label="Latest events">
        {lines.map((n, i) => (
          <li key={`${n.id}-${n.ts}`} className={`al-tone-${n.tone}${i === 0 ? " al-new" : ""}`}>
            <time>{(n.ts ?? "").slice(11, 16)}</time> {n.text}
          </li>
        ))}
        {quiet && <li className="al-quiet">Quiet for 10+ minutes: the engine is scanning for new postings.</li>}
      </ol>
    </section>
  );
}
