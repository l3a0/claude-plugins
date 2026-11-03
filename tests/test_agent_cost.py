#!/usr/bin/env python3
"""Tests for skills/loop-cost/scripts/agent-cost.py on synthetic transcripts.

    python3 tests/test_agent_cost.py

The transcripts are invented, so the test needs no session history and runs on
the Linux CI runner.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "loop-cost", "scripts", "agent-cost.py")


def message(mid, input_tokens):
    # One opus message; a million input tokens is 4.00 at list price.
    return {"uuid": f"u-{mid}", "message": {
        "id": mid, "role": "assistant", "model": "claude-opus-5-5",
        "usage": {"input_tokens": input_tokens}, "content": []}}


class AgentCost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        # agent id -> (description, messages)
        agents = {
            "a1": ("Read part 1", [message("m1", 1_000_000)]),
            "a2": ("Read part 2", [message("m2", 2_000_000)]),
            "b1": ("Architect lens on PRs", [message("m3", 3_000_000)]),
            # A fork of a1: repeats its message, which must count once.
            "c1": ("Verify findings", [message("m1", 1_000_000),
                                       message("m4", 500_000)]),
        }
        for aid, (description, records) in agents.items():
            base = os.path.join(self.dir, f"agent-{aid}")
            with open(base + ".jsonl", "w") as f:
                f.writelines(json.dumps(r) + "\n" for r in records)
            with open(base + ".meta.json", "w") as f:
                json.dump({"description": description}, f)

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args, ok=True):
        result = subprocess.run([sys.executable, SCRIPT, *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stderr)
        return result

    def totals(self, stdout):
        return [line.split(", ")[1].split(" ")[0]
                for line in stdout.splitlines() if line.startswith("total:")]

    def test_plain_paths_still_work(self):
        out = self.run_script(os.path.join(self.dir, "agent-a1.jsonl"),
                              os.path.join(self.dir, "agent-a2.jsonl")).stdout
        self.assertEqual(self.totals(out), ["$12.00"])

    def test_message_in_two_files_counts_once(self):
        out = self.run_script("--dir", self.dir, "a1", "c1").stdout
        self.assertEqual(self.totals(out), ["$6.00"])

    def test_ids_in_one_word_are_split(self):
        out = self.run_script("--dir", self.dir,
                              "a1 agent-a2,agent-b1.jsonl").stdout
        self.assertEqual(self.totals(out), ["$24.00"])

    def test_ids_file(self):
        ids = os.path.join(self.dir, "ids.txt")
        with open(ids, "w") as f:
            f.write("# reading\na1\na2  # second part\n")
        out = self.run_script("--dir", self.dir, "--ids-file", ids).stdout
        self.assertEqual(self.totals(out), ["$12.00"])

    def test_missing_id_fails_and_names_it(self):
        err = self.run_script("--dir", self.dir, "a1", "nope", ok=False).stderr
        self.assertIn("nope", err)
        self.assertNotIn("a1,", err)

    def test_match_description(self):
        result = self.run_script("--dir", self.dir, "--match", "^Read part")
        self.assertEqual(self.totals(result.stdout), ["$12.00"])
        self.assertIn("2 agent(s)", result.stderr)

    def test_match_nothing_fails(self):
        self.run_script("--dir", self.dir, "--match", "nothing", ok=False)

    def test_groups_and_combined_total(self):
        out = self.run_script(
            "--dir", self.dir,
            "--group", "reading=match:^Read",
            "--group", "lenses=b1",
            "--group", "verifiers=c1").stdout
        # Combined counts the forked m1 once: 4 + 8 + 12 + 2.
        self.assertEqual(self.totals(out),
                         ["$12.00", "$12.00", "$6.00", "$26.00"])
        self.assertIn("== combined: 3 group(s) ==", out)

    def test_group_without_name_fails(self):
        self.run_script("--dir", self.dir, "--group", "a1", ok=False)

    def test_no_arguments_prints_usage(self):
        result = self.run_script(ok=False)
        self.assertIn("Usage:", result.stderr)


if __name__ == "__main__":
    unittest.main()
