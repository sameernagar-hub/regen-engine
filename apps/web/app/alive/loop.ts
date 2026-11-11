// The living engine's one animation loop (ALIVE Phase 1, docs/ALIVE_PLAN.md §5).
// Events arrive in bursts (a pipeline pass discovers 30 postings in a second); the loop coalesces every state change
// into at most one React update per frame, and stops entirely while the tab is hidden (work queued meanwhile is
// applied in one step when the tab comes back, without replaying the motion). Movement itself is CSS transitions on
// SVG transforms, so the browser composites it; this loop only decides WHEN state lands.
// Dev builds count frame times on window.__aliveFrames (bench V3: p95 frame time with 40 chips).

type Job = () => void;

const jobs: Job[] = [];
let raf = 0;
let last = 0;

function frame(t: number) {
  raf = 0;
  if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
    const w = window as unknown as { __aliveFrames?: number[] };
    if (last) (w.__aliveFrames ??= []).push(t - last);
    if ((w.__aliveFrames?.length ?? 0) > 2000) w.__aliveFrames!.splice(0, 1000);
    last = t;
  }
  const batch = jobs.splice(0);
  for (const j of batch) j();
}

/** Queue a state change for the next visible frame. Never drops a job: hidden tabs keep them until visible. */
export function schedule(job: Job): void {
  jobs.push(job);
  if (raf || (typeof document !== "undefined" && document.hidden)) return;
  raf = requestAnimationFrame(frame);
}

/** Start the visibility watcher once per page: resume the queue when the tab is shown again. Returns a cleanup. */
export function watchVisibility(): () => void {
  const on = () => { if (!document.hidden && jobs.length && !raf) { last = 0; raf = requestAnimationFrame(frame); } };
  document.addEventListener("visibilitychange", on);
  return () => document.removeEventListener("visibilitychange", on);
}

/** True when the user asked the OS for less motion: chips jump between stations, no pistons, no breath. */
export function reducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
