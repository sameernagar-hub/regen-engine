// "Try it" quick start for the web: a line-for-line port of engine/try_it.py (skills, rank) and the default fit gate
// (engine/discovery/filters.py keep / us_location). The rules themselves come from try-rules.json, which
// scripts/try_rules.py writes from the Python source (tests/test_try_rules.py fails when it is stale), so the CLI and
// the site rank the same way. Pure functions: nothing here stores or logs the resume.
import R from "./try-rules.json";

export type Job = { company: string; title: string; location: string; posted: string | null; url: string };
export type Ranked = { company: string; title: string; location: string; url: string; reason: string };

const rx = (p: string, flags = "i") => new RegExp(p, flags);
const INCLUDE = rx(R.include_titles), EXCLUDE = rx(R.exclude_titles), EXCLUDE_CO = rx(R.exclude_companies);
const EXCLUDE_CO_SLUG = rx(R.exclude_companies.replaceAll(" ?", "").replaceAll(" ", ""));
const US_WORDS = rx(R.us_words), NON_US = rx(R.non_us), NON_SOFTWARE = rx(R.non_software);
const SOFTWARE_WORDS = rx(R.software_words), NOT_ENGINEERING = rx(R.not_engineering);
const US_STATES = new Set(R.us_states);
const FAMILIES = Object.entries(R.families as Record<string, { title: string; resume: string }>);

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

/** Families the resume shows, each with the words that showed it (sorted, lower case). */
export function skills(text: string): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const [fam, { resume }] of FAMILIES) {
    const hits = [...new Set([...text.matchAll(rx(resume, "gi"))].map((m) => m[0].toLowerCase()))].sort();
    if (hits.length) out[fam] = hits;
  }
  return out;
}

function usLocation(loc: string): boolean {
  loc = (loc || "").trim();
  if (!loc) return true;
  if (US_WORDS.test(loc)) return true;
  if ([...loc.matchAll(/(?:,|\s-)\s*([A-Z]{2})\b/g)].some((m) => US_STATES.has(m[1]))) return true;
  if (NON_US.test(loc)) return false;
  return /remote|anywhere|distributed/i.test(loc);
}

/** null when the job passes the default fit gate, else the short reason it was dropped. */
export function keep(title: string, location: string, company = ""): string | null {
  if (!INCLUDE.test(title)) return "title";
  if (EXCLUDE.test(title)) return "level/title excluded";
  if (NON_SOFTWARE.test(title) && !SOFTWARE_WORDS.test(title)) return "non-software discipline";
  if (NOT_ENGINEERING.test(title)) return "non-engineering role";
  if (company && (EXCLUDE_CO.test(company) || EXCLUDE_CO.test(company.replace(/[\s_-]+/g, " "))
                  || EXCLUDE_CO_SLUG.test(company.replace(/[\s_-]+/g, "")))) return "company excluded";
  if (R.require_us && (!usLocation(location) || (NON_US.test(title) && !US_WORDS.test(title)))) return "non-US";
  return null;
}

/** Best fits first, with the reason each passed; blocked = how many each gate reason dropped. */
export function rank(jobs: Job[], have: Record<string, string[]>, now = Date.now(), days = 14) {
  const passed: { score: number; job: Job; reason: string }[] = [];
  const blocked: Record<string, number> = {};
  for (const j of jobs) {
    let why = keep(j.title || "", j.location || "", j.company || "");
    const t = j.posted ? Date.parse(j.posted) : NaN;
    const age = Number.isNaN(t) ? null : Math.floor((now - t) / 86_400_000);
    if (why === null && age !== null && age > days) why = `older than ${days} days`;
    const fams = FAMILIES.filter(([, f]) => rx(f.title).test(j.title || "")).map(([k]) => k);
    const match = fams.filter((f) => f in have);
    if (why === null && fams.length && !match.length) why = "resume does not show this role's skills";
    if (why) { blocked[why] = (blocked[why] || 0) + 1; continue; }
    const score = 2 * match.length + (age !== null && age <= 3 ? 1 : 0);
    let reason = match.length ? "matches " + match.map((f) => `${f} (${have[f].slice(0, 3).join(", ")})`).join("; ")
      : "passes the gate (general software title)";
    if (age !== null) reason += `; posted ${age} d ago`;
    passed.push({ score, job: j, reason });
  }
  passed.sort((a, b) => b.score - a.score || (b.job.posted || "").localeCompare(a.job.posted || ""));
  const sortedBlocked = Object.fromEntries(Object.entries(blocked).sort((a, b) => b[1] - a[1]));
  return { passed, blocked: sortedBlocked };
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
