// ALIVE Phase 0 acceptance: feed a whole ledger's typed events through the same fold the page uses
// (lib/spine.ts) and print the end state as JSON. scripts/bench_alive.py compares it with the ledger.
// Usage: node scripts/spine_check.mjs <events.json>   (a JSON list of {type: "narration"|"signal", data})
// Node 22.18+ runs the .ts module directly (type stripping); spine.ts has only type imports.
import { readFileSync } from "node:fs";
import { empty, foldNarration, foldSignal } from "../lib/spine.ts";

const path = process.argv[2];
if (!path) { console.error("usage: node scripts/spine_check.mjs <events.json>"); process.exit(2); }
const events = JSON.parse(readFileSync(path, "utf-8"));
const s = empty();
const t0 = performance.now();
for (const e of events) (e.type === "signal" ? foldSignal : foldNarration)(s, e.data);
const ms = performance.now() - t0;
console.log(JSON.stringify({
  events: events.length, ms: Math.round(ms), submitted: s.submitted, chips: s.chips.size, tray: s.tray.size,
  gear: s.gear, shadow: s.shadow, keywords: s.keywords, cap: s.cap, problems: [...s.problems], heard: s.heard,
}));
