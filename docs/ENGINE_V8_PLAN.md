# Front engine: radial "star" -> real V8 (plan, 11-03)

## Problem
`apps/web/app/page.tsx` places the 8 cylinders on a circle (`ang(i) = -90 + i*45`). Since Desk joined as the 8th
part, cylinder 5 sits at 90 deg (straight down) on top of the gearbox at `GBX = (600, 696)`: the Desk label overlaps the
gears ("Desk" drawn inside the Gearbox, see the user's screenshot). The star also doesn't read as an engine.

## Layout: a V8 seen from the front-quarter
- Two banks of 4 cylinders at +/-45 deg from vertical (90 deg V), bank A left (cyl 1,3,5,7), bank B right (2,4,6,8),
  pistons on a shared crankshaft line at the bottom of the block.
- Crank + flywheel at the back (right), gearbox bolted behind the flywheel: horizontal, never under a cylinder.
- Intake manifold / throttle body in the valley between the banks = the core (Live / Fact Bank feed).
- Fuel rail (Fact Bank tank) on the left, spark wires (MCP cord) from the coil pack top-left, exhaust headers on the
  outer side of each bank, oil pan under the crank = Maintenance.
- Each cylinder: head, bore, piston with con-rod to the crank; label sits outside its bank (no label inside another part).
- Collision test: a small helper asserts no two part hit-boxes / labels intersect (unit test on the layout constants).

## Animation
- One crank angle `theta` driven by `requestAnimationFrame`, speed = current gear (N idle ~600 rpm feel, gear 4 fast).
- Piston y = crank geometry (r*cos + sqrt(l^2 - r^2 sin^2)), bank offset 90 deg, firing order 1-8-4-3-6-5-7-2:
  a cylinder flashes (combustion glow) at its TDC in that order; glow intensity = that part's live activity.
- Gears turn from the same `theta` (ratio by gear); shaft spins; fuel pulses along the rail per firing.
- `prefers-reduced-motion`: static pose, no rAF. Pause when the tab is hidden (already the `poll` pattern).

## Cleaner / more efficient
- Move geometry to `apps/web/app/engine/geometry.ts` (pure functions, unit-testable); `page.tsx` keeps data + hover.
- Animate via one rAF writing `transform` attributes on refs (no React re-render per frame); CSS keyframes removed.
- Responsive: SVG `viewBox` stays, labels switch to a legend list under ~640 px; hit areas >= 44 px.
- Gradients/specular highlights on heads and pistons, thin outline strokes, subtle block shadow: "more real" without
  raster images.

## Desk vs Gearbox
- Desk gets its own cylinder (bank B, #8) with its own color; Gearbox is the transmission behind the flywheel, labelled
  under itself. Hover cards stay per part.

## Check
- Tests: geometry collision test + existing suite. Build web, open `/`, screenshot at desktop and 400 px, both themes.
