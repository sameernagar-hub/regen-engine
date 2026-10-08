# Algorithms and complexity

Symbols: J jobs in a batch, S jobs sleeping, B CPU bursts, T vocabulary terms (~200), F Fact Bank entries, k facts in
a pool, n characters in a job description, E events in the log, A applications, N graph nodes.

## The problem: applying is mostly waiting
Profiling real applications showed the browser idle most of the time: the ATS parses the resume (Ashby ~6 s),
location boxes search remotely, the submit confirmation takes seconds, and a Greenhouse email code can take a minute.
Doing jobs one at a time wastes all of it. The answer is the same one operating systems use for processes waiting on
I/O: **time-sharing**.

## Round-robin with I/O blocking (`engine/apply/scheduler.py`)
Each application is a Python **generator** running in its own tab:
- `yield` is a checkpoint: "you may pause me here" (after each form field).
- `yield 6.0` is a wait: "the site needs 6 s"; the job sleeps and another runs.

```
ready  : deque of runnable jobs           pick = popleft      O(1)
sleep  : min-heap of (wake_time, job)     block = heappush    O(log S)
                                          wake  = heappop     O(log S)
tabs   : at most REGEN_TABS jobs hold a tab; the rest wait in a pending deque
```
A job runs until (a) it yields a wait → it goes on the heap, or (b) it reaches a checkpoint after using its quantum →
it goes to the back of the ready queue (preemption), or (c) it finishes → its tab goes to the next pending job.
If nothing is ready, the scheduler sleeps exactly until the earliest wake time. A job that raises is recorded and the
others continue. Whole batch: O(B log J) time, O(J) memory.

It is **cooperative**: a single browser call (a page load, a click) cannot be interrupted, so preemption happens at
checkpoints. Long browser calls are bounded by Playwright timeouts (15 s actions, 45 s navigation).

## Choosing the quantum
Too small and switching costs dominate; too large and round-robin degrades to first-come-first-served (one slow form
blocks everyone). The classic rule of thumb: **about 80% of CPU bursts should complete within one quantum.**

Burst lengths differ per ATS (Greenhouse forms have many searchable dropdowns; Lever forms are short), so the
scheduler learns a quantum per ATS with an exponentially weighted mean and variance (West, 1979):

```
d     = burst - mean
mean' = mean + α·d
var'  = (1 - α)·(var + α·d²)          α = 0.2, O(1) time and memory, no history stored
quantum = clamp(mean + 0.8416·sqrt(var), 2 s, 20 s)    # 0.8416 = z for the 80th percentile
```
Until a key has 3 samples the default (6 s) is used. Stats persist in `workspace/sched_stats.json`.

### Measurements
`python scripts/bench_scheduler.py` replays a seeded mix of jobs whose bursts and waits come from the real flows,
on a deterministic clock (no browser), so the numbers are exact and reproducible:

| Batch | Sequential | Round-robin | Speed-up | Browser busy |
|---|---|---|---|---|
| 20 jobs, 3 tabs | 500 s · 144 jobs/h | 244 s · 295 jobs/h | ×2.05 | 29% → 60% |
| 40 jobs, 4 tabs | 989 s · 146 jobs/h | 395 s · 365 jobs/h | ×2.50 | 32% → 80% |

Real forms are slower than the simulation in absolute terms; the ratio is what the scheduler buys. Every real run logs
a `schedule` event (wall time, active time, switches, per-job slices, quanta), so real throughput is on record too.

### Company interleaving
Before scheduling, the batch is reordered round-robin over companies (a dict of deques, O(J)): `A1 A2 A3 B1 C1` →
`A1 B1 C1 A2 A3`. Per-company caps and bot detectors then see spread-out traffic.

## Tailoring (`engine/tailoring/tailor.py`)
Scoring a fact = how many of the job's technologies it mentions, with whole-word matching.

| Step | Before | After |
|---|---|---|
| vocabulary of the candidate's terms | rebuilt every call | cached per loaded Fact Bank: O(1) |
| hits of T terms in a text of length n | per term: escape + regex-cache lookup + scan | compiled pattern per term, cached, behind a `term in text` substring test (C-speed); regex only confirms boundaries. Same O(T·n) worst case, far fewer regex scans in practice |
| ranking a pool of k facts | `list.index` in the sort key: O(k² log k) | precomputed positions: O(k log k); each text matched once per JD (memo) |
| overlap groups (no duplicate accomplishments) | O(k · groups · picked) | fact → group-id dict: O(k) |
| "is stack X missing from the bank?" | per JD | once per vocabulary |

Measured on 155 real job descriptions with **identical output** (`scripts/bench_tailor.py` asserts it):
`tailor()` 74.3 → 24.3 ms (×3.1), `fit()` 21.8 → 15.1 ms (×1.4).

Why not Aho-Corasick? With T ≈ 200 short terms and n ≈ 5–15 KB, the substring prefilter already rejects most terms
in a single memchr-style pass; a trie would add a dependency and complexity for little gain at this size. It becomes
worth it if the vocabulary grows by an order of magnitude.

## The event log (`engine/feedback/events.py`)
- **Writes:** an exclusive cross-process lock on `events.jsonl.lock` (`msvcrt.locking` on Windows, `flock` elsewhere),
  then one `os.write` of the whole line on an `O_APPEND` descriptor. Found the hard way: on Windows, Python's append
  mode is "seek to end, then write", and two processes overwrote each other's lines.
- **Reads:** incremental. The reader keeps the parsed events and the byte offset; each call parses only the bytes
  appended since (O(new lines)), leaves a half-written last line for next time, skips malformed lines and counts them,
  and starts over if the file shrinks or is replaced. The per-job rate cap and duplicate check used to re-read the whole
  log for every job (O(J·E)); now it's O(E) once plus O(new) per job.

## The knowledge graph (`engine/memory/graph.py`)
One pass over the events into dicts: O(E). Linking each lane to "You" once uses a set (the old version scanned every
edge for every application, O(A·E)). `neighbors()` is one O(N + E) pass.

## Drafted answers (`engine/apply/drafts.py`)
No model, no network: load the job's resume spec (O(F)), classify the question with a few regexes, assemble Fact Bank
sentences. Microseconds, against seconds for a page load.
