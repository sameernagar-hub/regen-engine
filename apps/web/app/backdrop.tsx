"use client";
// The neural field behind every page: points drift along the five engine stages and pull toward each other when
// close, drawing the links between them. Each real engine event (SSE narration) sends a pulse through the field,
// so the background is a heartbeat of the engine, not decoration. Canvas 2D, ~120 points, O(n^2) link pass at
// n=120 is ~7k distance checks per frame; pauses when the tab is hidden; static frame under reduced motion.
import { useEffect, useRef } from "react";

const STAGE_HUE = [210, 45, 160, 35, 280]; // discover, judge, write, apply, hear

export function Backdrop() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current!;
    const ctx = c.getContext("2d")!;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = 0, h = 0, raf = 0, pulse = 0, pulseHue = 45;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const pts = Array.from({ length: window.innerWidth < 700 ? 60 : 120 }, (_, i) => ({
      x: Math.random(), y: Math.random(), vx: (Math.random() - 0.5) * 0.0004, vy: (Math.random() - 0.5) * 0.0004,
      s: i % 5,
    }));
    const size = () => {
      w = c.clientWidth; h = c.clientHeight;
      c.width = w * dpr; c.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const frame = () => {
      ctx.clearRect(0, 0, w, h);
      pulse *= 0.96;
      for (const p of pts) {
        if (!still) { p.x += p.vx * (1 + pulse * 6); p.y += p.vy * (1 + pulse * 6); }
        if (p.x < 0 || p.x > 1) p.vx *= -1;
        if (p.y < 0 || p.y > 1) p.vy *= -1;
      }
      const R = Math.min(w, h) * 0.16;
      for (let i = 0; i < pts.length; i++) {
        const a = pts[i], ax = a.x * w, ay = a.y * h;
        for (let j = i + 1; j < pts.length; j++) {
          const b = pts[j], dx = ax - b.x * w, dy = ay - b.y * h, d = Math.hypot(dx, dy);
          if (d < R) {
            const hue = a.s === b.s ? STAGE_HUE[a.s] : pulseHue;
            ctx.strokeStyle = `hsla(${hue}, 80%, 65%, ${(1 - d / R) * (0.10 + pulse * 0.35)})`;
            ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(b.x * w, b.y * h); ctx.stroke();
          }
        }
        ctx.fillStyle = `hsla(${STAGE_HUE[a.s]}, 90%, 70%, ${0.35 + pulse * 0.5})`;
        ctx.beginPath(); ctx.arc(ax, ay, 1.4 + pulse * 1.6, 0, Math.PI * 2); ctx.fill();
      }
      if (!still) raf = requestAnimationFrame(frame);
    };
    size(); frame();
    const onResize = () => { size(); if (still) frame(); };
    const onVis = () => { cancelAnimationFrame(raf); if (!document.hidden && !still) raf = requestAnimationFrame(frame); };
    window.addEventListener("resize", onResize);
    document.addEventListener("visibilitychange", onVis);
    // every real engine event pulses the field in that stage's color
    let es: EventSource | null = null;
    if (process.env.NEXT_PUBLIC_REGEN_MODE !== "public") {
      es = new EventSource("/api/stream?after=999999999");
      es.addEventListener("narration", (m) => {
        const n = JSON.parse((m as MessageEvent).data);
        const k = ["listen", "judge", "write", "apply", "hear"].indexOf(n.stage);
        pulseHue = STAGE_HUE[Math.max(0, k)];
        pulse = n.tone === "win" ? 1 : 0.6;
        if (still) frame();
      });
    }
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", onResize); document.removeEventListener("visibilitychange", onVis); es?.close(); };
  }, []);
  return <canvas ref={ref} className="backdrop" aria-hidden />;
}
