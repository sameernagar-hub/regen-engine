"use client";
// v0.9 engine room data: stations (one per pipeline stage) and per-job timelines. Live by SSE: any new event in the
// log re-pulls the stations (one O(E) pass on the API), so every room updates the moment the engine does something.
import { useEffect, useState } from "react";
import { get } from "./types";

export type Line = { id: number; ts: string; tone: string; text: string; url?: string | null; job?: string | null };
export type Station = { key: string; name: string; about: string; feeds: string[]; total: number; today: number;
                        tones: Record<string, number>; recent: Line[] };
export type JobEvent = { id: number; ts: string; kind: string; status?: string | null; stage?: string | null; tone?: string | null;
                         text?: string | null; data: Record<string, any>; answers: [string, string][] };
export type Job = { url: string; job: string; events: JobEvent[] };

export const TONE: Record<string, string> = { win: "var(--gold)", alarm: "var(--alarm)", you: "var(--amber)", quiet: "var(--dim)", calm: "var(--calm)" };

export function useStations(recent = 8) {
  const [stations, setStations] = useState<Station[] | null>(null);
  const [beat, setBeat] = useState<{ stage: string; n: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true, pending = false;
    const pull = () => {
      if (pending) return;
      pending = true;
      get<Station[]>(`/api/stations?recent=${recent}`)
        .then((s) => { if (alive) { setStations(s); setError(null); } })
        .catch((e) => alive && setError(String(e.message || e)))
        .finally(() => { pending = false; });
    };
    pull();
    let es: EventSource | null = null;
    try {
      es = new EventSource("/api/stream?after=999999999");
      es.addEventListener("narration", (m) => {
        const n = JSON.parse((m as MessageEvent).data);
        setBeat((b) => ({ stage: n.stage, n: (b?.n || 0) + 1 }));
        pull();
      });
    } catch { /* no stream: the poll below keeps it fresh */ }
    const t = setInterval(pull, 15000);
    return () => { alive = false; clearInterval(t); es?.close(); };
  }, [recent]);
  return { stations, beat, error };
}

export const jobHref = (url?: string | null) => (url ? `/job?u=${encodeURIComponent(url)}` : "#");
export const when = (ts?: string | null) => (ts ? ts.replace("T", " ").slice(5, 16) : "");
