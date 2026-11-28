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

A literal brace in a template is written `{{` or `}}`.

Example: `rewrite_calls.py self._alerts.alarm '{func}(Alarm({args}))' src/*.py`
turns `self._alerts.alarm("disk full", code=3)` into
`self._alerts.alarm(Alarm("disk full", code=3))`.

With --spec, SPEC.json is a list with one entry per matching call in FILE, in
source order. An entry is a template for that call, or null to leave it as it
is. --list prints the matching calls with their line numbers, to write a spec
from.

--check prints a unified diff of what would change and writes nothing. It exits
1 if anything would change and 0 if nothing would. A normal run prints how many
calls it rewrote in each file.

The script works out every file's new text before it writes any file, and a
refusal in one file writes none. It refuses these cases and names the call:

1. A field the call lacks, such as `{severity}` for a call with no `severity=`.
2. A spec whose count differs from the file's matching calls.
3. One matching call inside another, since replacing the outer call would copy
   the inner one's old text. Rewrite such a file in two passes with --spec.
4. A keyword argument named `call`, `func` or `args`, which would hide the field
   of that name.
5. A comment inside the call that no field the template uses carries, such as
   one after the last argument when the template uses `{args}`, or one between
   arguments when it uses `{0}`. The rewrite would drop it.
6. A file that no longer parses after the rewrite.

Run `ruff format` afterwards, because a template does not lay out the lines it
makes. The script needs Python 3.12 or later, because older versions report
wrong positions for a call inside a multi-line f-string placeholder.
"""

import argparse
import ast
import difflib
import io
import json
import re
import string
import sys
import tokenize

RESERVED = ("call", "func", "args")


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = dotted(node.value)
        return None if head is None else f"{head}.{node.attr}"
    return None


class Source:
    """Maps the (line, UTF-8 byte column) positions `ast` reports to string offsets.

    Lines break only where Python breaks them, at \\r\\n, \\r or \\n, so a form feed
    or another character `str.splitlines` treats as a break does not shift them.
    """

    def __init__(self, text):
        self.text = text
        self.lines = [line for line in re.split(r"(?<=\n)|(?<=\r)(?!\n)", text) if line]
        self.starts = [0]
        for line in self.lines:
            self.starts.append(self.starts[-1] + len(line))
        try:
            found = list(tokenize.generate_tokens(io.StringIO(text).readline))
        except tokenize.TokenError as err:
            raise SyntaxError(err.args[0], ("<file>", err.args[1][0], 0, "")) from None
        self.comments = [self.starts[t.start[0] - 1] + t.start[1] for t in found if t.type == tokenize.COMMENT]

    def offset(self, lineno, col):
        line = self.lines[lineno - 1] if lineno <= len(self.lines) else ""
        return self.starts[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8"))

    def span(self, node):
        return self.offset(node.lineno, node.col_offset), self.offset(node.end_lineno, node.end_col_offset)

    def segment(self, node):
        start, end = self.span(node)
        return self.text[start:end]

    def line_of(self, offset):
        return next(n for n, start in enumerate(self.starts[1:], 1) if offset < start)


def find_calls(source, target):
    tree = ast.parse(source.text)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and dotted(n.func) == target]
    return sorted(calls, key=source.span)


def used_fields(template):
    """Return the field names a template uses, without any attribute, index, conversion or format spec."""
    names = set()
    for _, field, _, _ in string.Formatter().parse(template):
        if field is not None:
            names.add(re.split(r"[.\[]", field, maxsplit=1)[0])
    return names


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
    for keyword in call.keywords:
        if keyword.arg in RESERVED:
            raise ValueError(f"the call on line {call.lineno} has a keyword named {keyword.arg}, "
                             f"which would hide the {{{keyword.arg}}} field")
    nodes = [*call.args, *call.keywords]
    call_start, call_end = source.span(call)
    start = min((source.span(n)[0] for n in nodes), default=call_end)
    end = max((source.span(n)[1] for n in nodes), default=call_end)
    spans = {"call": (call_start, call_end), "func": source.span(call.func), "args": (start, end)}
    for n, arg in enumerate(call.args):
        spans[str(n)] = source.span(arg)
    for keyword in call.keywords:
        if keyword.arg is not None:
            spans[keyword.arg] = source.span(keyword.value)
    names = used_fields(template)
    if "" in names:
        names |= {str(n) for n in range(len(call.args))}
    kept = [spans[name] for name in names if name in spans]
    lost = [c for c in source.comments
            if call_start <= c < call_end and not any(a <= c < b for a, b in kept)]
    if lost:
        raise ValueError(f"the call on line {call.lineno} has a comment on line {source.line_of(lost[0])} that "
                         "no field of the template carries, so the rewrite would drop it; "
                         "move the comment or leave the call with --spec")

    fields = {name: source.text[a:b] for name, (a, b) in spans.items() if not name.isdigit()}
    positional = [source.segment(a) for a in call.args]
    return Fields(call.lineno).vformat(template, positional, fields)


def rewrite(text, target, templates):
    """Return the rewritten text and the number of calls changed.

    `templates` is one template for every call, or a list with one entry per call.
    """
    source = Source(text)
    calls = find_calls(source, target)
    spans = [source.span(c) for c in calls]
    for (_, a_end), (b_start, _), a, b in zip(spans, spans[1:], calls, calls[1:]):
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


def parse_failure(err):
    return (f"does not parse under Python {sys.version_info.major}.{sys.version_info.minor}: "
            f"{err.msg} on line {err.lineno}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target")
    parser.add_argument("rest", nargs="+", metavar="TEMPLATE|FILE")
    parser.add_argument("--spec", help="a JSON list of templates or nulls, one per matching call, in source order")
    parser.add_argument("--list", action="store_true", help="print the matching calls and change nothing")
    parser.add_argument("--check", action="store_true", help="print the diff, write nothing, exit 1 on a change")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 12):
        print("rewrite_calls.py needs Python 3.12 or later", file=sys.stderr)
        return 2

    if args.list or args.spec:
        template, paths = None, args.rest
    elif len(args.rest) < 2:
        parser.error("give a TEMPLATE and at least one FILE, or --spec, or --list")
    else:
        template, paths = args.rest[0], args.rest[1:]

    if args.list:
        for path in paths:
            try:
                source = Source(read(path))
                calls = find_calls(source, args.target)
            except SyntaxError as err:
                print(f"{path}: {parse_failure(err)}", file=sys.stderr)
                return 2
            for number, call in enumerate(calls):
                first = source.segment(call).split("\n")[0]
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

    results = []
    for path in paths:
        text = read(path)
        try:
            new, changed = rewrite(text, args.target, template)
        except SyntaxError as err:
            print(f"{path}: {parse_failure(err)}; no file was written", file=sys.stderr)
            return 2
        except (ValueError, LookupError) as err:
            print(f"{path}: {err}; no file was written", file=sys.stderr)
            return 2
        results.append((path, text, new, changed))

    any_change = False
    for path, text, new, changed in results:
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
