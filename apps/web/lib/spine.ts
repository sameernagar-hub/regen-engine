// The event spine's state (ALIVE Phase 0, docs/ALIVE_PLAN.md §4-5): one pure fold from typed live events to what
// the living engine draws. No React, no DOM, no fetch, so the same code runs in the page (useEngine) and in
// scripts/spine_check.mjs, which feeds a whole ledger through it and compares the result with the ledger.
// The UI never invents state: every field here changes only because an event or an API read said so.
import type { components } from "./api";

export type Narration = components["schemas"]["Narration"];
export type Signal = components["schemas"]["Signal"];
export type Stage = Narration["stage"];

/** One posting moving through the cylinders. by = who acted last ("shadow", "you", ...), if anyone said. */
export type Chip = { stage: Stage; company: string | null; by: string | null; since: string | null };
/** Something waiting on the user: a parked form, or the questions Shadow left. */
export type TrayItem = { company: string | null; detail: string | null; since: string | null; from: "parked" | "shadow" };
/** A container as one engine part: up (warm) or cold. Filled from /control/fleet; Phase 1 draws it. */
export type Part = "up" | "cold";

export type Spine = {
  chips: Map<string, Chip>;      // job (posting URL) -> where it is now; leaves when it submits, parks or falls out
  tray: Map<string, TrayItem>;   // job -> what waits on you
  trail: string[];               // submitted jobs, oldest first (the exhaust trail); deduplicated
  submitted: number;             // distinct submitted jobs seen (== trail.length, kept for cheap reads)
  heard: Record<string, number>; // outcome kind -> count (oa, interview, rejection, ...)
  gear: string | null;
  shadow: string | null;         // Shadow mode: calls / autopilot / always / off
  keywords: string | null;       // "on" / "off"
  cap: string | null;            // "level:cap", e.g. "2:50"
  problems: Set<string>;         // warning lights that are on
  parts: Record<string, Part>;
};

/** Listening chips beyond this many are dropped oldest-first: most discovered postings are never selected. */
export const MAX_LISTEN = 60;

export function empty(): Spine {
  return { chips: new Map(), tray: new Map(), trail: [], submitted: 0, heard: {}, gear: null, shadow: null,
           keywords: null, cap: null, problems: new Set(), parts: {} };
}

function move(s: Spine, job: string | null | undefined, stage: Stage, n: { company?: string | null; by?: string | null; ts?: string | null }) {
  if (!job) return;
  const prev = s.chips.get(job);
  s.chips.delete(job);  // re-insert so Map order is "most recently moved last"
  s.chips.set(job, { stage, company: n.company ?? prev?.company ?? null, by: n.by ?? prev?.by ?? null, since: n.ts ?? null });
  if (stage === "listen") {
    let listening = 0;
    for (const c of s.chips.values()) if (c.stage === "listen") listening++;
    for (const [k, c] of s.chips) {
      if (listening <= MAX_LISTEN) break;
      if (c.stage === "listen") { s.chips.delete(k); listening--; }
    }
  }
}

/**
 * Apply one narration to the spine, in place, and return it. Unknown kinds (an older API) change nothing.
 * Order of events is the ledger's; applying the same ledger twice from empty() gives the same result.
 */
export function foldNarration(s: Spine, n: Narration): Spine {
  const job = n.job ?? null;
  switch (n.kind) {
    case "discovered": move(s, job, "listen", n); break;
    case "gate.skip": if (job) s.chips.delete(job); break;           // fell out of the Judge cylinder
    case "resume": move(s, job, "write", n); break;
    case "apply.start": for (const j of n.jobs ?? []) move(s, j, "apply", { ts: n.ts }); break;
    case "shadow.answer": if (job) s.tray.delete(job); move(s, job, "apply", { ...n, by: "shadow" }); break;
    case "submitted":
      if (job) {
        s.chips.delete(job); s.tray.delete(job);
        if (!s.trail.includes(job)) { s.trail.push(job); s.submitted = s.trail.length; }
      }
      break;
    case "parked":
      if (job) { s.chips.delete(job); s.tray.set(job, { company: n.company ?? null, detail: n.detail ?? null, since: n.ts ?? null, from: "parked" }); }
      break;
    case "shadow.abstain":
      if (job) s.tray.set(job, { company: n.company ?? null, detail: n.detail ?? null, since: n.ts ?? null, from: "shadow" });
      break;
    case "apply.fail": if (job) s.chips.delete(job); break;           // retried later: it re-enters with its next event
    case "outcome": if (n.detail) s.heard[n.detail] = (s.heard[n.detail] ?? 0) + 1; break;
    default: break;
  }
  return s;
}

/** Apply one control-plane signal (gear, Shadow mode, cap, keywords, warning lights) to the spine, in place. */
export function foldSignal(s: Spine, g: Signal): Spine {
  switch (g.kind) {
    case "gear": s.gear = g.detail ?? s.gear; break;
    case "shadow.mode": s.shadow = g.detail ?? s.shadow; break;
    case "keywords": s.keywords = g.detail ?? s.keywords; break;
    case "cap": s.cap = g.detail ?? s.cap; break;
    case "problem": if (g.detail) s.problems.add(g.detail); break;
    case "problem.clear": if (g.detail) s.problems.delete(g.detail); break;
    default: break;  // targeting, outreach.sent, human.check: shown by later phases, no spine state yet
  }
  return s;
}

/** Fleet heartbeat rows -> parts. A role is "up" if any of its containers is up (appliers: one row each). */
export function partsFromFleet(members: { role?: string; up?: boolean }[]): Record<string, Part> {
  const out: Record<string, Part> = {};
  for (const m of members) {
    if (!m.role) continue;
    out[m.role] = out[m.role] === "up" || m.up ? "up" : "cold";
  }
  return out;
}
