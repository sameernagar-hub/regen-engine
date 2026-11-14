"use client";
// Alive in the tab (ALIVE Phase 6, docs/ALIVE_PLAN.md §5): the browser tab says what the engine is doing while you are
// on another tab. The title reads "REGEN · 3 sent · 2 yours" (sent today from the cap counter, yours = what waits on
// you) and is written only when it changes; the favicon is a tiny gold flywheel that turns once per submission.
// Both are driven by the stream: a `submitted` narration re-reads the cap, a `parked` one re-reads /api/human.
// Mounted from the ALIVE home only, so the released v1.x site (web :3000) is untouched.
import { useEffect } from "react";
import { subscribe } from "@/lib/stream";
import { get } from "@/lib/types";
import type { Narration } from "@/lib/spine";

/** Draw the flywheel at angle `a` (radians) into a 32 px canvas and return it as a PNG data URL. */
function wheel(a: number): string {
  const c = document.createElement("canvas");
  c.width = c.height = 32;
  const g = c.getContext("2d");
  if (!g) return "";
  g.translate(16, 16);
  g.fillStyle = "#17130b"; g.strokeStyle = "#f2c14e"; g.lineWidth = 3;
  g.beginPath(); g.arc(0, 0, 13, 0, Math.PI * 2); g.fill(); g.stroke();
  g.rotate(a); g.strokeStyle = "#c99a2e"; g.lineWidth = 2.5;
  for (let i = 0; i < 4; i++) { g.rotate(Math.PI / 4); g.beginPath(); g.moveTo(0, -11); g.lineTo(0, 11); g.stroke(); }
  g.fillStyle = "#f2c14e"; g.beginPath(); g.arc(0, 0, 4, 0, Math.PI * 2); g.fill();
  return c.toDataURL("image/png");
}

function setIcon(href: string) {
  if (!href) return;
  let link = document.querySelector<HTMLLinkElement>("link[rel~='icon'][data-alive]");
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon"; link.dataset.alive = "1";
    document.head.appendChild(link);
  }
  link.href = href;
}

export function TabPulse() {
  useEffect(() => {
    let alive = true, sent: number | null = null, yours: number | null = null, spin: number | undefined;
    const write = () => {
      if (sent === null && yours === null) return;
      const t = `REGEN · ${sent ?? "–"} sent · ${yours ?? "–"} yours`;
      if (document.title !== t) document.title = t;  // only when it changed
    };
    const pullSent = () => get<{ today: number }>("/api/control/cap").then((c) => { if (alive) { sent = c.today; write(); } }).catch(() => {});
    const pullYours = () => get<unknown[]>("/api/human").then((h) => { if (alive) { yours = h.length; write(); } }).catch(() => {});
    const turn = () => {  // one quarter turn over ~0.8 s; reduced motion: no animation, the title still updates
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      clearInterval(spin);
      let f = 0;
      spin = window.setInterval(() => { f += 1; setIcon(wheel((f / 8) * (Math.PI / 2))); if (f >= 8) clearInterval(spin); }, 100);
    };
    setIcon(wheel(0));
    pullSent(); pullYours();
    const unsub = subscribe((type, data) => {
      if (type !== "narration") return;
      const k = (data as Narration).kind;
      if (k === "submitted") { pullSent(); pullYours(); turn(); }
      else if (k === "parked" || k === "shadow.answer") pullYours();
    });
    return () => { alive = false; unsub(); clearInterval(spin); };
  }, []);
  return null;
}
