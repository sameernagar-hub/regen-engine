"use client";
// "While you were away" (ALIVE Phase 4, docs/ALIVE_PLAN.md §5). When you come back after more than 30 minutes, the
// gap plays through the drivetrain compressed to ~30 s: each past event becomes its pulse and caption again (stream
// type "replay", which Engine draws without re-folding, so the engine ends in exactly the live state it already
// shows). A bar with play/pause, 1x/10x/60x and skip appears only while the replay runs; then it is live again.
// Source: /api/narration (newest 500). If the gap holds more, the bar says it plays the latest 500.
// Last seen lives in localStorage (per browser, a convenience only; without it nothing replays).
import { useEffect, useState } from "react";
import { replay } from "@/lib/stream";
import { get } from "@/lib/types";
import type { Narration } from "@/lib/spine";

const KEY = "alive:lastSeen";
const AWAY_MS = 30 * 60 * 1000;
const BASE_MS = 30000;  // the whole gap at 1x
const SPEEDS = [1, 10, 60];

const seen = (): number | null => { try { const v = localStorage.getItem(KEY); return v ? Number(v) : null; } catch { return null; } };
const mark = () => { try { localStorage.setItem(KEY, String(Date.now())); } catch { /* storage blocked: no replay next time */ } };
const hhmm = (t: number) => new Date(t).toTimeString().slice(0, 5);

export function Replay() {
  const [queue, setQueue] = useState<Narration[] | null>(null);
  const [since, setSince] = useState(0);
  const [full, setFull] = useState(false);
  const [at, setAt] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);

  // on open: was the tab away long enough? then fetch the gap; keep "last seen" fresh while visible
  useEffect(() => {
    const last = seen();
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (last && Date.now() - last > AWAY_MS && !reduced) {
      get<Narration[]>("/api/narration?limit=500").then((ns) => {
        const gap = ns.filter((n) => n.ts && new Date(n.ts).getTime() > last);
        if (gap.length) { setSince(last); setFull(gap.length === ns.length && ns.length >= 500); setQueue(gap); }
      }).catch(() => { /* no history: stay live */ });
    }
    mark();
    const t = setInterval(() => { if (!document.hidden) mark(); }, 60000);
    const bye = () => mark();
    window.addEventListener("pagehide", bye);
    return () => { clearInterval(t); window.removeEventListener("pagehide", bye); };
  }, []);

  // the player: one event per step; the step length spreads the gap over BASE_MS / speed
  useEffect(() => {
    if (!queue || !playing || at >= queue.length) return;
    const step = Math.max(16, BASE_MS / queue.length / speed);
    const t = setTimeout(() => { replay(queue[at]); setAt((i) => i + 1); }, step);
    return () => clearTimeout(t);
  }, [queue, playing, at, speed]);
  useEffect(() => { if (queue && at >= queue.length) { const t = setTimeout(() => setQueue(null), 1200); return () => clearTimeout(t); } }, [queue, at]);

  if (!queue) return null;
  const sent = queue.slice(0, at).filter((n) => n.kind === "submitted").length;
  return (
    <div className="al-replay" role="region" aria-label="While you were away">
      <p><b>While you were away</b> · since {hhmm(since)}{full ? " (latest 500 events)" : ""} · {at} / {queue.length} events · {sent} sent</p>
      <progress max={queue.length} value={at} aria-hidden />
      <div className="al-replay-ctl">
        <button type="button" onClick={() => setPlaying((p) => !p)} aria-pressed={!playing}>{playing ? "Pause" : "Play"}</button>
        {SPEEDS.map((s) => <button key={s} type="button" aria-pressed={speed === s} onClick={() => setSpeed(s)}>{s}x</button>)}
        <button type="button" onClick={() => setQueue(null)}>Skip to live</button>
      </div>
    </div>
  );
}
