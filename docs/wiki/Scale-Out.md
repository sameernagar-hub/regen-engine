# Scale-out: container appliers

Applying is the slow, stateful part of the pipeline: each applier owns one browser profile and fills forms in several
tabs. Discovery, selection, and resume tailoring are fast, so they stay in one central pipeline. Applying fans out to as
many workers as the machine (or a VM) can hold.

```
             central pipeline (host)                         workers (N containers, or local processes)
  scan -> prune -> select (freshness bands, heap) -> build
                                 |
                   split into parts (round-robin)
                    |                         |
     local appliers (Popen)      batches/inbox/<part>.json  --atomic rename-->  batches/claimed/  -> apply -> done/
                                                      ^ one worker wins each part; no broker, no lock server
  shared workspace volume: queue, events.jsonl, logs, codes/*.wait  <-- the code relay writes codes/*.txt here
```

## Why a shared inbox instead of a message broker
- `os.rename` is atomic on a single filesystem. Two workers racing for the same file can't both win, so a batch is applied
  exactly once. That's the property a broker would give us, at zero cost and with zero extra services.
- A part is written as `.<name>.json` and then renamed into place, so a worker never reads a half-written file.
- Each part lands in `done/` after it finishes. The pipeline waits for every part, with a timeout, so a crashed
  worker can't stall the loop.

## Run it
```bash
docker compose -f deploy/appliers.compose.yml up -d --build --scale applier=4
REGEN_DOCKER_PARTS=4 python -m engine run --days 1 --max 120 --appliers 6 --tabs 4 --loop 10
```
- `REGEN_DOCKER_PARTS=K`: K parts go to containers and `--appliers` local browsers take the rest (hybrid).
- `REGEN_APPLIERS=docker`: every part goes to containers.
- Stop the workers after their current batch: create `workspace/batches/STOP`.

## Inside a worker
- `python:3.12-slim` plus Playwright Chromium and Xvfb. The browser runs **headed** on a virtual display, because some ATSs
  flag headless browsers.
- Runs as an unprivileged user. `profile/` is mounted **read-only**; the browser profile lives inside the container,
  never on the shared volume.
- Resource limits per worker: 1.5 CPU, 2 GB RAM, 1 GB `/dev/shm` (Chromium needs more than Docker's 64 MB default).

## Sizing
One worker with 3 tabs uses about 1.2 to 1.6 GB. Docker Desktop's VM memory is the ceiling: with 8 GB, run 4 workers
next to the host's local appliers.

## Email codes at scale
Workers write `workspace/codes/<board>_<id>.wait` to the shared volume. The [code relay](Email-Codes) on the host
answers within about 20 s, whichever container asked.

## The bank: data in Docker volumes (v0.12)
`deploy/bank.compose.yml` keeps your data in named volumes instead of local folders: `regen-profile` holds the
knowledge and `regen-workspace` holds the ledger. `seed` copies local folders in once and never deletes them. The `relay`
container receives codes from the Gmail tab. Back up the volumes before any `docker volume prune`: a pruned volume
is gone. Back-up commands are in the compose file header.
