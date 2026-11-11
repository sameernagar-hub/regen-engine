// One cylinder of the five-cylinder radial (ALIVE Phase 1): one pipeline stage, drawn as a barrel pointing out from
// the crankcase. It fires (piston stroke + flash, 300 ms) whenever a chip enters its stage; it is drawn cold (grey,
// still) when the container behind it is down. Geometry is shared with Engine.tsx through slot().

export const CX = 500, CY = 330, R_IN = 92, R_OUT = 250, HALF = 44;

/** The point at distance r along angle deg (degrees, 0 = right, clockwise) from the crank centre. */
export function at(deg: number, r: number): [number, number] {
  const a = (deg * Math.PI) / 180;
  return [CX + Math.cos(a) * r, CY + Math.sin(a) * r];
}

/** Where the i-th chip of a cylinder sits: 2 lanes x 4 rows inside the barrel (8 per cylinder, 40 on screen). */
export function slot(deg: number, i: number): [number, number] {
  const row = Math.floor(i / 2), side = i % 2 ? 1 : -1;
  const [x, y] = at(deg, R_IN + 38 + row * 34);
  const a = ((deg + 90) * Math.PI) / 180;  // perpendicular to the barrel
  return [x + Math.cos(a) * side * 19, y + Math.sin(a) * side * 19];
}

export type CylinderProps = {
  deg: number; label: string; verb: string; count: number; cold: boolean; fire: number; why?: string;
};

/** The barrel, its piston and its label. `fire` changes on each entry; the key restarts the CSS stroke animation. */
export function Cylinder({ deg, label, verb, count, cold, fire, why }: CylinderProps) {
  const [lx, ly] = at(deg, R_OUT + 52);  // beyond the head and its +N bundle
  return (
    <g className={`alive-cyl${cold ? " al-cold" : ""}`} aria-label={`${label}: ${cold ? `cold (${why ?? "container down"})` : `${count} ${verb}`}`} role="img">
      <g transform={`rotate(${deg} ${500} ${330})`}>
        <rect className="al-barrel" x={500 + R_IN} y={330 - HALF} width={R_OUT - R_IN} height={HALF * 2} rx={14} />
        {Array.from({ length: 6 }, (_, k) => (
          <line key={k} className="al-fin" x1={500 + R_IN + 18 + k * 24} x2={500 + R_IN + 18 + k * 24} y1={330 - HALF - 6} y2={330 + HALF + 6} />
        ))}
        <g key={fire} className={fire ? "al-piston al-fire" : "al-piston"}>
          <rect x={500 + R_OUT - 16} y={330 - HALF + 8} width={12} height={HALF * 2 - 16} rx={4} />
        </g>
        <rect key={`f${fire}`} className={fire ? "al-flash al-on" : "al-flash"} x={500 + R_IN} y={330 - HALF} width={R_OUT - R_IN} height={HALF * 2} rx={14} />
      </g>
      <text className="al-cyl-label" x={lx} y={ly - 6}>{label}</text>
      <text className="al-cyl-count" x={lx} y={ly + 14} dy="0.4em">{cold ? "cold" : `${count} ${verb}`}</text>
    </g>
  );
}
