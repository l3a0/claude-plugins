#!/usr/bin/env python3
"""Run a batch of hand-written mutants in one call, scoped to the tests that reach each one.

    python mutate.py SPEC.json [--only NAME ...] [--no-escalate] [--escalate-full]
                     [--workers N] [--out DIR]

The spec is JSON:

    {
      "root": "/path/to/worktree",            # the checkout to mutate; must be a git worktree
      "python": ".venv/bin/python",           # relative to root, or absolute
      "baseline": ["tests/a.py", "tests/b.py"],     # pytest args run once, unmutated
      "select": ["tests/a.py", "-k", "entitlement"],  # default pytest args per mutant
      "escalate": ["tests"],                  # optional: pytest args a survivor is re-run against
      "timeout": 300,                         # seconds per test run, see below for scripts
      "workers": 8,                           # optional: pytest-xdist workers on wide runs
      "workers_min_secs": 10,                 # optional: see below
      "mutants": [
        {"name": "ignore batch_size",
         "file": "src/pkg/mod.py",
         "edits": [["batch_size=batch_size, ", ""]],
         "select": ["tests/a.py", "-k", "batch"]}   # optional, overrides the default
      ]
    }

Each edit is an exact [old, new] string pair. ``old`` must occur exactly once in the file,
or the mutant is reported NOT-APPLIED and nothing is written. Every mutated file is restored
from a byte copy taken before the run, never from git, and the restore is checked byte for
byte. ``__pycache__`` is cleared after every write, because a same-length edit can keep a
stale bytecode file and fake a survivor.

A red baseline stops the run, because a baseline that already fails makes every mutant read
as caught. Survivors are re-run one at a time against ``escalate``. Mutants cannot share a
run, since two survivors applied together can mask each other and a failure cannot be
attributed.

Escalation is scoped by coverage by default. The ``escalate`` selection runs once, unmutated,
with the ``cover_map`` plugin from this directory, which records which tests start each
function in the mutated files. A survivor is then re-run only against the tests that start
the function its edits change. The one assumption is that a test which never starts the
mutated function cannot observe the mutation. Three cases fall back to the full ``escalate``
run for that mutant: an edit outside every function body, a function that runs outside any
test (at import or collection), and a file the map run never imported. The map credits a
function started by a wider-than-function fixture to every test using that fixture, and
adds every test that spawns a process to every selection. A survivor no test starts is
reported UNREACHED without a run. A red map run skips escalation, exit code 3.
``--escalate-full`` restores the full run per survivor. Coverage needs Python 3.12 in the
target interpreter, and an older one falls back to the full run.

``workers`` (or ``--workers N``, which wins) passes ``-n N`` to pytest-xdist on the wide runs
only: the map run, every full-escalation run, and a coverage-scoped escalation whose tests
took at least ``workers_min_secs`` (default 10) in the map run. The baseline and the
per-mutant runs stay serial, because starting workers costs 2 to 3 s and a narrow run takes
about 5 s. Under xdist each worker writes its own map and the plugin merges them. When the
target interpreter cannot import xdist, the runner says so and runs everything serially.
Without the key nothing changes. Leave ``-n`` out of ``escalate`` itself, or every scoped
escalation pays the worker startup.

``"runner": "script"`` runs a suite of plain test scripts instead of pytest. Each selection is
then one command, a list of arguments the target interpreter runs, such as
``["tests/test_x.py"]``, or a list of such commands that must all pass. Each command reads an
empty stdin. A run is green when every command exits 0. Its failures are the output lines that
match ``fail_pattern``, by default ``^(?:FAIL|ERROR)(?:ED)?\b.*``, which reads ``FAIL``,
``FAILED`` and ``unittest``'s ``ERROR:`` lines, and a command that exits
non-zero with no such line is named by its last line of output. ``timeout`` is one budget for
all the commands of a selection, and a run that has already failed when the budget runs out
reads red, not timeout. The baseline and escalation run the whole suite, so they run under
``escalate_timeout``, which defaults to twice ``timeout``. Escalation runs the full ``escalate``
selection, because the coverage map is a pytest plugin.
Workers are not used.

Every mutated ``file`` must resolve inside ``root`` and have no second hard link, or the run stops
before it writes anything. SIGINT (Ctrl-C), SIGTERM and SIGHUP restore every file before the runner exits, and any of
them arriving during that last restore is ignored. SIGKILL cannot be caught, so after one, copy each
file back from ``backup/`` in --out, where ``a/b.py`` is saved as ``a__b.py``. The runner prints
the --out path before the baseline runs.

Output: one line per mutant on stdout, ``results.jsonl`` and ``results.txt`` in --out, and
``cover_map.json`` when escalation was scoped. A red baseline stops the run with exit code 2 and
writes only ``results.txt``. A map run that is not green exits with code 3.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def clear_pycache(root: Path) -> None:
    for cache in root.rglob("__pycache__"):
        if ".venv" in cache.parts or ".git" in cache.parts:
            continue
        shutil.rmtree(cache, ignore_errors=True)


SCRIPTS = Path(__file__).resolve().parent


def interpreter(spec: dict, root: Path) -> str:
    py = spec.get("python", sys.executable)
    return py if os.path.isabs(py) else str(root / py)


def pytest(spec: dict, root: Path, args: list[str], env: dict | None = None,
           timeout: float | None = None, workers: int = 0) -> dict:
    cmd = [interpreter(spec, root), "-m", "pytest", "-q", "-p", "no:cacheprovider",
           "-p", "no:randomly", *args]
    if workers:
        cmd += ["-n", str(workers)]
    start = time.monotonic()
    try:
        done = subprocess.run(
            cmd, cwd=root, capture_output=True, text=True, env=env,
            timeout=timeout or spec.get("timeout", 300)
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "secs": round(time.monotonic() - start, 2), "failed": [],
                "_out": ""}
    out = done.stdout + done.stderr
    failed = re.findall(r"^(?:FAILED|ERROR) (\S+)", out, flags=re.M)
    summary = next(
        (ln for ln in reversed(out.splitlines()) if re.search(r"\d+ (passed|failed|error)", ln)),
        "",
    )
    if done.returncode == 5:
        status = "no-tests"
    elif done.returncode == 0:
        status = "green"
    else:
        status = "red"
    return {"status": status, "secs": round(time.monotonic() - start, 2),
            "failed": failed, "summary": summary.strip(), "code": done.returncode,
            "workers": workers, "_out": out}


STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


def quiet_signals() -> None:
    """Ignore every stop signal, so nothing can cut a restore short."""
    for sig in STOP_SIGNALS:
        signal.signal(sig, signal.SIG_IGN)


def exit_on_signal(signum, frame) -> None:
    """Turn a stop signal into SystemExit, which unwinds through main's restore.

    Later signals are ignored first, so a second Ctrl-C or SIGTERM cannot interrupt that restore.
    """
    quiet_signals()
    raise SystemExit(128 + signum)


def finish(restore) -> None:
    """The last restore, with every stop signal ignored, so one arriving now cannot cut it short."""
    quiet_signals()
    restore()


def is_script(spec: dict) -> bool:
    runner = spec.get("runner", "pytest")
    if runner not in ("pytest", "script"):
        raise SystemExit(f"runner must be 'pytest' or 'script', not {runner!r}")
    return runner == "script"


def commands(selection: list) -> list[list[str]]:
    """A script selection as a list of commands, each a list of arguments."""
    if not selection:
        raise SystemExit("a script selection names no command")
    if all(isinstance(a, str) for a in selection):
        return [selection]
    if all(isinstance(c, list) and c and all(isinstance(a, str) for a in c) for c in selection):
        return selection
    raise SystemExit(f"a script selection is a list of arguments or a list of commands: {selection!r}")


def scripts(spec: dict, root: Path, selection: list, env: dict | None = None,
            timeout: float | None = None) -> dict:
    """Run each command of a script selection, and read failures from its output."""
    pattern = re.compile(spec.get("fail_pattern", r"^(?:FAIL|ERROR)(?:ED)?\b.*"), re.M)
    start, outs, failed, code = time.monotonic(), [], [], 0
    limit = timeout or spec.get("timeout", 300)
    for cmd in commands(selection):
        left = limit - (time.monotonic() - start)
        try:
            if left <= 0:
                raise subprocess.TimeoutExpired(cmd, limit)
            done = subprocess.run([interpreter(spec, root), *cmd], cwd=root, capture_output=True,
                                  text=True, env=env, timeout=left, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            # A command that already failed decided the run, whatever a later one would do.
            return {"status": "red" if code else "timeout",
                    "secs": round(time.monotonic() - start, 2), "failed": failed,
                    "code": code, "workers": 0, "_out": "".join(outs)}
        out = done.stdout + done.stderr
        outs.append(out)
        found = [m.group(0).strip() for m in pattern.finditer(out)]
        if done.returncode and not found:
            tail = (out.strip().splitlines() or [f"exit {done.returncode}"])[-1]
            found = [f"{' '.join(cmd)}: {tail}"]
        failed += found
        code = code or done.returncode
    return {"status": "red" if code else "green", "secs": round(time.monotonic() - start, 2),
            "failed": failed, "summary": f"{len(commands(selection))} command(s), {len(failed)} failure(s)",
            "code": code, "workers": 0, "_out": "".join(outs)}


def run_tests(spec: dict, root: Path, args: list, env: dict | None = None,
              timeout: float | None = None, workers: int = 0) -> dict:
    if is_script(spec):
        return scripts(spec, root, args, env=env, timeout=timeout)
    return pytest(spec, root, args, env=env, timeout=timeout, workers=workers)


def resolve_workers(spec: dict, root: Path, opts) -> int:
    """The xdist worker count for wide runs, or 0 when they run serially."""
    wanted = opts.workers if opts.workers is not None else int(spec.get("workers", 0) or 0)
    if wanted <= 0:
        return 0
    if is_script(spec):
        print(f"workers: {wanted} was asked for, but the script runner does not use them."
              f" Running every run serially.", flush=True)
        return 0
    py = interpreter(spec, root)
    probe = subprocess.run([py, "-c", "import xdist"], capture_output=True, text=True)
    if probe.returncode != 0:
        print(f"workers: {wanted} was asked for, but {py} cannot import xdist. Install"
              f" pytest-xdist in that environment to use workers. Running every run"
              f" serially.", flush=True)
        return 0
    return wanted


def apply(root: Path, mutant: dict) -> str | None:
    """Write the mutant, or return why it cannot apply. Writes nothing unless all edits fit."""
    path = root / mutant["file"]
    text = path.read_text()
    for old, new in mutant["edits"]:
        count = text.count(old)
        if count != 1:
            return f"{old[:60]!r} occurs {count} times"
        text = text.replace(old, new)
    path.write_text(text)
    return None


def clean(result: dict) -> dict:
    """A pytest result without its captured output, for the results files."""
    return {k: v for k, v in result.items() if k != "_out"}


def child_env(**extra: str) -> dict:
    """The environment for a pytest run that loads ``cover_map`` from this directory."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(SCRIPTS), env.get("PYTHONPATH", "")) if p)
    env.update(extra)
    return env


_SPANS: dict = {}


def function_of_edits(spec: dict, root: Path, original: bytes, mutant: dict,
                      backup_path: Path) -> tuple[list[str], str | None]:
    """Qualnames of the functions a mutant's edits sit in, or the reason one is global.

    Each edit is located in the original text, and attributed to the outermost function whose
    body holds every byte the edit changes. Context shared by ``old`` and ``new`` is ignored. The spans come from ``cover_map.py --spans`` run under the
    target interpreter, because this script's own Python may not parse the target's syntax.
    """
    key = str(backup_path)
    if key not in _SPANS:
        done = subprocess.run([interpreter(spec, root), str(SCRIPTS / "cover_map.py"),
                               "--spans", key], capture_output=True, text=True)
        _SPANS[key] = (json.loads(done.stdout) if done.returncode == 0
                       else done.stderr.strip().splitlines()[-1:])
    spans = _SPANS[key]
    if spans and isinstance(spans[0], str):
        return [], f"cannot parse {mutant['file']}: {spans[0]}"
    quals: list[str] = []
    for old, new in mutant["edits"]:
        needle, replacement = old.encode(), new.encode()
        if original.count(needle) != 1:
            return [], f"edit {old[:40]!r} is not unique in the original file"
        # An edit often carries unchanged context to make ``old`` unique. Only the bytes that
        # differ say where the mutation is, so trim the shared prefix and suffix.
        same = min(len(needle), len(replacement))
        head = next((i for i in range(same) if needle[i] != replacement[i]), same)
        tail = next((i for i in range(same - head) if needle[-1 - i] != replacement[-1 - i]),
                    same - head)
        start = original.index(needle) + head
        end = original.index(needle) + len(needle) - tail
        owner = next((q for s, e, q in spans if s <= start and end <= e), None)
        if owner is None:
            line = original.count(b"\n", 0, start) + 1
            return [], f"global edit at line {line}"
        if owner not in quals:
            quals.append(owner)
    return quals, None


def load_map(path: Path) -> dict | None:
    """The map JSON, or None when the map run wrote none."""
    return json.loads(path.read_text()) if path.exists() else None


def plan_scope(spec: dict, root: Path, out: Path, survivors: list[dict], backups: dict,
               opts) -> tuple[dict, list[dict]]:
    """Decide each survivor's escalation scope. Returns per-mutant plans and extra rows.

    A plan is {"kind": "full" | "coverage" | "unreached", "tests": [...], "reason": str}.
    """
    plans: dict = {}
    rows: list[dict] = []

    def everyone(reason: str) -> dict:
        return {m["name"]: {"kind": "full", "tests": [], "reason": reason} for m in survivors}

    if opts.escalate_full:
        return everyone("--escalate-full"), rows
    if is_script(spec):
        return everyone("script runner, no coverage map"), rows
    py = interpreter(spec, root)
    probe = subprocess.run([py, "-c", "import sys; print(sys.version_info >= (3, 12))"],
                           capture_output=True, text=True)
    if probe.stdout.strip() != "True":
        print(f"coverage-scoped escalation needs Python 3.12 in {py}; running full escalation.",
              flush=True)
        return everyone("python older than 3.12"), rows

    targets = sorted({str((root / m["file"]).resolve()) for m in survivors})
    map_path = out / "cover_map.json"
    map_path.unlink(missing_ok=True)
    for stale in out.glob("cover_map.gw*.json"):
        stale.unlink()
    env = child_env(MUTATE_COVER_OUT=str(map_path),
                    MUTATE_COVER_TARGETS=os.pathsep.join(targets))
    clear_pycache(root)
    result = pytest(spec, root, [*spec["escalate"], "-p", "cover_map"], env=env,
                    timeout=2 * spec.get("timeout", 300), workers=opts.workers_n)
    row = {"name": "MAP", "map": str(map_path), **clean(result)}
    rows.append(row)
    shown = f" workers={opts.workers_n}" if opts.workers_n else ""
    print(f"MAP {result['status']} {result['secs']}s {result.get('summary', '')}{shown}"
          f"  -> {map_path}", flush=True)
    # A test that failed means the suite is red, whatever the plugin said. Under xdist a
    # crashed worker also leaves a cover_map line, and a full escalation of a red suite would
    # read every mutant as caught.
    if "cover_map:" in result["_out"] and not result["failed"]:
        reason = next(ln for ln in result["_out"].splitlines() if "cover_map:" in ln).strip()
        print(f"the coverage plugin failed ({reason}); running full escalation.", flush=True)
        return everyone("coverage plugin failed"), rows
    if result["status"] != "green":
        (out / "map.log").write_text(result["_out"])
        first = result.get("failed", [])[:1]
        print(f"the unmutated escalate run is not green{' (' + first[0] + ')' if first else ''},"
              f" so every wide verdict would read as caught. Skipping escalation. Log:"
              f" {out / 'map.log'}", flush=True)
        return {}, rows
    cover = load_map(map_path)
    if cover is None:
        print(f"the map run wrote no {map_path.name}; running full escalation.", flush=True)
        return everyone("map run wrote no map"), rows
    if os.path.realpath(cover["rootpath"]) != str(root):
        print(f"the map's rootpath {cover['rootpath']} differs from root {root}; node IDs would"
              f" not resolve, so running full escalation.", flush=True)
        return everyone("map rootpath differs from root"), rows
    if cover["spawns_outside_tests"]:
        print("a process was spawned outside any test; its effect cannot be credited to tests,"
              " so running full escalation.", flush=True)
        return everyone("process spawned outside tests"), rows

    spawners = cover["spawning_tests"]
    warned: set[str] = set()
    for m in survivors:
        target = str((root / m["file"]).resolve())
        backup = out / "backup" / m["file"].replace("/", "__")
        quals, global_reason = function_of_edits(spec, root, backups[m["file"]], m, backup)
        if target not in cover["targets_seen"]:
            if target not in warned:
                warned.add(target)
                elsewhere = cover["lookalikes"].get(target)
                print(f"WARNING: the map run never imported {m['file']}. The venv may import a"
                      f" different copy of the source"
                      f"{': ' + ', '.join(elsewhere) if elsewhere else ''}.", flush=True)
            plans[m["name"]] = {"kind": "full", "tests": [], "reason": "file never imported"}
            continue
        if global_reason:
            plans[m["name"]] = {"kind": "full", "tests": [], "reason": global_reason}
            continue
        outside = [q for q in quals if q in cover["outside_tests"].get(target, [])]
        if outside:
            plans[m["name"]] = {"kind": "full", "tests": [],
                                "reason": f"{', '.join(outside)} runs outside tests"}
            continue
        reached = cover["by_function"].get(target, {})
        tests = sorted(set().union(*(reached.get(q, []) for q in quals)) | set(spawners))
        durations = cover.get("durations", {})
        mapped_secs = round(sum(durations.get(t, 0.0) for t in tests), 2)
        plans[m["name"]] = {"kind": "coverage" if tests else "unreached", "tests": tests,
                            "functions": quals, "reason": "", "mapped_secs": mapped_secs}
    return plans, rows


def escalate(spec: dict, root: Path, out: Path, survivors: list[dict], backups: dict,
             restore, opts) -> list[dict]:
    """Re-run each survivor on its own against the escalate scope it was given."""
    plans, rows = plan_scope(spec, root, out, survivors, backups, opts)
    min_secs = float(spec.get("workers_min_secs", 10))
    for m in survivors:
        plan = plans.get(m["name"])
        if plan is None:
            continue
        kind = plan["kind"]
        if kind == "unreached":
            esc = {"status": "unreached", "secs": 0.0, "failed": []}
        else:
            if kind == "coverage":
                select = out / "select.json"
                report = out / "select-report.json"
                select.write_text(json.dumps(plan["tests"]))
                report.unlink(missing_ok=True)
                env = child_env(MUTATE_SELECT_FILE=str(select), MUTATE_SELECT_REPORT=str(report))
                args = [*spec["escalate"], "-p", "cover_map"]
                # Workers pay only when the selection ran long enough in the map run to
                # cover their startup.
                workers = opts.workers_n if plan["mapped_secs"] >= min_secs else 0
            else:
                env, args, workers = None, spec["escalate"], opts.workers_n
            apply(root, m)
            clear_pycache(root)
            limit = (spec.get("escalate_timeout", 2 * spec.get("timeout", 300))
                     if is_script(spec) else None)
            esc = run_tests(spec, root, args, env=env, timeout=limit, workers=workers)
            restore()
            if kind == "coverage" and esc["status"] != "red":
                seen = json.loads(report.read_text()) if report.exists() else None
                if not seen or seen["missing_count"]:
                    # The map's node IDs did not all collect, so the scoped run is not the
                    # selection it claims to be. Fall back rather than trust it.
                    missing = seen["missing"][:3] if seen else "no select report"
                    plan = {"kind": "full", "tests": [],
                            "reason": f"map node IDs not collected: {missing}"}
                    apply(root, m)
                    clear_pycache(root)
                    esc = pytest(spec, root, spec["escalate"], workers=opts.workers_n)
                    restore()
        if plan["kind"] == "full":
            note = f"scope=full ({plan['reason']})"
        else:
            note = f"scope=coverage ({len(plan['tests'])} tests)"
        if esc.get("workers"):
            note += f" workers={esc['workers']}"
        rows.append({"name": m["name"], "escalated": True, **clean(esc),
                     "scope": plan["kind"], "scope_tests": len(plan["tests"]),
                     "scope_reason": plan["reason"], "functions": plan.get("functions", []),
                     "mapped_secs": plan.get("mapped_secs")})
        verdict = {"red": "CAUGHT-WIDE", "unreached": "UNREACHED",
                   "timeout": "TIMEOUT-WIDE"}.get(esc["status"], "SURVIVED-ALL")
        first = esc.get("failed", [])[:1]
        print(f"{verdict:12} {esc['secs']!s:>7}  {m['name']}"
              f"{'  <- ' + first[0] if first else ''}  {note}", flush=True)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec")
    parser.add_argument("--only", nargs="*", default=None)
    parser.add_argument("--no-escalate", action="store_true")
    parser.add_argument("--escalate-full", action="store_true",
                        help="re-run each survivor against the whole escalate selection")
    parser.add_argument("--workers", type=int, default=None,
                        help="pytest-xdist workers for the wide runs; overrides the spec's"
                             " workers key, and 0 turns workers off")
    parser.add_argument("--out", default=None)
    opts = parser.parse_args()

    spec = json.loads(Path(opts.spec).read_text())
    root = Path(spec["root"]).resolve()
    out = Path(opts.out or tempfile.mkdtemp(prefix="mutate-")).resolve()
    out.mkdir(parents=True, exist_ok=True)
    mutants = [m for m in spec["mutants"] if opts.only is None or m["name"] in opts.only]
    opts.workers_n = resolve_workers(spec, root, opts)

    files = sorted({m["file"] for m in mutants})
    outside = [f for f in files if not (root / f).resolve().is_relative_to(root)]
    if outside:
        raise SystemExit(f"every mutated file must sit inside root {root}: {', '.join(outside)}")
    # A hard link shares its bytes with a file the root check cannot see.
    linked = [f for f in files if (root / f).stat().st_nlink > 1]
    if linked:
        raise SystemExit(f"a mutated file has another hard link, which may sit outside root: {', '.join(linked)}")
    backups = {f: (root / f).read_bytes() for f in files}
    (out / "backup").mkdir(exist_ok=True)
    for f, data in backups.items():
        (out / "backup" / f.replace("/", "__")).write_bytes(data)

    def restore() -> None:
        for f, data in backups.items():
            (root / f).write_bytes(data)
            assert (root / f).read_bytes() == data, f"restore of {f} did not stick"
        clear_pycache(root)

    for sig in STOP_SIGNALS:
        signal.signal(sig, exit_on_signal)

    print(f"out {out}", flush=True)
    clear_pycache(root)
    base = run_tests(spec, root, spec["baseline"],
                     timeout=spec.get("escalate_timeout", 2 * spec.get("timeout", 300))
                     if is_script(spec) else None)
    line = f"BASE {base['status']} {base['secs']}s {base.get('summary', '')}"
    print(line, flush=True)
    rows = [{"name": "BASE", **clean(base)}]
    if base["status"] != "green":
        print("baseline is not green; every mutant would read as caught. Stopping.", flush=True)
        (out / "results.txt").write_text(line + "\n")
        return 2

    survivors = []
    try:
        for m in mutants:
            why = apply(root, m)
            if why:
                row = {"name": m["name"], "status": "not-applied", "why": why}
            else:
                clear_pycache(root)
                row = {"name": m["name"],
                       **clean(run_tests(spec, root, m["select"] if "select" in m else spec["select"]))}
                restore()
                if row["status"] == "green":
                    survivors.append(m)
                elif row["status"] == "no-tests":
                    row["why"] = "the selection collected no tests"
            rows.append(row)
            verdict = {"red": "CAUGHT", "green": "SURVIVED", "timeout": "TIMEOUT"}.get(
                row["status"], row["status"].upper())
            first = row.get("failed", [])[:1]
            print(f"{verdict:12} {row.get('secs', '')!s:>7}  {m['name']}"
                  f"{'  <- ' + first[0] if first else ''}{'  (' + row['why'] + ')' if row.get('why') else ''}",
                  flush=True)

        if survivors and not opts.no_escalate and spec.get("escalate"):
            rows.extend(escalate(spec, root, out, survivors, backups, restore, opts))
        elif survivors and not opts.no_escalate:
            print("the spec has no escalate selection, so the survivors were not escalated.",
                  flush=True)
    finally:
        finish(restore)

    with (out / "results.jsonl").open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    scoped = [r for r in rows if r["name"] not in ("BASE", "MAP") and not r.get("escalated")]
    caught = sum(1 for r in scoped if r.get("status") == "red")
    applied = sum(1 for r in scoped if r.get("status") != "not-applied")
    print(f"applied {applied} caught {caught} survived-scoped {len(survivors)} results {out}",
          flush=True)
    (out / "results.txt").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    return 3 if any(r.get("name") == "MAP" and r.get("status") != "green" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
