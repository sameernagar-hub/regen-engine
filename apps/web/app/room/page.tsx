"use client";
// The engine room: one room per stage, laid out the way work flows through the engine, with the inbox looping back
// into the fit gate (every rejection becomes a rule). A room lights up the moment its stage logs an event; each room
// opens into its own page, and every line inside opens the job it is about.
import Link from "next/link";
import { Nav } from "../nav";
import { TONE, jobHref, useStations, when } from "@/lib/room";

export default function Room() {
  const { stations, beat, error } = useStations(4);
  return (
    <main className="page">
      <Nav />
      <header className="hero">
        <h1>Engine room</h1>
        <p>Five rooms, one pipeline. Rooms light up as the engine works; open any room to watch it up close, then any line to see that job end to end.</p>
      </header>
      {error && <p className="err" role="status">API unreachable ({error}). Start it: <code>uvicorn apps.api.main:app --port 8787</code></p>}
      {!stations && !error && <p className="dim">Connecting to the engine…</p>}
      {stations && (
        <ol className="rooms" aria-label="Pipeline stations, in order">
          {stations.map((s, i) => {
            const hot = beat?.stage === s.key;
            const tones = Object.entries(s.tones).sort((a, b) => b[1] - a[1]);
            const sum = tones.reduce((n, [, v]) => n + v, 0) || 1;
            return (
              <li key={s.key} className={`room${hot ? " hot" : ""}`} data-stage={s.key} style={{ ["--i" as any]: i }}>
                <Link href={`/room/${s.key}`} className="room-head">
                  <span className="room-no">0{i + 1}</span>
                  <h2>{s.name}</h2>
                  <span className="room-count"><b>{s.today}</b> today · {s.total} total</span>
                </Link>
                <p className="room-about">{s.about}</p>
                <div className="tonebar" aria-label="Outcomes at this station">
                  {tones.map(([t, v]) => <i key={t} title={`${t}: ${v}`} style={{ flexGrow: v / sum, background: TONE[t] }} />)}
                </div>
                <ul className="room-lines">
                  {s.recent.slice(0, 3).map((l) => (
                    <li key={l.id}>
                      <Link href={jobHref(l.url)} style={{ color: TONE[l.tone] }}><time>{when(l.ts)}</time> {l.text}</Link>
                    </li>
                  ))}
                  {!s.recent.length && <li className="dim">Quiet so far.</li>}
                </ul>
                <Link href={`/room/${s.key}`} className="enter">Enter {s.name.toLowerCase()} →</Link>
                {i < stations.length - 1 && <span className="flow" aria-hidden />}
              </li>
            );
          })}
        </ol>
      )}
      {stations && (
        <p className="loop">
          <span aria-hidden>↺</span> The inbox feeds back: rejections are read against their job descriptions and become new
          fit-gate rules, so the same miss never repeats. <Link href="/room/hear">See the inbox →</Link>
        </p>
      )}
    </main>
  );
}
