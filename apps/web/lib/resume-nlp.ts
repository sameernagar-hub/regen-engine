// The resume classifier for the web: a line-for-line port of engine/resume_nlp.py (read that file's docstring for the
// method). Data (families, stopwords, aliases, sections, weights) comes from try-rules.json, which scripts/try_rules.py
// writes from the Python source; tests/test_resume_nlp.py runs this file through node on the same corpus and fails on
// any difference. Pure functions, no I/O: the Test drive and the pipeline page run it in the browser, step by step.
import R from "./try-rules.json";

type Fam = { titles: string[]; terms: string[] };
const D = R.nlp as unknown as {
  families: Record<string, Fam>; stop: string[]; keep: string[]; aliases: Record<string, string>;
  sections: Record<string, string[]>; section_w: Record<string, number>; title_w: Record<string, number>;
  recency: number[]; min_evidence: number; secondary: number; blend: number; max_n: number; header_lines: number;
  bullet: string; date_range: string; months: string; segment: string; cues: Record<string, string[]>;
};
export const FAMILIES = Object.keys(D.families);
const STOP = new Set(D.stop), KEEP = new Set(D.keep);
const BULLET = new RegExp(D.bullet), DATE_RANGE = new RegExp(D.date_range, "i"), SEGMENT = new RegExp(D.segment);
const DATES_ONLY = new RegExp(`${D.date_range}|${D.months}`, "gi");

export function fold(text: string): string {
  let t = (text || "").normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();
  t = t.replace(/’/g, "'").replace(/‘/g, "'");
  t = t.replace(/c\+\+/g, " c plus plus ");
  t = t.replace(/(?<![a-z])c#/g, " c sharp ");
  t = t.replace(/(?<![a-z])f#/g, " f sharp ");
  t = t.replace(/\.net\b/g, " dot net ");
  t = t.replace(/\b([a-z]+)\.js\b/g, " $1 js ");
  t = t.replace(/\bci\s*\/\s*cd\b/g, " ci cd ");
  t = t.replace(/\ba\s*\/\s*b\b/g, " ab ");
  t = t.replace(/\bp\s*&\s*l\b/g, " pnl ");
  t = t.replace(/\bfp\s*&\s*a\b/g, " fp a ");
  t = t.replace(/\bpresident'?s\b/g, " president ");
  return t;
}

export function stem(w: string): string {
  if (KEEP.has(w) || [...w].length <= 3 || !/^\p{L}+$/u.test(w)) return w;
  if (w.endsWith("sses")) w = w.slice(0, -2);
  else if (w.endsWith("ies") && w.length > 4) w = w.slice(0, -3) + "y";
  else if (w.endsWith("s") && !(w.endsWith("ss") || w.endsWith("us") || w.endsWith("is"))) w = w.slice(0, -1);
  for (const suf of ["ing", "ed"]) {
    if (w.endsWith(suf) && w.length - suf.length >= 3 && /[aeiouy]/.test(w.slice(0, -suf.length))) { w = w.slice(0, -suf.length); break; }
  }
  if (w.endsWith("e") && w.length > 4) w = w.slice(0, -1);
  return w;
}

type Stats = { raw?: number; stopwords?: number; aliases?: number };
export function tokens(text: string, stats?: Stats): string[] {
  const raw = fold(text).split(/[^a-z0-9+#&]+/).filter(Boolean);
  const out: string[] = [];
  for (let t of raw) {
    t = t.replace(/^&+|&+$/g, "");
    if (!t || /^\d+$/.test(t)) continue;
    const al = D.aliases[t];
    const words = (al ?? t).split(/\s+/).filter(Boolean);
    if (stats && al !== undefined && al !== t) stats.aliases = (stats.aliases || 0) + 1;
    for (const w of words) {
      if (STOP.has(w) || (w.length === 1 && w !== "c" && w !== "r")) { if (stats) stats.stopwords = (stats.stopwords || 0) + 1; continue; }
      out.push(stem(w));
    }
  }
  if (stats) stats.raw = (stats.raw || 0) + raw.length;
  return out;
}

const phraseKey = (p: string) => tokens(p).join(" ");

export type Norm = { raw: string; out: string[]; why: "stopword" | "alias" | "stem" | "kept" | "number" };
/** For the pipeline view only: what step 2 did to each raw token, in order (same rules as tokens()). */
export function normalizeTrace(text: string, limit = 400): Norm[] {
  const res: Norm[] = [];
  for (let t of fold(text).split(/[^a-z0-9+#&]+/).filter(Boolean)) {
    if (res.length >= limit) break;
    t = t.replace(/^&+|&+$/g, "");
    if (!t) continue;
    if (/^\d+$/.test(t)) { res.push({ raw: t, out: [], why: "number" }); continue; }
    const al = D.aliases[t];
    const ws = (al ?? t).split(/\s+/).filter(Boolean).filter((w) => !(STOP.has(w) || (w.length === 1 && w !== "c" && w !== "r")));
    const out = ws.map(stem);
    const why = al !== undefined && al !== t ? "alias" : !out.length ? "stopword" : out[0] !== t ? "stem" : "kept";
    res.push({ raw: t, out, why });
  }
  return res;
}
export const rawTokens = (text: string) => fold(text).split(/[^a-z0-9+#&]+/).filter(Boolean);

type Hit = [string, "titles" | "terms"];
const INDEX = new Map<string, Hit[]>();
for (const [fam, d] of Object.entries(D.families)) {
  for (const kind of ["titles", "terms"] as const) {
    for (const p of d[kind]) {
      const k = phraseKey(p);
      if (!k) continue;
      const v = INDEX.get(k) ?? [];
      if (!v.some(([f, kk]) => f === fam && kk === kind)) v.push([fam, kind]);
      INDEX.set(k, v);
    }
  }
}
const SPEC = new Map<string, number>([...INDEX].map(([k, v]) => [k, 1 / new Set(v.map(([f]) => f)).size]));
const CENTROID: Record<string, Map<string, number>> = Object.fromEntries(FAMILIES.map((f) => [f, new Map<string, number>()]));
for (const [k, v] of INDEX) for (const [f, kind] of v) {
  const w = (kind === "titles" ? D.title_w.title : 1) * SPEC.get(k)!;
  CENTROID[f].set(k, Math.max(CENTROID[f].get(k) ?? 0, w));
}

export function match(toks: string[]): [string, Hit[]][] {
  const out: [string, Hit[]][] = [];
  let i = 0;
  const n = toks.length;
  while (i < n) {
    let hit = false;
    for (let size = Math.min(D.max_n, n - i); size > 0; size--) {
      const k = toks.slice(i, i + size).join(" ");
      const h = INDEX.get(k);
      if (h) { out.push([k, h]); i += size; hit = true; break; }
    }
    if (!hit) i += 1;
  }
  return out;
}

const words = (s: string) => s.trim().split(/\s+/).filter(Boolean);

export function sectionOf(line: string): string | null {
  const t = words(fold(line).replace(/[^a-z& ]+/g, " ").replace(/&/g, " and ")).join(" ");
  if (!t || words(t).length > 5) return null;
  for (const [sec, names] of Object.entries(D.sections)) {
    for (const name of names) {
      if (t === name || (t.startsWith(name + " ") && words(t).length <= words(name).length + 2)) return sec;
    }
  }
  return null;
}

export function splitLines(text: string): string[] {
  let lines = (text || "").split(/\r?\n/).filter((l) => l.trim());
  if (lines.length < 4) lines = lines.flatMap((part) => part.split(/\s+(?=[•▪◦‣]\s)|\s+(?=\*\s)|\s+(?=-\s[A-Z])/)).filter((l) => l && l.trim());
  return lines;
}

function roleTitle(line: string, section: string): string[] | null {
  if (BULLET.test(line) || !["experience", "body", "header", "projects", "volunteer"].includes(section)) return null;
  const w = words(line);
  if (w.length > 16 || (/[.;]$/.test(line.trimEnd()) && !DATE_RANGE.test(line))) return null;
  if (!/[a-z]{3,}/.test(fold(line).replace(DATES_ONLY, " "))) return null;  // a dates-only line is not another role
  const segs = line.trim().split(SEGMENT).filter((s) => s && s.trim());
  if (section === "header") return segs;
  if (segs.length >= 2 || DATE_RANGE.test(line) || w.length <= 6) return segs.length ? [segs[0]] : null;
  return null;
}

export type Score = { family: string; p: number; evidence: string[] };
export type Steps = { tokens: number; stopwords: number; aliases: number; terms: number; vocabulary: number; sample: string[];
  lines: number; sections: string[]; roles: number; phrases: number; top_features: string[]; scores: Score[] };
export type LineTrace = { line: string; section: string; kind: "header" | "role" | "text"; tokens: string[]; hits: { phrase: string; families: string[]; title: boolean }[] };
export type Analysis = { label: string; labels: string[]; confidence: number; level: "high" | "medium" | "low" | "none";
  hybrid: boolean; evidence_total: number; steps?: Steps; trace?: LineTrace[] };

const r3 = (x: number) => Math.round(x * 1000) / 1000;
const byScore = (a: [string, number], b: [string, number]) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0);

/** The whole pipeline on one resume. trace = what each line contributed (the pipeline page plays it back). */
export function analyze(text: string, explain = true, trace = false): Analysis {
  const stats: Stats = {}, lines = splitLines(text);
  let section = "header", roleI = -1;
  const secSeen: string[] = [], feats = new Map<string, number>(), traces: LineTrace[] = [];
  const famS: Record<string, number> = Object.fromEntries(FAMILIES.map((f) => [f, 0]));
  const evidence: Record<string, Map<string, number>> = Object.fromEntries(FAMILIES.map((f) => [f, new Map<string, number>()]));
  let allToks = 0;
  const add = (k: string, hits: Hit[], where: "title" | "summary" | "mention") => {
    const rec = D.recency[Math.min(Math.max(roleI, 0), D.recency.length - 1)];
    for (const [fam, kind] of hits) {
      const ww = kind === "titles" ? (where === "mention" ? D.title_w.mention : D.title_w[where] * rec) : (D.section_w[section] ?? 1) * rec;
      if (ww <= 0) continue;
      const s = SPEC.get(k)!;
      famS[fam] += ww * s;
      feats.set(k, (feats.get(k) ?? 0) + ww);
      evidence[fam].set(k, (evidence[fam].get(k) ?? 0) + ww * s);
    }
  };
  lines.forEach((line, li) => {
    if (section === "header" && li >= D.header_lines) section = "body";
    const sec = sectionOf(line);
    if (sec) {
      section = sec;
      if (!secSeen.includes(sec)) secSeen.push(sec);
      if (trace) traces.push({ line, section, kind: "header", tokens: [], hits: [] });
      return;
    }
    const titleSegs = roleTitle(line, section);
    const toks = tokens(line, stats);
    allToks += toks.length;
    if (titleSegs && titleSegs.length && (section === "experience" || section === "body")) roleI += 1;
    const tr: LineTrace = { line, section, kind: titleSegs && titleSegs.length ? "role" : "text", tokens: toks, hits: [] };
    if (titleSegs && titleSegs.length) {
      for (const seg of titleSegs) for (const [k, hits] of match(tokens(seg))) {
        add(k, hits, "title");
        tr.hits.push({ phrase: k, families: hits.map(([f]) => f), title: hits.some(([, kind]) => kind === "titles") });
      }
    } else {
      const where = section === "summary" ? "summary" : "mention";
      for (const [k, hits] of match(toks)) {
        add(k, hits, where);
        tr.hits.push({ phrase: k, families: hits.map(([f]) => f), title: hits.some(([, kind]) => kind === "titles") });
      }
    }
    if (trace) traces.push(tr);
  });

  const total = Object.values(famS).reduce((a, b) => a + b, 0);
  const norm = Math.sqrt([...feats.values()].reduce((a, v) => a + v * v, 0)) || 1;
  const cos: Record<string, number> = {};
  for (const f of FAMILIES) {
    const c = CENTROID[f];
    const cn = Math.sqrt([...c.values()].reduce((a, v) => a + v * v, 0)) || 1;
    let dot = 0;
    for (const [k, v] of c) dot += (feats.get(k) ?? 0) * v;
    cos[f] = dot / (norm * cn);
  }
  const cosSum = Object.values(cos).reduce((a, b) => a + b, 0) || 1;
  const final: [string, number][] = FAMILIES.map((f) => [f, D.blend * (total ? famS[f] / total : 0) + (1 - D.blend) * cos[f] / cosSum]);
  const ranked = [...final].sort(byScore);
  let labels: string[] = [], conf = 0;
  if (total >= D.min_evidence) {
    const top = ranked[0][1];
    labels = ranked.filter(([, s]) => s >= top * D.secondary && s >= 0.12).map(([f]) => f).slice(0, 3);
    conf = top;
  }
  const second = ranked.length > 1 ? ranked[1][1] : 0;
  const level = !labels.length ? "none" : conf >= 0.5 && conf - second >= 0.25 ? "high" : conf >= 0.3 ? "medium" : "low";
  const out: Analysis = { label: labels[0] ?? "unclassified", labels, confidence: r3(conf), level, hybrid: labels.length > 1,
                          evidence_total: Math.round(total * 100) / 100 };
  if (explain) {
    const uniq = [...new Set(tokens(text))].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
    out.steps = {
      tokens: stats.raw ?? 0, stopwords: stats.stopwords ?? 0, aliases: stats.aliases ?? 0, terms: allToks,
      vocabulary: uniq.length, sample: uniq.slice(0, 24), lines: lines.length, sections: secSeen, roles: Math.max(roleI + 1, 0),
      phrases: feats.size, top_features: [...feats.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([k]) => k),
      scores: ranked.slice(0, 6).filter(([, s]) => s > 0).map(([f, s]) => ({ family: f, p: r3(s),
        evidence: [...evidence[f].entries()].sort((a, b) => b[1] - a[1]).slice(0, 5).map(([k]) => k) })),
    };
  }
  if (trace) out.trace = traces;
  return out;
}

// Back-off for titles that name no full role: their domain words decide (same as CUES in the Python source).
const CUE_INDEX = new Map<string, string[]>();
for (const [fam, ws] of Object.entries(D.cues)) for (const w of ws) {
  const k = phraseKey(w);
  if (!k) continue;
  const v = CUE_INDEX.get(k) ?? [];
  if (!v.includes(fam)) v.push(fam);
  CUE_INDEX.set(k, v);
}
for (const [k, v] of CUE_INDEX) CUE_INDEX.set(k, [...v].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0)));
const CUE_N = Math.max(1, ...[...CUE_INDEX.keys()].map((k) => k.split(" ").length));

/** A posting title -> the families it belongs to. */
export function classifyTitle(title: string): string[] {
  const s = new Map<string, number>();
  const toks = tokens(title);
  let foundTitle = false;
  for (const [k, hits] of match(toks)) for (const [fam, kind] of hits) {
    s.set(fam, (s.get(fam) ?? 0) + (kind === "titles" ? D.title_w.title : 1) * SPEC.get(k)!);
    foundTitle = foundTitle || kind === "titles";
  }
  if (!foundTitle) {
    let i = 0;
    const n = toks.length;
    while (i < n) {
      let hit = false;
      for (let size = Math.min(CUE_N, n - i); size > 0; size--) {
        const fams = CUE_INDEX.get(toks.slice(i, i + size).join(" "));
        if (fams) { for (const f of fams) s.set(f, (s.get(f) ?? 0) + 1 / fams.length); i += size; hit = true; break; }
      }
      if (!hit) i += 1;
    }
  }
  if (!s.size) return [];
  const top = Math.max(...s.values());
  return [...s.entries()].sort(byScore).filter(([, v]) => v >= top * 0.5 && v >= 0.5).map(([f]) => f);
}
