# ALIVE benchmarks (docs/ALIVE_PLAN.md §6)

One row per phase. A phase that regresses a number does not ship.

| Date | Phase | Commit | Events | V6 unknown | V7 | V8 hits | S1 ledger/spine | Fold ms |
|---|---|---|---|---|---|---|---|---|
| 2026-11-10 | 0 | 5328097 | 47835 | 0 | pass | 0 | 495/495 | 458 |

## Phase 1 browser checks (11-10, commit 5683029)
| Check | Result |
|---|---|
| V9 container truth | applier paused at claimed 0: cold + warning light 18 s, warm 4 s after unpause (target <= 30 s) |
| V2 tab CPU (proxy) | 132 s live with 119 SVG updates and no reload: 0 long tasks (0% main thread in tasks > 50 ms), heap 6 MB. Not the full 10 min: the preview pane went hidden and a hidden tab pauses the loop by design. DevTools perf sampling is not reachable from the pane |
| V5 memory | JS heap 8 MB at load |
| V10 a11y | controls are buttons with aria-pressed in labelled fieldsets; cylinders carry aria-labels; reduced motion honored by CSS; axe not run |
