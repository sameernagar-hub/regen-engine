// One engine stream per tab (v1.2). Browsers allow ~6 connections per host and every EventSource holds one for
// good; the backdrop, the home engine and the room each opened their own, so two tabs could starve ordinary
// requests. Subscribers share this connection; it opens with the first and closes with the last.
import { api } from "./types";

// ALIVE Phase 0: "signal" carries control-plane events (gear, cap, Shadow mode, warning lights); see lib/spine.ts.
// ALIVE Phase 4: "replay" is local only (alive/Replay.tsx plays past narration at speed): pulses and captions, no fold.
type Handler = (type: "narration" | "snapshot" | "signal" | "replay", data: any) => void;
const subs = new Set<Handler>();
let es: EventSource | null = null;

export function subscribe(h: Handler): () => void {
  if (process.env.NEXT_PUBLIC_REGEN_MODE === "public") return () => {};  // the hosted site has no stream
  subs.add(h);
  if (!es) {
    es = new EventSource(api("/api/stream?after=999999999"));
    for (const t of ["narration", "snapshot", "signal"] as const)
      es.addEventListener(t, (m) => { const d = JSON.parse((m as MessageEvent).data); subs.forEach((s) => s(t, d)); });
  }
  return () => {
    subs.delete(h);
    if (!subs.size) { es?.close(); es = null; }
  };
}

/** Phase 4: hand a past narration to every subscriber as type "replay" (no network; subscribers decide what to draw). */
export function replay(data: unknown): void {
  subs.forEach((s) => s("replay", data));
}
