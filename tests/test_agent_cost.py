#!/usr/bin/env python3
"""Tests for skills/loop-cost/scripts/agent-cost.py on synthetic transcripts.

    python3 tests/test_agent_cost.py

The transcripts are invented, so the test needs no session history and runs on
the Linux CI runner. Prices are written out here rather than read from the
script, so a typo in its PRICES table fails a test. They are the list prices
per million tokens that the script cites, from the claude-api skill's model
table cached 2026-10-06. Change both together when a price changes.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "loop-cost", "scripts", "agent-cost.py")

MILLION = 1_000_000


def record(mid, usage=None, model="claude-opus-5-5", content=(), uuid=None):
    message = {"id": mid, "role": "assistant", "model": model,
               "content": list(content)}
    if usage is not None:
        message["usage"] = usage
    return {"uuid": uuid or f"u-{mid}", "message": message}


def message(mid, input_tokens):
    # One opus message; a million input tokens is 4.00 at list price.
    return record(mid, {"input_tokens": input_tokens})


class AgentCost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        # agent id -> (description, records)
        agents = {
            "a1": ("Read part 1", [message("m1", MILLION)]),
            "a2": ("Read part 2", [message("m2", 2 * MILLION)]),
            "b1": ("Architect lens on PRs", [message("m3", 3 * MILLION)]),
            # A fork of a1: repeats its message, which must count once.
            "c1": ("Verify findings", [message("m1", MILLION),
                                       message("m4", MILLION // 2)]),
        }
        for aid, (description, records) in agents.items():
            self.write_agent(aid, records, description)

    def tearDown(self):
        self.tmp.cleanup()

    def write_agent(self, aid, records, description=None, raw_tail=""):
        base = os.path.join(self.dir, f"agent-{aid}")
        with open(base + ".jsonl", "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in records)
            f.write(raw_tail)
        if description is not None:
            with open(base + ".meta.json", "w") as f:
                json.dump({"description": description}, f)
        return base + ".jsonl"

    def run_script(self, *args, ok=True, stdin=None):
        result = subprocess.run([sys.executable, SCRIPT, *args], input=stdin,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stderr)
        return result

    def totals(self, stdout):
        return [line.split(", ")[1].split(" ")[0]
                for line in stdout.splitlines() if line.startswith("total:")]

    def model_line(self, stdout, model):
        lines = [l for l in stdout.splitlines() if l.startswith(model + ":")]
        self.assertEqual(len(lines), 1, stdout)
        return lines[0]

    def price_one(self, records):
        return self.run_script(self.write_agent("x", records)).stdout

    # Selecting agents

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

    def test_ids_from_standard_input(self):
        out = self.run_script("--dir", self.dir, "--ids-file", "-",
                              stdin="a1\nb1\n").stdout
        self.assertEqual(self.totals(out), ["$16.00"])

    def test_missing_id_fails_and_names_it(self):
        err = self.run_script("--dir", self.dir, "a1", "nope", ok=False).stderr
        self.assertIn("nope", err)
        self.assertNotIn("a1,", err)

    def test_missing_path_is_not_looked_up_in_dir(self):
        # agent-a1.jsonl exists in DIR, but this path names another folder.
        wrong = os.path.join(self.dir, "elsewhere", "agent-a1.jsonl")
        err = self.run_script("--dir", self.dir, wrong, ok=False).stderr
        self.assertIn(wrong, err)

    def test_missing_path_with_a_space_is_named_whole(self):
        wrong = os.path.join(self.dir, "Application Support", "agent-a1.jsonl")
        err = self.run_script("--dir", self.dir, wrong, ok=False).stderr
        self.assertIn(wrong, err)

    def test_existing_path_with_a_space_and_comma(self):
        folder = os.path.join(self.dir, "Application Support, copy")
        os.mkdir(folder)
        path = os.path.join(folder, "agent-a1.jsonl")
        with open(path, "w") as f:
            f.write(json.dumps(message("m1", MILLION)) + "\n")
        self.assertEqual(self.totals(self.run_script(path).stdout), ["$4.00"])

    def test_dir_that_is_not_a_folder_fails(self):
        err = self.run_script("--dir", os.path.join(self.dir, "nope"), "a1",
                              ok=False).stderr
        self.assertIn("is not a folder", err)

    def test_match_description(self):
        result = self.run_script("--dir", self.dir, "--match", "^Read part")
        self.assertEqual(self.totals(result.stdout), ["$12.00"])
        self.assertIn("2 agent(s)", result.stderr)

    def test_match_is_unanchored(self):
        out = self.run_script("--dir", self.dir, "--match", "lens on").stdout
        self.assertEqual(self.totals(out), ["$12.00"])

    def test_match_nothing_fails(self):
        self.run_script("--dir", self.dir, "--match", "nothing", ok=False)

    def test_match_skips_meta_without_transcript(self):
        with open(os.path.join(self.dir, "agent-z9.meta.json"), "w") as f:
            json.dump({"description": "Read part 9"}, f)
        out = self.run_script("--dir", self.dir, "--match", "^Read part").stdout
        self.assertEqual(self.totals(out), ["$12.00"])

    # Groups

    def test_groups_and_combined_total(self):
        out = self.run_script(
            "--dir", self.dir,
            "--group", "reading=match:^Read",
            "--group", "lenses=b1",
            "--group", "verifiers=c1").stdout
        # Combined counts the forked m1 once: 4 + 8 + 12 + 2.
        self.assertEqual(self.totals(out),
                         ["$12.00", "$12.00", "$6.00", "$26.00"])
        self.assertIn("== reading: 2 agent(s) ==", out)
        self.assertIn("== combined: 3 group(s) ==", out)

    def test_group_from_ids_file(self):
        ids = os.path.join(self.dir, "ids.txt")
        with open(ids, "w") as f:
            f.write("a1\na2\n")
        out = self.run_script("--dir", self.dir, "--group", f"r=@{ids}").stdout
        self.assertEqual(self.totals(out), ["$12.00", "$12.00"])

    def test_group_counts_an_agent_named_twice_once(self):
        out = self.run_script("--dir", self.dir,
                              "--group", "r=a1,agent-a1.jsonl").stdout
        self.assertIn("== r: 1 agent(s) ==", out)

    def test_group_without_name_fails(self):
        self.run_script("--dir", self.dir, "--group", "a1", ok=False)

    def test_group_mixed_with_plain_agents_fails(self):
        self.run_script("--dir", self.dir, "a2", "--group", "x=a1", ok=False)

    def test_no_arguments_prints_usage(self):
        result = self.run_script(ok=False)
        self.assertIn("Usage:", result.stderr)

    # Reading transcripts

    def test_last_usage_record_per_message_counts(self):
        # Streaming writes one record per content block; the last holds the
        # final usage.
        out = self.price_one([
            record("m", {"input_tokens": 1, "output_tokens": 1}, uuid="u1"),
            record("m", {"input_tokens": 1, "output_tokens": MILLION}, uuid="u2"),
        ])
        self.assertIn("output 1,000,000", self.model_line(out, "claude-opus-5-5"))

    def test_output_is_at_least_visible_content(self):
        # 400 characters of tool input is 100 tokens at four characters each,
        # though the record says 1.
        tool = {"type": "tool_use", "input": {"k": "x" * 391}}
        self.assertEqual(len(json.dumps(tool["input"])), 400)
        out = self.price_one([record("m", {"output_tokens": 1}, content=[tool])])
        self.assertIn("output 100)", self.model_line(out, "claude-opus-5-5"))

    def test_text_and_thinking_count_toward_output(self):
        content = [{"type": "text", "text": "x" * 200},
                   {"type": "thinking", "thinking": "y" * 200}]
        out = self.price_one([record("m", {"output_tokens": 0}, content=content)])
        self.assertIn("output 100)", self.model_line(out, "claude-opus-5-5"))

    def test_forked_block_counts_its_characters_once(self):
        block = [{"type": "text", "text": "x" * 400}]
        first = record("m", {"output_tokens": 0}, content=block, uuid="same")
        path = self.write_agent("x", [first])
        fork = self.write_agent("y", [first])
        out = self.run_script(path, fork).stdout
        self.assertIn("output 100)", self.model_line(out, "claude-opus-5-5"))

    def test_user_records_are_not_counted(self):
        user = record("m-user", {"input_tokens": MILLION})
        user["message"]["role"] = "user"
        out = self.price_one([user, message("m", MILLION)])
        self.assertEqual(self.totals(out), ["$4.00"])

    def test_cut_off_last_line_is_skipped(self):
        # A running agent's transcript can end partway through a line.
        path = self.write_agent("x", [message("m", MILLION)],
                                raw_tail='{"uuid": "u-cut", "message": {"id"')
        self.assertEqual(self.totals(self.run_script(path).stdout), ["$4.00"])

    # Pricing

    def test_cache_writes_by_time_to_live(self):
        out = self.price_one([record("m", {"cache_creation": {
            "ephemeral_5m_input_tokens": MILLION,
            "ephemeral_1h_input_tokens": MILLION}})])
        line = self.model_line(out, "claude-opus-5-5")
        self.assertIn("write_5m 1,000,000, write_1h 1,000,000", line)
        self.assertEqual(self.totals(out), ["$13.00"])  # 5.00 + 8.00

    def test_cache_write_without_breakdown_is_priced_at_five_minutes(self):
        out = self.price_one([record("m", {"cache_creation_input_tokens": MILLION})])
        self.assertEqual(self.totals(out), ["$5.00"])

    def test_every_listed_price(self):
        # input, 5-minute write, 1-hour write, cache read, output
        prices = {
            "claude-opus-5-5": (4.00, 5.00, 8.00, 0.20, 20.00),
            "claude-sonnet-5-5": (2.00, 2.50, 4.00, 0.20, 10.00),
            "claude-fable-5-1": (10.00, 12.50, 20.00, 0.25, 50.00),
        }
        usage = {"input_tokens": MILLION, "cache_read_input_tokens": MILLION,
                 "output_tokens": MILLION, "cache_creation": {
                     "ephemeral_5m_input_tokens": MILLION,
                     "ephemeral_1h_input_tokens": MILLION}}
        out = self.price_one([record(f"m-{model}", usage, model=model)
                              for model in prices])
        for model, rates in prices.items():
            self.assertTrue(self.model_line(out, model).endswith(
                f", ${sum(rates):,.2f}"), model)
        self.assertEqual(self.totals(out),
                         [f"${sum(sum(r) for r in prices.values()):,.2f}"])

    def test_unpriced_model_is_flagged_not_dropped(self):
        out = self.price_one([message("m", MILLION),
                              record("n", {"input_tokens": 7}, model="claude-new-9")])
        self.assertTrue(self.model_line(out, "claude-new-9").endswith(", unpriced"))
        total = [l for l in out.splitlines() if l.startswith("total:")][0]
        self.assertIn("1,000,007 tokens, $4.00", total)
        self.assertIn("excludes unpriced: claude-new-9", total)


if __name__ == "__main__":
    unittest.main()
