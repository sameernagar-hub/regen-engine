// Shadow's seat (ALIVE Phase 2, docs/ALIVE_PLAN.md §5): the co-driver beside the engine. It shows Shadow's mode as the
// engine last reported it (shadow.mode signal), its ladder level and its held-out test score (/api/shadow/brain).
// The selector posts to /api/shadow; the seat changes only when the engine's shadow.mode signal comes back.

export const SEAT: [number, number] = [150, 585];

export type Brain = {
  ladder?: { level?: number };
  latest?: { test?: { answered?: number; correct?: number } };
};

/** ["level 1 · 67% right on test", "4 of 6 held-out answers right"], or null before the brain is read. */
export function badge(b: Brain | null): [string, string] | null {
  if (!b) return null;
  const lvl = b.ladder?.level;
  const t = b.latest?.test;
  const score = t && t.answered ? `${Math.round(((t.correct ?? 0) / t.answered) * 100)}% right on test` : "not tested yet";
  const detail = t && t.answered ? `${t.correct ?? 0} of ${t.answered} held-out answers right` : "no held-out test yet";
  return [`${lvl !== undefined ? `level ${lvl} · ` : ""}${score}`, detail];
}

/** Shadow drives only in autopilot (and the older "always"); in calls it rings you first; off = absent. */
export const hasWheel = (mode: string | null) => mode === "autopilot" || mode === "always";

/** The seat in the engine's SVG units: lit (violet) while Shadow has the wheel, dim when off. */
export function Seat({ mode, brain }: { mode: string | null; brain: Brain | null }) {
  const lit = hasWheel(mode);
  const label = mode === null ? "mode unknown" : mode === "always" ? "autopilot" : mode;
  const b = badge(brain);
  return (
    <g className={`al-seat${lit ? " al-lit" : ""}${mode === "off" ? " al-off" : ""}`} transform={`translate(${SEAT[0]} ${SEAT[1]})`}
       role="img" aria-label={`Shadow's seat: ${label}${b ? `, ${b[0]} (${b[1]})` : ""}`}>
      {b && <title>{b[1]}</title>}
      <rect x={-78} y={-34} width={156} height={68} rx={18} />
      <text className="al-seat-name" y={-8}>Shadow</text>
      <text className="al-seat-mode" y={12}>{label}</text>
      {b && <text className="al-seat-badge" y={54}>{b[0]}</text>}
    </g>
  );
}
