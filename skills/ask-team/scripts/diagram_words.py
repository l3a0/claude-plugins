#!/usr/bin/env python3
"""Check the words in a repository's Mermaid diagrams, which a parse check cannot see.

Usage:
    diagram_words.py compare <repo> <base commit> [--terms-file FILE] [--prose-may-change]
    diagram_words.py page <repo> <out.html> [--mermaid VERSION]

Both commands name the two faults that pass a render check.

1. Two statements joined on one line, which Mermaid draws as one. A sequence
   diagram draws one message whose label holds the second statement. A state
   diagram can draw one arrow, or a second one with no line of its own.
2. A flowchart, state or class label that starts like a Markdown block, such as
   "1. Refit". Mermaid 11.4.1 draws "Unsupported markdown: list" in its place,
   and 11.12.0 and 12.2.0 draw the words, so the fault depends on the reader's
   version. The check reads node and edge text, subgraph titles, state
   transitions, names, descriptions and one-line notes, and class names,
   relations and notes. A label in any other form, such as a state note over
   several lines, reaches only a page drawn at an older version, which reports
   what Mermaid printed there. A join with one space and no arrow or note, such
   as "acks activate B", reads as a sentence, so only the drawn words show it.

compare checks that a restyle of a diagram's words changed nothing else. It takes
every Markdown file that differs between the base commit and the working tree, so
check out the commit under review first. It splits each line of a block into
structure and label, and fails on:

- any change of structure: a participant, an arrow, a node, an edge, a state,
  a block keyword or the number of lines,
- a label that moved to another line or another place on its line,
- on a changed label, a number or code identifier that differs in value or order.
  An identifier is a backticked span, snake_case, camelCase or name.ext. A number
  keeps its sign and a percent mark, and the word after it is not compared,
- on a changed label, a term from --terms-file that was lost. A term is matched as
  a lowercase substring, so "journal" also holds "journaled". Build the file from
  the repository's documented vocabulary,
- on a changed label, an em dash, a semicolon, a hash or first person that the old
  label did not hold. A semicolon and a hash can end a label early. An entity such
  as #quot; is exempt,
- on a changed line in a changed block, either fault above,
- text outside the blocks, unless --prose-may-change makes that a note.

An unchanged line in a changed block reports a fault as a note. So does a changed
label segment longer than 58 characters, the width the first restyle wrapped at,
and a quoted string that changed in a sequence, state, class or entity label,
because an entry name stays exact. A label form this script cannot split is
compared as a whole line, so a change to it fails rather than passing unread. A
pass covers structure and those values. It says nothing about whether a new label
means what the old one meant.

It exits 0 on a pass, 1 on a failure, and 2 when it could compare nothing, so a
wrong base commit never reads as a pass.

page prints the faults it finds, and writes one HTML file that draws every Mermaid
block and lists the words each one drew. out.html must be alone in its folder,
because serving that folder serves everything in it, and a diagram can hold
anyone's words:

    mkdir <new folder>
    diagram_words.py page <repo> <new folder>/out.html
    python3 -m http.server <port> --bind 127.0.0.1 --directory <new folder>

Open the page in a browser. Its heading counts what drew, then it lists every block
that failed to draw, drew no words, printed "Unsupported markdown" or holds either
fault, then each diagram's words. The page loads Mermaid
from a CDN at the version --mermaid names, by default the one GitHub's viewer held
on 2026-11-06, which carries no published advisory there. A content security policy
stops a diagram's script from running or sending anything out at any version. At
11.4.1 a label can still move the page to another address, which reads no file.
"""
import argparse
import collections
import difflib
import html
import json
import os
import re
import secrets
import subprocess
import sys

MERMAID = "12.2.0"
MERMAID_SHA384 = "sha384-8xUhuLNMjW/cI2Dacg3DR4WliYznvIg0LVG1stctThKD/YVrJFI9TNCFxft5NYgp"
CDN = "https://cdn.jsdelivr.net/npm/mermaid@{}/dist/mermaid.min.js"
WRAP = 58
MAX_BYTES = 5_000_000

# Any indent, so a fence inside a list item is read too.
FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*(\S*)")
SEQ_ARROW = r"(?:<<-->>|<<->>|-->>|->>|-->|->|--x|-x|--\)|-\))"
SEQ_MSG = re.compile(r"^(\w+)\s*(" + SEQ_ARROW + r")\s*([+-]?)(\w+)\s*:\s*(.*)$")
SEQ_NOTE = re.compile(r"^Note\s+(over|left of|right of)\s+([\w, ]+?)\s*:\s*(.*)$", re.I)
SEQ_KEY = re.compile(r"^(loop|alt|else|opt|par|and|critical|option|break|rect)\b\s*(.*)$")
SEQ_JOIN = re.compile(
    r"\S {3,}\S|[\w-]+\s*" + SEQ_ARROW + r"\s*[+-]?[\w-]+\s*:|\bNote\s+(?:over|left of|right of)\s+[\w, -]+?\s*:", re.I
)
SEQ_STATEMENT = re.compile(r"^[\w-]+\s*" + SEQ_ARROW + r"\s*[+-]?[\w-]+\s*:")
STATE_EDGE = re.compile(r"^(\S+?)\s*-->\s*(\S+?)(?:\s*:\s*(.*))?$")
STATE_NOTE = re.compile(r"^note\s+(left of|right of)\s+(\S+?)\s*:\s*(.*)$")
STATE_NAME = re.compile(r'^state\s+"([^"]*)"')
STATE_TEXT = re.compile(r"^([\w-]+)\s*:\s*(.*)$")
STATE_JOIN = re.compile(r"-->\s*\S+\s*(?::.*)?$")
CLASS_NAME = re.compile(r'^(class\s+\S+?)\["([^"]*)"\](.*)$')
CLASS_RELATION = re.compile(r"^(\S.*?(?:--|\.\.)[^:]*):\s*(.*)$")
CLASS_NOTE = re.compile(r'^(note\b[^"]*)"([^"]*)"\s*$')
ER_REL = re.compile(r'^(\S+\s+\S+(?:--|\.\.)\S+\s+\S+)\s*:\s*(?:"(.*)"|(\S+))$')
FLOW_EXACT = re.compile(r"^(?:%%|classDef\b|class\b|style\b|linkStyle\b|click\b|direction\b|end\b|flowchart\b|graph\b)")
FLOW_SUBGRAPH = re.compile(r"subgraph\s+([^\[\"]*)")
FLOW_EDGE = re.compile(r"(?<![-=.])(--|==|-\.)\s+((?:(?!--|==|\.-).)+?)\s+(-->|==>|\.->|---|===|-\.-|--x|--o)(?=\s|$)")
MARKDOWN_BLOCK = re.compile(r"^\s*`?(?:\d+[.)]|[-+*]|#{1,6}|>)\s|^\s*-{3,}\s*$")
IDENT = re.compile(r"`[^`]+`|\b\w+_\w+\b|\b[A-Za-z][a-z0-9]+[A-Z]\w*\b|\b[\w-]+\.[A-Za-z]\w*\b")
NUMBER = re.compile(r"[-+−]?\d+(?:\.\d+)?%?")
ENTITY = re.compile(r"#\w+;")
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
    done = subprocess.run(
        ("git", "-C", repo, *args), capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return done.returncode, done.stdout, done.stderr.strip()


def stop(message):
    print(message, file=sys.stderr)
    sys.exit(2)


def split_blocks(text):
    """Return ([(line of the fence, [(line number, text)])], the lines outside every Mermaid block).

    Every fence is tracked, so a ```mermaid example inside a longer fence stays text.
    """
    blocks, outside = [], []
    fence, block, start = None, None, 0
    for number, line in enumerate(text.split("\n"), 1):
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
        return ("note", found[1], found[2].replace(" ", "")), [found[3]]
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


def skel_flow(text):
    """Replace each node's text and each edge label with an empty mark, keeping the shape around it."""
    if not text or FLOW_EXACT.match(text):
        return ("exact", text), []
    bare = FLOW_SUBGRAPH.fullmatch(text)
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
            if end > 0:
                labels.append(text[index + 1 : end].strip('"'))
                out.append(char + '""' + char if char == "|" else '""')
                index = end + 1
                continue
        if after_id and (char in OPENERS or char == ">"):
            end = flow_shape(text, index)
            if end > 0:
                inner = text[index : end + 1]
                width = 1 if char == ">" else len(inner) - len(inner.lstrip("[({/\\"))
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
        return ("rel", found[1], found[2] is not None), [found[2] if found[2] is not None else found[3]]
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
    if text.startswith("%%"):
        return found
    if family == "sequence":
        first = SEQ_STATEMENT.match(text)
        body = text[first.end() :] if first else " ".join(labels) or text
        if SEQ_JOIN.search(body):
            found.append(f"second statement suspected on this line: {text}")
    if family == "state":
        head, _, label = text.partition(":")
        if head.count("-->") > 1 or STATE_JOIN.search(label):
            found.append(f"second statement suspected on this line: {text}")
    if family in ("flowchart", "state", "class"):
        for label in labels:
            if MARKDOWN_BLOCK.match(label):
                found.append(f"label starts like a Markdown block: {label}")
    return found


def block_faults(lines):
    """Return (line number, fault) for every line of a block."""
    family = family_of(kind_of(lines))
    skeleton = SKELETONS.get(family, skel_exact)
    found = []
    for number, line in lines:
        text = line.strip()
        found += [(number, fault) for fault in faults(family, text, skeleton(text)[1])]
    return found


def changed_files(repo, base):
    code, out, err = git(repo, "diff", "-z", "--name-only", "--no-renames", base, "--", "*.md")
    if code:
        stop(f"git diff {base} failed: {err}")
    code, more, err = git(repo, "ls-files", "-z", "--others", "--exclude-standard", "--", "*.md")
    if code:
        stop(f"git ls-files failed: {err}")
    return sorted(set(out.split("\0") + more.split("\0")) - {""})


def read_base(repo, base, path):
    code, out, _ = git(repo, "show", f"{base}:{path}")
    return out if code == 0 else ""


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


def rose(old, new, pattern):
    """Say whether a label holds more of a mark than it did, leaving out entities."""
    return len(re.findall(pattern, ENTITY.sub("", new))) > len(re.findall(pattern, ENTITY.sub("", old)))


def compare_line(path, family, old, new, terms, block_changed, report, notes):
    """Compare one line of a block, and return its old and new labels."""
    old_line, new_number, new_line = old[1], new[0], new[1]
    skeleton = SKELETONS.get(family, skel_exact)
    old_text, new_text = old_line.strip(), new_line.strip()
    old_skel, old_labels = skeleton(old_text)
    new_skel, new_labels = skeleton(new_text)
    place = f"{path}:{new_number}"
    if old_line[: len(old_line) - len(old_line.lstrip())] != new_line[: len(new_line) - len(new_line.lstrip())]:
        report(f"{place}: leading whitespace changed")
    if old_skel != new_skel:
        report(f"{place}: structure changed\n  old {old_skel}\n  new {new_skel}")
    if block_changed:
        for fault in faults(family, new_text, new_labels):
            (report if old_line != new_line else notes.append)(f"{place}: {fault}")
    if old_line == new_line:
        return old_labels, new_labels
    was, now = " | ".join(old_labels), " | ".join(new_labels)
    for bad, name in (("—", "em dash"), (";", "semicolon"), ("#", "hash")):
        if rose(was, now, bad):
            report(f"{place}: {name} in label: {now}")
    if rose(was, now, FIRST_PERSON):
        report(f"{place}: first person: {now}")
    if now.count('"') % 2:
        report(f"{place}: unmatched quote: {now}")
    if NUMBER.findall(was) != NUMBER.findall(now):
        report(f"{place}: numbers changed: {was!r} -> {now!r}")
    if IDENT.findall(was) != IDENT.findall(now):
        report(f"{place}: identifiers changed: {was!r} -> {now!r}")
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
    """Return each label that left its place and landed where another changed label stood."""
    old = {(line, index): label for line, (labels, _) in enumerate(pairs) for index, label in enumerate(labels)}
    new = {(line, index): label for line, (_, labels) in enumerate(pairs) for index, label in enumerate(labels)}
    changed = {place for place in old if place in new and old[place] != new[place]}
    return sorted({new[place] for place in changed for other in changed - {place} if new[place] == old[other]})


def compare(args):
    code, base, err = git(args.repo, "rev-parse", "--verify", "--end-of-options", f"{args.base}^{{commit}}")
    if code:
        stop(f"{args.base} is not a commit in {args.repo}: {err}")
    base = base.strip()
    terms = []
    if args.terms_file:
        with open(args.terms_file, encoding="utf-8") as handle:
            terms = [line.strip().lower() for line in handle if line.strip()]

    failures, notes = [], []

    def report(message):
        failures.append(message)
        print("FAIL", message)

    blocks_seen, lines_seen, labels_changed = 0, collections.Counter(), 0
    for path in changed_files(args.repo, base):
        try:
            old_blocks, old_out = split_blocks(read_base(args.repo, base, path))
            new_blocks, new_out = split_blocks(read_file(args.repo, path))
        except ValueError as error:
            report(f"{path}: {error}")
            continue
        added, removed = [], []
        matcher = difflib.SequenceMatcher(a=old_out, b=new_out, autojunk=False)
        for op, a1, a2, b1, b2 in matcher.get_opcodes():
            if op != "equal":
                removed += old_out[a1:a2]
                added += new_out[b1:b2]
        if added or removed:
            message = f"{path}: text outside the blocks changed, {len(removed)} lines out, {len(added)} in"
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
            for old_line, new_line in zip(old, new):
                pairs.append(compare_line(path, family, old_line, new_line, terms, changed, report, notes))
                labels_changed += old_line[1] != new_line[1]
            for label in moved_labels(pairs):
                report(f"{path} block {index} (line {start}): label moved: {label}")

    print("base commit:", base)
    print("blocks compared:", blocks_seen)
    print("lines compared by kind:", dict(lines_seen))
    print("lines whose label changed:", labels_changed)
    print("notes:", *(notes or ["none"]), sep="\n  ")
    if blocks_seen == 0 and not failures:
        print("RESULT: NOTHING COMPARED, no changed Markdown file holds a Mermaid block")
        return 2
    print("RESULT:", "FAILED" if failures else "PASS", f"({len(failures)} failures)")
    return 1 if failures else 0


PAGE = """<!doctype html><meta charset=utf-8>
<meta http-equiv=Content-Security-Policy content="default-src 'none'; script-src 'nonce-%(nonce)s' %(url)s; style-src 'unsafe-inline'; img-src data:; font-src data:">
<title>drawing</title>
<h1 id=head>Drawing</h1><pre id=failed></pre><pre id=drawn></pre><div id=out></div>
<script src="%(url)s"%(integrity)s></script>
<script nonce=%(nonce)s>const BLOCKS=%(blocks)s;const VERSION=%(version)s;
const failed=[],drawn=[],out=document.getElementById('out');
function show(head){
document.getElementById('head').textContent=head;
document.getElementById('failed').textContent=failed.join('\\n');
document.getElementById('drawn').textContent=drawn.map(d=>d.place+'\\n  '+d.words.join('\\n  ')).join('\\n\\n');
out.remove();document.title='done'}
(async()=>{mermaid.initialize({startOnLoad:false});
for(const [i,b] of BLOCKS.entries()){const place=b.file+':'+b.line;failed.push(...b.faults);
try{const r=await mermaid.render('d'+i,b.src);const d=document.createElement('div');d.innerHTML=r.svg;out.appendChild(d);
d.querySelectorAll('br').forEach(e=>e.replaceWith(' / '));
const words=[...d.querySelectorAll('text, foreignObject')].map(e=>e.textContent.replace(/\\s+/g,' ').trim()).filter(Boolean);
drawn.push({place,words});
if(!words.length)failed.push(place+': drew no words');
for(const w of words)if(w.startsWith('Unsupported markdown'))failed.push(place+': drew '+w)
}catch(e){failed.push(place+': '+String(e.message||e).slice(0,300))}}
show(drawn.length+' of '+BLOCKS.length+' drew, in Mermaid '+VERSION+', '+failed.length+' failed')
})().catch(e=>{failed.push('the page could not run: '+String(e.message||e).slice(0,300));
show('Mermaid '+VERSION+' did not load, so nothing drew')});</script>
"""


def page(args):
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.mermaid):
        stop(f"--mermaid takes an exact version such as {MERMAID}, not {args.mermaid}")
    folder = os.path.dirname(os.path.abspath(args.out))
    others = set(os.listdir(folder)) - {os.path.basename(args.out)}
    if others:
        stop(f"{folder} holds other files, and serving it would serve them: use a new folder")
    code, out, err = git(args.repo, "ls-files", "-z", "--", "*.md")
    if code:
        stop(f"git ls-files failed: {err}")
    blocks, found = [], []
    for path in (path for path in out.split("\0") if path):
        try:
            parsed, _ = split_blocks(read_file(args.repo, path))
        except ValueError as error:
            stop(f"{path}: {error}")
        for start, lines in parsed:
            faulted = [f"{path}:{number}: {fault}" for number, fault in block_faults(lines)]
            found += faulted
            source = "\n".join(line for _, line in lines)
            blocks.append({"file": path, "line": start, "src": source, "faults": faulted})
    if not blocks:
        print("no Mermaid block in those files", file=sys.stderr)
        return 2
    integrity = ""
    if args.mermaid == MERMAID:
        integrity = f' integrity="{MERMAID_SHA384}" crossorigin=anonymous'
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(
            PAGE
            % {
                "nonce": secrets.token_hex(16),
                "url": html.escape(CDN.format(args.mermaid), quote=True),
                "integrity": integrity,
                "version": json.dumps(args.mermaid),
                "blocks": json.dumps(blocks).replace("<", "\\u003c"),
            }
        )
    print(f"wrote {len(blocks)} blocks to {args.out}, for Mermaid {args.mermaid}")
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
    two.add_argument("--mermaid", default=MERMAID, help=f"the Mermaid version to draw with, by default {MERMAID}")
    two.set_defaults(run=page)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
