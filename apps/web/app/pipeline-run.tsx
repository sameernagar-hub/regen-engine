"use client";
// The resume classifier, played back live: lib/resume-nlp.ts runs in the browser on the pasted text (the same code the
// server and `python -m engine try` run), then each step's REAL output is revealed in order: tokens, normalization,
// structure, phrase features, family scores, the label. Shared by /pipeline (full) and /test-drive (compact).
// Nothing leaves the browser for this part. Reduced motion: every step shows at once.
import { useEffect, useMemo, useRef, useState } from "react";
import { analyze, normalizeTrace, rawTokens, FAMILIES, type Analysis } from "@/lib/resume-nlp";

export const famColor = (f: string) => {
  const i = Math.max(0, FAMILIES.indexOf(f));
  return `hsl(${Math.round((i * 360) / Math.max(1, FAMILIES.length) + 205) % 360} 78% 66%)`;
};

export const STEPS: { key: string; name: string; does: string }[] = [
  { key: "tokenize", name: "Tokenize", does: "Unicode text is folded to plain lowercase, tech names are protected (C++, C#, .NET, Node.js) and the text is split into tokens." },
  { key: "normalize", name: "Normalize", does: "Abbreviations expand (k8s → kubernetes, RN → registered nurse, SDR → sales development representative), stopwords drop, and one fixed stemmer folds word forms together (engineers, engineering → engineer)." },
  { key: "structure", name: "Structure", does: "Sections are found (summary, experience, skills, education…) and each role line is split: only the job title counts; the employer and the place count for nothing. The newest role weighs most." },
  { key: "features", name: "Features", does: "The vocabulary of 25 role families is matched longest-first, so “sales engineer” is one phrase and not “sales” + “engineer”. A title on a role line weighs 3, a skill or task 1." },
  { key: "classify", name: "Classify", does: "Each phrase adds weight × its specificity (1 ÷ how many families use it, the IDF idea). That share is blended 70/30 with cosine similarity to each family’s centroid." },
  { key: "label", name: "Label", does: "The top family is the label; any family within 40% of it makes a hybrid profile. Too little evidence means “unclassified”: the engine says so instead of guessing." },
];

type Props = { text: string; runId: number; compact?: boolean; onDone?: (a: Analysis) => void };

export function PipelineRun({ text, runId, compact, onDone }: Props) {
  const [step, setStep] = useState(-1);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  // computed once per run: the whole analysis is instant; the animation reveals it step by step
  const data = useMemo(() => {
    if (!runId || !text.trim()) return null;
    return { a: analyze(text, true, true), raw: rawTokens(text), norm: normalizeTrace(text, 600) };
  }, [runId]);  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    timers.current.forEach(clearTimeout); timers.current = [];
    if (!data) { setStep(-1); return; }
    const reduce = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setStep(STEPS.length); onDone?.(data.a); return; }
    const every = compact ? 650 : 1500;
    setStep(0);
    STEPS.forEach((_, i) => timers.current.push(setTimeout(() => setStep(i + 1), every * (i + 1))));
    timers.current.push(setTimeout(() => onDone?.(data.a), every * STEPS.length));
    return () => { timers.current.forEach(clearTimeout); timers.current = []; };
  }, [data]);  // eslint-disable-line react-hooks/exhaustive-deps

  if (!data) return null;
  const { a, raw, norm } = data;
  const s = a.steps!;
  const trace = a.trace || [];
  const hits = trace.flatMap((t) => t.hits.map((h) => ({ ...h, role: t.kind === "role" })));
  const roleLines = trace.filter((t) => t.kind === "role" && t.section !== "header");  // the top lines are the headline, not a job
  const state = (i: number) => (step > i ? "done" : step === i ? "on" : "wait");
  const shown = (i: number) => step >= i;

  return (
    <ol className={`pl-steps${compact ? " compact" : ""}`} aria-live="polite">
      {STEPS.map((st, i) => (
        <li key={st.key} className={`pl-step ${state(i)}`} style={{ ["--i" as any]: i }}>
          <div className="pl-head">
            <span className="pl-dot" aria-hidden>{i + 1}</span>
            <b>{st.name}</b>
            <span className="pl-stat">{shown(i) ? statLine(i, a, raw.length, norm) : state(i) === "wait" ? "waiting" : "…"}</span>
          </div>
          {!compact && <p className="pl-does">{st.does}</p>}
          {shown(i) && <div className="pl-out">{body(i)}</div>}
        </li>
      ))}
    </ol>
  );

  function body(i: number) {
    const cap = compact ? 18 : 48;
    if (i === 0) return (
      <p className="pl-chips">{raw.slice(0, cap).map((t, k) => <span key={k} className="pl-tok" style={{ ["--k" as any]: k }}>{t}</span>)}
        {raw.length > cap && <span className="pl-more">+{raw.length - cap} more</span>}</p>);
    if (i === 1) {
      const pick = norm.filter((n) => n.why !== "kept" && n.why !== "number").slice(0, compact ? 12 : 36);
      return (
        <p className="pl-chips">{pick.map((n, k) => (
          <span key={k} className={`pl-norm ${n.why}`} style={{ ["--k" as any]: k }} title={n.why}>
            <s>{n.raw}</s>{n.out.length ? <> → <b>{n.out.join(" ")}</b></> : null}</span>))}
          <span className="pl-legend"><i className="stopword" />stopword <i className="alias" />abbreviation <i className="stem" />stem</span></p>);
    }
    if (i === 2) return (
      <div className="pl-struct">
        <p className="pl-chips">{s.sections.length ? s.sections.map((x) => <span key={x} className="pl-sec">{x}</span>) : <span className="pl-more">no section headers: read as one body</span>}
          <span className="pl-more">{s.roles} role{s.roles === 1 ? "" : "s"} · {s.lines} lines</span></p>
        {!compact && <ul className="pl-lines">{roleLines.slice(0, 6).map((t, k) => (
          <li key={k} style={{ ["--k" as any]: k }}><span className="pl-tag">{k === 0 ? "newest role" : `role ${k + 1}`}</span>
            <span className="pl-line">{t.line.length > 110 ? t.line.slice(0, 110) + "…" : t.line}</span>
            <span className="pl-title">title → {t.hits.filter((h) => h.title).map((h) => h.phrase).join(", ") || "no known title"}</span></li>))}
        </ul>}
      </div>);
    if (i === 3) {
      const seen = new Set<string>(), uniq = hits.filter((h) => !seen.has(h.phrase) && seen.add(h.phrase));
      return (
        <p className="pl-chips">{uniq.slice(0, compact ? 14 : 40).map((h, k) => (
          <span key={h.phrase} className={`pl-feat${h.title && h.role ? " title" : ""}`} style={{ ["--k" as any]: k, ["--c" as any]: famColor(h.families[0]) }}
                title={h.families.join(", ")}>{h.phrase}</span>))}
          {uniq.length > (compact ? 14 : 40) && <span className="pl-more">+{uniq.length - (compact ? 14 : 40)} more</span>}</p>);
    }
    if (i === 4) return (
      <ul className="pl-bars">{s.scores.slice(0, compact ? 4 : 6).map((x, k) => (
        <li key={x.family} style={{ ["--k" as any]: k, ["--c" as any]: famColor(x.family), ["--w" as any]: `${Math.max(2, x.p * 100)}%` }}>
          <span className="n">{x.family}</span><span className="bar"><i /></span><span className="p">{Math.round(x.p * 100)}%</span>
          {!compact && <span className="ev">{x.evidence.join(" · ")}</span>}</li>))}
        {!s.scores.length && <li className="pl-more">no family matched anything</li>}
      </ul>);
    return a.labels.length ? (
      <div className="pl-label">
        {a.labels.map((l, k) => <span key={l} className={k ? "sec" : "pri"} style={{ ["--c" as any]: famColor(l) }}>{l}</span>)}
        <span className={`pl-conf ${a.level}`}>{a.level} confidence · {Math.round(a.confidence * 100)}%{a.hybrid ? " · hybrid profile" : ""}</span>
      </div>) : (
      <div className="pl-label none"><span className="pri">unclassified</span>
        <span className="pl-conf none">too little evidence ({a.evidence_total}) of any kind of role: add your job titles and the work you did</span></div>);
  }
}

function statLine(i: number, a: Analysis, raw: number, norm: { why: string }[]) {
  const s = a.steps!;
  if (i === 0) return `${raw} tokens`;
  if (i === 1) return `${s.terms} terms · ${s.stopwords} stopwords dropped · ${s.aliases} expanded`;
  if (i === 2) return `${s.sections.length} sections · ${s.roles} roles`;
  if (i === 3) return `${s.phrases} phrases matched`;
  if (i === 4) return s.scores[0] ? `top: ${s.scores[0].family} ${Math.round(s.scores[0].p * 100)}%` : "no evidence";
  return a.labels.length ? `${a.label} (${a.level})` : "unclassified";
}
