// Public mode's data layer: the proxy dataset (scripts/proxy_dataset.py -> public/proxy/) stands in for the API on
// your machine, so every page of the control room works on the hosted site. The dataset is the real API's output
// over a synthetic engine (a fictional candidate, made-up companies); timestamps are moved forward to "now" when
// served, and writes (answers, marks, runs, filters) are simulated in this tab only. Nothing leaves the browser.

type Manifest = { generated: number; routes: Record<string, string>; jobs: Record<string, string> };

const BASE = "/proxy/";
let manifest: Promise<Manifest> | null = null;
const files = new Map<string, Promise<any>>();
const overlay = {
  answered: new Set<string>(),                        // questions answered in this tab
  marks: new Map<string, { mark: string; ts: string }>(),
  run: null as any,
  filters: null as any,
  gear: null as any,                                  // gearbox shifts in this tab
};

const load = (name: string) => {
  if (!files.has(name)) files.set(name, fetch(BASE + name).then((r) => { if (!r.ok) throw new Error(`${name}: ${r.status}`); return r.json(); }));
  return files.get(name)!;
};
const getManifest = () => (manifest ??= load("manifest.json"));

// Move every timestamp by (now - generated), so "3 min ago" stays 3 min ago on every visit.
const TIME_KEYS = new Set(["ts", "updated", "created", "started", "finished", "last_poll", "last_post", "marked"]);
const ISO = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/;
const pad = (n: number) => String(n).padStart(2, "0");
const isoLocal = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
function shiftIso(s: string, by: number) {
  const m = ISO.exec(s);
  if (!m) return s;
  const d = new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
  return isoLocal(new Date(d.getTime() + by * 1000)) + s.slice(19);
}
function rebase(v: any, by: number, key = ""): any {
  if (Array.isArray(v)) return v.map((x) => rebase(x, by, key));
  if (v && typeof v === "object") { const o: any = {}; for (const k in v) o[k] = rebase(v[k], by, k); return o; }
  if (typeof v === "number" && TIME_KEYS.has(key) && v > 1.6e9 && v < 2.3e9) return v + by;
  if (typeof v === "string" && ISO.test(v) && (TIME_KEYS.has(key) || key === "listed" || key === "")) return shiftIso(v, by);
  return v;
}

const nowIso = () => isoLocal(new Date());

// Shadow's switchboard, acted out in this tab (made-up companies): lines ring call 1, call 2, then Shadow picks up.
const SHADOW_DEMO = [
  ["Northwind Robotics - Software Engineer", "Desired Salary", 20],
  ["Lumen Health - Backend Engineer", "How did you hear about Lumen Health?", 75],
  ["Arcfield AI - ML Engineer", "Have you built or evaluated a workflow that uses a large language model?", 140],
  ["Quarry Labs - Platform Engineer", "In which quarter would you be available to begin?", 400],
] as const;
const DEMO_REC: Record<string, string> = {
  "Desired Salary": "$141,000-$160,000 (middle of the posted range)", "How did you hear about Lumen Health?": "Company website",
  "Have you built or evaluated a workflow that uses a large language model?": "Yes", "In which quarter would you be available to begin?": "Q4",
};
const shadowDemo = { mode: "calls", ring_min: 1, t0: Date.now(), picked: new Map<string, { who: string; at: number }>() };
function shadowState() {
  const ring = shadowDemo.ring_min * 60, now = Date.now() / 1000, lines: any[] = [];
  for (const [job, question, ago] of SHADOW_DEMO) {
    const url = "https://example.com/" + job.split(" - ")[0].toLowerCase().replace(/\W+/g, "-");
    const call1 = shadowDemo.t0 / 1000 - ago + 15, p = shadowDemo.picked.get(url);
    const shadowAt = call1 + 2 * ring, iso = (t: number) => isoLocal(new Date(t * 1000));
    if (p) { lines.push({ url, job, question, state: `picked up by ${p.who}`, by: p.who, next_s: null, open: false, ts: iso(p.at) }); continue; }
    if (now < call1) continue;
    if (now >= shadowAt && shadowDemo.mode !== "off") { lines.push({ url, job, question, state: "picked up by shadow", by: "shadow", next_s: null, open: false, ts: iso(shadowAt) }); continue; }
    const second = now >= call1 + ring;
    lines.push({ url, job, question, state: second ? "call 2" : "call 1", by: null, open: true, ts: iso(now),
                 recommend: [{ q: question, a: DEMO_REC[question] ?? null, from: DEMO_REC[question] ? "Fact Bank draft" : "nothing on file" }],
                 next_s: Math.max(0, Math.round((second ? call1 + 2 * ring : call1 + ring) - now)) });
  }
  return { mode: shadowDemo.mode, ring_min: shadowDemo.ring_min, lines, ringing: lines.filter((l) => l.open).length,
           by_shadow: lines.filter((l) => l.by === "shadow").length, by_you: lines.filter((l) => l.by === "you").length,
           who: { applications: { "you:SUBMITTED": 4, "shadow:SUBMITTED": 6 + lines.filter((l) => l.by === "shadow").length, "engine:SUBMITTED": 17 },
                  answers: { you: 3, shadow: 9 } },
           memory: { known: 5, by_you: 1, entries: [
             { question: "Are you willing to relocate?", answer: "Yes", by: "you", used: 6, submitted: 5, overridden: 1 },
             { question: "How did you hear about this role?", answer: "Company website", by: "shadow", used: 9, submitted: 8, moved_forward: 1 },
             { question: "Desired Salary", answer: "Middle of the posted range", by: "shadow", used: 7, submitted: 6 },
             { question: "Have you used our product before?", answer: "No", by: "shadow", used: 3, submitted: 3 },
             { question: "In which year would you be available to begin?", answer: "2026", by: "shadow", used: 2, submitted: 1 },
           ] } };
}

// 11-07: Shadow's brain and agent graph on the public site: illustrative numbers in the shape of the real API
// (engine/shadow_brain.py brain(), engine/agents.py), so the panels can be seen without the engine.
function shadowBrainDemo() {
  const need = (k: string, want: number, have: number) => ({ need: k, want, have });
  const run = (p: number, c: number, i: number) => ({ ts: isoLocal(new Date(Date.now() - (6 - i) * 3600e3)), precision: p, coverage: c, baseline: 0.62 });
  const rungs = [
    { level: 0, name: "Observe", owns: "nothing: reads the ledger", needs: {}, missing: [], unlocked: true },
    { level: 1, name: "Answer", owns: "questions, as you (mode calls or autopilot), abstaining when unsure", needs: {}, missing: [], unlocked: true },
    { level: 2, name: "Job agents", owns: "retry, requeue and skip its own parked jobs", needs: {}, missing: [need("test_n", 20, 19), need("test_precision", 0.9, 0.8)], unlocked: false },
    { level: 3, name: "Applier agents", owns: "scale and balance appliers inside the gear's limits", needs: {}, missing: [need("test_n", 40, 19), need("test_precision", 0.95, 0.8), need("live_answers", 30, 12), need("shadow_submitted", 10, 4)], unlocked: false },
    { level: 4, name: "Service agents", owns: "restart and update the engine's containers", needs: {}, missing: [need("test_n", 60, 19), need("live_answers", 100, 12), need("clean_days", 7, 2)], unlocked: false },
    { level: 5, name: "Owner", owns: "create, update, delete, scale and balance every agent", needs: {}, missing: [need("test_n", 100, 19), need("live_answers", 300, 12), need("clean_days", 30, 2)], unlocked: false },
  ];
  const test = { n: 19, answered: 5, correct: 4, wrong: 1, abstained: 14, precision: 0.8, coverage: 0.263 };
  return { policy: { tau: 0.5, sigma: 0.85, trained: isoLocal(new Date()), live: {},
                     reliability: { bank: 0.84, memory: 0.75, neighbor: 0.41, engine: 0.36, yesno: 0.46 } },
           latest: { ts: isoLocal(new Date()), secs: 1.7, gold: 104, train: { ...test, n: 85 }, test, tau: 0.5, sigma: 0.85, violations: [],
                     baseline_test: { ...test, answered: 8, correct: 5, wrong: 3, abstained: 11, precision: 0.625, coverage: 0.421 },
                     reliability: {}, misses: [{ q: "how did you hear about us?", you: "LinkedIn", shadow: "Company careers page" }] },
           history: [run(0.5, 0.42, 0), run(0.6, 0.26, 1), run(0.8, 0.26, 2)],
           ladder: { level: 1, rungs, record: {} } };
}
function shadowAgentsDemo() {
  const q = (id: string, label: string, answer: string | null, conf: number) => ({ id, kind: "question", label, state: answer ? "answer ready" : "abstains (yours)", owner: "shadow", answer, conf, children: [] });
  const job = (id: string, label: string, state: string, owner: string, kids: any[]) => ({ id, kind: "job", label, state, owner, children: kids });
  const graph = { id: "shadow", kind: "shadow", label: "Shadow", state: "mode autopilot, level 1", owner: "you", children: [
    { id: "g:a", kind: "group", label: "Applier agents", state: "2 running", owner: "supervisor", children: [
      { id: "a1", kind: "applier", label: "applier 3fa91c", state: "applying", owner: "supervisor", children: [
        job("j1", "Robotics startup - Software Engineer", "applying", "engine", []), job("j2", "Fintech - Backend Engineer", "applying", "engine", [])] },
      { id: "a2", kind: "applier", label: "applier 9b07de", state: "watching", owner: "supervisor", children: [] }] },
    { id: "g:p", kind: "group", label: "Parked jobs", state: "2 on a call", owner: "shadow", children: [
      job("p1", "AI lab - ML Engineer", "call 1", "shadow", [q("q1", "Are you open to relocation?", "Yes", 0.92), q("q2", "Earliest start date?", "Immediately (2 weeks notice)", 0.88)]),
      job("p2", "Streaming platform - SWE I", "call 2", "shadow", [q("q3", "Describe your experience with our product", null, 0.31)])] },
    { id: "g:s", kind: "group", label: "Service agents", state: "6 services", owner: "supervisor", children:
      ["pipeline", "answers", "desk", "feedback", "ledger", "web"].map((n) => ({ id: `s:${n}`, kind: "service", label: n, state: "ok", owner: "supervisor", children: [] })) }] };
  return { graph, counts: { shadow: 1, group: 3, applier: 2, job: 4, question: 3, service: 6 },
           plan: [{ action: "retry", target: "AI lab - ML Engineer", why: "Shadow has a confident answer for every open question", needs_level: 2, allowed: false },
                  { action: "scale", target: "appliers 2 -> 3", why: "8 jobs waiting; memory used 2400 MB", needs_level: 3, allowed: false }] };
}

export async function proxyGet<T>(path: string): Promise<T> {
  if (path.split("?")[0] === "/api/shadow") return shadowState() as T;
  if (path.split("?")[0] === "/api/shadow/brain") return shadowBrainDemo() as T;
  if (path.split("?")[0] === "/api/shadow/agents") return shadowAgentsDemo() as T;
  const m = await getManifest();
  const u = new URL(path, "http://x");
  const by = Date.now() / 1000 - m.generated;
  if (u.pathname === "/api/job") {
    const f = m.jobs[u.searchParams.get("url") || ""];
    if (!f) throw new Error("/api/job: 404 (no events for that URL)");
    return rebase(await load("job/" + f), by);
  }
  const name = m.routes[u.pathname];
  if (!name) throw new Error(`${u.pathname}: not in the public demo`);
  let d = rebase(await load(name), by);
  const limit = Number(u.searchParams.get("limit") || 0);
  switch (u.pathname) {
    case "/api/applications": {
      const st = u.searchParams.get("status");
      d = d.filter((a: any) => !st || a.status === st);
      break;
    }
    case "/api/human":
      // an answer clears that question on every job that asked it; a job with nothing left goes back in line
      d = d.filter((h: any) => !(h.missing || []).length || (h.missing || []).some((q: string) => !overlay.answered.has(q)))
           .map((h: any) => ({ ...h, missing: (h.missing || []).filter((q: string) => !overlay.answered.has(q)) }));
      break;
    case "/api/narration":
      if (limit) d = d.slice(-limit);
      break;
    case "/api/control/state":
      d = { ...d, write: true, ...(overlay.run ? playRun(overlay.run) : { run: { ...d.run, running: true } }) };
      break;
    case "/api/control/filters":
      if (overlay.filters) d = overlay.filters;
      break;
    case "/api/control/gearbox":
      if (overlay.gear) {
        const g = overlay.gear.gear ?? d.gear.gear;
        d = { ...d, gear: { ...d.gear, ...overlay.gear, gear: g, label: d.gear.gears[g], appliers: GEAR_APPLIERS[g], loop_min: GEAR_LOOP[g] } };
      }
      if (d.governor) {  // the demo snapshot is from build time: keep it live, and follow a simulated shift
        const r = GEAR_APPLIERS[d.gear.gear] || [1, 7];
        const ceiling = Math.max(r[0], Math.min(d.governor.ceiling ?? r[1], r[1]));
        d = { ...d, governor: { ...d.governor, stale: false, gear_range: r, ceiling, running: Math.min(d.governor.running ?? 0, ceiling),
              target: Math.min(ceiling, d.governor.supply_wants ?? ceiling) } };
      }
      break;
    case "/api/control/reach":
      d = { ...d, write: true, rows: d.rows.map((r: any) => overlay.marks.has(r.url) ? { ...r, mark: overlay.marks.get(r.url)!.mark, marked: overlay.marks.get(r.url)!.ts } : r) };
      d.marks = d.rows.reduce((c: any, r: any) => ({ ...c, [r.mark]: (c[r.mark] || 0) + 1 }), {});
      break;
  }
  if (limit && Array.isArray(d)) d = d.slice(0, limit);
  return d as T;
}

// A run started here plays out on a clock: each step takes STEP seconds and writes the lines the real runner would.
const STEP = 6;
const LINES: Record<string, string[]> = {
  discover: ["discover: polling ~5,500 boards on 9 ATSs", "discover: 38 new postings in the window"],
  newgrad: ["newgrad: 11 leads resolved to the employer's own ATS"],
  feed: ["feed: 6 roles from curated GitHub lists, 2 already seen"],
  apply: ["fit gate: 21 of 55 pass (14 years, 9 sponsorship, 6 grad window, 5 stack)", "compose: 21 one-page resumes, median JD coverage 88%",
          "apply: 3 appliers x 4 tabs, round-robin", "apply: 15 submitted with proof, 4 need you, 2 stopped by the airbag"],
};
function playRun(run: any) {
  if (run.finished && !run.running) return { run, run_log: run.log || [] };
  const t = Date.now() / 1000, log: string[] = [];
  let done = true;
  const steps = run.steps.map((s: any, i: number) => {
    const start = run.started + i * STEP, end = start + STEP;
    if (t < start) { done = false; return { ...s, status: "waiting" }; }
    const lines = LINES[s.name] || [];
    log.push(...lines.slice(0, Math.max(1, Math.ceil(((Math.min(t, end) - start) / STEP) * lines.length))));
    if (t < end) { done = false; return { ...s, status: "running", started: start }; }
    return { ...s, status: "done", started: start, finished: end };
  });
  if (done) log.push("run finished: open Applications for the proof of each submit");
  return { run: { ...run, steps, running: !done, finished: done ? run.started + run.steps.length * STEP : null, log }, run_log: log };
}

// Writes are acted out in this tab: the page behaves the way it does on your machine, and a reload resets it.
const GEAR_APPLIERS: Record<string, number[]> = { N: [0, 0], "1": [1, 1], "2": [1, 3], "3": [1, 7], "4": [2, 9] };
const GEAR_LOOP: Record<string, number | null> = { N: null, "1": 10, "2": 5, "3": 3, "4": 2 };
export async function proxyPost<T>(path: string, body: any): Promise<T> {
  const p = path.split("?")[0];
  if (p === "/api/shadow/train") return shadowBrainDemo().latest as T;
  switch (p) {
    case "/api/control/gearbox":
      overlay.gear = { ...(overlay.gear || {}), ...(body.gear ? { gear: String(body.gear).toUpperCase() } : {}), ...(body.clutch ? { clutch: body.clutch } : {}) };
      return proxyGet<T>("/api/control/gearbox");
    case "/api/answers":
      overlay.answered.add(body.question);
      return { pattern: String(body.question).toLowerCase(), answer: body.answer, source: "web app (demo)" } as T;
    case "/api/control/retry":
      return { started: true, note: "Demo: a retry pass would start now for every answered job." } as T;
    case "/api/control/run": {
      const params = { ...(await proxyGet<any>("/api/control/state")).defaults, ...body };
      const t = Date.now() / 1000;
      overlay.run = { running: true, params, started: t, finished: null,
                      steps: ["discover", "newgrad", "feed", "apply"].filter((s) => s === "apply" || params[s] !== false)
                        .map((name, i) => ({ name, status: i === 0 ? "running" : "waiting", started: i === 0 ? t : undefined })) };
      return overlay.run as T;
    }
    case "/api/control/stop":
      overlay.run = { ...(overlay.run ? playRun(overlay.run).run : (await proxyGet<any>("/api/control/state")).run),
                      running: false, finished: Date.now() / 1000 };
      overlay.run.log = [...(overlay.run.log || []), "stopped by you"];
      return overlay.run as T;
    case "/api/control/filters": {
      const cur = await proxyGet<any>("/api/control/filters");
      const filters = { ...cur.filters, ...body };
      overlay.filters = { ...cur, filters, terms: Object.fromEntries(Object.entries(filters).map(([k, v]) => [k, String(v).split("|").filter(Boolean)])) };
      return overlay.filters as T;
    }
    case "/api/reach/mark":
      overlay.marks.set(body.url, { mark: body.mark, ts: nowIso() });
      return { ok: true, url: body.url, mark: body.mark, ts: nowIso() } as T;
    case "/api/reach/fill":
      return { ok: true, queued: body.url, desk: "up", open: "#" } as T;
    case "/api/reach/open":
      return { ok: true, opening: body.url } as T;
    case "/api/outreach/build":
      return proxyGet<T>("/api/outreach");
    case "/api/shadow":
      if (body.mode) shadowDemo.mode = body.mode;
      if (body.ring_min) shadowDemo.ring_min = Math.min(240, Math.max(0.5, Number(body.ring_min)));
      return shadowState() as T;
    case "/api/shadow/pickup":
      shadowDemo.picked.set(body.url, { who: body.who, at: Date.now() / 1000 });
      return { ok: true } as T;
  }
  throw new Error(`${p}: not available in the public demo`);
}

// Files the API serves (proof screenshots, resume PDFs) map to the dataset's copies.
export function proxyFile(path: string): string {
  const u = new URL(path, "http://x");
  const name = decodeURIComponent(u.pathname.split("/").pop() || "");
  if (u.pathname.startsWith("/api/proof/")) return BASE + "files/" + name.replace(/\.png$/i, ".svg");
  if (u.pathname.startsWith("/api/resume/")) return BASE + "files/" + name.replace(/\.pdf$/i, ".html");  // no PDFs in the repo
  return path;
}
