// One engine stream per tab (v1.2). Browsers allow ~6 connections per host and every EventSource holds one for
// good; the backdrop, the home engine and the room each opened their own, so two tabs could starve ordinary
// requests. Subscribers share this connection; it opens with the first and closes with the last.
import { api } from "./types";

type Handler = (type: "narration" | "snapshot", data: any) => void;
const subs = new Set<Handler>();
let es: EventSource | null = null;

export function subscribe(h: Handler): () => void {
  if (process.env.NEXT_PUBLIC_REGEN_MODE === "public") return () => {};  // the hosted site has no stream
  subs.add(h);
  if (!es) {
    es = new EventSource(api("/api/stream?after=999999999"));
    for (const t of ["narration", "snapshot"] as const)
      es.addEventListener(t, (m) => { const d = JSON.parse((m as MessageEvent).data); subs.forEach((s) => s(t, d)); });
  }
  return () => {
    subs.delete(h);
    if (!subs.size) { es?.close(); es = null; }
  };
}
