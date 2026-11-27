"""A pytest plugin that maps each function in a few target files to the tests that start it.

mutate.py loads it as ``-p cover_map`` with this directory on ``PYTHONPATH``. It has two
modes, chosen by environment variables, and does nothing when neither is set.

Map mode, ``MUTATE_COVER_OUT=path`` and ``MUTATE_COVER_TARGETS=abs1:abs2`` (``os.pathsep``):
    A global ``sys.monitoring`` PY_START callback records, for each code object whose file is a
    target, the test that was running when it started. Each code object fires once per test,
    because the callback returns DISABLE and every test begins with ``restart_events()``.
    Nested code counts as its outermost function, so ``outer.<locals>.inner`` and
    ``outer.<locals>.<genexpr>`` both record ``outer``. Code that starts while no test runs,
    during collection or import, goes to ``outside_tests``.

    Two cases would let a test observe code it never starts in its own run. Both are folded
    into the map so that mutate.py stays conservative.

    1. A fixture wider than function scope is set up once, inside the first test that asks
       for it, and its value is reused by later tests. Code started during that setup is
       credited to every test whose fixture closure names the fixture.
    2. A test that spawns a process can run target code in the child, where this process
       cannot see it. Such tests are listed in ``spawning_tests``, and mutate.py adds them to
       every coverage-scoped selection.

    At session end it writes JSON to ``MUTATE_COVER_OUT``. The map also records each test's
    wall-clock time, which mutate.py uses to decide whether a scoped run is worth workers.

    Under pytest-xdist each worker is its own process with its own ``sys.monitoring`` state,
    so each worker maps only the tests it ran. A worker writes its map next to
    ``MUTATE_COVER_OUT``, with its id before the extension, as in ``cover_map.gw0.json``.
    Collection runs in every worker, so each worker's collection-time calls land in its own
    ``outside_tests``. The fixture and spawn rules above hold inside each worker, because a
    worker sets up its own copy of every wider fixture. The controller, the process that
    starts the workers, runs no test. At session end it merges its own map and every worker's
    into ``MUTATE_COVER_OUT``, in the serial shape: node IDs, ``outside_tests`` and
    ``targets_seen`` are unioned, and the ``rootpath`` of every map must agree. A process
    that xdist or execnet starts itself, such as a worker or the ``uname`` call a worker
    makes on macOS while reporting its platform, is not counted as a spawn. When a worker's map
    is missing or a ``rootpath`` disagrees, the controller writes no map and prints a
    ``cover_map:`` line, and mutate.py falls back to the full escalation.

Select mode, ``MUTATE_SELECT_FILE=path`` holding a JSON list of node IDs:
    Collection skips Python files that hold none of them, then keeps exactly those items
    and deselects the rest. Passing node IDs through a file avoids both the argument-length
    limit and node IDs that do not parse on a command line. ``MUTATE_SELECT_REPORT=path``
    receives ``{"wanted", "matched", "missing", "missing_count"}``. Under pytest-xdist every
    worker reads the same file and so collects the same filtered set, which xdist requires.
    Only the controller writes the report, from the node IDs the workers say they collected.

Spans mode, ``python cover_map.py --spans FILE``:
    Prints the byte span of every function body in FILE that mutate.py can attribute an edit
    to, as JSON. It runs under the target interpreter so that the parser matches the source.

Map mode needs Python 3.12 or newer, for ``sys.monitoring``. It uses no third-party package.
"""

from __future__ import annotations

import ast
import functools
import json
import os
import sys
import sysconfig
import time

_OUT = os.environ.get("MUTATE_COVER_OUT")
_SELECT = os.environ.get("MUTATE_SELECT_FILE")


def top(qualname: str) -> str:
    """The outermost function a qualname belongs to."""
    cut = qualname.find(".<locals>.")
    return qualname if cut < 0 else qualname[:cut]


# -- spans mode ------------------------------------------------------------------------------


def _blocks(node: ast.stmt) -> list[list[ast.stmt]]:
    """Statement lists directly inside a compound statement that is not a def or a class."""
    blocks = [getattr(node, name) for name in ("body", "orelse", "finalbody")
              if isinstance(getattr(node, name, None), list)]
    blocks += [handler.body for handler in getattr(node, "handlers", [])]
    blocks += [case.body for case in getattr(node, "cases", [])]
    return blocks


def spans(source: bytes) -> list[list]:
    """``[start, end, qualname]`` byte spans of each outermost function body in a module.

    A function counts when it is defined in the module or in a class, nested classes included,
    reached through any module-level or class-level compound statement. The span runs from the
    first body statement to the end of the def, so a decorator, the signature and its defaults
    lie outside it. Function bodies are not descended into, so nested defs belong to the
    outermost function, the same way ``top()`` folds qualnames.
    """
    tree = ast.parse(source)
    starts = [0]
    for line in source.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))

    def offset(lineno: int, col: int) -> int:
        return starts[lineno - 1] + col  # ast columns are UTF-8 byte offsets

    found: list[list] = []

    def walk(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                first = node.body[0]
                found.append([offset(first.lineno, first.col_offset),
                              offset(node.end_lineno, node.end_col_offset),
                              prefix + node.name])
            elif isinstance(node, ast.ClassDef):
                walk(node.body, prefix + node.name + ".")
            else:
                for block in _blocks(node):
                    walk(block, prefix)

    walk(tree.body, "")
    return found


# -- map mode --------------------------------------------------------------------------------

_state: dict = {
    "test": None,       # node ID of the running test, or None
    "fixtures": [],     # stack of wider-than-function fixtures being set up
    "by_test": {},      # file -> qualname -> set of node IDs
    "by_fixture": {},   # file -> qualname -> set of fixture names
    "outside": {},      # file -> set of qualnames
    "seen": set(),      # target files whose code started at all
    "closures": {},     # node ID -> fixture closure
    "spawning": set(),  # node IDs that spawned a process
    "spawn_fixtures": set(),
    "spawn_outside": 0,
    "programs": {},     # node ID -> programs it spawned
    "durations": {},    # node ID -> wall-clock seconds of its run protocol
    "config": None,     # the pytest config, once configured
    "nodes": {},        # xdist worker id -> error, on the controller
}
_resolved: dict[str, str | None] = {}
_tool: int | None = None


def _on_start(code, instruction_offset):  # noqa: ARG001 - the signature sys.monitoring calls
    name = code.co_filename
    path = _resolved.get(name, "")
    if path == "":
        real = os.path.realpath(name)
        path = _resolved[name] = real if real in _TARGETS else None
    if path is not None:
        _state["seen"].add(path)
        qual = code.co_qualname
        if qual != "<module>":
            qual = top(qual)
            test = _state["test"]
            if test is None:
                _state["outside"].setdefault(path, set()).add(qual)
            else:
                _state["by_test"].setdefault(path, {}).setdefault(qual, set()).add(test)
                for fixture in _state["fixtures"]:
                    _state["by_fixture"].setdefault(path, {}).setdefault(qual, set()).add(fixture)
    return sys.monitoring.DISABLE


def _program(attr: str, args: tuple) -> str:
    """The program a spawn call starts, for the map's diagnostics."""
    try:
        if attr == "_execute_child":
            first = args[1] if isinstance(args[1], (str, bytes)) else args[1][0]
        elif attr in ("fork_exec", "posix_spawn", "posix_spawnp"):
            first = args[0] if isinstance(args[0], (str, bytes)) else args[0][0]
        elif attr == "system":
            first = str(args[0]).split()[0]
        else:
            return attr
        first = os.fsdecode(first)
        return os.path.basename(first.split()[0]) if first.strip() else "?"
    except (IndexError, TypeError, ValueError):
        return "?"


def is_worker(config) -> bool:
    return hasattr(config, "workerinput")


def is_controller(config) -> bool:
    """True in the process that starts pytest-xdist workers and runs no test itself."""
    return (config is not None and not is_worker(config)
            and config.pluginmanager.getplugin("dsession") is not None)


def worker_path(out: str, worker: str) -> str:
    """Where a worker writes its map: the worker id goes before the extension."""
    stem, ext = os.path.splitext(out)
    return f"{stem}.{worker}{ext}"


_ME = os.path.realpath(__file__)
_STDLIB = tuple({os.path.realpath(sysconfig.get_paths()[k]) + os.sep
                 for k in ("stdlib", "platstdlib")})
_REAL: dict[str, str] = {}


def _in_stdlib(real: str) -> bool:
    """True for a standard-library file, but not for an installed package beneath it."""
    return real.startswith(_STDLIB) and not any(
        f"{os.sep}{d}{os.sep}" in real for d in ("site-packages", "dist-packages"))


def _launched_by_xdist() -> bool:
    """True when the nearest caller outside the standard library is xdist or execnet.

    The controller starts each worker through execnet, and each worker calls
    ``platform.platform()``, which runs ``uname`` and ``file``. Those launches belong to
    xdist, not to the suite. A test or a conftest that spawns a process is its own nearest
    caller, so it still counts.
    """
    owners = tuple(os.path.dirname(os.path.realpath(module.__file__)) + os.sep
                   for module in (sys.modules.get("xdist"), sys.modules.get("execnet"))
                   if getattr(module, "__file__", None))
    if not owners:
        return False
    frame = sys._getframe(1)
    while frame is not None:
        name = frame.f_code.co_filename
        real = _REAL.get(name)
        if real is None:
            real = _REAL[name] = os.path.realpath(name)
        if real != _ME and not name.startswith("<frozen") and not _in_stdlib(real):
            return real.startswith(owners)
        frame = frame.f_back
    return False


def _note_spawn(attr: str, args: tuple) -> None:
    if _launched_by_xdist():
        return
    test = _state["test"]
    if test is not None:
        _state["programs"].setdefault(test, set()).add(_program(attr, args))
    if _state["fixtures"]:
        _state["spawn_fixtures"].update(_state["fixtures"])
    if _state["test"] is not None:
        _state["spawning"].add(_state["test"])
    elif not _state["fixtures"]:
        _state["spawn_outside"] += 1


def _watch_spawns() -> None:
    """Wrap every route that starts a process, so a test that spawns one is recorded."""
    import _posixsubprocess
    import subprocess

    def wrap(owner, attr: str) -> None:
        original = getattr(owner, attr, None)
        if original is None:
            return

        @functools.wraps(original)
        def spawning(*args, **kwargs):
            _note_spawn(attr, args)
            return original(*args, **kwargs)

        setattr(owner, attr, spawning)

    wrap(subprocess.Popen, "_execute_child")
    wrap(_posixsubprocess, "fork_exec")  # multiprocessing's spawn start method calls it
    for attr in ("fork", "posix_spawn", "posix_spawnp", "system"):
        wrap(os, attr)


if _OUT:
    if sys.version_info < (3, 12):
        raise RuntimeError(
            f"cover_map: map mode needs Python 3.12 or newer for sys.monitoring, "
            f"and this is {sys.version.split()[0]}")
    _TARGETS = {os.path.realpath(p)
                for p in os.environ.get("MUTATE_COVER_TARGETS", "").split(os.pathsep) if p}
    if not _TARGETS:
        raise RuntimeError("cover_map: MUTATE_COVER_TARGETS names no file")
    _tool = sys.monitoring.COVERAGE_ID
    if sys.monitoring.get_tool(_tool) is not None:
        raise RuntimeError(
            f"cover_map: sys.monitoring tool id {_tool} is already taken by "
            f"{sys.monitoring.get_tool(_tool)!r}. Run without coverage tools, or pass "
            f"--escalate-full to mutate.py.")
    # Registered at import, before conftest files load, so collection-time calls are seen.
    sys.monitoring.use_tool_id(_tool, "mutate-cover-map")
    sys.monitoring.register_callback(_tool, sys.monitoring.events.PY_START, _on_start)
    sys.monitoring.set_events(_tool, sys.monitoring.events.PY_START)
    _watch_spawns()


def _hookimpl(**kwargs):
    import pytest
    return pytest.hookimpl(**kwargs)


def merge(reports: list[dict]) -> dict:
    """One map from several, in the shape a single process writes.

    Every map must name the same ``rootpath``, or node IDs would not resolve, and a
    ValueError says which differ. Node IDs, ``outside_tests``, ``targets_seen`` and the other
    sets are unioned. A fixture's credit was already given inside the map that set it up.
    """
    roots = sorted({r["rootpath"] for r in reports})
    if len(roots) != 1:
        raise ValueError(f"the maps disagree on rootpath: {roots}")

    def union(field: str) -> dict:
        joined: dict = {}
        for r in reports:
            for path, quals in r[field].items():
                for qual, names in quals.items():
                    joined.setdefault(path, {}).setdefault(qual, set()).update(names)
        return {p: {q: sorted(n) for q, n in quals.items()} for p, quals in joined.items()}

    outside: dict = {}
    for r in reports:
        for path, quals in r["outside_tests"].items():
            outside.setdefault(path, set()).update(quals)
    programs: dict = {}
    lookalikes: dict = {}
    for r in reports:
        for test, progs in r["spawned_programs"].items():
            programs.setdefault(test, set()).update(progs)
        for target, where in r["lookalikes"].items():
            lookalikes.setdefault(target, set()).update(where)
    return {
        "rootpath": roots[0],
        "python": reports[0]["python"],
        "exitstatus": reports[0]["exitstatus"],
        "tests": sum(r["tests"] for r in reports),
        "targets": sorted(set().union(*(r["targets"] for r in reports))),
        "targets_seen": sorted(set().union(*(r["targets_seen"] for r in reports))),
        "by_function": union("by_function"),
        "via_fixture": union("via_fixture"),
        "outside_tests": {p: sorted(q) for p, q in outside.items()},
        "spawning_tests": sorted(set().union(*(r["spawning_tests"] for r in reports))),
        "spawned_programs": {t: sorted(p) for t, p in sorted(programs.items())},
        "spawns_outside_tests": sum(r["spawns_outside_tests"] for r in reports),
        "lookalikes": {t: sorted(w) for t, w in lookalikes.items()},
        "durations": {k: v for r in reports for k, v in r.get("durations", {}).items()},
        "workers": sorted(w for r in reports for w in r.get("workers", ())),
    }


if _OUT:
    def pytest_configure(config):
        _state["config"] = config

    @_hookimpl(tryfirst=True)
    def pytest_sessionstart(session):
        """On the xdist controller, remove worker maps an earlier run left behind."""
        if is_controller(session.config):
            folder, name = os.path.split(_OUT)
            stem, ext = os.path.splitext(name)
            for entry in os.listdir(folder or "."):
                if entry.startswith(stem + ".gw") and entry.endswith(ext):
                    os.unlink(os.path.join(folder, entry))

    @_hookimpl(optionalhook=True)
    def pytest_testnodedown(node, error):
        _state["nodes"][node.workerinput["workerid"]] = error

    @_hookimpl(wrapper=True)
    def pytest_runtest_protocol(item, nextitem):  # noqa: ARG001
        _state["test"] = item.nodeid
        _state["closures"][item.nodeid] = list(getattr(item, "fixturenames", ()))
        sys.monitoring.restart_events()
        start = time.perf_counter()
        try:
            return (yield)
        finally:
            _state["durations"][item.nodeid] = round(time.perf_counter() - start, 4)
            _state["test"] = None

    @_hookimpl(wrapper=True)
    def pytest_fixture_setup(fixturedef, request):  # noqa: ARG001
        if fixturedef.scope == "function":
            return (yield)
        _state["fixtures"].append(fixturedef.argname)
        sys.monitoring.restart_events()
        try:
            return (yield)
        finally:
            _state["fixtures"].pop()
            sys.monitoring.restart_events()

    def _report(session, exitstatus) -> dict:
        """This process's own map."""
        users: dict[str, set[str]] = {}
        for nodeid, closure in _state["closures"].items():
            for name in closure:
                users.setdefault(name, set()).add(nodeid)
        by_function: dict[str, dict[str, set[str]]] = {}
        for path, quals in _state["by_test"].items():
            for qual, tests in quals.items():
                by_function.setdefault(path, {}).setdefault(qual, set()).update(tests)
        via_fixture: dict[str, dict[str, list[str]]] = {}
        for path, quals in _state["by_fixture"].items():
            for qual, fixtures in quals.items():
                via_fixture.setdefault(path, {})[qual] = sorted(fixtures)
                for fixture in fixtures:
                    by_function[path][qual].update(users.get(fixture, ()))
        spawning = set(_state["spawning"])
        for fixture in _state["spawn_fixtures"]:
            spawning.update(users.get(fixture, ()))
        # A module whose file has the target's package path but resolves elsewhere means the
        # venv imports a different copy of the source than the one being mutated.
        lookalikes: dict[str, list[str]] = {}
        for target in _TARGETS:
            tail = os.sep + os.path.join(*target.split(os.sep)[-2:])
            for module in list(sys.modules.values()):
                where = getattr(module, "__file__", None)
                if where and where.endswith(tail) and os.path.realpath(where) != target:
                    lookalikes.setdefault(target, []).append(os.path.realpath(where))
        report = {
            "rootpath": str(session.config.rootpath),
            "python": sys.executable,
            "exitstatus": int(exitstatus),
            "tests": len(_state["closures"]),
            "targets": sorted(_TARGETS),
            "targets_seen": sorted(_state["seen"]),
            "by_function": {p: {q: sorted(t) for q, t in quals.items()}
                            for p, quals in by_function.items()},
            "via_fixture": via_fixture,
            "outside_tests": {p: sorted(q) for p, q in _state["outside"].items()},
            "spawning_tests": sorted(spawning),
            "spawned_programs": {t: sorted(p) for t, p in sorted(_state["programs"].items())},
            "spawns_outside_tests": _state["spawn_outside"],
            "lookalikes": lookalikes,
            "durations": dict(_state["durations"]),
            "workers": [],
        }
        return report

    def _write(path: str, report: dict) -> None:
        with open(path, "w") as fh:
            json.dump(report, fh, indent=1, sort_keys=True)

    def pytest_sessionfinish(session, exitstatus):
        config = session.config
        report = _report(session, exitstatus)
        if is_worker(config):
            worker = config.workerinput["workerid"]
            report["workers"] = [worker]
            _write(worker_path(_OUT, worker), report)
        elif is_controller(config):
            reports, problems = [report], []
            for worker, error in sorted(_state["nodes"].items()):
                path = worker_path(_OUT, worker)
                if error is not None or not os.path.exists(path):
                    problems.append(f"worker {worker} wrote no map ({error or 'no file'})")
                    continue
                with open(path) as fh:
                    reports.append(json.load(fh))
            if not _state["nodes"]:
                problems.append("no xdist worker reported back")
            if not problems:
                try:
                    _write(_OUT, merge(reports))
                except ValueError as exc:
                    problems.append(str(exc))
            for problem in problems:
                sys.stderr.write(f"cover_map: {problem}; no merged map written\n")
        else:
            _write(_OUT, report)
        sys.monitoring.set_events(_tool, 0)
        sys.monitoring.register_callback(_tool, sys.monitoring.events.PY_START, None)
        sys.monitoring.free_tool_id(_tool)


# -- select mode -----------------------------------------------------------------------------

if _SELECT:
    with open(_SELECT) as fh:
        _WANTED = set(json.load(fh))
    _WANTED_FILES: set[str] | None = None

    def pytest_ignore_collect(collection_path, config):
        """Skip a Python file that holds no wanted test, so collection stays small.

        Directories, ``conftest.py`` and ``__init__.py`` are always collected, so fixtures and
        packages resolve as they do in the full run. Returning None leaves the decision to
        pytest's own rules.
        """
        global _WANTED_FILES
        if _WANTED_FILES is None:
            _WANTED_FILES = {os.path.realpath(config.rootpath / nodeid.split("::")[0])
                             for nodeid in _WANTED}
        if (collection_path.suffix == ".py"
                and collection_path.name not in ("conftest.py", "__init__.py")
                and os.path.realpath(collection_path) not in _WANTED_FILES):
            return True
        return None

    def _select_report(collected: set[str]) -> None:
        report = os.environ.get("MUTATE_SELECT_REPORT")
        if report:
            matched = _WANTED & collected
            missing = sorted(_WANTED - matched)
            with open(report, "w") as fh:
                json.dump({"wanted": len(_WANTED), "matched": len(matched),
                           "missing": missing[:20], "missing_count": len(missing)}, fh)

    def pytest_collection_modifyitems(session, config, items):  # noqa: ARG001
        wanted = _WANTED
        keep = [item for item in items if item.nodeid in wanted]
        drop = [item for item in items if item.nodeid not in wanted]
        if drop:
            config.hook.pytest_deselected(items=drop)
        items[:] = keep
        if not hasattr(config, "workerinput"):
            # Under xdist only the controller reports, from what the workers collected.
            _select_report({item.nodeid for item in keep})

    _COLLECTED: set[str] = set()

    @_hookimpl(optionalhook=True)
    def pytest_xdist_node_collection_finished(node, ids):  # noqa: ARG001
        _COLLECTED.update(ids)
        _select_report(_COLLECTED)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--spans":
        with open(sys.argv[2], "rb") as fh:
            print(json.dumps(spans(fh.read())))
    else:
        sys.exit("usage: python cover_map.py --spans FILE")
