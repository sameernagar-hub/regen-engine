// One posting on its way through the engine (ALIVE Phase 1). A disc with the employer's initial; the full name and
// role show on hover/focus (SVG <title>). Its position is a CSS transform, so moving between stations is a
// composited transition (none under reduced motion, see engine.css).

export type ChipProps = { id: string; x: number; y: number; company: string | null; by: string | null; tone?: string };

/** A chip at (x, y) in the engine's SVG units. `by === "shadow"` draws Shadow's ring around it. */
export function Chip({ x, y, company, by }: ChipProps) {
  const name = company || "a posting";
  return (
    <g className={`alive-chip${by === "shadow" ? " al-by-shadow" : ""}`} style={{ transform: `translate(${x}px, ${y}px)` }}
       role="img" aria-label={name}>
      <title>{name}{by === "shadow" ? " (Shadow is answering)" : ""}</title>
      <circle r={11} />
      <text y={4}>{name.charAt(0).toUpperCase()}</text>
    </g>
  );
}

/** "+12": the chips a station holds beyond what fits, so the screen never carries more than 40 discs. */
export function Bundle({ x, y, n }: { x: number; y: number; n: number }) {
  if (n <= 0) return null;
  return (
    <g className="alive-bundle" transform={`translate(${x} ${y})`} role="img" aria-label={`${n} more`}>
      <rect x={-18} y={-10} width={36} height={20} rx={10} />
      <text y={4}>+{n}</text>
    </g>
  );
}
