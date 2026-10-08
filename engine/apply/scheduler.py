"""Round-robin scheduler for applications: every job gets a time quantum, then the next job runs.

Why: a single application spends most of its wall time *waiting*: the ATS parsing the resume (Ashby ~6 s),
location autocomplete, the submit confirmation (up to 25 s), a Greenhouse email code (minutes). Run one job
at a time and the browser idles through all of it. Here each job is a generator running in its own tab:

    yield            checkpoint: "I can be paused here" (between form fields)
    yield 6.0        "I'm waiting 6 s for the site": the job sleeps, another job runs meanwhile

A job keeps the CPU until its quantum is used up at a checkpoint (preempted -> back of the ready queue) or
it starts a wait (blocked -> sleep heap until its wake time). This is round-robin (RR) with I/O blocking,
as in an OS scheduler, cooperative because a browser call can't be interrupted halfway.

Adaptive quantum (per ATS): the textbook rule is that ~80% of CPU bursts should finish inside one quantum
(too small -> switching overhead dominates; too large -> RR degrades to first-come-first-served). Bursts
are tracked with an exponentially weighted mean and variance (O(1) time and space per update), and
quantum = mean + 0.84 * stddev (the 80th percentile of a normal), clamped to [Q_MIN, Q_MAX].

Complexity, with J jobs, S sleeping jobs, B bursts:
    pick next ready job     O(1)       deque.popleft
    preempt                 O(1)       deque.append
    block / wake            O(log S)   heapq push / pop
    quantum update          O(1)       EWMA, constant memory per ATS key
    whole run               O(B log J) time, O(J) memory (only `concurrency` tabs are open at once)
"""
import collections, heapq, itertools, json, math, os, time

Q_MIN, Q_MAX, Q_DEFAULT = 2.0, 20.0, 6.0
Z80 = 0.8416  # standard normal 80th percentile


class Quantum:
    """Per-key EWMA of burst lengths -> quantum. Persisted as {key: [mean, var, n]} so it learns across runs."""

    def __init__(self, path=None, alpha=0.2):
        self.path, self.alpha, self.stats = path, alpha, {}
        if path and os.path.exists(path):
            try:
                self.stats = {k: list(v) for k, v in json.load(open(path)).items()}
            except (OSError, ValueError):
                self.stats = {}

    def update(self, key, burst):
        """West's EWMA variance: one pass, O(1) memory, no stored history."""
        if burst <= 0:
            return
        s = self.stats.get(key)
        if not s:
            self.stats[key] = [burst, 0.0, 1]
            return
        mean, var, n = s
        d = burst - mean
        inc = self.alpha * d
        self.stats[key] = [mean + inc, (1 - self.alpha) * (var + d * inc), n + 1]

    def get(self, key):
        s = self.stats.get(key)
        if not s or s[2] < 3:  # too few samples to trust: fall back to the default
            return Q_DEFAULT
        return min(Q_MAX, max(Q_MIN, s[0] + Z80 * math.sqrt(max(s[1], 0.0))))

    def save(self):
        if self.path:
            json.dump({k: [round(x, 4) for x in v[:2]] + [v[2]] for k, v in self.stats.items()}, open(self.path, "w"), indent=1)


class Task:
    __slots__ = ("name", "key", "gen", "factory", "result", "error", "slices", "active", "waited", "started", "ended", "preempted")

    def __init__(self, name, key, factory):
        self.name, self.key, self.factory, self.gen = name, key, factory, None
        self.result = self.error = None
        self.slices = self.preempted = 0
        self.active = self.waited = 0.0
        self.started = self.ended = None

    def stats(self):
        wall = (self.ended or 0) - (self.started or 0)
        return {"job": self.name, "key": self.key, "slices": self.slices, "preempted": self.preempted,
                "active_s": round(self.active, 2), "waited_s": round(self.waited, 2), "wall_s": round(wall, 2)}


class RoundRobin:
    """run(tasks) -> list of finished tasks. `factory(resource)` builds a task's generator once a resource
    (a browser tab) is free, so at most `concurrency` jobs hold a tab at any time."""

    def __init__(self, quantum=None, concurrency=3, clock=time.monotonic, sleep=time.sleep, on_switch=None):
        self.q = quantum or Quantum()
        self.concurrency, self.clock, self.sleep, self.on_switch = concurrency, clock, sleep, on_switch
        self.switches = 0

    def run(self, tasks, resources):
        pending = collections.deque(tasks)
        free = collections.deque(resources[: self.concurrency])
        ready, sleeping, done = collections.deque(), [], []
        seq = itertools.count()  # heap tiebreak: never compares Task objects
        held = {}

        def admit():
            while pending and free:
                t = pending.popleft()
                res = free.popleft()
                held[id(t)] = res
                t.started = self.clock()
                t.gen = t.factory(res)
                ready.append(t)

        def finish(t):
            t.ended = self.clock()
            free.append(held.pop(id(t)))
            done.append(t)
            admit()

        admit()
        while ready or sleeping:
            now = self.clock()
            while sleeping and sleeping[0][0] <= now:
                _, _, t, since = heapq.heappop(sleeping)
                t.waited += now - since
                ready.append(t)
            if not ready:
                self.sleep(max(0.0, sleeping[0][0] - now))
                continue
            t = ready.popleft()
            if self.on_switch:
                self.on_switch(t, held.get(id(t)))  # e.g. bring the job's tab to the front
            self.switches += 1
            t.slices += 1
            q, start = self.q.get(t.key), self.clock()
            while True:
                try:
                    y = next(t.gen)
                except StopIteration as stop:
                    t.result = stop.value
                    burst = self.clock() - start
                    t.active += burst
                    self.q.update(t.key, burst)
                    finish(t)
                    break
                except Exception as e:  # one job's failure never stops the others
                    t.error = e
                    t.active += self.clock() - start
                    finish(t)
                    break
                now = self.clock()
                if y:  # blocking wait: sleep, let another job run
                    burst = now - start
                    t.active += burst
                    self.q.update(t.key, burst)
                    heapq.heappush(sleeping, (now + float(y), next(seq), t, now))
                    break
                if now - start >= q:  # quantum used up at a checkpoint: preempt
                    t.active += now - start
                    t.preempted += 1
                    self.q.update(t.key, now - start)
                    ready.append(t)
                    break
        self.q.save()
        return done


def wait(seconds):
    """Inside a job generator: `yield from wait(6)` instead of time.sleep(6)."""
    yield float(seconds)


def poll(check, timeout, every=1.0):
    """Inside a job generator: wait until check() is truthy (checked every `every` s), or the timeout.
    Returns check()'s last value. Each wait yields, so other jobs run while this one polls."""
    deadline = time.monotonic() + timeout
    while True:
        v = check()
        if v or time.monotonic() >= deadline:
            return v
        yield every
