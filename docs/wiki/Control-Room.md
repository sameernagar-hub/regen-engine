# Control room (web)

The web app (`apps/web`, Next.js 16 + React 19.3) is the engine's front face. It reads the same append-only log as
the CLI through the REST API (`apps/api`, FastAPI), and its few writes are guarded: `REGEN_API_WRITE=1` on your
machine **and** a request from localhost.

| Page | What you see | Data |
|---|---|---|
| `/control` | pipeline strip (the running stage glows), run settings (days, max, appliers, tabs, cap, rescan interval, sources, ATSs, dry run), Start / Stop, queue by ATS, live applier cards (each tab's job and state, latest answers), run log, editable title/company filters | `GET /api/control/state` every 2 s, `POST /api/control/run`, `/stop`, `GET/POST /api/control/filters` |
| `/applications` | every application with status filters and search; select one to see the **resume PDF that was sent**, every question with the answer given, Fact Bank ids used, proof screenshot | `GET /api/applications`, `GET /api/resume/{file}`, `GET /api/proof/{file}` |
| `/facts` | the Fact Bank as a radial map (you → roles → facts, sized by use, colored by lane), every fact with usage bars, skills, sources | `GET /api/factbank` |
| `/room`, `/room/[stage]`, `/job` | each stage as a room with its live log; one job's full timeline | `/api/stations`, `/api/job` |
| `/graph` | the knowledge graph, layer by layer | `/api/graph` |

## Design system (v0.11)
- **Living backdrop**: a canvas field whose points belong to the five stages; every real engine event (SSE) pulses
  it in that stage's color. Paused when the tab is hidden; a still frame under reduced motion.
- **Page morphs**: React `ViewTransition` wraps every page; the title, brand and the nav underline carry
  view-transition names, so navigation morphs instead of cutting.
- **Aurora type** (`@property --spin` conic gradient), **glass surfaces** with gradient hairlines,
  **scroll-driven reveals** (`animation-timeline: view()`), a scroll-progress hairline, container-query bento grids.
- Accessibility: keyboard paths, visible focus, `prefers-reduced-motion` and `prefers-contrast` fallbacks.

## Run it
```bash
REGEN_API_WRITE=1 python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787
npm --prefix apps/web run dev     # http://127.0.0.1:3000/control
```
