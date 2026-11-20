// Test drive for everyone, the Render site included: POST { text } -> the resume's profile (lane, years, level,
// keywords) and the 10 roles from a sample of public Greenhouse boards that fit it best by ATS match on each job
// description (lib/tryit.ts, the same rules as `python -m engine try`). Runs in this Next.js server, so it needs no
// Python API, database or Docker. Nothing is stored or logged: the resume text lives only for this request. One run per
// client per 30 s; the board listing is shared and cached for 10 minutes, job descriptions for an hour.
import { screenResume } from "@/lib/screen-input";
import { greenhouse, greenhouseJd, rank, sampleBoards, type Job } from "@/lib/tryit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const EVERY_MS = 30_000, CACHE_MS = 600_000, JD_MS = 3_600_000, MAX_CHARS = 50_000;
const hits = new Map<string, number>();
let cache: { at: number; jobs: Job[]; boards: number } = { at: 0, jobs: [], boards: 0 };
let loading: Promise<typeof cache> | null = null;
const jds = new Map<string, { at: number; html: string }>();

async function jobs() {
  if (Date.now() - cache.at < CACHE_MS && cache.jobs.length) return cache;
  loading ??= (async () => {  // one fetch at a time, however many visitors arrive together
    const lists = await Promise.all((await sampleBoards()).map((b) => greenhouse(b)));
    const all = lists.flat();
    if (all.length) cache = { at: Date.now(), jobs: all, boards: lists.filter((l) => l.length).length };
    return cache;
  })().finally(() => { loading = null; });
  return loading;
}

async function cachedJd(j: Job) {
  const hit = jds.get(j.url);
  if (hit && Date.now() - hit.at < JD_MS) return hit.html;
  const html = await greenhouseJd(j);
  if (html) jds.set(j.url, { at: Date.now(), html });
  if (jds.size > 2000) for (const [k, v] of jds) if (Date.now() - v.at > JD_MS) jds.delete(k);
  return html;
}

const err = (status: number, detail: string) => Response.json({ detail }, { status });

export async function POST(req: Request) {
  let text = "";
  try { text = String((await req.json())?.text ?? ""); } catch { return err(400, "send JSON: { \"text\": \"...\" }"); }
  if (!text.trim()) return err(400, "paste your resume text");
  if (text.length > MAX_CHARS) return err(413, `resume text over ${MAX_CHARS} characters`);
  const screened = screenResume(text);  // abuse, sensitive data, not a resume: refused before any work (and not logged)
  if (!screened.ok) return Response.json({ detail: screened.reason, kind: screened.kind }, { status: 422 });
  const who = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim() || req.headers.get("x-real-ip") || "local";
  const now = Date.now(), last = hits.get(who) ?? 0;
  if (now - last < EVERY_MS) return err(429, `one run every ${EVERY_MS / 1000} s; try again in ${Math.ceil((EVERY_MS - (now - last)) / 1000)} s`);
  hits.set(who, now);
  for (const [k, t] of hits) if (now - t > EVERY_MS) hits.delete(k);  // forget old clients: the table stays small

  const { jobs: list, boards } = await jobs();
  if (!list.length) return err(502, "the sample boards did not answer; try again in a minute");
  const out = await rank(list, text, cachedJd);
  return Response.json({ ...out, boards, postings: list.length, stored: false }, { headers: { "Cache-Control": "no-store" } });
}
