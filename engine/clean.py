"""Disk hygiene: delete the engine's own regenerable files once they are logged. Nothing outside workspace/ is touched.

    python -m engine clean [--dry]

Retention policy (user, 10-11). The event log keeps the record: job, status, resume name, proof name, answers.
  proof/*.png            older than PROOF_DAYS (90)   confirmation screenshots: the evidence a submission happened
  out/*.pdf              older than RESUME_DAYS (3)   tailored resumes; rebuilt from the Fact Bank on demand
  jd/*                   older than JD_DAYS (14)      cached job descriptions
  logs/*.log             older than LOG_DAYS (14)
  codes/*                older than CODE_DAYS (1)     email codes and waits: useless (and sensitive) after a day
  batches/done/*, batches/*.json older than 2 days
  pw-profile*/**/{Cache, Code Cache, GPUCache, CacheStorage}   browser caches (cookies and logins stay)
What stays: events.jsonl, queue.json, seen.json, profile/ (never touched), quarantine/ (the user reviews it),
anything newer than its window. Each window can be overridden with REGEN_KEEP_<NAME>_DAYS (e.g. REGEN_KEEP_PROOF_DAYS).
The supervisor runs it hourly. O(files under workspace).
"""
import os, shutil, sys, time

from engine.config import WORKSPACE

def _days(name, default):
    return float(os.environ.get(f"REGEN_KEEP_{name}_DAYS", default))


PROOF_DAYS, RESUME_DAYS, JD_DAYS, LOG_DAYS, BATCH_DAYS, CODE_DAYS = (
    _days("PROOF", 90), _days("RESUME", 3), _days("JD", 14), _days("LOG", 14), _days("BATCH", 2), _days("CODE", 1))
CACHE_DIRS = {"Cache", "Code Cache", "GPUCache", "CacheStorage", "ShaderCache", "GrShaderCache"}


def _inside(path):
    """Every delete is checked against the workspace root (no symlink escapes)."""
    root = os.path.realpath(WORKSPACE)
    return os.path.realpath(path).startswith(root + os.sep)


def _old_files(sub, days, exts=None):
    d = os.path.join(WORKSPACE, sub)
    if not os.path.isdir(d):
        return
    cut = time.time() - days * 86400
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.path.getmtime(p) < cut and (exts is None or name.lower().endswith(exts)):
            yield p


def plan():
    """(files, dirs) that would be removed."""
    files = []
    files += _old_files("proof", PROOF_DAYS, (".png", ".jpg", ".jpeg"))
    files += _old_files("out", RESUME_DAYS, (".pdf", ".docx"))
    files += _old_files("jd", JD_DAYS)
    files += _old_files("logs", LOG_DAYS, (".log",))
    files += _old_files("codes", CODE_DAYS)
    files += _old_files(os.path.join("batches", "done"), BATCH_DAYS, (".json",))
    files += _old_files("batches", BATCH_DAYS, (".json",))
    dirs = []
    for name in os.listdir(WORKSPACE):
        if name.startswith("pw-profile") and os.path.isdir(os.path.join(WORKSPACE, name)):
            for root, subdirs, _ in os.walk(os.path.join(WORKSPACE, name)):
                for s in list(subdirs):
                    if s in CACHE_DIRS:
                        dirs.append(os.path.join(root, s))
                        subdirs.remove(s)
    keep = pending_resumes()
    return [f for f in files if _inside(f) and os.path.basename(f) not in keep], [d for d in dirs if _inside(d)]


def pending_resumes():
    """Resume file names a batch that has not finished still points at (inbox, claimed, or a local run's batch file
    from the last 2 days): never delete those, or that job fails with "Missing entry: Resume"."""
    import json
    names = set()
    for sub in ("batches/inbox", "batches/claimed", "batches"):
        d = os.path.join(WORKSPACE, sub)
        if not os.path.isdir(d):
            continue
        for n in os.listdir(d):
            p = os.path.join(d, n)
            if n.endswith(".json") and os.path.isfile(p) and (sub != "batches" or time.time() - os.path.getmtime(p) < BATCH_DAYS * 86400):
                try:
                    for j in json.load(open(p, encoding="utf-8")):
                        if isinstance(j, dict) and j.get("resume"):
                            names.add(os.path.basename(j["resume"].replace("\\", "/")))
                except (ValueError, OSError):
                    pass
    return names


def size(p):
    if os.path.isfile(p):
        return os.path.getsize(p)
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs if os.path.exists(os.path.join(r, f)))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    files, dirs = plan()
    total = sum(size(p) for p in files + dirs)
    if "--dry" not in argv:
        for f in files:
            try:
                os.remove(f)
            except OSError:
                pass  # in use by a running applier: next clean gets it
        for d in dirs:
            shutil.rmtree(d, ignore_errors=True)
    print(f"clean{' (dry)' if '--dry' in argv else ''}: {len(files)} files + {len(dirs)} cache dirs, {total / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
