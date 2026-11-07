#!/usr/bin/env python3
"""Tests for skills/ask-team/scripts/diagram_words.py on real git repositories it builds in a temporary folder.

    python3 tests/test_diagram_words.py
"""
import os, subprocess, sys, tempfile

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
    ORDER }o..|| PLAN : belongs
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
        ('PLAN : belongs', 'PLAN : belongs to'),
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
        ('a block kind', 'erDiagram', 'classDiagram', 'kind erDiagram became classDiagram'),
        ('an added line', '    Note over S: journal holds it\n', '    Note over S: journal holds it\n    Note over S: more\n', 'lines became'),
        ('an added block', 'The text beside the diagrams.\n', 'The text beside the diagrams.\n\n```mermaid\nflowchart TD\n    a --> b\n```\n', 'blocks became'),
        ('indentation', '    S->>B: asks again', '      S->>B: asks again', 'leading whitespace'),
        ('a number in a label', 'over 20 days', 'over 30 days', 'numbers changed'),
        ('an identifier in a label', 'order_id in order.json', 'id in order.json', 'identifiers changed'),
        ('a file name in a label', 'order_id in order.json', 'order_id in the file', 'identifiers changed'),
        ('a semicolon in a label', 'B-->>-S: acks', 'B-->>-S: acks; then waits', 'semicolon in label'),
        ('an em dash in a label', 'B-->>-S: acks', 'B-->>-S: acks — then waits', 'em dash in label'),
        ('first person in a label', 'B-->>-S: acks', 'B-->>-S: we ack', 'first person'),
        ('a hash in a label', 'B-->>-S: acks', 'B-->>-S: acks #4', 'hash in label'),
    ):
        code, out = edited(root, 'c' + name.replace(' ', ''), (old, new))
        check(f'{name} fails with {word!r}', code == 1 and word in out and 'RESULT: FAILED' in out)

    for name, old, new in (
        ('three spaces', 'B-->>-S: acks', 'B-->>-S: acks   S->>B: goes on'),
        ('three spaces and no arrow', 'B-->>-S: acks', 'B-->>-S: acks   activate S'),
        ('one space', 'B-->>-S: acks', 'B-->>-S: acks S->>B: goes on'),
        ('a note', 'B-->>-S: acks', 'B-->>-S: acks Note over S: goes on'),
    ):
        code, out = edited(root, 'join' + name.replace(' ', ''), (old, new))
        check(f'a sequence statement joined with {name} fails', code == 1 and 'second statement joined' in out)

    code, out = edited(root, 'joinstate', ('Flat --> Long: z below 1', 'Flat --> Long: z   Long --> Flat: y 1'))
    check('a joined state statement fails', code == 1 and 'second statement joined' in out)

    for name, old, new in (
        ('a numbered flowchart node', 'a["Refit the hedge', 'a["1. Refit the hedge'),
        ('a closing-bracket number', 'a["Refit the hedge', 'a["1) Refit the hedge'),
        ('an unquoted flowchart node', 'b[Write the plan]', 'b[2. Write the plan]'),
        ('a bullet', 'b[Write the plan]', 'b[- Write the plan]'),
        ('a heading', 'b[Write the plan]', 'b[## Write the plan]'),
        ('an edge label', '|sends the order|', '|1. sends the order|'),
        ('a state transition', 'z below 1', '1. z below'),
        ('a state note', 'holds one unit', '1. holds one unit'),
        ('a state name', '"Flat (0 units)"', '"1. Flat (0 units)"'),
    ):
        code, out = edited(root, 'md' + name.replace(' ', ''), (old, new))
        check(f'{name} that starts like a Markdown block fails', code == 1 and 'starts like a Markdown block' in out)

    class_doc = DOC.replace('    class Order {', '    class Order["3. the order"] {')
    code, out = edited(root, 'mdclass', ('+order_id str', '+order_id str'), ('The text beside', 'Text beside'),
                       text=class_doc)
    check('a class label fault fails on an unchanged line of a changed file', 'starts like a Markdown block' in out)

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
    code, out = run('compare', repo, '--output=x')
    check('a base that reads as a flag stops', code != 0)

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
    git(repo, 'add', '-A')
    page = os.path.join(root, 'page.html')
    code, out = run('page', repo, page)
    with open(page) as f:
        text = f.read()
    check('page writes every tracked block', code == 0 and 'wrote 6 blocks' in out)
    check('page leaves the fenced example out', 'stays text' not in text)
    check('page keeps a label from closing its script', '</script><script>alert' not in text)
    check('page names the default version', 'mermaid@11.4.1/' in text)
    check('page reports both faults a render passes', "startsWith('Unsupported markdown')" in text and 'JOINED.test(w)' in text)
    code, _ = run('page', repo, page, '--mermaid', '12.2.0', '--file', 'doc.md')
    with open(page) as f:
        check('page takes a version', code == 0 and 'mermaid@12.2.0/' in f.read())
    code, out = run('page', setup(root, 'empty', 'no diagrams\n'), page)
    check('page with no block stops', code == 2 and 'no Mermaid block' in out)

print('failures:', failures)
sys.exit(1 if failures else 0)
