#!/usr/bin/env python3
"""Tests for skills/ask-team/scripts/diagram_words.py on real git repositories it builds in a temporary folder.

    python3 tests/test_diagram_words.py
"""
import html.parser, os, re, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'skills', 'ask-team', 'scripts', 'diagram_words.py')

failures = 0


def check(name, cond):
    global failures
    print(('ok   ' if cond else 'FAIL ') + name)
    failures += not cond


class Report(html.parser.HTMLParser):
    """Keep only what the drawn page wrote into its three report elements, so text in its script counts for nothing."""

    def __init__(self):
        super().__init__()
        self.inside, self.text = False, []

    def handle_starttag(self, tag, attrs):
        self.inside = dict(attrs).get('id') in ('head', 'failed', 'drawn')

    def handle_endtag(self, tag):
        self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.text.append(data)


def report_of(page):
    report = Report()
    report.feed(page)
    return '\n'.join(report.text)


def git(repo, *args):
    subprocess.run(['git', '-C', repo, '-c', 'user.name=t', '-c', 'user.email=t@example.com', *args], check=True,
                   capture_output=True)


def run(*args):
    try:
        done = subprocess.run([sys.executable, '-I', SCRIPT, *args], capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return 124, 'the script ran past the limit'
    return done.returncode, done.stdout + done.stderr


DOC = """# Design

The text beside the diagrams.

```mermaid
flowchart TD
    a["Refit the hedge<br/>over 20 days"] --> b[Write the plan]
    b -->|sends the order| c(Broker takes it)
    c -- answers --> d{Filled?}
    classDef hot fill:#f96
```

```mermaid
sequenceDiagram
    participant S as Supervisor
    S->>+B: sends the order_id in order.json
    B-->>-S: acks
    Note over S: journal holds it
    alt it fills
        S->>B: asks again
    end
```

```mermaid
stateDiagram-v2
    state "Flat (0 units)" as Flat
    [*] --> Flat
    Flat --> Long: z below 1
    note right of Long: holds one unit
```

```mermaid
erDiagram
    ORDER ||--o{ FILL : "gets filled by"
    ORDER }o..|| PLAN : "belongs"
```

```mermaid
classDiagram
    class Order {
        +order_id str
    }
```

````markdown
```mermaid
sequenceDiagram
    Old->>Example: stays text
```
````
"""


def setup(root, name, text=DOC):
    repo = os.path.join(root, name)
    os.mkdir(repo)
    git(repo, 'init', '-q')
    with open(os.path.join(repo, 'doc.md'), 'w') as f:
        f.write(text)
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', 'base')
    return repo


def edited(root, name, *pairs, text=DOC):
    """Return the exit code and output of compare after one or more replacements."""
    repo = setup(root, name, text)
    for old, new in pairs:
        assert text.count(old) >= 1, old
        text = text.replace(old, new)
    with open(os.path.join(repo, 'doc.md'), 'w') as f:
        f.write(text)
    return run('compare', repo, 'HEAD')


with tempfile.TemporaryDirectory() as root:
    restyle = (
        ('Refit the hedge<br/>over 20 days', 'The system refits the hedge<br/>over 20 days'),
        ('b[Write the plan]', 'b[Supervisor writes the plan]'),
        ('|sends the order|', '|execution sends the order|'),
        ('c -- answers --> d', 'c -- the broker answers --> d'),
        ('B-->>-S: acks', 'B-->>-S: the broker answers'),
        ('S->>B: asks again', 'S->>B: the supervisor asks again'),
        ('Note over S: journal holds it', 'Note over S: the journal holds the order'),
        ('z below 1', 'the z-score falls below 1'),
        ('holds one unit', 'the book holds one unit'),
        ('"gets filled by"', '"is filled by"'),
        ('"belongs"', '"belongs to"'),
    )
    code, out = edited(root, 'restyle', *restyle)
    check('a label-only restyle of every kind passes', code == 0 and 'RESULT: PASS' in out)
    check('it counts the five blocks and leaves the fenced example out', 'blocks compared: 5' in out)
    check('it counts each changed label', 'lines whose label changed: 10' in out)

    for name, old, new, word in (
        ('a message arrow', 'B-->>-S: acks', 'B->>-S: acks', 'structure changed'),
        ('a message direction', 'B-->>-S: acks', 'S-->>-B: acks', 'structure changed'),
        ('an activation mark', 'S->>+B:', 'S->>B:', 'structure changed'),
        ('a participant', 'participant S as Supervisor', 'participant S as Boss', 'structure changed'),
        ('a flowchart target', 'a["Refit the hedge<br/>over 20 days"] --> b', 'a["Refit the hedge<br/>over 20 days"] --> c', 'structure changed'),
        ('a flowchart arrow', 'c -- answers --> d', 'c -- answers --- d', 'structure changed'),
        ('a node shape', 'c(Broker takes it)', 'c[Broker takes it]', 'structure changed'),
        ('a style line', 'fill:#f96', 'fill:#f97', 'structure changed'),
        ('a state edge', 'Flat --> Long: z below 1', 'Flat --> Short: z below 1', 'structure changed'),
        ('a state name', '"Flat (0 units)" as Flat', '"Flat (no units)" as Flat', 'structure changed'),
        ('a state edge gaining a label', '[*] --> Flat', '[*] --> Flat: starts', 'structure changed'),
        ('an entity link', 'ORDER ||--o{ FILL', 'ORDER ||--|| FILL', 'structure changed'),
        ('a class member', '+order_id str', '+order_key str', 'structure changed'),
        ('a note target', 'Note over S: journal holds it', 'Note over B: journal holds it', 'structure changed'),
        ('a note placement', 'Note over S: journal holds it', 'Note left of S: journal holds it', 'structure changed'),
        ('a block keyword', 'alt it fills', 'opt it fills', 'structure changed'),
        ('a state note target', 'note right of Long: holds', 'note left of Long: holds', 'structure changed'),
        ('a state edge source', 'Flat --> Long: z below 1', 'Long --> Long: z below 1', 'structure changed'),
        ('an edge gaining pipes', '-->|sends the order| c', '--> c', 'structure changed'),
        ('a node hidden in an edge label', 'c -- answers --> d', 'c -- answers-->e --> d', 'structure changed'),
        ('an entity label losing its quotes', '"gets filled by"', 'gets filled by', 'structure changed'),
        ('a class name', 'class Order {', 'class Bill {', 'structure changed'),
        ('a block kind', 'erDiagram', 'classDiagram', 'kind erDiagram became classDiagram'),
        ('an added line', '    Note over S: journal holds it\n', '    Note over S: journal holds it\n    Note over S: more\n', 'lines became'),
        ('an added block', 'The text beside the diagrams.\n', 'The text beside the diagrams.\n\n```mermaid\nflowchart TD\n    a --> b\n```\n', 'blocks became'),
        ('indentation', '    S->>B: asks again', '      S->>B: asks again', 'leading whitespace'),
        ('a number in a label', 'over 20 days', 'over 30 days', 'numbers differ or moved'),
        ('an identifier in a label', 'order_id in order.json', 'id in order.json', 'identifiers differ or moved'),
        ('a file name in a label', 'order_id in order.json', 'order_id in the file', 'identifiers differ or moved'),
        ('a swapped pair of identifiers', 'order_id in order.json', 'order.json in order_id', 'identifiers differ or moved'),
        ('a sign', 'over 20 days', 'over -20 days', 'numbers differ or moved'),
        ('a percent mark', 'over 20 days', 'over 20% days', 'numbers differ or moved'),
        ('a semicolon in a label', 'B-->>-S: acks', 'B-->>-S: acks; then waits', 'ends this label early'),
        ('an em dash in a label', 'B-->>-S: acks', 'B-->>-S: acks — then waits', 'em dash in label'),
        ('first person in a label', 'B-->>-S: acks', 'B-->>-S: we ack', 'first person'),
        ('first person opening a label', 'B-->>-S: acks', 'B-->>-S: We ack', 'first person'),
        ('a hash in a label', 'B-->>-S: acks', 'B-->>-S: acks #4', 'ends this label early'),
        ('a semicolon in a state label', 'z below 1', 'z below 1; then waits', 'ends this label early'),
    ):
        code, out = edited(root, 'c' + name.replace(' ', ''), (old, new))
        check(f'{name} fails with {word!r}', code == 1 and word in out and 'RESULT: FAILED' in out)

    for name, old, new in (
        ('three spaces', 'B-->>-S: acks', 'B-->>-S: acks   S->>B: goes on'),
        ('three spaces and no arrow', 'B-->>-S: acks', 'B-->>-S: acks   activate S'),
        ('one space', 'B-->>-S: acks', 'B-->>-S: acks S->>B: goes on'),
        ('a note', 'B-->>-S: acks', 'B-->>-S: acks Note over S: goes on'),
        ('a lowercase note', 'B-->>-S: acks', 'B-->>-S: acks note over S: goes on'),
        ('a cross arrow', 'B-->>-S: acks', 'B-->>-S: acks S--xB: goes on'),
        ('an open arrow', 'B-->>-S: acks', 'B-->>-S: acks S-)B: goes on'),
        ('a two-way arrow', 'B-->>-S: acks', 'B-->>-S: acks S<<->>B: goes on'),
        ('a hyphened target', 'B-->>-S: acks', 'B-->>-S: acks S->>Order-Svc: goes on'),
        ('a participant line', 'participant S as Supervisor', 'participant S as Supervisor S->>B: goes on'),
        ('a hyphened sender', 'B-->>-S: acks', 'Data-Eng->>S: acks S->>B: goes on'),
    ):
        code, out = edited(root, 'join' + name.replace(' ', ''), (old, new))
        check(f'a sequence statement joined with {name} fails', code == 1 and 'second statement suspected' in out)

    for name, old, new in (
        ('with its own label', 'Flat --> Long: z below 1', 'Flat --> Long: z below 1   Long --> Flat: y'),
        ('with no label', '    [*] --> Flat', '    [*] --> Flat Flat --> Long'),
        ('after a label', 'Flat --> Long: z below 1', 'Flat --> Long: z below 1 Long --> Flat'),
    ):
        code, out = edited(root, 'joins' + name.replace(' ', ''), (old, new))
        check(f'a joined state statement {name} fails', code == 1 and 'second statement suspected' in out)
    check('a state label that mentions an arrow in a sentence passes',
          edited(root, 'stateprose', ('z below 1', 'z 1 moves x --> y in the ledger'))[0] == 0)
    check('a state comment with two arrows passes', edited(
        root, 'statecomment', ('holds one unit', 'the book holds one unit'),
        text=DOC.replace('    [*] --> Flat', '    %% old --> mid --> new\n    [*] --> Flat'))[0] == 0)
    for name, old, new in (
        ('the word Note in a sentence', 'B-->>-S: acks', 'B-->>-S: Note over the ledger stays in the record'),
        ('a hyphened word', 'B-->>-S: acks', 'B-->>-S: the two-way link holds'),
    ):
        check(f'a sequence label with {name} passes', edited(root, 'seq' + name.replace(' ', ''), (old, new))[0] == 0)

    for name, old, new in (
        ('a numbered flowchart node', 'a["Refit the hedge', 'a["1. Refit the hedge'),
        ('a closing-bracket number', 'a["Refit the hedge', 'a["1) Refit the hedge'),
        ('an unquoted flowchart node', 'b[Write the plan]', 'b[2. Write the plan]'),
        ('a bullet', 'b[Write the plan]', 'b[- Write the plan]'),
        ('a heading', 'b[Write the plan]', 'b[## Write the plan]'),
        ('an edge label', '|sends the order|', '|1. sends the order|'),
        ('a state transition', 'z below 1', '1. z below'),
        ('a state note', 'holds one unit', '1. holds one unit'),
        ('a plus', 'b[Write the plan]', 'b[+ Write the plan]'),
        ('a star', 'b[Write the plan]', 'b[* Write the plan]'),
        ('a blockquote', 'b[Write the plan]', 'b[> Write the plan]'),
        ('a rule', 'b[Write the plan]', 'b[---]'),
        ('a backticked number', 'a["Refit the hedge', 'a["`1. Refit the hedge'),
        ('a state description', '    [*] --> Flat', '    Flat : 1. holds nothing'),
    ):
        code, out = edited(root, 'md' + name.replace(' ', ''), (old, new))
        check(f'{name} that starts like a Markdown block fails', code == 1 and 'starts like a Markdown block' in out)

    for kind, line in (
        ('stateDiagram', '    [*] --> A\n    A --> B: LABEL'),
        ('graph TD', '    a[LABEL] --> b'),
        ('flowchart-elk TD', '    a[LABEL] --> b'),
        ('flowchart TD', '    subgraph LABEL\n    a --> b\n    end'),
        ('classDiagram', '    class A["LABEL"]'),
        ('classDiagram-v2', '    A --> B : LABEL'),
        ('classDiagram', '    note for A "LABEL"'),
        ('classDiagram', '    note "LABEL"'),
    ):
        text = f'```mermaid\n{kind}\n{line}\n```\n'
        code, out = edited(root, 'k' + str(abs(hash(kind + line))), ('LABEL', '1. Refit'), text=text)
        check(f'{kind} {line.strip()[:24]!r} reads the Markdown fault', code == 1 and 'starts like a Markdown block' in out)
        code, out = edited(root, 'r' + str(abs(hash(kind + line))), ('LABEL', 'the system refits'), text=text)
        if 'subgraph' not in line:
            check(f'{kind} {line.strip()[:24]!r} lets the label change', code == 0)
    two = '```mermaid\nclassDiagram\n    Order : + total\n    -id : - string\n```\n'
    code, out = edited(root, 'mdmember', ('total', 'totals'), text=two)
    check("a class member's visibility mark is no label", 'Markdown block' not in out)

    fault_doc = DOC + '\n```mermaid\nflowchart TD\n    a["1. Refit"] --> b\n```\n'
    code, out = edited(root, 'mdother', ('asks again', 'the supervisor asks again'), text=fault_doc)
    check('a fault in an unchanged block does not fail a restyle', code == 0 and 'Markdown block' not in out)
    note_doc = fault_doc.replace('a["1. Refit"] --> b', 'a["1. Refit"] --> b\n    b["old"] --> c')
    code, out = edited(root, 'mdnote2', ('b["old"]', 'b["the new"]'), text=note_doc)
    check('a fault on an unchanged line of a changed block is a note', code == 0 and 'Markdown block' in out)

    check('a label moved across lines fails', 'label moved' in edited(
        root, 'mv', ('S->>B: asks again', 'S->>B: acks'), ('B-->>-S: acks', 'B-->>-S: asks again'))[1])
    check('two labels swapped on one line fail', 'label moved' in edited(
        root, 'mv2', ('a[Buy] --> b[Sell]', 'a[Sell] --> b[Buy]'), text='```mermaid\nflowchart TD\n    a[Buy] --> b[Sell]\n```\n')[1])
    code, out = edited(root, 'numbered2', ('over 20 days at 5 bps', 'over 5 days at 20 bps'),
                       text=DOC.replace('over 20 days', 'over 20 days at 5 bps'))
    check('swapped numbers fail', code == 1 and 'numbers differ or moved' in out)
    code, out = edited(root, 'ent', ('read #quot;x#quot; first', 'first read #quot;x#quot;'),
                       text=DOC.replace('Write the plan', 'read #quot;x#quot; first'))
    check('an entity the old label held passes', code == 0)
    code, out = edited(root, 'io', ('flush I/O', 'the supervisor flushes I/O'), text=DOC.replace('Write the plan', 'flush I/O'))
    check('I/O is no first person', code == 0)
    wide = 'x' * 58
    code, out = edited(root, 'w58', ('B-->>-S: acks', f'B-->>-S: {wide}'))
    check('a segment of 58 characters draws no note', '58 characters' not in out)
    code, out = edited(root, 'w59', ('B-->>-S: acks', f'B-->>-S: {wide}y'))
    check('a segment of 59 characters draws a note', '59 characters' in out)
    code, out = edited(root, 'quoted', ('S->>B: asks "sending" again', 'S->>B: asks again'),
                       text=DOC.replace('S->>B: asks again', 'S->>B: asks "sending" again'))
    check('a quoted string changing in a message is a note', code == 0 and 'quoted string changed' in out)

    for name, base, new, word in (
        ('a backticked span', 'calls `gate()`', 'calls `check()`', 'identifiers differ or moved'),
        ('a camelCase name', 'calls placeOrder', 'calls sendOrder', 'identifiers differ or moved'),
    ):
        code, out = edited(root, 'id' + name.replace(' ', ''), (base, new), text=DOC.replace('Write the plan', base))
        check(f'{name} that differs fails', code == 1 and word in out)
    code, out = edited(root, 'thirdnode', ('--- b ---', '--- x ---'), text='```mermaid\nflowchart TD\n    a --- b --- c\n```\n')
    check('a node between two plain links is no edge label', code == 1 and 'structure changed' in out)
    check('an entity label can gain the quotes a phrase needs', edited(
        root, 'erquote', ('PLAN : "belongs"', 'PLAN : "belongs to"'), text=DOC.replace('PLAN : "belongs"', 'PLAN : belongs').replace('PLAN : belongs', 'PLAN : "belongs"'))[0] == 0)
    code, out = edited(root, 'wekept', ('we ack', 'we ack it now'), text=DOC.replace('B-->>-S: acks', 'B-->>-S: we ack'))
    check('first person the old label held passes', code == 0)

    for name, text, old, new in (
        ('a class relation arrow', '    A --> B : holds', 'A --> B', 'A <-- B'),
        ('a class relation target', '    A --> B : holds', 'A --> B', 'A --> C'),
        ('a class note target', '    note for A "holds"', 'for A', 'for B'),
        ('the text after a class name', '    class A["holds"]:::hot', ':::hot', ':::cold'),
    ):
        code, out = edited(root, 'cl' + name.replace(' ', ''), (old, new), text=f'```mermaid\nclassDiagram\n{text}\n```\n')
        check(f'{name} is structure', code == 1 and 'structure changed' in out)
    for name, text, old, new in (
        ('a state note target', '    A --> B\n    note right of A: holds', 'of A', 'of B'),
        ('a state description id', '    A --> B\n    A : holds', 'A : holds', 'B : holds'),
    ):
        code, out = edited(root, 'st' + name.replace(' ', ''), (old, new), text=f'```mermaid\nstateDiagram-v2\n{text}\n```\n')
        check(f'{name} is structure', code == 1 and 'structure changed' in out)
    for name, text, old, new in (
        ('a double-bracket shape', '    a[(holds)] --> b', 'a[(holds)]', 'a[[holds]]'),
        ('a flag shape', '    a>holds] --> b', 'a>holds]', 'a[holds]'),
        ('a shape written with @', '    a@{ shape: "rect", label: "x" } --> b', '"rect"', '"diam"'),
    ):
        code, out = edited(root, 'fl' + name.replace(' ', ''), (old, new), text=f'```mermaid\nflowchart TD\n{text}\n```\n')
        check(f'{name} is structure', code == 1 and 'structure changed' in out)
    for name, text, old, new in (
        ('a double-bracket label', '    a[[holds]] --> b', 'holds', 'it holds'),
        ('a flag label', '    a>holds] --> b', 'holds', 'it holds'),
        ('an underscored id', '    a_b[holds] --> c', 'holds', 'it holds'),
        ('a subgraph title in brackets', '    subgraph one [holds]\n    a --> b\n    end', 'holds', 'it holds'),
        ('a thick edge', '    a == holds ==> b', 'holds', 'it holds'),
        ('a dotted edge', '    a -. holds .-> b', 'holds', 'it holds'),
        ('a circle edge', '    a -- holds --o b', 'holds', 'it holds'),
    ):
        code, out = edited(root, 'fp' + name.replace(' ', ''), (old, new), text=f'```mermaid\nflowchart TD\n{text}\n```\n')
        check(f'{name} can change', code == 0)
    hyphen = '```mermaid\nsequenceDiagram\n    web-app->>api: holds\n    Note over web-app: waits\n```\n'
    code, out = edited(root, 'hy', ('holds', 'it holds'), ('waits', 'it waits'), text=hyphen)
    check('a hyphened participant can change its labels', code == 0)
    for name, old, new in (
        ('e.g.', 'rejects, e.g. a stale quote', 'the broker rejects a stale quote'),
        ('a range', 'retries 1-3 times', 'the worker retries 1 to 3 times'),
        ('a setting relative to the close', 'decide at close-20', 'decide at 20 before the close'),
    ):
        code, out = edited(root, 'ok' + name.replace(' ', ''), (old, new), text=DOC.replace('Write the plan', old))
        check(f'{name} can be reworded', code == 0)
    for name, old, new in (
        ('a call', 'calls gate()', 'calls check()'),
        ('a short camelCase name', 'reads zScore', 'reads yScore'),
    ):
        code, out = edited(root, 'bad' + name.replace(' ', ''), (old, new), text=DOC.replace('Write the plan', old))
        check(f'{name} that differs fails', code == 1 and 'identifiers differ or moved' in out)
    code, out = edited(root, 'minus', ('close−20', 'close−30'), text=DOC.replace('Write the plan', 'at close−20'))
    check('a minus sign keeps its number', code == 1 and 'numbers differ or moved' in out)
    code, out = edited(root, 'perlabel', ('a["hold 20 units"] --> b["stop"]', 'a["hold units"] --> b["stop 20"]'),
                       text='```mermaid\nflowchart TD\n    a["hold 20 units"] --> b["stop"]\n```\n')
    check('a number moved between labels on one line fails', code == 1 and 'numbers differ or moved' in out)
    code, out = edited(root, 'idmoved', ('order_id', 'id'), ('b["stop"]', 'b["stop order_id"]'),
                       text='```mermaid\nflowchart TD\n    a["order_id"] --> b["stop"]\n```\n')
    check('an identifier moved between labels fails', code == 1 and 'identifiers differ or moved' in out)
    neighbours = '```mermaid\nsequenceDiagram\n    A->>B: sends\n    B->>A: sends the order\n```\n'
    code, out = edited(root, 'near', ('B->>A: sends the order', 'B->>A: sends the order to the broker'),
                       ('A->>B: sends\n', 'A->>B: sends the order\n'), text=neighbours)
    check('a label reworded into its neighbour is no move', code == 0)
    for name, label in (('a bare number', '1.'), ('a bare dash', '-'), ('a bare hash', '#'), ('a star rule', '***'), ('an underscore rule', '___')):
        code, out = edited(root, 'bare' + name.replace(' ', ''), ('b[Write the plan]', f'b["{label}"]'))
        check(f'{name} starts like a Markdown block', 'starts like a Markdown block' in out)
    for name, old, new in (
        ('a name line', '    [*] --> Flat', '    state "Other" as Other [*] --> Other'),
        ('a note', 'z below 1', 'z below 1 note right of Long: y'),
        ('three spaces', 'z below 1', 'z below 1   Long: y'),
    ):
        code, out = edited(root, 'sj' + name.replace(' ', ''), (old, new))
        check(f'a state join on {name} fails', code == 1 and 'second statement suspected' in out)
    code, out = edited(root, 'hashok', ('a hash', 'a hash in a flowchart'), text=DOC.replace('Write the plan', 'a hash #4 stays'))
    check('a hash in a flowchart label draws fine and passes', code == 0)
    code, out = edited(root, 'seqent', ('says it', 'says it now'), text=DOC.replace('B-->>-S: acks', 'B-->>-S: says it #quot;done#quot;'))
    check('an entity in a sequence label passes', code == 0)
    code, out = edited(root, 'comment', ('%% one', '%% two'), text=DOC.replace('    S->>B: asks again', '    %% one\n    S->>B: the asks again'))
    check('a change to a comment alone compares nothing', code == 2 and 'structure changed' not in out)
    for name, old, new in (
        ('a sender', 'S->>B: asks again', 'B->>B: asks again'),
        ('a target', 'S->>B: asks again', 'S->>S: asks again'),
        ('a line turned into a comment', '    S->>B: asks again', '    %% S->>B: asks again'),
        ('a two-word participant in a note', 'Note over Order Svc: holds', 'Note over OrderSvc: holds'),
    ):
        text = DOC.replace('Note over S: journal holds it', 'Note over Order Svc: holds')
        code, out = edited(root, 'so' + name.replace(' ', ''), (old, new), text=text)
        check(f'{name} is structure', code == 1 and 'structure changed' in out)
    for name, text, old, new in (
        ('a class id', '```mermaid\nclassDiagram\n    class A["x"]\n```\n', 'class A', 'class B'),
        ('a node between thick links', '```mermaid\nflowchart TD\n    a === b === c\n```\n', '=== b ===', '=== x ==='),
        ('a state style class', '```mermaid\nstateDiagram-v2\n    A --> B:::hot\n```\n', ':::hot', ':::cold'),
        ('a state style class turned into a label', '```mermaid\nstateDiagram-v2\n    A --> B:::hot\n```\n', ':::hot', ': hot'),
        ('a state style class on its own', '```mermaid\nstateDiagram-v2\n    B:::hot\n```\n', ':::hot', ':::cold'),
        ('a class member holding dots', '```mermaid\nclassDiagram\n    class A {\n        +send(args...): void\n    }\n```\n', 'void', 'bool'),
        ('a directive', '```mermaid\n%%{init: {"theme": "dark"}}%%\nsequenceDiagram\n    A->>B: x\n```\n', 'dark', 'forest'),
        ('a YAML header in a state diagram', '```mermaid\n---\nlayout: dagre\n---\nstateDiagram-v2\n    A --> B\n```\n', 'dagre', 'elk'),
        ('a style line with parentheses', '```mermaid\nflowchart TD\n    a --> b\n    style a fill:rgb(1,2,3)\n```\n', '1,2', '9,2'),
    ):
        code, out = edited(root, 'se' + name.replace(' ', ''), (old, new), text=text)
        check(f'{name} is structure', code == 1 and 'structure changed' in out)
    for name, text, old, new in (
        ('a block keyword', '```mermaid\nsequenceDiagram\n    loop every 5 days\n    A->>B: x\n    end\n```\n', '5 days', '6 days'),
        ('an entity', '```mermaid\nerDiagram\n    A ||--o{ B : "has 5 rows"\n```\n', '5 rows', '6 rows'),
        ('a spaced edge', '```mermaid\nflowchart TD\n    a -- within 5 days --> b\n```\n', '5 days', '6 days'),
    ):
        code, out = edited(root, 'nu' + name.replace(' ', ''), (old, new), text=text)
        check(f'a number changed in {name} label fails', code == 1 and 'numbers differ or moved' in out)
    for name, text, old in (
        ('a spaced edge', '```mermaid\nflowchart TD\n    a -- x --> b\n```\n', '-- x -->'),
        ('a state name', '```mermaid\nstateDiagram-v2\n    state "x" as X\n```\n', '"x"'),
    ):
        code, out = edited(root, 'fa' + name.replace(' ', ''), (old, old.replace('x', '1. x')), text=text)
        check(f'{name} reads the Markdown fault', 'starts like a Markdown block' in out)
    for name, old, new, word in (
        ('a backticked span', 'calls `gate()`', 'calls `check()`', 'identifiers differ'),
        ('a PascalCase name', 'calls PlaceOrder', 'calls SendOrder', 'identifiers differ'),
        ('a plus sign', 'at close+20', 'at close−20', 'numbers differ'),
    ):
        code, out = edited(root, 'mo' + name.replace(' ', ''), (old, new), text=DOC.replace('Write the plan', old))
        check(f'{name} that differs fails', code == 1 and word in out)
    code, out = edited(root, 'dash2', ('acks — done', 'acks — done — then'), text=DOC.replace('B-->>-S: acks', 'B-->>-S: acks — done'))
    check('a second em dash fails', code == 1 and 'em dash' in out)
    for word in ('my', 'mine', 'our'):
        code, out = edited(root, 'fp' + word, ('B-->>-S: acks', f'B-->>-S: acks {word} order'))
        check(f'{word} is first person', code == 1 and 'first person' in out)
    code, out = edited(root, 'stateh', ('z below 1 at', 'the z-score falls below 1 at'), text=DOC.replace('z below 1', 'z below 1 at item #4'))
    check('a hash in a state label draws fine and passes', code == 0)
    code, out = edited(root, 'trail', ('B-->>-S: acks', 'B-->>-S: acks now;'))
    check('a trailing semicolon in a sequence label passes', code == 0)
    code, out = edited(root, 'entnum', ('order #4x filled', 'the order #35;4x is filled'), text=DOC.replace('Write the plan', 'order #4x filled'))
    check('an entity is no number', code == 0)
    code, out = edited(root, 'dec2', ('B-->>-S: acks', 'B-->>-S: order #35;4 filled'), text=DOC)
    check('writing the entity the skill names fails no check on the mark', 'ends this label early' not in out)
    code, out = edited(root, 'stnamed', ('holds one unit', 'the book holds it'), text=DOC.replace('"Flat (0 units)" as Flat', '"Flat; part remains" as Flat'))
    check('a semicolon in a quoted state name draws fine', code == 0 and 'ends this label early' not in out)
    code, out = edited(root, 'partalias', ('participant S as Supervisor', 'participant S as order #4'))
    check('a hash in a participant alias is named', 'ends this label early' in out)
    aligned = DOC.replace('participant S as Supervisor', 'participant S   as Supervisor')
    code, out = edited(root, 'align', ('asks again', 'the supervisor asks again'), text=aligned)
    check('an aligned participant line is no join', code == 0 and 'second statement' not in out)
    fence = '- item\n\n    ```mermaid\n    sequenceDiagram\n        A->>B: x\n    ```\n'
    code, out = edited(root, 'indent', ('A->>B', 'B->>A'), text=fence)
    check('a fence inside a list item is read', code == 1 and 'structure changed' in out)
    slow = '```mermaid\nsequenceDiagram\n    Note over' + ' ' * 900 + 'x\n```\n\n```mermaid\nflowchart TD\n    a --' + ' ' * 900 + 'x\n```\n'
    repo = setup(root, 'slow', slow)
    folder = os.path.join(root, 'slowpage')
    os.mkdir(folder)
    started = time.time()
    code, out = run('page', repo, os.path.join(folder, 'out.html'))
    check('a long run of spaces stays fast', code == 0 and time.time() - started < 10)
    code, out = edited(root, 'tilde2', ('b[Write the plan]', 'b["~~~"]'))
    check('a tilde rule starts like a Markdown block', 'starts like a Markdown block' in out)
    click_id = '```mermaid\nflowchart TD\n    click-a["x"] --> b\n```\n'
    code, out = edited(root, 'clickid', ('"x"', '"1. x"'), text=click_id)
    check('a node id that starts with a keyword is still read', 'starts like a Markdown block' in out)
    code, out = edited(root, 'kw2', ('alt it fills', 'alt it fills S->>B: goes on'))
    check('a statement joined onto a keyword fails', code == 1 and 'second statement suspected' in out)
    code, out = edited(root, 'kw3', ('else it waits', 'else it waits B->>S: more'), text=DOC.replace('    end\n', '    else it waits\n    end\n', 1))
    check('a statement joined onto else fails', code == 1 and 'second statement suspected' in out)
    code, out = edited(root, 'erjoin', ('"gets filled by"', '"gets filled by" C ||--o{ D : "y"'))
    check('a joined entity line is structure', code == 1 and 'structure changed' in out)
    flag = '```mermaid\nflowchart TD\n    a -- z>2 --> b[Sell]\n```\n'
    for name, new in (('target', 'a -- z>2 --> c[Sell]'), ('arrow', 'a -- z>2 --- b[Sell]')):
        code, out = edited(root, 'gt' + name, ('a -- z>2 --> b[Sell]', new), text=flag)
        check(f'a > in an edge label hides no {name}', code == 1 and 'structure changed' in out)
    check('a > in an edge label can still change', edited(root, 'gtok', ('z>2', 'when z>2'), text=flag)[0] == 0)
    for name, text, old, new in (
        ('class', '```mermaid\nclassDiagram\n    A --> B : uses\n```\n', 'uses', 'uses\rC --> D : extra'),
        ('entity', '```mermaid\nerDiagram\n    A ||--o{ B : "has"\n```\n', '"has"', '"has"\rC ||--o{ D : "y"'),
        ('sequence', '```mermaid\nsequenceDiagram\n    A->>B: hello\n```\n', 'hello', 'hello\rdeactivate B'),
    ):
        code, out = edited(root, 'cr' + name, (old, new), text=text)
        check(f'a bare return in a {name} line adds a line', code == 1 and 'lines became' in out)
    code, out = edited(root, 'rect', ('rect pink', 'rect red'), text=DOC.replace('    alt it fills', '    rect pink\n    alt it fills', 1).replace('    end\n', '    end\n    end\n', 1))
    check('a rect colour is structure', code == 1 and 'structure changed' in out)
    code, out = edited(root, 'sgq', ('"x"', '"y"'), text='```mermaid\nflowchart TD\n    subgraph "x"\n    a --> b\n    end\n```\n')
    check('a subgraph title in quotes is its id', code == 1 and 'structure changed' in out)
    code, out = edited(root, 'title', ('title: Order flw', 'title: How an order flows'), text='```mermaid\nsequenceDiagram\n    title: Order flw\n    A->>B: x\n```\n')
    check('a title can change', code == 0)
    code, out = edited(root, 'title2', ('title: Order flw', 'title: order #4'), text='```mermaid\nsequenceDiagram\n    title: Order flw\n    A->>B: x\n```\n')
    check('a hash in a title is named', 'ends this label early' in out)
    code, out = edited(root, 'stylelabel', ('holds', 'it holds'), text='```mermaid\nstateDiagram-v2\n    A --> B:::hot: holds\n```\n')
    check('a label after a state style class can change', code == 0)
    for name, label in (('tilde', '~~~ x'), ('backtick', '``` x')):
        code, out = edited(root, 'fence' + name, ('z below 1', label))
        check(f'a {name} fence opening a label starts like a Markdown block', 'starts like a Markdown block' in out)
    check('an arrow inside a quoted state name is no join', 'second statement' not in edited(
        root, 'namedarrow', ('holds one unit', 'the book holds it'), text=DOC.replace('"Flat (0 units)" as Flat', '"from --> to" as Flat'))[1])
    code, out = edited(root, 'acc', ('holds one unit', 'the book holds it'), ('    accTitle: Orders; fills', '    accTitle: Orders; all fills'), text=DOC.replace('    [*] --> Flat', '    accTitle: Orders; fills\n    [*] --> Flat'))
    check('an accessible title is not drawn, so it raises no fault', 'ends this label early' not in out)
    code, out = edited(root, 'c1', ('asks again', 'asks \x9b2J\u2028RESULT: PASS #4'))
    check('C1 bytes and Unicode line breaks never reach the output', '\x9b' not in out and '\u2028' not in out)
    header = '```mermaid\n---\ntitle: 1. Orders; fills\n---\nstateDiagram-v2\n    A --> B: holds\n```\n'
    code, out = edited(root, 'hdr', ('holds', 'it holds'), text=header)
    check('a YAML header raises no fault', code == 0 and 'Markdown block' not in out and 'ends this label' not in out)
    code, out = edited(root, 'hdr2', ('title: 1. Orders; fills', 'title: 2. Orders; fills'), text=header)
    check('a changed YAML header fails as structure alone', code == 1 and 'structure changed' in out and 'Markdown block' not in out)
    repo = setup(root, 'hdrpage', header)
    folder = os.path.join(root, 'hdrfolder')
    os.mkdir(folder)
    check('page reads no fault in a YAML header', 'none' in run('page', repo, os.path.join(folder, 'out.html'))[1])
    slow = '```mermaid\nflowchart TD\n    a --' + ' ' * 900 + 'x --> b\n```\n'
    code, out = edited(root, 'slowcmp', ('x --> b', 'y --> b'), text=slow)
    check('compare cuts a long run of spaces', code != 124)
    code, out = edited(root, 'slowword', ('b[Write the plan]', 'b["' + 'w' * 900 + '"]'))
    check('compare reads a long unbroken word', code != 124)
    repo = setup(root, 'nametext')
    blob = subprocess.run(['git', '-C', repo, 'hash-object', '-w', 'doc.md'], capture_output=True, text=True).stdout.strip()
    subprocess.run(['git', '-C', repo, 'update-index', '--add', '--cacheinfo', f'100644,{blob}'.encode() + b',bad\xff.md'], check=True)
    git(repo, 'commit', '-qm', 'bad name')
    with open(os.path.join(repo, 'doc.md'), 'w') as f:
        f.write(DOC.replace('asks again', 'the supervisor asks again'))
    code, out = run('compare', repo, 'HEAD')
    check('compare fails on a file name that is not valid text', code == 1 and 'not valid text' in out)
    folder = os.path.join(root, 'namefolder')
    os.mkdir(folder)
    code, out = run('page', repo, os.path.join(folder, 'out.html'))
    check('page stops on a file name that is not valid text', code == 2 and 'not valid text' in out)
    repo = setup(root, 'nameline')
    with open(os.path.join(repo, 'a\nRESULT: PASS\n.md'), 'w') as f:
        f.write('```mermaid\nflowchart TD\n    a["1. x"] --> b\n```\n')
    git(repo, 'add', '-A')
    folder = os.path.join(root, 'linefolder')
    os.mkdir(folder)
    page2 = os.path.join(folder, 'out.html')
    code, out = run('page', repo, page2)
    with open(page2) as f:
        check('a file name cannot forge a line of the page', code == 0 and '\\nRESULT' not in f.read())
    many = '```mermaid\nsequenceDiagram\n' + ''.join(f'    A->>B: x{n}\n' for n in range(20000)) + '```\n'
    repo = setup(root, 'many', many)
    with open(os.path.join(repo, 'doc.md'), 'w') as f:
        f.write(many.replace('x', 'y'))
    started = time.time()
    code, out = run('compare', repo, 'HEAD')
    check('20,000 changed labels finish quickly', code == 0 and time.time() - started < 10)
    repo = setup(root, 'atbase', 'x' * 5_000_000)
    with open(os.path.join(repo, 'doc.md'), 'w') as f:
        f.write('small\n')
    check('a base blob at the size limit is read', 'bytes at the base commit' not in run('compare', repo, 'HEAD')[1])
    repo = setup(root, 'bigbase', 'x' * 5_000_001)
    with open(os.path.join(repo, 'doc.md'), 'w') as f:
        f.write('small\n')
    code, out = run('compare', repo, 'HEAD')
    check('compare fails on a base blob over the size limit', code == 1 and 'bytes at the base commit' in out)
    code, out = edited(root, 'wrapbr', ('B-->>-S: acks', 'B-->>-S: ' + 'x' * 40 + '<br/>' + 'y' * 40))
    check('a label wrapped by a line break draws no note', 'characters:' not in out)
    terms2 = os.path.join(root, 'terms2.txt')
    with open(terms2, 'w') as f:
        f.write('Kill Switch\n')
    repo = setup(root, 'termcase', DOC.replace('journal holds it', 'the kill switch holds it'))
    with open(os.path.join(repo, 'doc.md'), 'w') as f:
        f.write(DOC.replace('journal holds it', 'the stop holds it'))
    check('a term is matched in any case', 'pinned term dropped' in run('compare', repo, 'HEAD', '--terms-file', terms2)[1])
    repo = setup(root, 'badname')
    with open(os.path.join(repo, 'evil\nRESULT: PASS.md'), 'w') as f:
        f.write('x\n')
    code, out = run('compare', repo, 'HEAD')
    check('a file name cannot forge a line of the report', not any(line.startswith('RESULT: PASS') for line in out.split('\n')[:-2]) and 'RESULT: PASS (' not in out.split('\n')[0])
    repo = setup(root, 'crlf', DOC.replace('\n', '\r\n'))
    with open(os.path.join(repo, 'doc.md'), 'w', newline='') as f:
        f.write(DOC.replace('asks again', 'the supervisor asks again').replace('\n', '\r\n'))
    code, out = run('compare', repo, 'HEAD')
    check('a restyle of a file with Windows line ends passes', code == 0 and 'lines whose label changed: 1' in out)
    code, out = edited(root, 'longline', ('asks again', 'x' * 1001))
    check('a line over the limit fails', code == 1 and 'over 1000 characters' in out)
    code, out = run('compare', setup(root, 'noterms'), 'HEAD', '--terms-file', os.path.join(root, 'none.txt'))
    check('a missing terms file stops', code == 2 and 'cannot read the terms file' in out)
    code, out = edited(root, 'ctl', ('asks again', 'asks \x1b[31magain #4'))
    check('a control character never reaches the output', '\x1b' not in out and '?[31m' in out)

    numbered = DOC.replace('B-->>-S: acks', 'B-->>-S: 1. acks').replace('"gets filled by"', '"1. gets filled by"')
    code, out = edited(root, 'safe', ('asks again', 'the supervisor asks again'), text=numbered)
    check('a numbered sequence or entity label draws fine and passes', code == 0)
    plain = DOC.replace('Write the plan', '20 days of data')
    check('a label starting with a plain number passes',
          edited(root, 'plain', ('|sends the order|', '|execution sends the order|'), text=plain)[0] == 0)

    click = DOC.replace('fill:#f96', 'fill:#f96\n    click a "https://example.com/one"')
    code, out = edited(root, 'click', ('example.com/one', 'example.com/two'), text=click)
    check('a click target is structure rather than a label', code == 1 and 'structure changed' in out)

    code, out = edited(root, 'prose', ('The text beside the diagrams.', 'Other text.'))
    check('a change outside the blocks fails', code == 1 and 'text outside the blocks changed' in out)
    repo = setup(root, 'prose2')
    with open(os.path.join(repo, 'doc.md'), 'w') as f:
        f.write(DOC.replace('The text beside the diagrams.', 'Other text.'))
    code, out = run('compare', repo, 'HEAD', '--prose-may-change')
    check('prose alone compares no label', code == 2 and 'NOTHING COMPARED' in out)
    with open(os.path.join(repo, 'doc.md'), 'w') as f:
        f.write(DOC.replace('The text beside the diagrams.', 'Other text.').replace('asks again', 'the supervisor asks again'))
    code, out = run('compare', repo, 'HEAD', '--prose-may-change')
    check('--prose-may-change turns it into a note', code == 0 and 'text outside the blocks changed' in out)

    terms = os.path.join(root, 'terms.txt')
    with open(terms, 'w') as f:
        f.write('journal\n\nkill switch\n')
    repo = setup(root, 'terms')
    with open(os.path.join(repo, 'doc.md'), 'w') as f:
        f.write(DOC.replace('journal holds it', 'the record holds it'))
    code, out = run('compare', repo, 'HEAD', '--terms-file', terms)
    check('a dropped term fails', code == 1 and "pinned term dropped ['journal']" in out)
    check('without a terms file the same change passes', run('compare', repo, 'HEAD')[0] == 0)
    with open(os.path.join(repo, 'doc.md'), 'w') as f:
        f.write(DOC.replace('journal holds it', 'it is journaled'))
    check('a term kept inside a longer word passes', run('compare', repo, 'HEAD', '--terms-file', terms)[0] == 0)

    code, out = edited(root, 'pie', text='```mermaid\npie title Shares\n    "a" : 3\n```\n',
                       *[('"a" : 3', '"b" : 3')])
    check('a change in a kind the script cannot split fails', code == 1 and 'structure changed' in out)

    header = '```mermaid\n---\ntitle: Sketch\n---\n%%{init: {"theme": "dark"}}%%\nsequenceDiagram\n    A->>B: acks\n```\n'
    code, out = edited(root, 'head', ('A->>B: acks', 'A->>B: the broker answers'), text=header)
    check('a header and a directive before the keyword still read the kind', code == 0 and 'sequenceDiagram' in out)

    tilde = '~~~mermaid\nsequenceDiagram\n    A->>B: acks\n~~~\n'
    code, out = edited(root, 'tilde', ('A->>B: acks', 'A->>B: the broker answers'), text=tilde)
    check('a tilde fence is a block', code == 0 and 'blocks compared: 1' in out)

    code, out = edited(root, 'open', ('```\n', '\n'), text='```mermaid\nsequenceDiagram\n    A->>B: acks\n```\n')
    check('a block with no closing fence fails', code == 1 and 'no closing fence' in out)

    repo = setup(root, 'none')
    code, out = run('compare', repo, 'HEAD')
    check('no changed file reports that nothing was compared', code == 2 and 'NOTHING COMPARED' in out)
    code, out = run('compare', repo, 'no-such-commit')
    check('a wrong base stops', code == 2 and 'not a commit' in out)
    code, out = run('compare', repo, '--', '--output=x')
    check('a base that reads as a flag stops at the commit check', code == 2 and 'not a commit' in out)

    repo = setup(root, 'name', DOC)
    os.rename(os.path.join(repo, 'doc.md'), os.path.join(repo, 'désign.md'))
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', 'moved')
    with open(os.path.join(repo, 'désign.md'), 'w') as f:
        f.write(DOC.replace('S->>B: asks again', 'B->>S: asks again'))
    code, out = run('compare', repo, 'HEAD')
    check('a file name git would quote is still compared', code == 1 and 'structure changed' in out)

    repo = setup(root, 'link')
    outside = os.path.join(root, 'outside.md')
    with open(outside, 'w') as f:
        f.write('```mermaid\nflowchart TD\n    a[PRIVATE] --> b\n```\n')
    os.symlink(outside, os.path.join(repo, 'leak.md'))
    git(repo, 'add', '-A')
    folder = os.path.join(root, 'linkpage')
    os.mkdir(folder)
    code, out = run('page', repo, os.path.join(folder, 'out.html'))
    check('page refuses a link out of the repository', code == 2 and 'inside the repository' in out)
    code, out = run('compare', repo, 'HEAD')
    check('compare fails on a link out of the repository', code == 1 and 'inside the repository' in out)
    repo = setup(root, 'big')
    with open(os.path.join(repo, 'doc.md'), 'w') as f:
        f.write('x' * 5_000_001)
    code, out = run('compare', repo, 'HEAD')
    check('compare fails on a file over the size limit', code == 1 and 'over 5000000 bytes' in out)

    repo = setup(root, 'moved')
    with open(os.path.join(repo, 'doc.md'), 'w') as f:
        f.write(DOC.replace('The text beside the diagrams.\n', ''))
    with open(os.path.join(repo, 'new.md'), 'w') as f:
        f.write('```mermaid\nflowchart TD\n    a --> b\n```\n')
    code, out = run('compare', repo, 'HEAD', '--prose-may-change')
    check('an untracked file with a block fails', code == 1 and 'new.md: 0 blocks became 1' in out)

    repo = setup(root, 'page')
    with open(os.path.join(repo, 'doc.md'), 'a') as f:
        f.write('\n```mermaid\nflowchart TD\n    a["</script><script>alert(1)</script>"] --> b\n```\n')
        f.write('\n```mermaid\nflowchart TD\n    a["1. Refit"] --> b\n```\n')
        f.write('\n```mermaid\nsequenceDiagram\n    A->>B: one   B->>A: two\n```\n')
        f.write('\n```mermaid\nstateDiagram-v2\n    %% old --> mid --> new\n    [*] --> A\n```\n')
    git(repo, 'add', '-A')
    folder = os.path.join(root, 'pagefolder')
    os.mkdir(folder)
    page = os.path.join(folder, 'out.html')
    code, out = run('page', repo, page)
    with open(page) as f:
        text = f.read()
    check('page writes every tracked block', code == 0 and 'wrote 9 blocks' in out)
    check('page reads no fault in a comment', 'old --> mid' not in out)
    check('page leaves the fenced example out', 'stays text' not in text)
    check('page keeps a label from closing its script', '</script><script>alert' not in text)
    check('page names the pinned version', 'mermaid@12.2.0/' in text and 'for Mermaid 12.2.0' in out)
    check('page prints the Markdown fault with its place', re.search(r'doc\.md:\d+: label starts like a Markdown block: 1\. Refit', out))
    check('page prints the join with its place', re.search(r'doc\.md:\d+: second statement suspected', out))
    check('page hands both faults to the drawing', text.count('label starts like a Markdown block: 1. Refit') == 1
          and 'second statement suspected' in text)
    nonce = re.search(r"'nonce-(\w+)'", text)
    policy = (f"default-src 'none'; script-src 'nonce-{nonce[1]}' https://cdn.jsdelivr.net/npm/mermaid@12.2.0/dist/mermaid.min.js; "
              "style-src 'unsafe-inline'; img-src data:; font-src data:; form-action 'none'; base-uri 'none'")
    check('page holds the whole content security policy', f'http-equiv=Content-Security-Policy content="{policy}"' in text)
    check('the inline script carries the nonce', f'<script nonce={nonce[1]}>' in text)
    code, _ = run('page', repo, page)
    with open(page) as f:
        check('each page gets its own nonce', nonce[1] not in f.read())
    check('the page carries the integrity value', 'integrity="sha384-' in text and 'crossorigin=anonymous' in text)
    with open(os.path.join(repo, 'new.md'), 'w') as f:
        f.write('```mermaid\nflowchart TD\n    a["2. Untracked"] --> b\n```\n')
    code, out = run('page', repo, page)
    check('page reads a new file git has not seen', code == 0 and '2. Untracked' in out)
    os.remove(os.path.join(repo, 'new.md'))
    code, out = run('page', repo, os.path.join(root, 'no-such-folder', 'out.html'))
    check('a missing folder stops', code == 2 and 'does not exist' in out)
    with open(os.path.join(folder, 'brief.md'), 'w') as f:
        f.write('private')
    code, out = run('page', repo, page)
    check('page refuses a folder that holds anything else', code == 2 and 'holds other files' in out)
    os.remove(os.path.join(folder, 'brief.md'))
    code, out = run('page', setup(root, 'empty', 'no diagrams\n'), page)
    check('page with no block stops', code == 2 and 'no Mermaid block' in out)

    chrome = next((path for path in (shutil.which('google-chrome'), shutil.which('chromium'), shutil.which('chromium-browser'),
                                     '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
                   if path and os.path.exists(path)), None)
    if chrome is None:
        check('CI has a browser, so the page runs there', 'CI' not in os.environ)
        print('skip the drawn page: no Chrome here, so no test runs the page in a browser on this machine')
    else:
        def drawn(name):
            sandbox = ['--no-sandbox'] if 'CI' in os.environ else []
            done = subprocess.run([chrome, '--headless=new', *sandbox, '--disable-gpu', '--timeout=30000',
                                   '--virtual-time-budget=25000', f'--user-data-dir={os.path.join(root, "chrome" + name)}',
                                   '--dump-dom', 'file://' + page], capture_output=True, text=True, timeout=120)
            return report_of(done.stdout)
        with open(os.path.join(repo, 'doc.md'), 'a') as f:
            f.write('\n```mermaid\nflowchart TD\n    a[ --> \n```\n')
            f.write('\n```mermaid\nflowchart TD\n    %% nothing to draw\n```\n')
        run('page', repo, page)
        dom = drawn('one')
        check('a drawn page reports the two faults and the block that cannot draw', re.search(r'10 of 11 drew, 4 failed', dom))
        check('a drawn page lists the words, with a line break shown', 'Refit the hedge / over 20 days' in dom)
        check('a drawn page names a block that drew no words', 'drew no words' in dom)
        check('a drawn page names the block that failed to draw', re.search(r'doc\.md:\d+: \S', dom) and 'Parse error' in dom)
        hostile = setup(root, 'hostile', '```mermaid\nsequenceDiagram\n    participant A as Alice<meta http-equiv=refresh content="0,url=http://127.0.0.1:9/">$$\\\\text{Alice}$$\n    A->>A: holds\n```\n')
        moved = os.path.join(root, 'hostilepage')
        os.mkdir(moved)
        kept, page = page, os.path.join(moved, 'out.html')
        run('page', hostile, page)
        check('a label cannot move the drawn page', '1 of 1 drew' in drawn('three'))
        page = kept
        with open(page) as f:
            text = f.read()
        with open(page, 'w') as f:
            f.write(text.replace('https://cdn.jsdelivr.net/npm/mermaid@12.2.0/dist/mermaid.min.js', 'http://127.0.0.1:9/none.js'))
        dom = drawn('two')
        check('a page whose Mermaid does not load says so', 'Mermaid did not load, so nothing drew' in dom)
        check('it still names the faults Python found', 'label starts like a Markdown block: 1. Refit' in dom)

print('failures:', failures)
sys.exit(1 if failures else 0)
