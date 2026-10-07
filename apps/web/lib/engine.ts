"use client";
// One data layer, two sources:
//   local  -> the private REGEN API (/api/*, SSE stream): your real data, on 127.0.0.1 only
//   public -> the anonymized feed (/api/public, polled): no company names, no answers, no proofs
// NEXT_PUBLIC_REGEN_MODE=public is set at build time for the hosted site.
import { useEffect, useRef, useState } from "react";
import { get, type Application, type Narration, type Snapshot } from "./types";

export const PUBLIC = process.env.NEXT_PUBLIC_REGEN_MODE === "public";

type Feed = {
  generated: string; verified: number; boards: number; last_poll?: number | null;
  verified_roles: [string, string][];
  events: { stage: Narration["stage"]; tone: Narration["tone"]; text: string; ts: string }[];
  graph: { nodes: any[]; edges: any[] };
};

export function useEngine() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [apps, setApps] = useState<Application[]>([]);
  const [lines, setLines] = useState<Narration[]>([]);
  const [pulse, setPulse] = useState<{ stage: string; id: number } | null>(null);
  const seen = useRef(new Set<string>());
  const seq = useRef(0);

  useEffect(() => {
    if (PUBLIC) {
      let stop = false;
      const queue: Narration[] = [];
      const pull = async () => {
        try {
          const f: Feed = await get("/api/public");
          setSnap({ verified: f.verified, verified_today: 0, waiting: 0, boards: f.boards, last_poll: f.last_poll ?? null,
                    by_lane: {}, outcomes: {}, backend: "jsonl" });
          setApps(f.verified_roles.map(([role, lane], i) => ({ job: `${i}`, company: "", role, lane, status: "SUBMITTED", ts: "", proof: "public" } as Application)));
          const first = seen.current.size === 0;
          for (const e of f.events) {
            const k = e.ts + e.text;
            if (seen.current.has(k)) continue;
            seen.current.add(k);
            const n = { id: ++seq.current, ts: e.ts, stage: e.stage, tone: e.tone, text: e.text } as Narration;
            if (first) setLines((l) => [...l.slice(-5), n]); else queue.push(n);
          }
        } catch { /* feed unreachable: keep showing what we have */ }
      };
      // new events play one by one, so an update arrives as motion, not a jump
      const play = setInterval(() => {
        const n = queue.shift();
        if (!n) return;
        setLines((l) => [...l.slice(-5), n]);
        setPulse({ stage: n.stage, id: n.id });
      }, 1400);
      pull();
      const poll = setInterval(() => !stop && pull(), 30000);
      return () => { stop = true; clearInterval(play); clearInterval(poll); };
    }
    const refresh = () => get<Application[]>("/api/applications?status=SUBMITTED&limit=500").then(setApps).catch(() => {});
    refresh();
    get<Narration[]>("/api/narration?limit=6").then(setLines).catch(() => {});
    get<Snapshot>("/api/snapshot").then(setSnap).catch(() => {});
    const es = new EventSource("/api/stream?after=999999999");
    es.addEventListener("snapshot", (m) => setSnap(JSON.parse((m as MessageEvent).data)));
    es.addEventListener("narration", (m) => {
      const n: Narration = JSON.parse((m as MessageEvent).data);
      setLines((l) => [...l.slice(-5), n]);
      setPulse({ stage: n.stage, id: n.id });
      if (n.stage === "apply" && n.tone === "win") refresh();
    });
    return () => es.close();
  }, []);

  return { snap, apps, lines, pulse };
}

export async function loadGraph(): Promise<{ nodes: any[]; edges: any[] }> {
  if (PUBLIC) return (await get<Feed>("/api/public")).graph;
  return get("/api/graph?questions=false");
}
