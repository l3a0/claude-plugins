#!/usr/bin/env python3
"""Rewrite every call of one dotted function in Python files, from a template.

Usage:
    rewrite_calls.py TARGET TEMPLATE FILE... [--check]
    rewrite_calls.py TARGET --spec SPEC.json FILE [--check]
    rewrite_calls.py TARGET --list FILE...

TARGET is the called name as the source spells it, such as `self._alerts.alarm`
or `log.warning`. A call matches when its function is exactly that chain of
names and attributes, so `other.self._alerts.alarm(...)` and
`self._alerts.alarm_later(...)` do not.

The script parses each file with `ast`, finds the matching calls, and replaces
each whole call with TEMPLATE filled in from that call's own source text. The
fields a template can use:

    {call}   the whole call as written
    {func}   the called name as written
    {args}   every argument as written, from the first one's start to the last
             one's end, so comments and line breaks between them stay
    {0} {1}  each positional argument as written, starred ones with their `*`
    {name}   the value of the keyword argument `name`, as written

A literal brace in a template is written `{{` or `}}`. A field a call lacks,
such as `{severity}` for a call with no `severity=` keyword, stops the run and
names the call.

Example: `rewrite_calls.py self._alerts.alarm '{func}(Alarm({args}))' src/*.py`
turns `self._alerts.alarm("disk full", code=3)` into
`self._alerts.alarm(Alarm("disk full", code=3))`.

With --spec, SPEC.json is a list with one entry per matching call in FILE, in
source order. An entry is a template for that call, or null to leave it as it
is. --list prints the matching calls with their line numbers, to write a spec
from. A count that differs from the matches stops the run.

--check prints a unified diff of what would change and writes nothing. It exits
1 if anything would change and 0 if nothing would. A normal run writes each file
and prints how many calls it rewrote.

The script refuses a file in which one matching call sits inside another, since
replacing the outer call would copy the inner one's old text. Rewrite such files
in two passes with --spec. It refuses a call with a comment between its opening
bracket and first argument, or between its last argument and closing bracket,
because `{args}` would drop it. And it refuses to write a file that no longer
parses after the rewrite. Run `ruff format` afterwards, because a template does not lay
out the lines it makes.
"""

import argparse
import ast
import difflib
import json
import io
import string
import sys
import tokenize


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = dotted(node.value)
        return None if head is None else f"{head}.{node.attr}"
    return None


class Source:
    """Maps the (line, UTF-8 byte column) positions `ast` reports to string offsets."""

    def __init__(self, text):
        self.text = text
        self.lines = text.splitlines(keepends=True)
        self.starts = [0]
        for line in self.lines:
            self.starts.append(self.starts[-1] + len(line))
        self.comments = [self.starts[t.start[0] - 1] + t.start[1]
                         for t in tokenize.generate_tokens(io.StringIO(text).readline) if t.type == tokenize.COMMENT]

    def offset(self, lineno, col):
        line = self.lines[lineno - 1] if lineno <= len(self.lines) else ""
        return self.starts[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8"))

    def span(self, node):
        return self.offset(node.lineno, node.col_offset), self.offset(node.end_lineno, node.end_col_offset)

    def segment(self, node):
        start, end = self.span(node)
        return self.text[start:end]


def find_calls(source, target):
    tree = ast.parse(source.text)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and dotted(n.func) == target]
    return sorted(calls, key=source.span)


class Fields(string.Formatter):
    def __init__(self, call_line):
        self.call_line = call_line

    def get_value(self, key, args, kwargs):
        if isinstance(key, int):
            if key >= len(args):
                raise LookupError(f"the call on line {self.call_line} has no positional argument {key}")
            return args[key]
        if key not in kwargs:
            raise LookupError(f"the call on line {self.call_line} has no field {{{key}}}")
        return kwargs[key]


def fill(source, call, template):
    nodes = [*call.args, *call.keywords]
    call_start, call_end = source.span(call)
    start = min((source.span(n)[0] for n in nodes), default=call_end)
    end = max((source.span(n)[1] for n in nodes), default=call_end)
    args_text = source.text[start:end]
    if "{call}" not in template:
        func_end = source.span(call.func)[1]
        lost = [c for c in source.comments if func_end <= c < start or end <= c < call_end]
        if lost:
            line = source.text.count("\n", 0, lost[0]) + 1
            raise ValueError(f"the call on line {call.lineno} has a comment on line {line} outside its arguments, "
                             "which the rewrite would drop; move the comment or leave the call with --spec")
    fields = {"call": source.segment(call), "func": source.segment(call.func), "args": args_text}
    for keyword in call.keywords:
        if keyword.arg is not None:
            fields[keyword.arg] = source.segment(keyword.value)
    positional = [source.segment(a) for a in call.args]
    return Fields(call.lineno).vformat(template, positional, fields)


def rewrite(text, target, templates):
    """Return the rewritten text and the number of calls changed.

    `templates` is one template for every call, or a list with one entry per call.
    """
    source = Source(text)
    calls = find_calls(source, target)
    spans = [source.span(c) for c in calls]
    for (a_start, a_end), (b_start, b_end), a, b in zip(spans, spans[1:], calls, calls[1:]):
        if b_start < a_end:
            raise ValueError(f"the call on line {b.lineno} sits inside the call on line {a.lineno}; "
                             "rewrite them in two passes with --spec")
    if isinstance(templates, list):
        if len(templates) != len(calls):
            raise ValueError(f"the spec has {len(templates)} entries but the file has {len(calls)} matching calls")
    else:
        templates = [templates] * len(calls)
    out, changed = text, 0
    for call, (start, end), template in reversed(list(zip(calls, spans, templates))):
        if template is None:
            continue
        out = out[:start] + fill(source, call, template) + out[end:]
        changed += 1
    if changed:
        try:
            ast.parse(out)
        except SyntaxError as err:
            raise ValueError(f"the rewritten file no longer parses: {err.msg} on line {err.lineno}") from None
    return out, changed


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target")
    parser.add_argument("rest", nargs="+", metavar="TEMPLATE|FILE")
    parser.add_argument("--spec", help="a JSON list of templates or nulls, one per matching call, in source order")
    parser.add_argument("--list", action="store_true", help="print the matching calls and change nothing")
    parser.add_argument("--check", action="store_true", help="print the diff, write nothing, exit 1 on a change")
    args = parser.parse_args(argv)

    if args.list or args.spec:
        template, paths = None, args.rest
    elif len(args.rest) < 2:
        parser.error("give a TEMPLATE and at least one FILE, or --spec, or --list")
    else:
        template, paths = args.rest[0], args.rest[1:]

    if args.list:
        for path in paths:
            source = Source(read(path))
            for number, call in enumerate(find_calls(source, args.target)):
                first = source.segment(call).splitlines()[0]
                print(f"{number}: {path}:{call.lineno}: {first}")
        return 0

    if args.spec:
        if len(paths) != 1:
            parser.error("--spec takes exactly one FILE, since its entries follow that file's calls")
        with open(args.spec, encoding="utf-8") as f:
            spec = json.load(f)
        if not isinstance(spec, list) or not all(e is None or isinstance(e, str) for e in spec):
            parser.error("the spec must be a JSON list whose entries are strings or null")
        template = spec

    any_change = False
    for path in paths:
        text = read(path)
        try:
            new, changed = rewrite(text, args.target, template)
        except (ValueError, LookupError, SyntaxError) as err:
            print(f"{path}: {err}", file=sys.stderr)
            return 2
        if new == text:
            if not args.check:
                print(f"{path}: no calls rewritten")
            continue
        any_change = True
        if args.check:
            sys.stdout.writelines(difflib.unified_diff(
                text.splitlines(keepends=True), new.splitlines(keepends=True), path, path))
        else:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            print(f"{path}: {changed} calls rewritten")
    return 1 if args.check and any_change else 0


if __name__ == "__main__":
    sys.exit(main())
