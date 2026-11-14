"use client";
// "While you were away" (ALIVE Phase 4, docs/ALIVE_PLAN.md §5). When you come back after more than 30 minutes, the
// gap plays through the drivetrain compressed to ~30 s: each past event becomes its pulse and caption again (stream
// type "replay", which Engine draws without re-folding, so the engine ends in exactly the live state it already
// shows). A bar with play/pause, 1x/10x/60x and skip appears only while the replay runs; then it is live again.
// Source: GET /api/replay?since= (the whole gap, oldest first; past 2000 events it keeps the newest 2000 and says so).
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
const LIMIT = 2000;
/** Local ISO without zone ("2026-11-13T19:40:00"), the way the ledger writes ts. */
const local = (t: number) => { const d = new Date(t), p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`; };

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
      get<Narration[]>(`/api/replay?since=${encodeURIComponent(local(last))}&limit=${LIMIT}`).then((gap) => {
        if (gap.length) { setSince(last); setFull(gap.length >= LIMIT); setQueue(gap); }
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
      <p><b>While you were away</b> · since {hhmm(since)}{full ? ` (latest ${LIMIT} events)` : ""} · {at} / {queue.length} events · {sent} sent</p>
      <progress max={queue.length} value={at} aria-hidden />
      <div className="al-replay-ctl">
        <button type="button" onClick={() => setPlaying((p) => !p)} aria-pressed={!playing}>{playing ? "Pause" : "Play"}</button>
        {SPEEDS.map((s) => <button key={s} type="button" aria-pressed={speed === s} onClick={() => setSpeed(s)}>{s}x</button>)}
        <button type="button" onClick={() => setQueue(null)}>Skip to live</button>
      </div>
    </div>
  );
}
