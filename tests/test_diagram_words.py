#!/usr/bin/env python3
"""Tests for skills/ask-team/scripts/diagram_words.py on real git repositories it builds in a temporary folder.

    python3 tests/test_diagram_words.py
"""
import os, re, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'skills', 'ask-team', 'scripts', 'diagram_words.py')

failures = 0


def check(name, cond):
    global failures
    print(('ok   ' if cond else 'FAIL ') + name)
    failures += not cond


def git(repo, *args):
    subprocess.run(['git', '-C', repo, '-c', 'user.name=t', '-c', 'user.email=t@example.com', *args], check=True,
                   capture_output=True)


def run(*args):
    done = subprocess.run([sys.executable, '-I', SCRIPT, *args], capture_output=True, text=True)
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
        ('a class relation', 'class Order {', 'class Bill {', 'structure changed'),
        ('a block kind', 'erDiagram', 'classDiagram', 'kind erDiagram became classDiagram'),
        ('an added line', '    Note over S: journal holds it\n', '    Note over S: journal holds it\n    Note over S: more\n', 'lines became'),
        ('an added block', 'The text beside the diagrams.\n', 'The text beside the diagrams.\n\n```mermaid\nflowchart TD\n    a --> b\n```\n', 'blocks became'),
        ('indentation', '    S->>B: asks again', '      S->>B: asks again', 'leading whitespace'),
        ('a number in a label', 'over 20 days', 'over 30 days', 'numbers changed'),
        ('an identifier in a label', 'order_id in order.json', 'id in order.json', 'identifiers changed'),
        ('a file name in a label', 'order_id in order.json', 'order_id in the file', 'identifiers changed'),
        ('a swapped pair of identifiers', 'order_id in order.json', 'order.json in order_id', 'identifiers changed'),
        ('a sign', 'over 20 days', 'over -20 days', 'numbers changed'),
        ('a percent mark', 'over 20 days', 'over 20% days', 'numbers changed'),
        ('a semicolon in a label', 'B-->>-S: acks', 'B-->>-S: acks; then waits', 'semicolon in label'),
        ('an em dash in a label', 'B-->>-S: acks', 'B-->>-S: acks — then waits', 'em dash in label'),
        ('first person in a label', 'B-->>-S: acks', 'B-->>-S: we ack', 'first person'),
        ('first person opening a label', 'B-->>-S: acks', 'B-->>-S: We ack', 'first person'),
        ('an unmatched quote', 'B-->>-S: acks', 'B-->>-S: acks "now', 'unmatched quote'),
        ('a hash in a label', 'B-->>-S: acks', 'B-->>-S: acks #4', 'hash in label'),
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
    code, out = edited(root, 'mdnote', ('b\n```\n', 'c\n```\n'), text=fault_doc.replace('a["1. Refit"] --> b', 'a["1. Refit"] --> b\n    b --> b'))
    check('a fault on an unchanged line of a changed block fails on the change it holds', code == 1)
    note_doc = fault_doc.replace('a["1. Refit"] --> b', 'a["1. Refit"] --> b\n    b["old"] --> c')
    code, out = edited(root, 'mdnote2', ('b["old"]', 'b["the new"]'), text=note_doc)
    check('a fault on an unchanged line of a changed block is a note', code == 0 and 'Markdown block' in out)

    check('a label moved across lines fails', 'label moved' in edited(
        root, 'mv', ('S->>B: asks again', 'S->>B: acks'), ('B-->>-S: acks', 'B-->>-S: asks again'))[1])
    check('two labels swapped on one line fail', 'label moved' in edited(
        root, 'mv2', ('a[Buy] --> b[Sell]', 'a[Sell] --> b[Buy]'), text='```mermaid\nflowchart TD\n    a[Buy] --> b[Sell]\n```\n')[1])
    code, out = edited(root, 'numbered2', ('over 20 days at 5 bps', 'over 5 days at 20 bps'),
                       text=DOC.replace('over 20 days', 'over 20 days at 5 bps'))
    check('swapped numbers fail', code == 1 and 'numbers changed' in out)
    code, out = edited(root, 'ent', ('read #quot;x#quot; first', 'first read #quot;x#quot;'),
                       text=DOC.replace('Write the plan', 'read #quot;x#quot; first'))
    check('an entity the old label held passes', code == 0)
    code, out = edited(root, 'io', ('flush I/O', 'the supervisor flushes I/O'), text=DOC.replace('Write the plan', 'flush I/O'))
    check('I/O is no first person', code == 0)
    code, out = edited(root, 'kept', ('acks; waits', 'the broker acks; it waits'), text=DOC.replace('B-->>-S: acks', 'B-->>-S: acks; waits'))
    check('a semicolon the old label held passes', code == 0)
    wide = 'x' * 58
    code, out = edited(root, 'w58', ('B-->>-S: acks', f'B-->>-S: {wide}'))
    check('a segment of 58 characters draws no note', '58 characters' not in out)
    code, out = edited(root, 'w59', ('B-->>-S: acks', f'B-->>-S: {wide}y'))
    check('a segment of 59 characters draws a note', '59 characters' in out)
    code, out = edited(root, 'quoted', ('S->>B: asks "sending" again', 'S->>B: asks again'),
                       text=DOC.replace('S->>B: asks again', 'S->>B: asks "sending" again'))
    check('a quoted string changing in a message is a note', code == 0 and 'quoted string changed' in out)

    for name, base, new, word in (
        ('a backticked span', 'calls `gate()`', 'calls `check()`', 'identifiers changed'),
        ('a camelCase name', 'calls placeOrder', 'calls sendOrder', 'identifiers changed'),
    ):
        code, out = edited(root, 'id' + name.replace(' ', ''), (base, new), text=DOC.replace('Write the plan', base))
        check(f'{name} that differs fails', code == 1 and word in out)
    code, out = edited(root, 'thirdnode', ('--- b ---', '--- x ---'), text='```mermaid\nflowchart TD\n    a --- b --- c\n```\n')
    check('a node between two plain links is no edge label', code == 1 and 'structure changed' in out)
    check('an entity label losing its quotes fails on one word', 'structure changed' in edited(
        root, 'erquote', ('"belongs"', 'belongs'))[1])
    code, out = edited(root, 'wekept', ('we ack', 'we ack it now'), text=DOC.replace('B-->>-S: acks', 'B-->>-S: we ack'))
    check('first person the old label held passes', code == 0)

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
    check('page names the default version', 'mermaid@12.2.0/' in text)
    check('page prints the Markdown fault with its place', re.search(r'doc\.md:\d+: label starts like a Markdown block: 1\. Refit', out))
    check('page prints the join with its place', re.search(r'doc\.md:\d+: second statement suspected', out))
    check('page hands both faults to the drawing', text.count('label starts like a Markdown block: 1. Refit') == 1
          and 'second statement suspected' in text)
    check('page holds a content security policy', "default-src 'none'" in text and 'http-equiv=Content-Security-Policy' in text)
    nonce = re.search(r"'nonce-(\w+)'", text)
    check('the policy and the script share a nonce', nonce and f'<script nonce={nonce[1]}>' in text)
    code, _ = run('page', repo, page)
    with open(page) as f:
        check('each page gets its own nonce', nonce[1] not in f.read())
    check('the default version carries an integrity value', 'integrity="sha384-' in text and 'crossorigin=anonymous' in text)
    code, _ = run('page', repo, page, '--mermaid', '11.4.1')
    with open(page) as f:
        other = f.read()
    check('page takes a version, with no integrity value of the default', code == 0 and 'mermaid@11.4.1/' in other and 'integrity' not in other)
    for bad in ('latest', '11.4.1/../../evil@1/index.js?x=', '"><script>'):
        code, out = run('page', repo, page, '--mermaid', bad)
        check(f'page refuses the version {bad[:12]!r}', code == 2 and 'exact version' in out)
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
        def drawn(version):
            run('page', repo, page, '--mermaid', version)
            done = subprocess.run([chrome, '--headless=new', '--no-sandbox', '--disable-gpu', '--timeout=30000',
                                   '--virtual-time-budget=25000', f'--user-data-dir={os.path.join(root, "chrome" + version)}',
                                   '--dump-dom', 'file://' + page], capture_output=True, text=True, timeout=120)
            return re.sub(r'<script.*?</script>', '', done.stdout, flags=re.S)
        with open(os.path.join(repo, 'doc.md'), 'a') as f:
            f.write('\n```mermaid\nflowchart TD\n    a[ --> \n```\n')
            f.write('\n```mermaid\nflowchart TD\n    %% nothing to draw\n```\n')
        dom = drawn('12.2.0')
        check('a drawn page reports the two faults and the block that cannot draw', re.search(r'10 of 11 drew, in Mermaid 12\.2\.0, 4 failed', dom))
        check('a drawn page lists the words, with a line break shown', 'Refit the hedge / over 20 days' in dom)
        check('a drawn page names a block that drew no words', 'drew no words' in dom)
        check('a drawn page names the block that failed to draw', re.search(r'doc\.md:\d+: \S', dom) and 'Parse error' in dom)
        with open(os.path.join(repo, 'doc.md'), 'a') as f:
            f.write('\n```mermaid\nstateDiagram-v2\n    note right of A\n        1. Python cannot read this body\n    end note\n```\n')
        dom = drawn('11.4.1')
        check('an older version reports what Mermaid printed', 'drew Unsupported markdown: list' in dom)
        dom = drawn('0.0.0')
        check('a version that does not load says so', 'did not load, so nothing drew' in dom)

print('failures:', failures)
sys.exit(1 if failures else 0)
