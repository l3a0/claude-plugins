#!/usr/bin/env python3
"""Check the words in a repository's Mermaid diagrams, which a parse check cannot see.

Usage:
    diagram_words.py compare <repo> <base commit> [--terms-file FILE] [--prose-may-change]
    diagram_words.py page <repo> <out.html> [--mermaid VERSION] [--file PATH ...]

compare proves that a restyle of a diagram's words changed nothing else. It takes
every Markdown file that differs between the base commit and the working tree,
lists each block's lines as structure and label, and fails when any structure
differs: a participant, an arrow, a node, an edge, a state, the order of any of
them, or the number of lines. On a line whose label changed it fails when a
number, a code identifier or a term from --terms-file was lost. A term is matched
as a lowercase substring of the label, so one term per line such as "journal"
also holds "journaled". A label form this script cannot split is compared as a
whole line, so a change to it fails rather than passing unread. Text outside the
blocks must not change either, unless --prose-may-change turns that into a note.

Two faults pass a render check, so compare fails on each on every line of a
changed block, whether or not the line changed.

1. Two statements joined on one line of a sequence diagram, which Mermaid draws
   as one message whose label holds the second statement.
2. A flowchart, state or class label that starts like a Markdown block, such as
   "1. Refit". Mermaid 11.4.1 draws "Unsupported markdown: list" in its place.
   Mermaid 11.12.0 draws the words, so the fault depends on the reader's version.

It exits 0 on a pass, 1 on a failure, and 2 when it could compare nothing, so a
wrong base commit never reads as a proof.

page writes one HTML file that draws every Mermaid block and lists the words each
one drew. Serve its folder and read the page in a browser, because a parser
reports only whether a block parsed:

    python3 -m http.server <port> --bind 127.0.0.1 --directory <folder of out.html>

The page loads Mermaid from a CDN, at the version --mermaid names. It lists every
block that failed to draw or drew either fault above, then each diagram's words,
and sets window.RESULT. The default is the older version, because it shows both
faults, and a version a repository's readers use can be named beside it.
"""
import argparse
import collections
import difflib
import html
import json
import os
import re
import subprocess
import sys

MERMAID = "11.4.1"
WRAP = 58  # A changed label segment longer than this is listed as one to wrap.

FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*(\S*)")
SEQ_ARROW = r"(?:<<-->>|<<->>|-->>|->>|-->|->|--x|-x|--\)|-\))"
SEQ_MSG = re.compile(r"^(\w+)\s*(" + SEQ_ARROW + r")\s*([+-]?)(\w+)\s*:\s*(.*)$")
SEQ_NOTE = re.compile(r"^Note\s+(over|left of|right of)\s+([\w, ]+?)\s*:\s*(.*)$")
SEQ_KEY = re.compile(r"^(loop|alt|else|opt|par|and|critical|option|break|rect)\b\s*(.*)$")
SEQ_JOIN = re.compile(r"\S {3,}\S|\w+\s*" + SEQ_ARROW + r"\s*[+-]?\w+\s*:|\bNote\s+(?:over|left of|right of)\b")
STATE_EDGE = re.compile(r"^(\S+)\s+-->\s+(\S+?)(?:\s*:\s*(.*))?$")
STATE_NOTE = re.compile(r"^note\s+(left of|right of)\s+(\S+?)\s*:\s*(.*)$")
STATE_NAME = re.compile(r'^state\s+"([^"]*)"')
CLASS_LABEL = re.compile(r'\["([^"]*)"\]|\s:\s*(.*)$')
ER_REL = re.compile(r'^(\S+\s+\S+(?:--|\.\.)\S+\s+\S+)\s*:\s*"?(.*?)"?$')
FLOW_EXACT = re.compile(r"^(?:%%|classDef\b|class\b|style\b|linkStyle\b|click\b|direction\b|end\b|flowchart\b|graph\b)")
FLOW_EDGE = re.compile(r"(--|==|-\.)\s+(.+?)\s+(-->|==>|\.->|---|===|-\.-|--x|--o)")
MARKDOWN_BLOCK = re.compile(r"^\s*`?(?:\d+[.)]|[-+*]|#{1,6}|>)\s")
IDENT = re.compile(r"\b\w+_\w+\b|\b\w+\.json\b|\b\w+\.md\b|\bIf-Match\b")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
FIRST_PERSON = re.compile(r"\b(I|my|mine|we|our)\b")
OPENERS = {"[": "]", "(": ")", "{": "}"}


def git(repo, *args):
    done = subprocess.run(("git", "-C", repo, *args), capture_output=True, text=True)
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
    depth, index, opener = 0, start, text[start]
    if opener == ">":
        return text.find("]", start)
    quoted = False
    while index < len(text):
        char = text[index]
        if char == '"':
            quoted = not quoted
        elif not quoted and char in OPENERS:
            depth += 1
        elif not quoted and char in OPENERS.values():
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def skel_flow(text):
    """Replace each node's text and each edge label with an empty mark, keeping the shape around it."""
    if not text or FLOW_EXACT.match(text) or re.fullmatch(r"subgraph\b[^\[\"]*", text):
        return ("exact", text), []
    out, labels, index = [], [], 0
    subgraph = text.startswith("subgraph ")
    while index < len(text):
        char = text[index]
        after_id = index > 0 and (text[index - 1].isalnum() or text[index - 1] == "_")
        after_id = after_id or (subgraph and text[index - 1:index] == " ")
        if char == '"' or char == "|":
            end = text.find(char, index + 1)
            if end > 0:
                labels.append(text[index + 1:end].strip('"'))
                out.append(char + '""' + char if char == "|" else '""')
                index = end + 1
                continue
        if after_id and (char in OPENERS or char == ">"):
            end = flow_shape(text, index)
            if end > 0:
                inner = text[index : end + 1]
                width = len(inner) - len(inner.lstrip("[({/\\>"))
                labels.append(inner[width:-width].strip('"'))
                out.append(inner[:width] + '""' + inner[-width:])
                index = end + 1
                continue
        out.append(char)
        index += 1
    def edge(found):
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
    return ("exact", text), []


def skel_exact(text):
    return ("exact", text), []


def skel_er(text):
    found = ER_REL.match(text)
    if found:
        return ("rel", found[1]), [found[2]]
    return ("exact", text), []


SKELETONS = {
    "sequenceDiagram": skel_sequence,
    "flowchart": skel_flow,
    "graph": skel_flow,
    "stateDiagram-v2": skel_state,
    "stateDiagram": skel_state,
    "erDiagram": skel_er,
}


def faults(kind, text, labels):
    """Name what renders without an error yet draws the wrong thing, on one stripped line."""
    found = []
    if kind == "sequenceDiagram":
        if any(SEQ_JOIN.search(label) for label in labels):
            found.append(f"second statement joined to this line: {text}")
    if kind in ("stateDiagram-v2", "stateDiagram") and len(re.findall(r"-->", text)) > 1:
        found.append(f"second statement joined to this line: {text}")
    if kind in ("flowchart", "graph", "stateDiagram-v2", "stateDiagram"):
        words = labels + STATE_NAME.findall(text)
    elif kind == "classDiagram":
        words = [a or b for a, b in CLASS_LABEL.findall(text)]
    else:
        words = []
    for word in words:
        if MARKDOWN_BLOCK.match(word):
            found.append(f"label starts like a Markdown block: {word}")
    return found


def changed_files(repo, base):
    code, out, err = git(repo, "diff", "--name-only", "--no-renames", base, "--", "*.md")
    if code:
        stop(f"git diff {base} failed: {err}")
    code, more, err = git(repo, "ls-files", "--others", "--exclude-standard", "--", "*.md")
    if code:
        stop(f"git ls-files failed: {err}")
    return sorted(set(out.split("\n") + more.split("\n")) - {""})


def read_base(repo, base, path):
    code, out, _ = git(repo, "show", f"{base}:{path}")
    return out if code == 0 else ""


def read_file(repo, path):
    try:
        with open(os.path.join(repo, path), newline="", encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        return ""


def compare_line(path, kind, old, new, terms, report, notes):
    """Compare one line of a block, and return whether its label changed."""
    number, old_line = old[0], old[1]
    new_number, new_line = new[0], new[1]
    skeleton = SKELETONS.get(kind, skel_exact)
    old_text, new_text = old_line.strip(), new_line.strip()
    old_skel, old_labels = skeleton(old_text)
    new_skel, new_labels = skeleton(new_text)
    place = f"{path}:{new_number}"
    if old_line[: len(old_line) - len(old_line.lstrip())] != new_line[: len(new_line) - len(new_line.lstrip())]:
        report(f"{place}: leading whitespace changed")
    if old_skel != new_skel:
        report(f"{place}: structure changed\n  old {old_skel}\n  new {new_skel}")
    for fault in faults(kind, new_text, new_labels):
        report(f"{place}: {fault}")
    if old_line == new_line:
        return False
    was, now = " | ".join(old_labels), " | ".join(new_labels)
    for bad, name in (("—", "em dash"), (";", "semicolon"), ("#", "hash")):
        if bad in now:
            report(f"{place}: {name} in label: {now}")
    if FIRST_PERSON.search(now):
        report(f"{place}: first person: {now}")
    if now.count('"') % 2:
        report(f"{place}: unmatched quote: {now}")
    if collections.Counter(NUMBER.findall(was)) != collections.Counter(NUMBER.findall(now)):
        report(f"{place}: numbers changed: {was!r} -> {now!r}")
    if collections.Counter(IDENT.findall(was)) != collections.Counter(IDENT.findall(now)):
        report(f"{place}: identifiers changed: {was!r} -> {now!r}")
    lost = {term for term in terms if term in was.lower() and term not in now.lower()}
    if lost:
        report(f"{place}: pinned term dropped {sorted(lost)}: {was!r} -> {now!r}")
    for segment in re.split(r"<br\s*/?>| \| ", now):
        if len(segment) > WRAP:
            notes.append(f"{place}: {len(segment)} characters: {segment}")
    return True


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
            for old_line, new_line in zip(old, new):
                labels_changed += compare_line(path, kind, old_line, new_line, terms, report, notes)

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


PAGE = """<!doctype html><meta charset=utf-8><title>drawing</title>
<h1 id=head>Drawing</h1><pre id=failed></pre><pre id=drawn></pre><div id=out hidden></div>
<script src="https://cdn.jsdelivr.net/npm/mermaid@%(version)s/dist/mermaid.min.js"></script>
<script>const BLOCKS=%(blocks)s;
const JOINED=/\\w\\s*-{1,2}>{1,2}\\s*[+-]?\\w+\\s*:|\\bNote (over|left of|right of)\\b/;
(async()=>{mermaid.initialize({startOnLoad:false});
const failed=[],drawn=[],out=document.getElementById('out');out.hidden=false;
for(const [i,b] of BLOCKS.entries()){const place=b.file+':'+b.line;
try{const r=await mermaid.render('d'+i,b.src);const d=document.createElement('div');d.innerHTML=r.svg;out.appendChild(d);
d.querySelectorAll('br').forEach(e=>e.replaceWith(' / '));
const words=[...d.querySelectorAll('text, foreignObject')].map(e=>e.textContent.replace(/\\s+/g,' ').trim()).filter(Boolean);
drawn.push({place,words});
for(const w of words)if(w.startsWith('Unsupported markdown')||JOINED.test(w))failed.push(place+': drew '+w)
}catch(e){failed.push(place+': '+String(e.message||e).slice(0,300))}}
out.hidden=true;
window.RESULT={version:%(version_json)s,total:BLOCKS.length,failed,drawn};
document.getElementById('head').textContent=drawn.length+' of '+BLOCKS.length+' drew, in Mermaid '+%(version_json)s+', '+failed.length+' failed';
document.getElementById('failed').textContent=failed.join('\\n');
document.getElementById('drawn').textContent=drawn.map(d=>d.place+'\\n  '+d.words.join('\\n  ')).join('\\n\\n');
document.title='done'})();</script>
"""


def page(args):
    paths = args.paths
    if not paths:
        code, out, err = git(args.repo, "ls-files", "--", "*.md")
        if code:
            stop(f"git ls-files failed: {err}")
        paths = [path for path in out.split("\n") if path]
    blocks = []
    for path in paths:
        try:
            found, _ = split_blocks(read_file(args.repo, path))
        except ValueError as error:
            stop(f"{path}: {error}")
        for start, lines in found:
            blocks.append({"file": path, "line": start, "src": "\n".join(line for _, line in lines)})
    if not blocks:
        print("no Mermaid block in those files", file=sys.stderr)
        return 2
    data = json.dumps(blocks).replace("<", "\\u003c")
    version = html.escape(args.mermaid, quote=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(PAGE % {"version": version, "version_json": json.dumps(version), "blocks": data})
    print(f"wrote {len(blocks)} blocks to {args.out}, for Mermaid {args.mermaid}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Check the words in a repository's Mermaid diagrams.")
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("compare", help="prove a restyle changed only labels")
    one.add_argument("repo")
    one.add_argument("base")
    one.add_argument("--terms-file", help="the repository's documented vocabulary, one term per line")
    one.add_argument("--prose-may-change", action="store_true", help="note a change outside the blocks, not fail")
    one.set_defaults(run=compare)
    two = commands.add_parser("page", help="write a page that lists the words each block drew")
    two.add_argument("repo")
    two.add_argument("out")
    two.add_argument("--file", action="append", dest="paths", help="a Markdown file, by default every tracked one")
    two.add_argument("--mermaid", default=MERMAID, help=f"the Mermaid version to draw with, by default {MERMAID}")
    two.set_defaults(run=page)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
