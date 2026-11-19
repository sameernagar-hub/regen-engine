// Test drive for the web: a line-for-line port of engine/try_it.py. Read the resume like a recruiter (lane, years,
// level, keywords), keep only postings that fit that profile, fetch the shortlist's job descriptions and score each like
// an ATS (JD keywords the resume shares, years asked vs shown, freshness). Every rule comes from try-rules.json, which
// scripts/try_rules.py writes from the Python source (tests/test_try_rules.py fails when it is stale), so the CLI and the
// site rank the same way. Nothing here stores or logs the resume.
import R from "./try-rules.json";

export type Job = { company: string; title: string; location: string; posted: string | null; url: string };
export type Profile = { lanes: string[]; years: number; senior: boolean; student: boolean; keywords: string[] };
export type Ranked = { company: string; title: string; location: string; url: string; reason: string; match: number; matched: string[]; missing: string[] };
type P = Profile & { staff: boolean; people: boolean; low: string };

const LANES = Object.entries(R.lanes as Record<string, { title: string; resume: string }>);
// titleG counts the lane's title on a resume; resume_title narrows loose words ("software" in an employer's name)
const RT = (R.resume_title ?? {}) as Record<string, string>;
const LANE = Object.fromEntries(LANES.map(([k, v]) => [k, { title: new RegExp(v.title, "i"), resume: new RegExp(v.resume, "g"), titleG: new RegExp(RT[k] ?? v.title, "gi") }]));
const LEVELS = (R.levels as unknown as [string, string][]).map(([p, rule]) => [new RegExp(p), rule] as const);
const SPECIALTY = Object.entries(R.specialty as Record<string, string>).map(([w, need]) => [new RegExp(`\\b${w}\\b`, "i"), new RegExp(need)] as const);
const TERMS = Object.entries(R.terms as Record<string, string[]>).map(([name, ps]) => [name, new RegExp(ps.map((p) => `(?:${p})`).join("|"))] as const);
const STUDENT = new RegExp(R.student), BOILER = new RegExp(R.boilerplate);
const EXCLUDE_CO = new RegExp(R.exclude_companies, "i"), US_WORDS = new RegExp(R.us_words, "i"), NON_US = new RegExp(R.non_us, "i");
const NON_SOFTWARE = new RegExp(R.non_software, "i"), SOFTWARE_WORDS = new RegExp(R.software_words, "i");
const US_STATES = new Set(R.us_states);
const W = R.weights as { ats: number; fresh: number; lane: number };
const DAY = 86_400_000;

const unescape = (s: string) => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;|&#x27;/g, "'").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&");
export const plain = (t: string) => unescape(unescape(t || "")).replace(/<[^>]+>/g, " ").split(/\s+/).filter(Boolean).join(" ").toLowerCase();
const count = (rx: RegExp, s: string) => (s.match(rx) || []).length;

export function keywords(text: string, isPlain = false): Set<string> {
  const low = isPlain ? text : plain(text);
  return new Set(TERMS.filter(([, rx]) => rx.test(low)).map(([n]) => n));
}

function years(text: string): number {
  const low = text.toLowerCase();
  const said = [...low.matchAll(/(\d{1,2})\+?\s*(?:years|yrs)/g)].map((m) => +m[1]).filter((n) => n < 40);
  if (said.length) return Math.max(...said);
  const now = new Date().getFullYear();
  const starts = [...low.matchAll(/((?:19|20)\d\d)\s*(?:-|–|—|to)\s*((?:19|20)\d\d|present|current|now)/g)].map((m) => +m[1]);
  return starts.length ? Math.max(0, now - Math.min(...starts)) : 0;
}

export function profile(text: string): P {
  const low = plain(text);
  const score = Object.fromEntries(LANES.map(([k]) => [k, count(LANE[k].resume, low) + 2 * count(LANE[k].titleG, low)]));
  const best = Math.max(0, ...Object.values(score));
  const lanes = Object.entries(score).sort((a, b) => b[1] - a[1]).filter(([, s]) => s && s >= best * 0.5).map(([k]) => k).slice(0, 3);
  const y = years(text);
  return { lanes: lanes.length ? lanes : ["software"], years: y, senior: y >= 5 || /\bsenior\b|\bsr\.?\s/.test(low), student: STUDENT.test(low),
           keywords: [...keywords(low, true)].sort(), staff: y >= 8 || /\bstaff\b|\bprincipal\b/.test(low),
           people: /engineering manager|managed a team of|direct reports/.test(low), low };
}

function levelOk(title: string, p: P): string | null {
  const t = title.toLowerCase();
  for (const [rx, rule] of LEVELS) {
    if (!rx.test(t)) continue;
    if (rule === "student") return p.student ? null : "internship (resume is not a student's)";
    if (rule === "exec") return p.years < 12 ? "executive level" : null;
    if (rule === "staff") return p.staff ? null : "staff / principal level";
    if (rule === "people") return p.people ? null : "people-manager role";
    if (rule === "senior") return p.senior || p.years >= 4 ? null : "senior level";
    if (rule === "junior") return p.years <= 3 || (t.includes("associate") && t.includes("product") && p.years <= 5) ? null : "junior level";
  }
  return null;
}

function usLocation(loc: string): boolean {
  loc = (loc || "").trim();
  if (!loc) return true;
  if (US_WORDS.test(loc)) return true;
  if ([...loc.matchAll(/(?:,|\s-)\s*([A-Z]{2})\b/g)].some((m) => US_STATES.has(m[1]))) return true;
  if (NON_US.test(loc)) return false;
  return /remote|anywhere|distributed/i.test(loc);
}

const ageDays = (j: Job, now: number) => { const t = j.posted ? Date.parse(j.posted) : NaN; return Number.isNaN(t) ? null : Math.floor((now - t) / DAY); };

function gate(j: Job, p: P, now: number, days: number): string | null {
  const title = j.title || "", loc = j.location || "";
  const lanes = p.lanes.filter((l) => LANE[l].title.test(title));
  if (!lanes.length) return "different kind of role";
  if (lanes.length === 1 && lanes[0] === "software" && NON_SOFTWARE.test(title) && !SOFTWARE_WORDS.test(title)) return "different kind of role";
  const why = levelOk(title, p);
  if (why) return "level: " + why;
  for (const [word, need] of SPECIALTY) if (word.test(title) && !need.test(p.low)) return "specialty the resume doesn't show";
  const co = j.company || "";
  if (co && (EXCLUDE_CO.test(co) || EXCLUDE_CO.test(co.replace(/[\s_-]+/g, " ")))) return "company excluded (clearance / defense)";
  if (!usLocation(loc) || (NON_US.test(title) && !US_WORDS.test(title))) return "outside the US";
  const age = ageDays(j, now);
  if (age !== null && age > days) return `older than ${days} days`;
  return null;
}

function roleText(jd: string): string {
  const low = plain(jd), cut = Math.floor(low.length * 0.6);
  const m = low.slice(cut).search(BOILER);
  return m >= 0 ? low.slice(0, cut + m) : low;
}

function jdYears(low: string): number | null {
  const asks = [...low.matchAll(/(\d{1,2})\+?\s*(?:or more\s*)?(?:years|yrs)/g)].map((m) => +m[1]).filter((n) => n > 0 && n < 20);
  return asks.length ? Math.min(...asks) : null;
}

function score(j: Job, jd: string, p: P, now: number) {
  const low = roleText(jd), co = (j.company || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  let want = new Set(TERMS.filter(([n, rx]) => rx.test(low) && n.toLowerCase().replace(/[^a-z0-9]/g, "") !== co).map(([n]) => n));
  if (!want.size) want = keywords(j.title || "");
  const have = new Set(p.keywords);
  const matched = [...want].filter((k) => have.has(k)).sort(), missing = [...want].filter((k) => !have.has(k)).sort();
  const ats = want.size ? (matched.length / want.size) * (0.6 + 0.4 * Math.min(1, want.size / 10)) : 0;
  const age = ageDays(j, now), fresh = age === null ? 1 : Math.max(0, 1 - age / 30);
  const lane = LANE[p.lanes[0]].title.test(j.title || "") ? 1 : 0.6;
  const asks = jdYears(low);
  let s = W.ats * ats + W.fresh * fresh + W.lane * lane;
  if (asks !== null && asks > p.years + 1) s -= 0.15 * Math.min(3, asks - p.years - 1);
  if (/\bsenior\b|\bsr\.?\b/i.test(j.title || "") && p.years < 5) s -= 0.08;
  return { s, matched, missing, asks, age };
}

function reason(pct: number, matched: string[], missing: string[], asks: number | null, p: P, age: number | null) {
  let r = `ATS match ${pct}% (${matched.length} of ${matched.length + missing.length} JD keywords)`;
  if (matched.length) r += ": " + matched.slice(0, 6).join(", ");
  if (missing.length) r += "; missing " + missing.slice(0, 4).join(", ");
  if (asks !== null) r += `; asks ${asks}+ yrs, resume shows ${p.years}`;
  if (age !== null) r += `; posted ${age} d ago`;
  return r;
}

function shortlist(jobs: Job[], p: P, now: number, days: number, n = 36, perCompany = 3) {
  const blocked: Record<string, number> = {};
  const have = new Set(p.keywords), cand: { pre: number; posted: string; j: Job }[] = [];
  for (const j of jobs) {
    const why = gate(j, p, now, days);
    if (why) { blocked[why] = (blocked[why] || 0) + 1; continue; }
    const tk = keywords(j.title || ""), age = ageDays(j, now);
    const pre = [...tk].filter((k) => have.has(k)).length - 0.5 * [...tk].filter((k) => !have.has(k)).length + (age !== null && age <= 7 ? 1 : 0);
    cand.push({ pre, posted: j.posted || "", j });
  }
  cand.sort((a, b) => b.pre - a.pre || b.posted.localeCompare(a.posted));
  const out: Job[] = [], per: Record<string, number> = {};
  for (const { j } of cand) {
    if ((per[j.company] || 0) < perCompany) { out.push(j); per[j.company] = (per[j.company] || 0) + 1; }
    if (out.length >= n) break;
  }
  return { cands: out, blocked: Object.fromEntries(Object.entries(blocked).sort((a, b) => b[1] - a[1])), passing: cand.length };
}

/** The posting's description HTML from the public board API ("" when it fails). */
export async function greenhouseJd(j: Job): Promise<string> {
  const m = /greenhouse\.io\/([^/]+)\/jobs\/(\d+)/.exec(j.url || "");
  if (!m) return "";
  try {
    const r = await fetch(`https://boards-api.greenhouse.io/v1/boards/${m[1]}/jobs/${m[2]}`, { signal: AbortSignal.timeout(10_000), cache: "no-store" });
    return r.ok ? ((await r.json())?.content || "") : "";
  } catch { return ""; }
}

/** Everything the page needs: the profile, the ranked top roles with reasons, what the gate filtered and why. */
export async function rank(jobs: Job[], text: string, fetchJd = greenhouseJd, now = Date.now(), days: number = R.days, top = 10) {
  const p = profile(text);
  const { cands, blocked, passing } = shortlist(jobs, p, now, days);
  const jds = await Promise.all(cands.map((j) => fetchJd(j)));
  const ranked = cands.map((j, i) => {
    const { s, matched, missing, asks, age } = score(j, jds[i], p, now);
    const pct = Math.round((100 * matched.length) / Math.max(1, matched.length + missing.length));
    return { s, j, why: reason(pct, matched, missing, asks, p, age), pct, matched, missing };
  }).sort((a, b) => b.s - a.s);
  const per: Record<string, number> = {}, seen = new Set<string>(), best: typeof ranked = [];
  for (const r of ranked) {  // at most two roles per company, one per title (multi-city reposts)
    const key = `${r.j.company}|${r.j.title}`;
    if (seen.has(key)) continue;
    seen.add(key);
    if ((per[r.j.company] || 0) < 2) { best.push(r); per[r.j.company] = (per[r.j.company] || 0) + 1; }
    if (best.length >= top) break;
  }
  const prof: Profile = { lanes: p.lanes, years: p.years, senior: p.senior, student: p.student, keywords: p.keywords };
  return { profile: prof, passing, blocked, checked: cands.length,
           top: best.map(({ j, why, pct, matched, missing }) => ({ company: j.company, title: j.title, location: j.location, url: j.url, reason: why, match: pct, matched, missing })) as Ranked[] };
}

// The sample boards stay in engine/discovery/boards.example.txt only (the privacy gate's one allowed company list).
// Read it from the repo checkout (Render runs from a full clone with rootDir apps/web); a web image that ships only
// apps/web falls back to the same file on the public repo.
const BOARDS_RAW = `https://raw.githubusercontent.com/sameernagar-hub/regen-engine/main/${R.boards_file}`;
const parseBoards = (t: string) => t.split(",").map((x) => x.trim()).filter(Boolean).slice(0, R.boards_n);

export async function sampleBoards(): Promise<string[]> {
  try {
    const { readFile } = await import("node:fs/promises");
    const { join } = await import("node:path");
    const list = parseBoards(await readFile(join(/* turbopackIgnore: true */ process.cwd(), "..", "..", R.boards_file), "utf8"));
    if (list.length) return list;
  } catch { /* not in a full checkout: use the public copy */ }
  try {
    const r = await fetch(BOARDS_RAW, { signal: AbortSignal.timeout(8_000), cache: "no-store" });
    if (r.ok) return parseBoards(await r.text());
  } catch { /* fall through */ }
  return [];
}

/** One public Greenhouse board, normalized like engine/discovery/ats.py greenhouse(); [] when it fails. */
export async function greenhouse(token: string, timeoutMs = 12_000): Promise<Job[]> {
  try {
    const r = await fetch(`https://boards-api.greenhouse.io/v1/boards/${token}/jobs`, { signal: AbortSignal.timeout(timeoutMs), cache: "no-store" });
    if (!r.ok) return [];
    const d = await r.json();
    return (d?.jobs || []).map((j: any) => {
      const ts = j.first_published || j.updated_at;
      return { company: j.company_name || token, title: j.title, location: j.location?.name || "",
               posted: ts ? new Date(ts).toISOString() : null, url: `https://job-boards.greenhouse.io/${token}/jobs/${j.id}` };
    });
  } catch { return []; }
}
