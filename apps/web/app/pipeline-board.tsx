"use client";
// The pipeline board: one connected component for the whole run. A rail of stages (read the resume in six steps, then
// search the live boards in three, then the two stages only a real run uses) with a live wire between them, and a
// detail panel that opens ANY stage's full output: every token, every normalization, every role line, every phrase,
// every family score, every filtered reason, every ranked role. Nothing is cut to "+300 more": long lists scroll and
// filter. The board follows the run until you click a stage; "Follow live" hands control back.
// The read steps are lib/resume-nlp.ts in the browser (the same code the server and `python -m engine try` run); the
// search stages show POST /api/public/try. Reduced motion: every stage lands at once.
import { useEffect, useMemo, useRef, useState } from "react";
import { analyze, normalizeTrace, rawTokens, FAMILIES, type Analysis } from "@/lib/resume-nlp";
import type { TryOut } from "./try-box";

export const famColor = (f: string) => {
  const i = Math.max(0, FAMILIES.indexOf(f));
  return `hsl(${Math.round((i * 360) / Math.max(1, FAMILIES.length) + 205) % 360} 78% 66%)`;
};

type Stage = { key: string; name: string; group: "read" | "search" | "real"; tone: string; does: string };
export const STEPS: Stage[] = [
  { key: "tokenize", name: "Tokenize", group: "read", tone: "#6fb7ff",
    does: "Splits the text into words. Tech names survive intact, so C++, C# and Node.js stay themselves instead of turning into punctuation." },
  { key: "normalize", name: "Normalize", group: "read", tone: "#7dd3fc",
    does: "Expands shorthand (k8s → kubernetes, SDR → sales development representative), drops filler words, and folds word forms together (engineering → engineer)." },
  { key: "structure", name: "Structure", group: "read", tone: "#a78bfa",
    does: "Finds the sections and the role lines. Only the job title on a role line counts: a salesperson at a software company is still a salesperson. Your newest role weighs most." },
  { key: "features", name: "Features", group: "read", tone: "#ff7eb6",
    does: "Matches the vocabulary of 25 role families, longest phrase first, so “sales engineer” is one thing, not “sales” plus “engineer”. A title weighs 3×, a skill 1×." },
  { key: "classify", name: "Classify", group: "read", tone: "#ff9f43",
    does: "Scores every family. Rare phrases count more than common ones, blended 70/30 with how close the whole resume sits to each family’s centre." },
  { key: "label", name: "Label", group: "read", tone: "#f2c14e",
    does: "Picks the top family. A close second makes you a hybrid. Too little evidence and it says “unclassified” rather than guess." },
];
const SEARCH: Stage[] = [
  { key: "discover", name: "Discover", group: "search", tone: "#6fb7ff",
    does: "Pulls every open posting from 40 public company job boards, right now. Nothing cached from last week." },
  { key: "gate", name: "Fit gate", group: "search", tone: "#ff9f43",
    does: "Throws out what doesn’t fit: a different kind of role, the wrong level, outside the US, or older than a month. Most postings die here, on purpose." },
  { key: "rank", name: "Rank", group: "search", tone: "#5ee6b5",
    does: "Reads the job description of every survivor and scores it the way an applicant tracking system would: which keywords the job asks for that your resume actually has." },
];
const REAL: Stage[] = [
  { key: "apply", name: "Apply", group: "real", tone: "#ff7eb6",
    does: "In a real run: fills each application in a real browser from your Fact Bank and keeps a receipt. Questions it can’t answer truthfully wait for you." },
  { key: "inbox", name: "Inbox", group: "real", tone: "#a78bfa",
    does: "In a real run: reads the replies, sorts interviews from rejections, and uses every rejection to tighten the fit gate." },
];

export type Search = { busy: boolean; out: TryOut | null; err: string };
type Props = { text: string; runId: number; search?: Search; onDone?: (a: Analysis) => void; pace?: number };

export function PipelineBoard({ text, runId, search, onDone, pace = 900 }: Props) {
  const stages = useMemo(() => (search ? [...STEPS, ...SEARCH, ...REAL] : STEPS), [!!search]);  // eslint-disable-line react-hooks/exhaustive-deps
  const runnable = search ? STEPS.length + SEARCH.length : STEPS.length;
  const [step, setStep] = useState(-1);      // stage being worked on; runnable = finished
  const [sel, setSel] = useState<number | null>(null);  // null = follow the run
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const reduce = useRef(false);
  const data = useMemo(() => {
    if (!runId || !text.trim()) return null;
    return { a: analyze(text, true, true), raw: rawTokens(text), norm: normalizeTrace(text, 20000) };
  }, [runId]);  // eslint-disable-line react-hooks/exhaustive-deps
  const clear = () => { timers.current.forEach(clearTimeout); timers.current = []; };

  // the read steps run on a clock
  useEffect(() => {
    clear(); setSel(null);
    if (!data) { setStep(-1); return; }
    reduce.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce.current) { setStep(STEPS.length); onDone?.(data.a); return; }
    setStep(0);
    STEPS.forEach((_, i) => timers.current.push(setTimeout(() => setStep(i + 1), pace * (i + 1))));
    timers.current.push(setTimeout(() => onDone?.(data.a), pace * STEPS.length));
    return clear;
  }, [data]);  // eslint-disable-line react-hooks/exhaustive-deps

  // the search stages wait for the server, then land one after another
  const out = search?.out ?? null;
  useEffect(() => {
    if (!search || step < STEPS.length || step >= runnable || !out) return;
    const t = setTimeout(() => setStep((s) => s + 1), reduce.current ? 0 : 650);
    return () => clearTimeout(t);
  }, [step, out]);  // eslint-disable-line react-hooks/exhaustive-deps

  const failed = !!search?.err && !out && step >= STEPS.length;
  const state = (i: number) => {
    if (i >= runnable) return step >= runnable ? "ghost done" : "ghost";
    if (step > i) return "done";
    if (step === i) return failed ? "error" : "on";
    return "wait";
  };
  const live = step < 0 ? 0 : Math.min(step, runnable - 1);
  const open = sel ?? live;
  const cur = stages[open];
  const pct = step < 0 ? 0 : Math.min(100, (step / runnable) * 100);

  return (
    <div className={`pb${step >= 0 && step < runnable ? " running" : ""}${step >= runnable ? " finished" : ""}`}>
      <div className="pb-railwrap">
        <div className="pb-groups" aria-hidden>
          <span style={{ ["--span" as any]: STEPS.length }}>Read your resume</span>
          {search && <span style={{ ["--span" as any]: SEARCH.length }}>Search live boards</span>}
          {search && <span className="real" style={{ ["--span" as any]: REAL.length }}>Real runs only</span>}
        </div>
        <ol className="pb-rail" role="tablist" aria-label="Pipeline stages" style={{ ["--n" as any]: stages.length }}>
          <span className="pb-wire" aria-hidden><i style={{ width: `${pct}%` }} /></span>
          {stages.map((st, i) => {
            const s = state(i);
            return (
              <li key={st.key} className={`pb-node ${s}${open === i ? " open" : ""}`} style={{ ["--tone" as any]: st.tone, ["--i" as any]: i }}>
                <button type="button" role="tab" aria-selected={open === i} aria-controls="pb-panel" onClick={() => setSel(i)}>
                  <span className="orb" aria-hidden><b>{s === "done" ? "✓" : i + 1}</b></span>
                  <span className="nm">{st.name}</span>
                  <span className="mt">{metric(i, st.key)}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </div>

      <div id="pb-panel" role="tabpanel" className={`pb-panel ${state(open)}`} style={{ ["--tone" as any]: cur.tone }} key={cur.key}>
        <header>
          <div>
            <p className="pb-kicker">{cur.group === "read" ? "Read" : cur.group === "search" ? "Search" : "Real runs only"} · stage {open + 1} of {stages.length}</p>
            <h3>{cur.name}</h3>
          </div>
          <div className="pb-nav">
            {sel !== null && step >= 0 && step < runnable && <button type="button" className="pb-follow" onClick={() => setSel(null)}>Follow live</button>}
            <button type="button" aria-label="Previous stage" disabled={open === 0} onClick={() => setSel(Math.max(0, open - 1))}>←</button>
            <button type="button" aria-label="Next stage" disabled={open === stages.length - 1} onClick={() => setSel(Math.min(stages.length - 1, open + 1))}>→</button>
          </div>
        </header>
        <p className="pb-does">{cur.does}</p>
        <div className="pb-body">{body(open, cur.key)}</div>
      </div>
    </div>
  );

  function metric(i: number, key: string): string {
    const s = state(i);
    if (s === "ghost") return "not on a test drive";
    if (s === "ghost done") return "skipped: nothing sent";
    if (s === "wait") return step < 0 ? "ready" : "queued";
    if (s === "error") return "stalled";
    if (!data) return "";
    const { a, raw } = data, x = a.steps!;
    if (key === "tokenize") return `${raw.length.toLocaleString()} tokens`;
    if (key === "normalize") return `${x.terms.toLocaleString()} terms`;
    if (key === "structure") return `${x.roles} role${x.roles === 1 ? "" : "s"}`;
    if (key === "features") return `${x.phrases} phrases`;
    if (key === "classify") return x.scores[0] ? `${x.scores[0].family} ${Math.round(x.scores[0].p * 100)}%` : "no evidence";
    if (key === "label") return a.labels.length ? a.label : "unclassified";
    if (s === "on") return key === "discover" ? "pulling boards…" : "working…";
    if (!out) return "";
    if (key === "discover") return `${out.postings.toLocaleString()} postings`;
    if (key === "gate") return `${out.passing.toLocaleString()} survive`;
    if (key === "rank") return out.top[0] ? `best ${out.top[0].match}%` : "no match";
    return "";
  }

  function body(i: number, key: string) {
    const s = state(i);
    if (s === "ghost" || s === "ghost done") return <p className="pb-empty">A test drive never applies anywhere and never sends anything. Start the engine for real and this stage runs for every job that made it through Rank.</p>;
    if (!data || s === "wait") return <p className="pb-empty">{data ? "Queued: this stage runs as soon as the one before it finishes." : "Waiting for a resume. Paste one above, or try the sample, and this panel fills with the real output."}</p>;
    if (s === "error") return <p className="pb-empty err">{search?.err || "The search stalled."} The resume reading above still stands; try again in a minute.</p>;
    const { a, raw, norm } = data, x = a.steps!, trace = a.trace || [];
    if (key === "tokenize") return <ChipList items={raw.map((t) => ({ id: t, label: t }))} unit="tokens" tone="#6fb7ff" highlightSame />;
    if (key === "normalize") {
      const changed = norm.filter((n) => n.why !== "kept" && n.why !== "number");
      return <ChipList unit="changes" tone="#7dd3fc"
        filters={[["alias", "expanded"], ["stem", "stemmed"], ["stopword", "dropped"]]}
        items={changed.map((n) => ({ id: n.raw, kind: n.why, label: <><s>{n.raw}</s>{n.out.length ? <> → <b>{n.out.join(" ")}</b></> : null}</> }))} />;
    }
    if (key === "structure") return <Structure trace={trace} sections={x.sections} lines={x.lines} />;
    if (key === "features") {
      const seen = new Map<string, { phrase: string; families: string[]; title: boolean; n: number }>();
      for (const t of trace) for (const h of t.hits) {
        const e = seen.get(h.phrase);
        if (e) { e.n++; e.title ||= h.title && t.kind === "role"; } else seen.set(h.phrase, { ...h, title: h.title && t.kind === "role", n: 1 });
      }
      const all = [...seen.values()].sort((p, q) => Number(q.title) - Number(p.title) || q.n - p.n);
      const fams = [...new Set(all.flatMap((h) => h.families))].sort((p, q) => all.filter((h) => h.families.includes(q)).length - all.filter((h) => h.families.includes(p)).length);
      return <ChipList unit="phrases" tone="#ff7eb6" filters={fams.map((f) => [f, f, famColor(f)])}
        items={all.map((h) => ({ id: h.phrase, kind: h.families, color: famColor(h.families[0]), strong: h.title,
          label: <>{h.phrase}{h.n > 1 && <sup>×{h.n}</sup>}</>, title: `${h.families.join(", ")}${h.title ? " · job title" : ""}` }))} />;
    }
    if (key === "classify") return <Scores scores={x.scores} />;
    if (key === "label") return (
      <div className="pb-label">
        {a.labels.length ? <div className="pb-verdict">
          {a.labels.map((l, k) => <span key={l} className={k ? "sec" : "pri"} style={{ ["--c" as any]: famColor(l) }}>{l}</span>)}
          <span className={`pb-conf ${a.level}`}>{a.level} confidence · {Math.round(a.confidence * 100)}%{a.hybrid ? " · hybrid profile" : ""}</span>
        </div> : <div className="pb-verdict none"><span className="pri">unclassified</span>
          <span className="pb-conf none">only {a.evidence_total} evidence of any role: add your job titles and what you did in each</span></div>}
        {out && <><h4>Keywords the search will look for ({out.profile.keywords.length})</h4>
          <ChipList unit="keywords" tone="#f2c14e" items={out.profile.keywords.map((k) => ({ id: k, label: k }))} />
          <p className="pb-note">{out.profile.years} years of experience read{out.profile.senior ? " · senior" : ""}{out.profile.student ? " · student" : ""}.</p></>}
      </div>);
    if (!out) return <div className="pb-wait"><span className="pb-spinner" aria-hidden />Searching {key === "discover" ? "40 public boards" : "…"}: this takes about 15 seconds.</div>;
    if (key === "discover") return (
      <div className="pb-big">
        <div><b><Count to={out.postings} /></b><span>open postings</span></div>
        <div><b><Count to={out.boards} /></b><span>company boards</span></div>
        <p className="pb-note">Every one of these is live right now. The next stage decides which of them are worth your time.</p>
      </div>);
    if (key === "gate") return <Gate out={out} />;
    return <Ranked out={out} />;
  }
}

type Item = { id: string; label: React.ReactNode; kind?: string | string[]; color?: string; strong?: boolean; title?: string };

/** The full list, never "+N more": filter box, kind filters with counts, click a chip to light up its twins. */
function ChipList({ items, unit, tone, filters, highlightSame }: { items: Item[]; unit: string; tone: string; filters?: (string[])[]; highlightSame?: boolean }) {
  const [q, setQ] = useState("");
  const [kind, setKind] = useState<string | null>(null);
  const [hl, setHl] = useState<string | null>(null);
  const has = (it: Item, k: string) => Array.isArray(it.kind) ? it.kind.includes(k) : it.kind === k;
  const shown = items.filter((it) => (!kind || has(it, kind)) && (!q || it.id.includes(q.toLowerCase())));
  if (!items.length) return <p className="pb-empty">Nothing here for this resume.</p>;
  return (
    <div className="pb-chips" style={{ ["--tone" as any]: tone }}>
      <div className="pb-tools">
        <input type="search" placeholder={`Filter ${items.length.toLocaleString()} ${unit}`} value={q} onChange={(e) => setQ(e.target.value)} aria-label={`Filter ${unit}`} />
        {filters && <div className="pb-kinds" role="group" aria-label="Show only">
          <button type="button" className={!kind ? "on" : ""} onClick={() => setKind(null)}>all <small>{items.length}</small></button>
          {filters.map(([k, name, c]) => {
            const n = items.filter((it) => has(it, k)).length;
            return n ? <button key={k} type="button" className={kind === k ? "on" : ""} style={c ? { ["--c" as any]: c } : undefined} onClick={() => setKind(kind === k ? null : k)}>{name} <small>{n}</small></button> : null;
          })}
        </div>}
        <span className="pb-count">{shown.length === items.length ? `all ${items.length.toLocaleString()}` : `${shown.length.toLocaleString()} of ${items.length.toLocaleString()}`}</span>
      </div>
      <p className="pb-cloud">
        {shown.map((it, k) => (
          <button type="button" key={`${it.id}-${k}`} title={it.title}
                  className={`pb-chip${it.strong ? " strong" : ""}${typeof it.kind === "string" ? ` ${it.kind}` : ""}${hl && it.id === hl ? " lit" : ""}`}
                  style={{ ["--k" as any]: Math.min(k, 90), ...(it.color ? { ["--c" as any]: it.color } : {}) }}
                  onClick={() => highlightSame && setHl(hl === it.id ? null : it.id)}>{it.label}</button>))}
        {!shown.length && <span className="pb-empty">No {unit} match “{q}”.</span>}
      </p>
      {highlightSame && hl && <p className="pb-note">“{hl}” appears {items.filter((it) => it.id === hl).length}× in your resume.</p>}
    </div>
  );
}

function Structure({ trace, sections, lines }: { trace: NonNullable<Analysis["trace"]>; sections: string[]; lines: number }) {
  const [every, setEvery] = useState(false);
  const roles = trace.filter((t) => t.kind === "role" && t.section !== "header");
  const list = every ? trace : roles;
  return (
    <div className="pb-struct">
      <p className="pb-cloud">{sections.length ? sections.map((s, k) => <span key={s} className="pb-chip sec" style={{ ["--k" as any]: k }}>{s}</span>)
        : <span className="pb-empty">No section headers: read as one body.</span>}</p>
      <div className="pb-tools">
        <div className="pb-kinds" role="group" aria-label="Show">
          <button type="button" className={!every ? "on" : ""} onClick={() => setEvery(false)}>role lines <small>{roles.length}</small></button>
          <button type="button" className={every ? "on" : ""} onClick={() => setEvery(true)}>every line <small>{lines}</small></button>
        </div>
      </div>
      <ol className="pb-lines">{list.map((t, k) => {
        const titles = t.hits.filter((h) => h.title).map((h) => h.phrase);
        const ri = roles.indexOf(t);
        return (
          <li key={k} className={t.kind} style={{ ["--k" as any]: Math.min(k, 40) }}>
            <span className="tag">{t.kind === "role" && ri >= 0 ? (ri === 0 ? "newest role" : `role ${ri + 1}`) : t.section}</span>
            <span className="ln">{t.line}</span>
            {t.kind === "role" && <span className="ti">{titles.length ? `title → ${titles.join(", ")}` : "no known title on this line"}</span>}
            {every && t.kind !== "role" && t.hits.length > 0 && <span className="ti dim">{t.hits.map((h) => h.phrase).join(" · ")}</span>}
          </li>);
      })}
        {!list.length && <li className="pb-empty">No role lines found: add lines like “Job title | Company | 2022 – Present”.</li>}
      </ol>
    </div>
  );
}

function Scores({ scores }: { scores: NonNullable<Analysis["steps"]>["scores"] }) {
  const [openF, setOpenF] = useState<string | null>(scores[0]?.family ?? null);
  if (!scores.length) return <p className="pb-empty">No family matched anything.</p>;
  return (
    <ul className="pb-bars">{scores.map((x, k) => (
      <li key={x.family} className={openF === x.family ? "open" : ""} style={{ ["--k" as any]: k, ["--c" as any]: famColor(x.family), ["--w" as any]: `${Math.max(2, x.p * 100)}%` }}>
        <button type="button" onClick={() => setOpenF(openF === x.family ? null : x.family)} aria-expanded={openF === x.family}>
          <span className="n">{x.family}</span><span className="bar"><i /></span><span className="p">{Math.round(x.p * 100)}%</span>
        </button>
        {openF === x.family && <p className="ev">Decided by: {x.evidence.map((e) => <span key={e}>{e}</span>)}</p>}
      </li>))}
    </ul>
  );
}

function Gate({ out }: { out: TryOut }) {
  const rows = Object.entries(out.blocked).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...rows.map(([, n]) => n));
  const cut = rows.reduce((s, [, n]) => s + n, 0);
  return (
    <div className="pb-gate">
      <div className="pb-funnel">
        <div><b><Count to={out.postings} /></b><span>in</span></div>
        <i aria-hidden />
        <div className="cut"><b><Count to={cut} /></b><span>thrown out</span></div>
        <i aria-hidden />
        <div className="keep"><b><Count to={out.passing} /></b><span>fit you</span></div>
      </div>
      <ul>{rows.map(([r, n], k) => (
        <li key={r} style={{ ["--k" as any]: k, ["--w" as any]: `${Math.max(2, (n / max) * 100)}%` }}>
          <span>{r}</span><b>{n.toLocaleString()}</b><i />
        </li>))}
      </ul>
    </div>
  );
}

function Ring({ pct, i }: { pct: number; i: number }) {
  const tone = pct >= 70 ? "#3ddc84" : pct >= 50 ? "#f2c14e" : "#ff9f43";
  return <span className="td-ring" style={{ ["--p" as any]: pct, ["--tone" as any]: tone, ["--i" as any]: i }} aria-label={`ATS match ${pct}%`}><b>{pct}<small>%</small></b></span>;
}

function Ranked({ out }: { out: TryOut }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!out.top.length) return <p className="pb-empty">{out.profile.lanes.length ? "Nothing on these boards fits this resume right now. Postings change by the hour: try again later." : "The engine couldn’t tell what kind of role this resume is for, so it didn’t guess. Add your job titles and what you did, then run it again."}</p>;
  return (
    <>
      <p className="pb-note">Read {out.checked} job descriptions. Your {out.top.length} best, highest ATS match first. Click a role for every keyword it asks for.</p>
      <ol className="td-roles">{out.top.map((j, i) => {
        const isOpen = open === j.url;
        return (
          <li key={j.url} className={isOpen ? "open" : ""} style={{ ["--i" as any]: i }}>
            <Ring pct={j.match} i={i} />
            <div className="body">
              <a href={j.url} target="_blank" rel="noreferrer noopener">{j.title}</a>
              <span className="co">{j.company}{j.location ? ` · ${j.location}` : ""}</span>
              <p className="chips">{(isOpen ? j.matched : j.matched.slice(0, 6)).map((k) => <span key={k} className="ok">{k}</span>)}
                {(isOpen ? j.missing : j.missing.slice(0, 3)).map((k) => <span key={k} className="miss">{k}</span>)}</p>
              <button type="button" className="pb-more" onClick={() => setOpen(isOpen ? null : j.url)} aria-expanded={isOpen}>
                {isOpen ? "Show less" : `All ${j.matched.length + j.missing.length} keywords · ${j.matched.length} you have`}</button>
            </div>
          </li>);
      })}</ol>
      <p className="td-legend"><span className="ok">your resume has it</span><span className="miss">the job asks, your resume doesn&apos;t show it</span></p>
    </>
  );
}

/** A number that counts up when it lands (instant with reduced motion). */
export function Count({ to }: { to: number }) {
  const [v, setV] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setV(to); from.current = to; return; }
    const a = from.current, t0 = performance.now(); let raf = 0;
    const tick = (t: number) => { const k = Math.min(1, (t - t0) / 1100); setV(Math.round(a + (to - a) * (1 - (1 - k) ** 3))); if (k < 1) raf = requestAnimationFrame(tick); else from.current = to; };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to]);
  return <>{v.toLocaleString()}</>;
}
