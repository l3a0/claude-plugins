#!/usr/bin/env python3
"""Check the words in a repository's Mermaid diagrams, which a parse check cannot see.

Usage:
    diagram_words.py compare <repo> <base commit> [--terms-file FILE] [--prose-may-change]
    diagram_words.py page <repo> <new folder>/out.html

Both commands name three faults that pass a render check.

1. Two statements joined on one line, which Mermaid draws as one. A sequence
   diagram draws one message whose label holds the second statement. A state
   diagram can draw one arrow, or a second one with no line of its own.
2. A flowchart, state or class label that starts like a Markdown block, such as
   "1. Refit". Mermaid 11.4.1 draws "Unsupported markdown: list" in its place,
   and 11.12.0 and 12.2.0 draw the words, so a reader's version decides whether
   this shows. The check reads node text, edge text with a space on each side,
   subgraph titles, state transitions, names, descriptions and one-line notes,
   and class names, relations with a space around the arrow, and notes. A label in
   any other form, such as a node label over several lines or a class member, goes
   unnamed, and so does a line of a state note over several lines unless it reads
   "word: text".
3. A hash or semicolon that ends a label early. A sequence label stops at a hash
   or a semicolon inside it, and a semicolon in a state transition, description or
   one-line note draws more states. An entity such as #quot; is exempt.

These are checks on what Mermaid reads, by patterns over one line at a time. They
catch the forms a real restyle produced and do not read Mermaid's whole grammar, so
a clean result is no proof. A one- or two-space join with no arrow or note, such as
"acks activate B", reads as a sentence, and only the drawn words show it. A sequence
or state label that holds a statement as words, such as "moves pending -> filled:
done", or a word such as "non-xml: bad", is named though it draws correctly, as is a
semicolon on a "word: text" line of a state note over several lines.

compare checks that a restyle of a diagram's words changed nothing else. It takes
every Markdown file that differs between the base commit and the working tree, so
check out the commit under review first. It splits each line of a block into
structure and label, and fails on:

- any change of structure: a participant, an arrow, a node, an edge, a state, a
  block keyword, a line's indent or the number of lines,
- two whole labels in one block that traded places,
- on a changed label, a number or code identifier that differs in value or order.
  An identifier is a backticked span, snake_case, camelCase, name() or a name.ext
  with two or more characters on each side. A number written in digits keeps its
  sign and a percent mark, and becoming a word counts as differing. A hyphen straight
  after a word is not read as a sign,
- on a changed label, a term from --terms-file that was lost. A term is matched as
  a lowercase substring, so "journal" also holds "journaled". Build the file from
  the repository's documented vocabulary,
- on a changed label, a new em dash or a new I, my, mine, we or our,
- on a changed line in a changed block, any fault above,
- text outside the blocks, unless --prose-may-change makes that a note.

An unchanged line in a changed block reports a fault as a note. So does a changed
label segment longer than 58 characters, the width the first restyle wrapped at,
and a quoted string that changed in a sequence, state or class label. A label form
this script cannot split is compared as a whole line, so a change to it fails rather
than passing unread, and an unquoted label that holds an arrow, such as "x --> y",
reads as such a form. A comment is ignored, and a directive or a YAML header compares as a
whole line.

A pass covers structure and those values. It does not read meaning, so a lens still
reads each new label. These pass and are the lens's to catch: a number written as a
word, the word after a number, a state or participant named in a label, a reworded
label that moved, a label that moved between blocks, and a diagram outside a *.md
file or inside a blockquote.

It exits 0 on a pass, 1 on a failure, and 2 when it compared no changed label, so a
wrong base commit never reads as a pass. A file name that is not valid text fails.

page prints the faults it finds, and writes one HTML file that draws every Mermaid
block and lists the words each one drew. out.html must be alone in its folder,
because serving that folder serves everything in it, and a diagram can hold
anyone's words:

    mkdir <new folder>
    diagram_words.py page <repo> <new folder>/out.html
    python3 -m http.server <port> --bind 127.0.0.1 --directory <new folder>

Open the page in a browser. Its heading counts what drew, then it lists every fault
and every block that failed to draw or drew no words, then each diagram's words. The
page loads Mermaid 12.2.0 from a CDN at a pinned integrity value, the version GitHub's
viewer held on 2026-11-06, which carries no published advisory there. A content
security policy stops a diagram's script from running and stops the page loading or
sending anything else. Mermaid 12.2.0 itself removes the markup that could move the
page, which the policy cannot stop, so a new version needs a fresh hostile test. The
page draws as 12.2.0 draws, so a clean page does not clear a label for a reader on an
older version. CI's browser test needs that CDN, so an outage there fails the step.
"""
import argparse
import collections
import json
import os
import re
import secrets
import subprocess
import sys

MERMAID = "12.2.0"
MERMAID_SHA384 = "sha384-8xUhuLNMjW/cI2Dacg3DR4WliYznvIg0LVG1stctThKD/YVrJFI9TNCFxft5NYgp"
CDN = f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID}/dist/mermaid.min.js"
WRAP = 58
MAX_BYTES = 5_000_000
MAX_LINE = 1_000  # Over twice any real line. Time grows faster than length, so this also bounds the run.

# Any indent, so a fence inside a list item is read too.
FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*(\S*)")
ACTOR = r"[\w-]+"
ACTORS = rf"{ACTOR}(?:\s*,\s*{ACTOR}|\s+{ACTOR})*"
SEQ_ARROW = r"(?:<<-->>|<<->>|-->>|->>|-->|->|--x|-x|--\)|-\))"
SEQ_MSG = re.compile(rf"^({ACTOR}?)\s*({SEQ_ARROW})\s*([+-]?)({ACTOR})\s*:\s*(.*)$")
SEQ_NOTE = re.compile(rf"^Note\s+(over|left of|right of)\s+({ACTORS})\s*:\s*(.*)$", re.I)
SEQ_ALIAS = re.compile(r"^(?:participant|actor)\s+\S+\s+as\s+(.*)$", re.I)
SEQ_TITLE = re.compile(r"^title\b\s*:?\s*(.*)$", re.I)
SEQ_KEY = re.compile(r"^(loop|alt|else|opt|par|and|critical|option|break)\b\s*(.*)$")
SEQ_JOIN = re.compile(
    rf"\S {{3,}}\S|(?<![\w-]){ACTOR}\s*{SEQ_ARROW}\s*[+-]?{ACTOR}\s*:|\bNote\s+(?:over|left of|right of)\s+{ACTORS}\s*:",
    re.I,
)
SEQ_STATEMENT = re.compile(rf"^[^:]*?{SEQ_ARROW}\s*[+-]?[^:]*?:")
STATE_EDGE = re.compile(r"^(\S+?)\s*-->\s*([^\s:]+(?::::\S+)?)(?:\s*:(?!:)\s*(.*))?$")
STATE_NOTE = re.compile(r"^note\s+(left of|right of)\s+(\S+?)\s*:\s*(.*)$", re.I)
STATE_NAME = re.compile(r'^state\s+"([^"]*)"')
STATE_TEXT = re.compile(r"^([\w-]+)\s*:(?!:)\s*(.*)$")
STATE_JOIN = re.compile(r"-->\s*\S+\s*(?::.*)?$|\S {3,}\S|\bnote\s+(?:left of|right of)\s+\S+\s*:", re.I)
CLASS_NAME = re.compile(r'^(class\s+\S+?)\["([^"]*)"\](.*)$')
CLASS_RELATION = re.compile(r'^(\S+(?:\s+"[^"]*")?\s+\S*(?:--|\.\.)\S*(?:\s+"[^"]*")?\s+\S+)\s*:\s*(.*)$')
CLASS_NOTE = re.compile(r'^(note\b[^"]*)"([^"]*)"\s*$')
ER_REL = re.compile(r'^(\S+\s+\S+(?:--|\.\.)\S+\s+\S+)\s*:\s*(?:"([^"]*)"|((?:(?!--)[^\s":])+))$')
FLOW_EXACT = re.compile(r"^(?:.*@\{|%%|(?:classDef|class|style|linkStyle|click|direction|end|flowchart|graph)(?=\s|$))")
FLOW_SUBGRAPH = re.compile(r"subgraph\s+([^\[\"]*)")
FLOW_QUOTED_SUBGRAPH = re.compile(r'subgraph\s+"([^"\s]*)"')
FLOW_ARROWS = ("-->", "==>", ".->", "---", "===")
FLOW_CROSS = re.compile(r"--[xo](?=\s|$)")
FLOW_EDGE = re.compile(r"(?<![-=.])(--|==|-\.)\s+((?:(?!--|==|\.-).)+?)\s+(-->|==>|\.->|---|===|-\.-|--x|--o)(?=\s|$)")
MARKDOWN_BLOCK = re.compile(r"^\s*`?(?:\d+[.)]|[-+*]|#{1,6}|>)(?:\s|$)|^\s*(?:-{3,}|\*{3,}|_{3,})\s*$|^\s*(?:~{3,}|`{3,})")
IDENT = re.compile(r"`[^`]+`|\b\w+\(\)|\b\w+_\w+\b|\b[a-z][a-zA-Z0-9]*[A-Z]\w*\b|\b[A-Z][a-z0-9]+[A-Z]\w*\b|\b[\w-]{2,}\.[A-Za-z]\w+\b")
NUMBER = re.compile(r"(?:(?<!\w)-|[+−])?\d+(?:\.\d+)?%?")
ENTITY = re.compile(r"#\w+;")
NOT_DRAWN = re.compile(r"^(?:%%|accTitle\b|accDescr\b)")
SPACES = re.compile(r"\s{4,}")
FIRST_PERSON = re.compile(r"\b(?:I(?!/)|[Mm]y|[Mm]ine|[Ww]e|[Oo]ur)\b")
OPENERS = {"[": "]", "(": ")", "{": "}"}
FAMILIES = (
    ("flowchart", "flowchart"),
    ("graph", "flowchart"),
    ("sequenceDiagram", "sequence"),
    ("stateDiagram", "state"),
    ("classDiagram", "class"),
    ("erDiagram", "er"),
)


def git(repo, *args):
    done = subprocess.run(("git", "-C", repo, *args), capture_output=True)
    return done.returncode, done.stdout.decode(errors="replace"), done.stderr.decode(errors="replace").strip()


def plain(text):
    """Blank control characters and line breaks, so a diagram's words or a file's name cannot forge a line."""
    return re.sub(r"[\x00-\x1f\x7f-\x9f\u200e\u200f\u2028-\u202e\u2066-\u2069]", "?", text)


def stop(message):
    print(plain(message), file=sys.stderr)
    sys.exit(2)


def split_blocks(text):
    """Return ([(line of the fence, [(line number, text)])], the lines outside every Mermaid block).

    Every fence is tracked, so a ```mermaid example inside a longer fence stays text.
    """
    blocks, outside = [], []
    fence, block, start = None, None, 0
    for number, line in enumerate(re.split(r"\r\n?|\n", text), 1):  # Mermaid breaks a line at a bare return too.
        if fence is None:
            opened = FENCE.match(line)
            if opened and opened[2] == "mermaid":
                fence, block, start = opened[1], [], number
                outside.append("<<BLOCK>>")
                continue
            if opened:
                fence = opened[1]
            outside.append(line)
            continue
        closes = line.strip() and set(line.strip()) == {fence[0]} and len(line.strip()) >= len(fence)
        if block is None:
            outside.append(line)
        elif not closes:
            if len(line) > MAX_LINE:
                raise ValueError(f"line {number} is over {MAX_LINE} characters")
            block.append((number, line))
        else:
            blocks.append((start, block))
        if closes:
            fence, block = None, None
    if block is not None:
        raise ValueError(f"the block at line {start} has no closing fence")
    return blocks, outside


def kind_of(lines):
    """Return the diagram's first keyword, past a comment or a YAML header."""
    header = False
    for _, line in lines:
        text = line.strip()
        if text == "---":
            header = not header
        elif text and not header and not text.startswith("%%"):
            return text.split()[0]
    return "?"


def header_lines(lines):
    """Return the numbers of the lines of a block's YAML header, which draw no label."""
    numbers, inside = set(), False
    for number, line in lines:
        if line.strip() == "---":
            numbers.add(number)
            inside = not inside
        elif inside:
            numbers.add(number)
        elif line.strip():
            break
    return numbers


def squeezed(text):
    """Cut a long run of spaces, which could otherwise match the patterns below many ways."""
    return SPACES.sub("   ", text.strip())


def family_of(kind):
    for prefix, family in FAMILIES:
        if kind.startswith(prefix):
            return family
    return None


def skel_sequence(text):
    if not text:
        return ("blank",), []
    found = SEQ_MSG.match(text)
    if found:
        return ("msg", found[1], found[2], found[3], found[4]), [found[5]]
    found = SEQ_NOTE.match(text)
    if found:
        return ("note", found[1], re.sub(r"\s*,\s*", ",", found[2])), [found[3]]
    found = SEQ_ALIAS.match(text)
    if found:
        return ("exact", text), [found[1]]
    found = SEQ_TITLE.match(text)
    if found:
        return ("title",), [found[1]]
    found = SEQ_KEY.match(text)
    if found:
        return ("key", found[1]), [found[2]]
    return ("exact", text), []


def flow_shape(text, start):
    """Return where the node text opening at start closes, or -1."""
    if text[start] == ">":
        return text.find("]", start)
    depth, quoted = 0, False
    for index in range(start, len(text)):
        char = text[index]
        if char == '"':
            quoted = not quoted
        elif not quoted and char in OPENERS:
            depth += 1
        elif not quoted and char in OPENERS.values():
            depth -= 1
            if depth == 0:
                return index
    return -1


def holds_link(span, opener):
    """Say whether a span runs past a closing arrow, so it is more of the line rather than a label."""
    words = span.strip()
    if opener == '"' or words.startswith('"') or not words.strip("-=."):
        return False
    return any(arrow in words for arrow in FLOW_ARROWS) or FLOW_CROSS.search(words) is not None


def skel_flow(text):
    """Replace each node's text and each edge label with an empty mark, keeping the shape around it."""
    if not text or FLOW_EXACT.match(text):
        return ("exact", text), []
    bare = FLOW_SUBGRAPH.fullmatch(text) or FLOW_QUOTED_SUBGRAPH.fullmatch(text)
    if bare:
        return ("exact", text), [bare[1]]
    out, labels, index = [], [], 0
    subgraph = text.startswith("subgraph ")
    while index < len(text):
        char = text[index]
        before = text[index - 1] if index else ""
        after_id = before.isalnum() or before == "_" or (subgraph and before == " ")
        if char == '"' or char == "|":
            end = text.find(char, index + 1)
            if end > 0 and holds_link(text[index + 1 : end], char):
                return ("exact", text), []
            if end > 0:
                labels.append(text[index + 1 : end].strip('"'))
                out.append(char + '""' + char if char == "|" else '""')
                index = end + 1
                continue
        if after_id and (char in OPENERS or char == ">"):
            end = flow_shape(text, index)
            inner = text[index : end + 1] if end > 0 else ""
            width = 1 if char == ">" else len(inner) - len(inner.lstrip("[({/\\"))
            if end > 0 and holds_link(inner[width:-width], char) and char != ">":
                return ("exact", text), []
            if end > 0 and not holds_link(inner[width:-width], char):
                labels.append(inner[width:-width].strip('"'))
                out.append(inner[:width] + '""' + inner[-width:])
                index = end + 1
                continue
        out.append(char)
        index += 1

    def edge(found):
        if found[2] != '""':
            labels.append(found[2])
        return found[1] + ' "" ' + found[3]

    return ("line", FLOW_EDGE.sub(edge, "".join(out))), labels


def skel_state(text):
    if not text:
        return ("blank",), []
    found = STATE_EDGE.match(text)
    if found:
        return ("edge", found[1], found[2], bool(found[3])), [found[3]] if found[3] else []
    found = STATE_NOTE.match(text)
    if found:
        return ("note", found[1], found[2]), [found[3]]
    found = STATE_NAME.match(text)
    if found:
        return ("exact", text), [found[1]]
    found = STATE_TEXT.match(text)
    if found:
        return ("text", found[1]), [found[2]]
    return ("exact", text), []


def skel_class(text):
    found = CLASS_NAME.match(text)
    if found:
        return ("name", found[1], found[3]), [found[2]]
    found = CLASS_RELATION.match(text)
    if found:
        return ("rel", found[1].strip()), [found[2]]
    found = CLASS_NOTE.match(text)
    if found:
        return ("note", found[1].strip()), [found[2]]
    return ("exact", text), []


def skel_er(text):
    found = ER_REL.match(text)
    if found:
        return ("rel", found[1]), [found[2] if found[2] is not None else found[3]]
    return ("exact", text), []


def skel_exact(text):
    return ("exact", text), []


SKELETONS = {
    "sequence": skel_sequence,
    "flowchart": skel_flow,
    "state": skel_state,
    "class": skel_class,
    "er": skel_er,
}


def faults(family, text, labels):
    """Name what renders without an error yet draws the wrong thing, on one stripped line."""
    found = []
    if NOT_DRAWN.match(text):
        return found
    if family == "sequence":
        statement = SEQ_MSG.match(text) or not (SEQ_ALIAS.match(text) or SEQ_TITLE.match(text) or SEQ_KEY.match(text))
        first = SEQ_STATEMENT.match(text) if statement else None
        body = text[first.end() :] if first else " ".join(labels) or text
        if SEQ_JOIN.search(body):
            found.append(f"second statement suspected on this line: {text}")
    named = family == "state" and STATE_NAME.match(text)
    if family == "state":
        rest = text[named.end() :] if named else text
        head, _, label = rest.partition(":")
        if (named and "-->" in rest) or head.count("-->") > 1 or STATE_JOIN.search(label):
            found.append(f"second statement suspected on this line: {text}")
    if family == "sequence" or (family == "state" and not named):
        for label in labels:
            words = ENTITY.sub("", label)
            if family == "sequence":
                words = words.rstrip("; ")
            if any(mark in words for mark in ("#;" if family == "sequence" else ";")):
                found.append(f"hash or semicolon ends this label early: {label}")
    if family in ("flowchart", "state", "class"):
        for label in labels:
            if MARKDOWN_BLOCK.match(label):
                found.append(f"label starts like a Markdown block: {label}")
    return found


def block_faults(lines):
    """Return (line number, fault) for every line of a block."""
    family = family_of(kind_of(lines))
    skeleton = SKELETONS.get(family, skel_exact)
    header = header_lines(lines)
    found = []
    for number, line in lines:
        if number not in header:
            text = squeezed(line)
            found += [(number, fault) for fault in faults(family, text, skeleton(text)[1])]
    return found


def markdown_files(repo, *which):
    code, out, err = git(repo, "ls-files", "-z", *which, "--exclude-standard", "--", "*.md")
    if code:
        stop(f"git ls-files failed: {err}")
    return set(out.split("\0")) - {""}


def changed_files(repo, base):
    code, out, err = git(repo, "diff", "-z", "--name-only", "--no-renames", base, "--", "*.md")
    if code:
        stop(f"git diff {base} failed: {err}")
    return sorted((set(out.split("\0")) - {""}) | markdown_files(repo, "--others"))


def read_base(repo, base, path):
    code, size, _ = git(repo, "cat-file", "-s", f"{base}:{path}")
    if code:
        return ""
    if int(size) > MAX_BYTES:
        raise ValueError(f"over {MAX_BYTES} bytes at the base commit")
    return git(repo, "show", f"{base}:{path}")[1]


def read_file(repo, path):
    """Read a file inside the repository, or return "" for one that is gone."""
    full = os.path.join(repo, path)
    if not os.path.lexists(full):
        return ""
    root, real = os.path.realpath(repo), os.path.realpath(full)
    if os.path.commonpath([root, real]) != root or not os.path.isfile(real):
        raise ValueError("not a regular file inside the repository")
    if os.path.getsize(real) > MAX_BYTES:
        raise ValueError(f"over {MAX_BYTES} bytes")
    with open(real, newline="", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def per_label(pattern, labels):
    return [pattern.findall(ENTITY.sub("", label)) for label in labels]


def compare_line(path, family, old, new, terms, block_changed, header, report, notes):
    """Compare one line of a block, and return its old and new labels."""
    old_line, new_number, new_line = old[1], new[0], new[1]
    skeleton = skel_exact if old[0] in header else SKELETONS.get(family, skel_exact)
    old_text, new_text = squeezed(old_line), squeezed(new_line)
    if old_text.startswith("%%") and new_text.startswith("%%") and "%%{" not in old_text + new_text:
        return [], []
    old_skel, old_labels = skeleton(old_text)
    new_skel, new_labels = skeleton(new_text)
    place = f"{path}:{new_number}"
    if old_line[: len(old_line) - len(old_line.lstrip())] != new_line[: len(new_line) - len(new_line.lstrip())]:
        report(f"{place}: leading whitespace changed")
    if old_skel != new_skel:
        report(f"{place}: structure changed, old {old_skel}, new {new_skel}")
    if block_changed and old[0] not in header:
        for fault in faults(family, new_text, new_labels):
            (report if old_line != new_line else notes.append)(f"{place}: {fault}")
    if old_labels == new_labels:
        return old_labels, new_labels
    was, now = " | ".join(old_labels), " | ".join(new_labels)
    if now.count("—") > was.count("—"):
        report(f"{place}: em dash in label: {now}")
    if len(FIRST_PERSON.findall(now)) > len(FIRST_PERSON.findall(was)):
        report(f"{place}: first person: {now}")
    if per_label(NUMBER, old_labels) != per_label(NUMBER, new_labels):
        report(f"{place}: numbers differ or moved: {was!r} -> {now!r}")
    if per_label(IDENT, old_labels) != per_label(IDENT, new_labels):
        report(f"{place}: identifiers differ or moved: {was!r} -> {now!r}")
    lost = {term for term in terms if term in was.lower() and term not in now.lower()}
    if lost:
        report(f"{place}: pinned term dropped {sorted(lost)}: {was!r} -> {now!r}")
    if family != "flowchart" and re.findall(r'"([^"]*)"', was) != re.findall(r'"([^"]*)"', now):
        notes.append(f"{place}: quoted string changed: {was!r} -> {now!r}")
    for segment in re.split(r"<br\s*/?>| \| ", now):
        if len(segment) > WRAP:
            notes.append(f"{place}: {len(segment)} characters: {segment}")
    return old_labels, new_labels


def moved_labels(pairs):
    """Return each label that traded places with another changed label."""
    old = {(line, index): label for line, (labels, _) in enumerate(pairs) for index, label in enumerate(labels)}
    new = {(line, index): label for line, (_, labels) in enumerate(pairs) for index, label in enumerate(labels)}
    changed = {place for place in old if place in new and old[place] != new[place]}
    arrived = {new[place] for place in changed}
    left = collections.defaultdict(set)
    for place in changed:
        left[old[place]].add(place)
    return sorted({new[place] for place in changed if left[new[place]] and old[place] in arrived})


def compare(args):
    code, base, err = git(args.repo, "rev-parse", "--verify", "--end-of-options", f"{args.base}^{{commit}}")
    if code:
        stop(f"{args.base} is not a commit in {args.repo}: {err}")
    base = base.strip()
    terms = []
    if args.terms_file:
        try:
            with open(args.terms_file, encoding="utf-8") as handle:
                terms = [line.strip().lower() for line in handle if line.strip()]
        except OSError as error:
            stop(f"cannot read the terms file: {error}")

    failures, notes = [], []

    def report(message):
        failures.append(message)
        print("FAIL", plain(message))

    blocks_seen, lines_seen, labels_changed = 0, collections.Counter(), 0
    for path in changed_files(args.repo, base):
        if "\ufffd" in path:
            report(f"{path}: the file name is not valid text, so it cannot be read")
            continue
        try:
            old_blocks, old_out = split_blocks(read_base(args.repo, base, path))
            new_blocks, new_out = split_blocks(read_file(args.repo, path))
        except ValueError as error:
            report(f"{path}: {error}")
            continue
        if old_out != new_out:
            before, after = collections.Counter(old_out), collections.Counter(new_out)
            out_count, in_count = sum((before - after).values()), sum((after - before).values())
            message = f"{path}: text outside the blocks changed, {out_count} lines out, {in_count} in"
            (notes.append if args.prose_may_change else report)(message)
        if not old_blocks and not new_blocks:
            continue
        if len(old_blocks) != len(new_blocks):
            report(f"{path}: {len(old_blocks)} blocks became {len(new_blocks)}")
            continue
        for index, ((start, old), (_, new)) in enumerate(zip(old_blocks, new_blocks), 1):
            blocks_seen += 1
            kind = kind_of(old)
            if kind != kind_of(new):
                report(f"{path} block {index}: kind {kind} became {kind_of(new)}")
                continue
            if len(old) != len(new):
                report(f"{path} block {index} (line {start}): {len(old)} lines became {len(new)}")
                continue
            lines_seen[kind] += len(old)
            family, changed, pairs = family_of(kind), old != new, []
            header = header_lines(old)
            for old_line, new_line in zip(old, new):
                pairs.append(compare_line(path, family, old_line, new_line, terms, changed, header, report, notes))
                labels_changed += pairs[-1][0] != pairs[-1][1] or (old_line[0] in header and old_line[1] != new_line[1])
            for label in moved_labels(pairs):
                report(f"{path} block {index} (line {start}): label moved: {label}")

    print("base commit:", base)
    print("blocks compared:", blocks_seen)
    print("lines compared by kind:", dict(lines_seen))
    print("lines whose label changed:", labels_changed)
    print("notes:", *(plain(note) for note in notes or ["none"]), sep="\n  ")
    if labels_changed == 0 and not failures:
        print("RESULT: NOTHING COMPARED, no changed Markdown file holds a changed Mermaid label")
        return 2
    print("RESULT:", "FAILED" if failures else "PASS", f"({len(failures)} failures)")
    return 1 if failures else 0


PAGE = """<!doctype html><meta charset=utf-8>
<meta http-equiv=Content-Security-Policy content="default-src 'none'; script-src 'nonce-%(nonce)s' %(url)s; style-src 'unsafe-inline'; img-src data:; font-src data:; form-action 'none'; base-uri 'none'">
<title>drawing</title>
<h1 id=head>Drawing</h1><pre id=failed></pre><pre id=drawn></pre><div id=out></div>
<script src="%(url)s" integrity="%(integrity)s" crossorigin=anonymous></script>
<script nonce=%(nonce)s>const BLOCKS=%(blocks)s;
const failed=BLOCKS.flatMap(b=>b.faults),drawn=[],out=document.getElementById('out');
function show(head){document.getElementById('head').textContent=head;
document.getElementById('failed').textContent=failed.join('\\n');
document.getElementById('drawn').textContent=drawn.map(d=>d.place+'\\n  '+d.words.join('\\n  ')).join('\\n\\n');
out.remove()}
(async()=>{mermaid.initialize({startOnLoad:false});
for(const [i,b] of BLOCKS.entries()){const place=b.file+':'+b.line;
try{const r=await mermaid.render('d'+i,b.src);const d=document.createElement('div');d.innerHTML=r.svg;out.appendChild(d);
d.querySelectorAll('br').forEach(e=>e.replaceWith(' / '));
const words=[...d.querySelectorAll('text, foreignObject')].map(e=>e.textContent.replace(/\\s+/g,' ').trim()).filter(Boolean);
drawn.push({place,words});
if(!words.length)failed.push(place+': drew no words')
}catch(e){failed.push(place+': '+String(e.message||e).slice(0,300))}}
show(drawn.length+' of '+BLOCKS.length+' drew, '+failed.length+' failed')
})().catch(e=>{failed.push('the page could not run: '+String(e.message||e).slice(0,300));
show('Mermaid did not load, so nothing drew')});</script>
"""


def page(args):
    folder = os.path.dirname(os.path.abspath(args.out))
    if not os.path.isdir(folder):
        stop(f"{folder} does not exist")
    others = set(os.listdir(folder)) - {os.path.basename(args.out)}
    if others:
        stop(f"{folder} holds other files, and serving it would serve them: use a new folder")
    blocks, found = [], []
    for path in sorted(markdown_files(args.repo, "--cached", "--others")):
        if "\ufffd" in path:
            stop(f"{path}: the file name is not valid text, so it cannot be read")
        try:
            parsed, _ = split_blocks(read_file(args.repo, path))
        except ValueError as error:
            stop(f"{path}: {error}")
        for start, lines in parsed:
            faulted = [plain(f"{path}:{number}: {fault}") for number, fault in block_faults(lines)]
            found += faulted
            source = "\n".join(line for _, line in lines)
            blocks.append({"file": plain(path), "line": start, "src": source, "faults": faulted})
    if not blocks:
        print("no Mermaid block in those files", file=sys.stderr)
        return 2
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(
            PAGE
            % {
                "nonce": secrets.token_hex(16),
                "url": CDN,
                "integrity": MERMAID_SHA384,
                "blocks": json.dumps(blocks).replace("<", "\\u003c"),
            }
        )
    print(f"wrote {len(blocks)} blocks to {args.out}, for Mermaid {MERMAID}")
    print("faults:", *(found or ["none"]), sep="\n  ")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("compare", help="check that a restyle changed only labels")
    one.add_argument("repo")
    one.add_argument("base")
    one.add_argument("--terms-file", help="the repository's documented vocabulary, one term per line")
    one.add_argument("--prose-may-change", action="store_true", help="note a change outside the blocks, not fail")
    one.set_defaults(run=compare)
    two = commands.add_parser("page", help="write a page that lists the words each block drew")
    two.add_argument("repo")
    two.add_argument("out")
    two.set_defaults(run=page)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
