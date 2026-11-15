// "Try it" for everyone, the Render site included: POST { text } -> the 10 best-fitting fresh roles from a sample of
// public Greenhouse boards, ranked by the same rules as `python -m engine try` (lib/tryit.ts). Runs in this Next.js
// server, so it needs no Python API, database or Docker. Nothing is stored or logged: the resume text lives only for
// this request. One try per client per 30 s; the board fetch is shared and cached for 10 minutes.
import { greenhouse, rank, sampleBoards, skills, type Job } from "@/lib/tryit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const EVERY_MS = 30_000, CACHE_MS = 600_000, MAX_CHARS = 50_000;
const hits = new Map<string, number>();
let cache: { at: number; jobs: Job[]; boards: number } = { at: 0, jobs: [], boards: 0 };
let loading: Promise<typeof cache> | null = null;

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

const err = (status: number, detail: string) => Response.json({ detail }, { status });

export async function POST(req: Request) {
  let text = "";
  try { text = String((await req.json())?.text ?? ""); } catch { return err(400, "send JSON: { \"text\": \"...\" }"); }
  if (!text.trim()) return err(400, "paste your resume text");
  if (text.length > MAX_CHARS) return err(413, `resume text over ${MAX_CHARS} characters`);
  const who = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim() || req.headers.get("x-real-ip") || "local";
  const now = Date.now(), last = hits.get(who) ?? 0;
  if (now - last < EVERY_MS) return err(429, `one try every ${EVERY_MS / 1000} s; wait ${Math.ceil((EVERY_MS - (now - last)) / 1000)} s`);
  hits.set(who, now);
  for (const [k, t] of hits) if (now - t > EVERY_MS) hits.delete(k);  // forget old clients: the table stays small

  const have = skills(text);
  const { jobs: list, boards } = await jobs();
  if (!list.length) return err(502, "the sample boards did not answer; try again in a minute");
  const { passed, blocked } = rank(list, have);
  return Response.json({
    skills: Object.fromEntries(Object.entries(have).map(([f, w]) => [f, w.slice(0, 4)])),
    boards, postings: list.length, passing: passed.length,
    top: passed.slice(0, 10).map(({ job: j, reason }) => ({ company: j.company, title: j.title, location: j.location, url: j.url, reason })),
    blocked, stored: false,
  }, { headers: { "Cache-Control": "no-store" } });
}
