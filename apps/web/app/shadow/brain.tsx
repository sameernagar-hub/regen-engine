"use client";
// Shadow's brain, training ground, vision map and agent graph (11-07). Backend: engine/shadow_brain.py (strategies,
// train/test, ownership ladder) and engine/agents.py (the nested agent graph). Read-only except "Train now".
import { useEffect, useState } from "react";
import { get, post, poll } from "@/lib/types";

type Counts = { n: number; answered: number; correct: number; wrong: number; abstained: number; precision: number | null; coverage: number | null };
type Run = { ts: string; secs: number; gold: number; train: Counts; test: Counts; baseline_test: Counts; tau: number; sigma: number;
  violations: string[]; reliability: Record<string, number>; context?: Record<string, number>; misses: { q: string; you: string; shadow: string }[] };
type Miss = { need: string; want: number | string; have: number | string };
type Rung = { level: number; name: string; owns: string; needs: Record<string, number>; missing: Miss[]; unlocked: boolean };
export type Brain = { policy: { tau: number; sigma: number; trained: string | null; reliability: Record<string, number>; live: Record<string, number[]> };
  latest: Run | null; history: { ts: string; precision: number | null; coverage: number | null; baseline: number | null }[];
  ladder: { level: number; rungs: Rung[]; record: Record<string, number | string | null> } };
type Node = { id: string; kind: string; label: string; state: string; owner: string; answer?: string | null; conf?: number | null; strategy?: string | null; children: Node[] };
type Step = { action: string; target: string; why: string; needs_level: number; allowed: boolean; done?: boolean };
type Agents = { graph: Node; counts: Record<string, number>; plan: Step[] };

const STRAT: [string, string, string][] = [
  ["bank", "Your answer bank", "your approved answer whose pattern matches"],
  ["memory", "Shadow's memory", "what it answered for this exact wording before"],
  ["neighbor", "Similar question", "your answer to the closest question (TF-IDF cosine)"],
  ["engine", "Fact Bank draft", "presets, rules, derived facts, drafts"],
  ["yesno", "Yes/no policy", "willing -> Yes; have-you -> only if the Fact Bank backs it"],
];
const NEED: Record<string, string> = {
  test_n: "held-out questions", test_precision: "test precision", violations: "truthfulness violations",
  live_answers: "live answers", override_rate: "your corrections", shadow_submitted: "forms Shadow got through",
  clean_days: "days without a kill switch", trained: "eval run",
};
const pct = (x: number | null | undefined) => (x == null ? "–" : `${Math.round(x * 100)}%`);

export function useBrain() {
  const [b, setB] = useState<Brain | null>(null);
  const [a, setA] = useState<Agents | null>(null);
  const pull = () => { get<Brain>("/api/shadow/brain").then(setB).catch(() => {}); get<Agents>("/api/shadow/agents").then(setA).catch(() => {}); };
  useEffect(() => { pull(); return poll(pull, 10000); }, []);
  return { b, a, pull };
}

// How Shadow decides: five strategies -> confidence (raw x reliability) -> agreeing ones vote (noisy-OR) -> tau gate.
export function Decide({ b }: { b: Brain | null }) {
  const rel = b?.policy.reliability || {};
  return (
    <section className="card shadow-decide" aria-label="How Shadow decides">
      <h2>How Shadow decides <span className="dim small">five strategies, one vote, a confidence gate</span></h2>
      <div className="shadow-flow">
        <div className="shadow-flow-q"><b>A question</b><span className="dim small">from a form</span></div>
        <ol className="shadow-strats">
          {STRAT.map(([k, label, about], i) => (
            <li key={k} style={{ animationDelay: `${i * 70}ms` }}>
              <span><b>{label}</b><span className="dim small">{about}</span></span>
              <span className="shadow-rel" title="reliability: how often this strategy matched your own answers">
                <span style={{ width: pct(rel[k]) }} /></span>
              <b className="shadow-rel-n">{pct(rel[k])}</b>
            </li>))}
        </ol>
        <div className="shadow-flow-gate">
          <b>Vote</b><span className="dim small">strategies that agree combine: 1 − Π(1 − c)</span>
          <b>Gate τ = {b ? b.policy.tau.toFixed(2) : "…"}</b><span className="dim small">below it Shadow abstains and the job waits for you</span>
          <span className="dim small">similar-question floor σ = {b ? b.policy.sigma.toFixed(2) : "…"}</span>
        </div>
      </div>
      <p className="dim small">Reliability is learned per question type (yes/no, what/which, open) and keeps moving with live feedback:
        a form Shadow got through counts for it, a job that parked again or an answer you corrected counts against it.
        A human check or a fact only you know gets no candidate from any strategy, ever.</p>
    </section>
  );
}

// Training ground: tuned on your answers (train split), scored once on held-out questions it never saw.
export function Training({ b, onTrained }: { b: Brain | null; onTrained: () => void }) {
  const [busy, setBusy] = useState(false), [msg, setMsg] = useState("");
  const r = b?.latest, h = b?.history || [];
  const train = async () => {
    setBusy(true);
    try { const x: any = await post("/api/shadow/train", {}); setMsg(`Trained: test precision ${pct(x.test?.precision)}, coverage ${pct(x.test?.coverage)}.`); onTrained(); }
    catch (e: any) { setMsg(e.message); }
    setBusy(false);
  };
  const W = 320, H = 90, pts = (key: "precision" | "coverage") => h.map((x, i) =>
    `${h.length < 2 ? W / 2 : (i / (h.length - 1)) * W},${H - (x[key] ?? 0) * H}`).join(" ");
  return (
    <section className="card shadow-train" aria-label="Training ground">
      <h2>Training ground <span className="dim small">{r ? `last run ${r.ts.replace("T", " ").slice(5, 16)} · ${r.secs}s · retrains hourly` : "not trained yet"}</span></h2>
      {!r ? <p className="dim">Shadow has not been tested yet.</p> : (
        <div className="shadow-train-grid">
          <div className="shadow-score">
            <span className="shadow-big">{pct(r.test.precision)}</span><span className="dim small">right when it answers (held-out test)</span>
            <span className="shadow-big sub">{pct(r.test.coverage)}</span><span className="dim small">of questions it was sure enough to answer</span>
            <span className="small">{r.test.correct} right · {r.test.wrong} wrong · {r.test.abstained} left to you · of {r.test.n}</span>
            <span className="dim small">untuned: {pct(r.baseline_test.precision)} right at {pct(r.baseline_test.coverage)} coverage</span>
            <span className={`shadow-truth${r.violations.length ? " bad" : ""}`}>{r.violations.length ? `${r.violations.length} truthfulness violation(s)` : "0 truthfulness violations"}</span>
          </div>
          <figure className="shadow-curve">
            <svg viewBox={`-6 -6 ${W + 12} ${H + 12}`} role="img" aria-label={`Test precision over ${h.length} runs`}>
              <line x1="0" x2={W} y1={H * 0.1} y2={H * 0.1} className="shadow-curve-goal" />
              <polyline points={pts("coverage")} className="shadow-curve-cov" />
              <polyline points={pts("precision")} className="shadow-curve-prec" />
              {h.map((x, i) => <circle key={i} r="3" cx={h.length < 2 ? W / 2 : (i / (h.length - 1)) * W} cy={H - (x.precision ?? 0) * H} className="shadow-curve-dot" />)}
            </svg>
            <figcaption className="dim small"><i className="k prec" /> precision <i className="k cov" /> coverage · dashed: 90% · {h.length} run(s)</figcaption>
          </figure>
        </div>)}
      {r?.misses?.length ? (
        <details className="shadow-misses"><summary className="small">Where it disagreed with you ({r.misses.length})</summary>
          <ul className="small">{r.misses.map((m, i) => <li key={i}><span className="dim">{m.q}</span><br />you: <b>{m.you}</b> · Shadow: <b>{m.shadow}</b></li>)}</ul>
        </details>) : null}
      <p className="row small"><button className="btn" disabled={busy} onClick={train}>{busy ? "Training…" : "Train now"}</button>
        <span className="dim">{msg || `${r?.gold ?? 0} of your own answers: 80% train, 20% held out by a fixed hash.`}</span></p>
    </section>
  );
}

// Vision map: the road from answering to owning the engine. Each station unlocks only from evidence.
export function Vision({ b }: { b: Brain | null }) {
  const L = b?.ladder, level = L?.level ?? 1, rungs = L?.rungs || [];
  const n = 7, x = (i: number) => 40 + i * 140;
  const stations = [...rungs.map((r) => ({ k: `L${r.level}`, name: r.name, on: r.level <= level })),
    { k: "∞", name: "Nested agents", on: false }];
  return (
    <section className="card shadow-vision" aria-label="Vision map">
      <h2>Vision map <span className="dim small">where Shadow is on the road to running the engine itself</span></h2>
      <div className="shadow-track-wrap">
        <svg viewBox={`0 0 ${x(n - 1) + 60} 150`} className="shadow-track" role="img" aria-label={`Shadow is at level ${level} of 5`}>
          <line x1={x(0)} x2={x(n - 1)} y1="56" y2="56" className="shadow-track-line" />
          <line x1={x(0)} x2={x(Math.min(level, n - 1))} y1="56" y2="56" className="shadow-track-done" />
          {stations.map((s, i) => (
            <g key={s.k} transform={`translate(${x(i)} 56)`} className={`shadow-stop${s.on ? " on" : ""}${i === level ? " here" : ""}`}>
              {i === level && <circle r="24" className="shadow-stop-pulse" />}
              <circle r="15" className="shadow-stop-dot" />
              <text y="5" className="shadow-stop-k">{s.k}</text>
              <text y="44" className="shadow-stop-name">{s.name}</text>
              {i === level && <text y="-28" className="shadow-stop-here">Shadow is here</text>}
            </g>))}
        </svg>
      </div>
      <ol className="shadow-rungs">
        {rungs.map((r) => (
          <li key={r.level} data-on={r.level <= level ? "true" : "false"}>
            <b>L{r.level} · {r.name}</b><span className="small">{r.owns}</span>
            {r.level > level && r.missing.length ? (
              <ul className="shadow-needs">{r.missing.map((m) => {
                const have = typeof m.have === "number" ? m.have : 0, want = typeof m.want === "number" ? m.want : 1;
                const inv = m.need === "override_rate" || m.need === "violations";
                const fill = inv ? (have <= want ? 1 : Math.max(0, 1 - (have - want))) : Math.min(1, want ? have / want : 0);
                return (<li key={m.need}><span className="dim small">{NEED[m.need] || m.need}</span>
                  <span className="shadow-need-bar"><span style={{ width: `${Math.round(fill * 100)}%` }} /></span>
                  <span className="small">{String(m.have)} / {inv ? "≤ " : ""}{String(m.want)}</span></li>);
              })}</ul>) : <span className="dim small">{r.level <= level ? "earned" : ""}</span>}
          </li>))}
        <li data-on="false"><b>∞ · Nested agents</b><span className="small">Shadow spawns a sub-agent per applier and per job, and
          sub-sub-agents per question; creates, updates, deletes, scales and balances them. Reached only after L5 holds for 30 clean days.</span></li>
      </ol>
      <p className="dim small">Nobody switches a rung on by hand: each one opens from the held-out test and Shadow's live record,
        and one truthfulness violation closes every rung above L1 until it is fixed.</p>
    </section>
  );
}

// The agent graph: Shadow -> agents -> sub-agents -> sub-sub-agents, coloured by who owns each one today.
export function AgentGraph({ a }: { a: Agents | null }) {
  if (!a) return <section className="card"><h2>Agent graph</h2><p className="dim">Reading the fleet…</p></section>;
  const c = a.counts;
  return (
    <section className="card shadow-agents" aria-label="Agent graph">
      <h2>Agent graph <span className="dim small">{c.applier || 0} applier · {c.job || 0} job · {c.question || 0} question · {c.service || 0} service agents</span></h2>
      <p className="shadow-legend small">
        <span className="shadow-own shadow">Shadow</span><span className="shadow-own supervisor">supervisor</span>
        <span className="shadow-own engine">engine</span><span className="shadow-own you">you</span></p>
      <ul className="shadow-tree" role="tree"><Tree n={a.graph} depth={0} /></ul>
      <h3 className="small">What Shadow would do now</h3>
      {!a.plan.length ? <p className="dim small">Nothing to do: every agent is where it should be.</p> : (
        <ul className="shadow-plan">{a.plan.map((p, i) => (
          <li key={i} data-allowed={p.allowed ? "true" : "false"}>
            <span className={`shadow-lock${p.allowed ? " open" : ""}`}>{p.done ? "done" : p.allowed ? "allowed" : `locked · L${p.needs_level}`}</span>
            <b>{p.action}</b> <span>{p.target}</span> <span className="dim small">{p.why}</span>
          </li>))}</ul>)}
    </section>
  );
}

function Tree({ n, depth }: { n: Node; depth: number }) {
  const [open, setOpen] = useState(depth < 2);
  const kids = n.children || [];
  return (
    <li role="treeitem" aria-expanded={kids.length ? open : undefined} className={`shadow-node k-${n.kind}`}>
      <button className="shadow-node-row" onClick={() => setOpen(!open)} disabled={!kids.length}>
        <span className="shadow-caret" aria-hidden="true">{kids.length ? (open ? "▾" : "▸") : "·"}</span>
        <span className={`shadow-own ${n.owner}`} title={`owner: ${n.owner}`} />
        <b>{n.label}</b>
        <span className="dim small">{n.state}{n.answer ? ` → ${n.answer}` : ""}{n.conf != null && n.answer ? ` (${Math.round(n.conf * 100)}%)` : ""}</span>
        {kids.length ? <span className="dim small">{kids.length}</span> : null}
      </button>
      {open && kids.length ? <ul role="group">{kids.slice(0, 40).map((k) => <Tree key={k.id} n={k} depth={depth + 1} />)}</ul> : null}
    </li>
  );
}
