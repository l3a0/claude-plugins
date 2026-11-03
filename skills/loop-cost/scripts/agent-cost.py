#!/usr/bin/env python3
"""Price one or more Claude Code agent transcripts in tokens and dollars.

Usage:
    agent-cost.py [--dir DIR] [AGENT ...] [--ids-file FILE] [--match REGEX]
    agent-cost.py [--dir DIR] --group NAME=SPEC [--group NAME=SPEC ...]

An AGENT is a transcript path, such as the `output_file` an Agent spawn
returns or any session or subagent `.jsonl` under ~/.claude/projects, or an
agent id (`a1b2...`, `agent-a1b2...` or `agent-a1b2....jsonl`) resolved to
DIR/agent-<id>.jsonl. DIR defaults to the current directory and is normally
~/.claude/projects/<project>/<session>/subagents. An argument that is not an
existing file is split on spaces and commas, so a list of ids passed as one
word (a zsh variable, which zsh does not split) still works. An id with no
transcript in DIR is an error that names it.

--ids-file FILE reads ids from FILE, one or more per line, `#` starting a
comment; `-` reads standard input. --match REGEX selects every agent in DIR
whose `agent-<id>.meta.json` description matches REGEX (Python re.search), so
a loop can be priced by its agents' descriptions after a context compaction.
The matched agents are listed on standard error. Matching nothing is an error.

--group NAME=SPEC prices one group of agents, and repeating it prints one
total per group and then a combined total. SPEC is a list of agents as above,
`@FILE` for a file of ids, or `match:REGEX` for a description match. An agent
in two groups counts in each group's total but once in the combined total.

Pass every agent a loop ran (the builder, each review lens, each verifier) to
price the loop as a whole.

Streaming writes several records per message, one per content block, so the
last usage record per message id is the one counted. A message id seen in two
files (a forked transcript) counts once.

Input and cache figures are exact. Output is a lower bound. A subagent
transcript often keeps the usage from the start of the stream, so a turn that
wrote a long tool call can record single-digit output_tokens. Each message's
output is therefore the larger of that figure and its visible content (text,
tool inputs, thinking) at four characters a token. Thinking that the API
omitted is not in the transcript and cannot be counted.

The figure an Agent completion notice reports as subagent_tokens is the size
of the agent's context at its last turn, not its spend. Do not quote it as a
cost.

Prices are Anthropic first-party list prices per million tokens, from the
claude-api skill's model table cached 2026-10-06. They are list prices: on a
subscription plan the bill does not change per token, and the figure measures
usage instead. A model missing from PRICES is reported in tokens and flagged.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

# input, 5-minute cache write, 1-hour cache write, cache read, output
PRICES = {
    "claude-opus-5-5": (4.00, 5.00, 8.00, 0.20, 20.00),
    "claude-sonnet-5-5": (2.00, 2.50, 4.00, 0.20, 10.00),
    "claude-fable-5-1": (10.00, 12.50, 20.00, 0.25, 50.00),
}
FIELDS = ("input", "write_5m", "write_1h", "read", "output")


def visible_chars(content):
    chars = 0
    for block in content if isinstance(content, list) else []:
        kind = block.get("type")
        if kind == "text":
            chars += len(block.get("text", ""))
        elif kind == "thinking":
            chars += len(block.get("thinking", ""))
        elif kind == "tool_use":
            chars += len(json.dumps(block.get("input", {})))
    return chars


def last_usage_per_message(paths):
    usage, chars, seen = {}, defaultdict(int), set()
    for path in paths:
        with open(path) as f:
            for line in f:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = record.get("message") or {}
                mid = message.get("id")
                if not mid or message.get("role") != "assistant":
                    continue
                # Count each content block once, even when a forked
                # transcript repeats the record.
                key = record.get("uuid") or (path, line)
                if key not in seen:
                    seen.add(key)
                    chars[mid] += visible_chars(message.get("content"))
                if message.get("usage"):
                    usage[mid] = (message.get("model"), message["usage"])
    return {mid: (model, u, chars[mid] // 4) for mid, (model, u) in usage.items()}


def split(u, visible_output):
    created = u.get("cache_creation") or {}
    w5 = created.get("ephemeral_5m_input_tokens")
    w1 = created.get("ephemeral_1h_input_tokens")
    if w5 is None and w1 is None:
        # No TTL breakdown: price every cache write at the 5-minute rate.
        w5, w1 = u.get("cache_creation_input_tokens") or 0, 0
    return (
        u.get("input_tokens") or 0,
        w5 or 0,
        w1 or 0,
        u.get("cache_read_input_tokens") or 0,
        max(u.get("output_tokens") or 0, visible_output),
    )


def fail(message):
    sys.exit(f"agent-cost.py: {message}")


def agent_path(token, folder):
    """Resolve an agent id, in any of its spellings, to its transcript."""
    name = os.path.basename(token)
    for suffix in (".jsonl", ".meta.json"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    if not name.startswith("agent-"):
        name = "agent-" + name
    return os.path.join(folder, name + ".jsonl")


def resolve(tokens, folder):
    """Turn paths and ids into transcript paths, failing on any not found."""
    paths, missing = [], []
    for arg in tokens:
        if os.path.isfile(arg):
            paths.append(arg)
            continue
        for token in re.split(r"[\s,]+", arg.strip()):
            if not token:
                continue
            path = token if os.path.isfile(token) else agent_path(token, folder)
            if os.path.isfile(path):
                paths.append(path)
            else:
                missing.append(token)
    if missing:
        fail(f"no transcript in {folder} for {len(missing)} agent(s): "
             + ", ".join(missing))
    return paths


def read_ids(source):
    try:
        f = sys.stdin if source == "-" else open(source)
    except OSError as e:
        fail(f"cannot read ids file: {e}")
    with f:
        return [line.split("#", 1)[0] for line in f]


def match_description(pattern, folder):
    """Transcripts in folder whose agent's spawn description matches pattern."""
    try:
        regex = re.compile(pattern)
    except re.error as e:
        fail(f"bad --match pattern {pattern!r}: {e}")
    try:
        names = sorted(os.listdir(folder))
    except OSError as e:
        fail(f"cannot list {folder}: {e}")
    paths = []
    for name in names:
        if not name.endswith(".meta.json"):
            continue
        try:
            with open(os.path.join(folder, name)) as f:
                description = json.load(f).get("description") or ""
        except (OSError, ValueError, AttributeError):
            print(f"skipping unreadable {name}", file=sys.stderr)
            continue
        path = os.path.join(folder, name[: -len(".meta.json")] + ".jsonl")
        if regex.search(description) and os.path.isfile(path):
            paths.append((path, description))
    if not paths:
        fail(f"no agent in {folder} has a description matching {pattern!r}")
    print(f"match {pattern!r}: {len(paths)} agent(s)", file=sys.stderr)
    for path, description in paths:
        print(f"  {os.path.basename(path)}  {description}", file=sys.stderr)
    return [path for path, _ in paths]


def group_paths(spec, folder):
    if spec.startswith("match:"):
        return match_description(spec[len("match:"):], folder)
    if spec.startswith("@"):
        return resolve(read_ids(spec[1:]), folder)
    return resolve([spec], folder)


def report(paths):
    """Print one line per model and a total; return (tokens, dollars, unpriced)."""
    totals = defaultdict(lambda: [0] * len(FIELDS))
    turns = defaultdict(int)
    for model, u, visible_output in last_usage_per_message(paths).values():
        turns[model] += 1
        for i, n in enumerate(split(u, visible_output)):
            totals[model][i] += n

    grand_tokens, grand_dollars, unpriced = 0, 0.0, []
    for model, counts in sorted(totals.items(), key=lambda kv: str(kv[0])):
        tokens = sum(counts)
        grand_tokens += tokens
        price = PRICES.get(model)
        line = f"{model}: {turns[model]} turns, {tokens:,} tokens"
        line += " (" + ", ".join(f"{k} {n:,}" for k, n in zip(FIELDS, counts)) + ")"
        if price:
            dollars = sum(n * p for n, p in zip(counts, price)) / 1e6
            grand_dollars += dollars
            line += f", ${dollars:,.2f}"
        else:
            unpriced.append(str(model))
            line += ", unpriced"
        print(line)
    print(f"total: {grand_tokens:,} tokens, ${grand_dollars:,.2f}"
          " (output is a lower bound: omitted thinking is not counted)"
          + (f"; excludes unpriced: {', '.join(unpriced)}" if unpriced else ""))


def unique(paths):
    seen, out = set(), []
    for path in paths:
        real = os.path.realpath(path)
        if real not in seen:
            seen.add(real)
            out.append(path)
    return out


def main(argv):
    if not argv:
        sys.exit(__doc__)
    parser = argparse.ArgumentParser(
        usage=__doc__.split("Usage:\n")[1].split("\n\n")[0].strip())
    parser.add_argument("agents", nargs="*")
    parser.add_argument("--dir", default=".")
    parser.add_argument("--ids-file", action="append", default=[])
    parser.add_argument("--match", action="append", default=[])
    parser.add_argument("--group", action="append", default=[])
    args = parser.parse_args(argv)
    if not os.path.isdir(args.dir):
        fail(f"--dir {args.dir} is not a folder")

    if not args.group:
        paths = resolve(args.agents, args.dir)
        for source in args.ids_file:
            paths += resolve(read_ids(source), args.dir)
        for pattern in args.match:
            paths += match_description(pattern, args.dir)
        if not paths:
            fail("no transcripts selected")
        report(unique(paths))
        return

    if args.agents or args.ids_file or args.match:
        fail("with --group, put every agent in a group")
    groups = []
    for entry in args.group:
        name, sep, spec = entry.partition("=")
        if not sep or not name or not spec:
            fail(f"--group needs NAME=SPEC, got {entry!r}")
        groups.append((name, unique(group_paths(spec, args.dir))))
    combined = []
    for name, paths in groups:
        print(f"== {name}: {len(paths)} agent(s) ==")
        report(paths)
        combined += paths
    print(f"== combined: {len(groups)} group(s) ==")
    report(unique(combined))


if __name__ == "__main__":
    main(sys.argv[1:])
