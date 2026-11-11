"use client";
import { api } from "./types";
import { subscribe } from "./stream";
// One data layer, two sources:
//   local  -> the private REGEN API (/api/*, SSE stream): your real data, on 127.0.0.1 only
//   public -> the anonymized feed (/api/public, polled): no company names, no answers, no proofs
// NEXT_PUBLIC_REGEN_MODE=public is set at build time for the hosted site.
import { useEffect, useRef, useState } from "react";
import { get, type Application, type Narration, type Snapshot } from "./types";
import { empty, foldNarration, foldSignal, partsFromFleet, type Signal, type Spine } from "./spine";

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
  const [pulse, setPulse] = useState<{ stage: string; id: number; tone: string } | null>(null);
  const [replaying, setReplaying] = useState(false);
  // ALIVE Phase 0: the event spine (lib/spine.ts), folded from typed stream events; `alive` re-renders on each fold.
  const spine = useRef<Spine>(empty());
  const [alive, setAlive] = useState<Spine>(() => spine.current);
  const publish = () => setAlive({ ...spine.current });
  const seen = useRef(new Set<string>());
  const seq = useRef(0);
  const queue = useRef<Narration[]>([]);     // new real events, played first
  const recent = useRef<Narration[]>([]);    // the last real events, replayed when nothing new is happening

  // one event every 1.6 s: the sentence appears and a light travels to its station
  useEffect(() => {
    const t = setInterval(() => {
      if (document.hidden) return;  // nobody is watching: keep the queue for when the tab comes back
      let n = queue.current.shift();
      let replay = false;
      if (!n && recent.current.length) {
        const i = seq.current % recent.current.length;
        n = { ...recent.current[i] };
        replay = true;
      }
      if (!n) return;
      n = { ...n, id: ++seq.current };
      setReplaying(replay);
      setLines((l) => [...l.slice(-5), n!]);
      setPulse({ stage: n.stage, id: n.id, tone: n.tone });
    }, 1600);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (PUBLIC) {
      const pull = async () => {
        try {
          const f: Feed = await get("/api/public");
          setSnap({ verified: f.verified, verified_today: 0, waiting: 0, boards: f.boards, last_poll: f.last_poll ?? null,
                    by_lane: {}, outcomes: {}, backend: "jsonl" });
          setApps(f.verified_roles.map(([role, lane], i) => ({ job: `${i}`, company: "", role, lane, status: "SUBMITTED", ts: "", proof: "public" } as Application)));
          const first = seen.current.size === 0;
          const evs = f.events.map((e) => ({ id: 0, ts: e.ts, stage: e.stage, tone: e.tone, text: e.text } as Narration));
          recent.current = evs.slice(-40);
          for (const n of evs) {
            const k = n.ts + n.text;
            if (seen.current.has(k)) continue;
            seen.current.add(k);
            if (!first) queue.current.push(n);
          }
        } catch { /* feed unreachable: keep showing what we have */ }
      };
      pull();
      const poll = setInterval(pull, 30000);
      return () => clearInterval(poll);
    }
    const refresh = () => get<Application[]>("/api/applications?status=SUBMITTED&limit=500").then(setApps).catch(() => {});
    refresh();
    get<Narration[]>("/api/narration?limit=40").then((r) => { recent.current = r; }).catch(() => {});
    get<Snapshot>("/api/snapshot").then(setSnap).catch(() => {});
    // one read each at mount: the current control state from the ledger, and which containers are warm
    get<Signal[]>("/api/signals").then((r) => { r.forEach((g) => foldSignal(spine.current, g)); publish(); })
      .catch((e) => console.warn("signals unavailable: gear / cap / Shadow wait for their next event", e));
    get<{ members: { role?: string; up?: boolean }[] }>("/api/control/fleet")
      .then((f) => { spine.current.parts = partsFromFleet(f.members); publish(); })
      .catch((e) => console.warn("fleet unavailable: every part is drawn cold", e));
    return subscribe((type, data) => {
      if (type === "snapshot") return setSnap(data);
      if (type === "signal") { foldSignal(spine.current, data as Signal); return publish(); }
      const n: Narration = data;
      foldNarration(spine.current, n);
      publish();
      queue.current.push(n);
      recent.current = [...recent.current.slice(-39), n];
      if (n.stage === "apply" && n.tone === "win") refresh();
    });
  }, []);

  return { snap, apps, lines, pulse, replaying, alive };
}

export async function loadGraph(): Promise<{ nodes: any[]; edges: any[] }> {
  if (PUBLIC) return (await get<Feed>("/api/public")).graph;
  return get("/api/graph?questions=false");
}
