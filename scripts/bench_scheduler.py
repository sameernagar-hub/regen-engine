"""Scheduler benchmark: the same simulated batch run one job at a time vs round-robin over N tabs.

    python scripts/bench_scheduler.py [jobs=20] [tabs=3] [seed=7]

Each simulated application is a sequence of CPU bursts (filling fields) and waits (the site working), with
durations taken from the real flows in engine/apply/runner.py:
    Ashby       load 2 s, resume parse 6 s wait, ~12 fields x 0.4 s, answer pass 1 s wait, submit poll ~4 s wait
    Greenhouse  load 2 s, upload 2.5 s wait, ~18 fields x 0.5 s, submit ~3 s wait, 30% need an email code (~45 s wait)
    Lever       load 1.5 s wait, upload ~3 s wait, ~10 fields x 0.4 s, submit ~2 s wait
A deterministic fake clock is used, so the numbers are exact and reproducible (no browser involved).
Reports wall time, throughput (jobs/hour), browser utilization and context switches.
"""
import os, random, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.apply.scheduler import Quantum, RoundRobin, Task


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def profile(rng, ats):
    work = lambda s: ("work", s * rng.uniform(0.8, 1.25))
    wait = lambda s: ("wait", s * rng.uniform(0.8, 1.25))
    if ats == "ashby":
        steps = [work(2), wait(6)] + [work(0.4)] * 12 + [wait(1)] + [work(0.4)] * 3 + [wait(4)]
    elif ats == "greenhouse":
        steps = [work(2), wait(2.5)] + [work(0.5)] * 18 + [wait(3)]
        if rng.random() < 0.3:
            steps += [wait(45), work(0.5), wait(3)]
    else:
        steps = [wait(1.5), wait(3)] + [work(0.4)] * 10 + [wait(2)]
    return steps


def make(clock, steps):
    def factory(res):
        def g():
            for kind, s in steps:
                if kind == "work":
                    clock.t += s
                    yield
                else:
                    yield s
        return g()
    return factory


def run(jobs, tabs):
    clock = Clock()
    rr = RoundRobin(Quantum(), concurrency=tabs, clock=clock, sleep=clock.sleep)
    tasks = [Task(f"job{i}", ats, make(clock, steps)) for i, (ats, steps) in enumerate(jobs)]
    done = rr.run(tasks, [f"tab{i}" for i in range(tabs)])
    busy = sum(t.active for t in done)
    return clock.t, busy, rr.switches


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    tabs = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 7)
    jobs = [(a, profile(rng, a)) for a in (rng.choice(["ashby", "greenhouse", "greenhouse", "lever"]) for _ in range(n))]
    print(f"{n} simulated applications (seeded), tabs = 1 vs {tabs}")
    print(f"{'mode':<22}{'wall (s)':>10}{'jobs/hour':>11}{'browser busy':>14}{'switches':>10}")
    base = None
    for t in (1, tabs):
        wall, busy, sw = run(jobs, t)
        base = base or wall
        print(f"{('sequential' if t == 1 else f'round-robin x{t}'):<22}{wall:>10.0f}{n / wall * 3600:>11.0f}{busy / wall:>13.0%}{sw:>10}"
              + ("" if t == 1 else f"   speed-up x{base / wall:.2f}"))


if __name__ == "__main__":
    main()
