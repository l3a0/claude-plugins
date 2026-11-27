#!/usr/bin/env python3
"""Check that the plugin's manifest describes the plugin and names every skill.

    python3 tests/test_plugin_manifest.py

On 2026-11-26 a merge resolved a conflict on `.claude-plugin/plugin.json`'s
version line by writing the version alone, and the `description` line, which
sat inside the same conflict, was dropped. Every check passed and two pull
requests carried the loss to main. This test fails on that loss: the manifest
must carry a description that names each skill under `skills/`, a version, and
the fields the marketplace reads.
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
failures = []


def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        failures.append(name)


manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
skills = sorted(p.name for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file())

for field in ("name", "description", "version", "author", "repository", "license"):
    check(f"plugin.json has a non-empty {field}", bool(manifest.get(field)))
description = manifest.get("description", "")
for skill in skills:
    check(f"the description names the {skill} skill", skill in description)
check("the version reads as three numbers", len(str(manifest.get("version", "")).split(".")) == 3)

sys.exit(1 if failures else 0)
