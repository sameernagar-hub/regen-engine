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

export async function proxyGet<T>(path: string): Promise<T> {
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
      d = { ...d, write: true, run: overlay.run ?? { ...d.run, running: true } };
      break;
    case "/api/control/filters":
      if (overlay.filters) d = overlay.filters;
      break;
    case "/api/control/reach":
      d = { ...d, write: true, rows: d.rows.map((r: any) => overlay.marks.has(r.url) ? { ...r, mark: overlay.marks.get(r.url)!.mark, marked: overlay.marks.get(r.url)!.ts } : r) };
      d.marks = d.rows.reduce((c: any, r: any) => ({ ...c, [r.mark]: (c[r.mark] || 0) + 1 }), {});
      break;
  }
  if (limit && Array.isArray(d)) d = d.slice(0, limit);
  return d as T;
}

// Writes are acted out in this tab: the page behaves the way it does on your machine, and a reload resets it.
export async function proxyPost<T>(path: string, body: any): Promise<T> {
  const p = path.split("?")[0];
  switch (p) {
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
      overlay.run = { ...(overlay.run || (await proxyGet<any>("/api/control/state")).run), running: false, finished: Date.now() / 1000 };
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
  }
  throw new Error(`${p}: not available in the public demo`);
}

// Files the API serves (proof screenshots, resume PDFs) map to the dataset's copies.
export function proxyFile(path: string): string {
  const u = new URL(path, "http://x");
  const name = decodeURIComponent(u.pathname.split("/").pop() || "");
  if (u.pathname.startsWith("/api/proof/")) return BASE + "files/" + name.replace(/\.png$/i, ".svg");
  if (u.pathname.startsWith("/api/resume/")) return BASE + "files/" + name;
  return path;
}
