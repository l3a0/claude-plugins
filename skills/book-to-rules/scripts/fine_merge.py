#!/usr/bin/env python3
"""Three-way merge a conflicted Markdown file clause by clause, for prose that keeps each paragraph on one long line.

    git merge origin/main        # stops on a conflict in docs/design.md
    python3 -I fine_merge.py $(git diff --name-only --diff-filter=U -- '*.md')

git merges whole lines, so two sides that touched different sentences of one paragraph conflict on all of it. This
reads the three versions git's index holds for each path, cuts them at every space after . , : ; ? or !, runs
git merge-file on the pieces and joins them again. A conflict stays only where the two sides changed one clause or
clauses close together, and git folds conflicts within about three clauses of each other into one. It works at any
stop that leaves a path conflicted, such as a merge, a rebase or a cherry-pick.

A conflict keeps its markers at the start of their own lines, inside the paragraph, so rejoin those lines when
resolving it. Each file's previous text is saved first and the copy printed, because a hand resolution, or one rerere
replayed, looks the same to git as a fresh stop. The copies sit in the worktree's git folder, so they go when the
worktree does. Line ends and ident come out in the stored form until the next checkout. A symlink, a path whose
attributes name a filter or a working-tree encoding, and a path git does not hold as conflicted with a base, ours and
theirs are refused, and then no path is written. The exit status is 0 when no conflict remains, 1 when one does and 2 when no
path was given, a path was refused, or a read, a write or a tool failed.

The price of merging clauses is a clean result that can still read wrong, as when one side renames a term and the
other uses the old name in the next clause. So keep this to prose, since it can also join two sides of a line of code
into something that does not compile.
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile

MARK = b'\x01'
CLAUSE_END = rb'(?<=[.,:;?!])'
LABELS = 'ours', 'base', 'theirs'


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(2)


def git(*args):
    p = subprocess.run(['git', *args], capture_output=True)
    if p.returncode:
        fail(f'git {args[0]}: {p.stderr.decode(errors="replace").strip()}')
    return p.stdout


def cut(text):
    return re.sub(CLAUSE_END + b' ', b'\n' + MARK + b' ', text)


def join(text):
    # A marker line ends in no clause punctuation, so the piece after it keeps its line.
    return re.sub(CLAUSE_END + b'\n' + MARK, b'', text).replace(MARK, b'')


def stages(path):
    """Ours, base and theirs from the index."""
    if not git('ls-files', '-u', '--', path):
        fail(f'{path}: is not conflicted')
    if os.path.islink(path):
        fail(f'{path}: is a symlink, so writing it would reach another file')
    attributes = git('check-attr', 'filter', 'working-tree-encoding', '--', path)
    if re.search(rb': (filter|working-tree-encoding): (?!(unspecified|unset)$)', attributes, re.M):
        fail(f'{path}: git may convert this path on checkout, so the form git stores cannot be written back')
    # The real path lets an absolute path through a linked folder, such as macOS's /var, match the index.
    sides = [git('show', f':{n}:./{os.path.relpath(os.path.realpath(path))}') for n in (2, 1, 3)]
    if any(MARK in side for side in sides):
        fail(f'{path}: holds the byte this script marks clause breaks with')
    return sides


def merge(path, sides):
    with tempfile.TemporaryDirectory() as d:
        files = [os.path.join(d, name) for name in LABELS]
        for name, text in zip(files, sides):
            with open(name, 'wb') as f:
                f.write(cut(text))
        labels = [arg for label in LABELS for arg in ('-L', label)]
        p = subprocess.run(['git', 'merge-file', '-p', *labels, *files], capture_output=True)
    # git merge-file exits with its conflict count, capped at 127, 255 on an error, and a signal shows as negative.
    # None of those last two leaves a merge on stdout, so they must stop before the write.
    if not 0 <= p.returncode <= 127:
        fail(f'{path}: git merge-file exited {p.returncode}: {p.stderr.decode(errors="replace").strip()}')
    return join(p.stdout), p.returncode


def save(path):
    """Keep the file's text under the git folder, one copy per distinct text, and return where it went."""
    with open(path, 'rb') as f:
        text = f.read()
    folder = git('rev-parse', '--git-path', 'fine-merge').decode().strip()
    os.makedirs(folder, exist_ok=True)
    copy = os.path.join(folder, f'{hashlib.sha256(text).hexdigest()[:12]}-{os.path.basename(path)}')
    with open(copy, 'wb') as f:
        f.write(text)
    return copy


def main(argv):
    if not argv:
        fail(__doc__)
    try:
        merged = [(path, *merge(path, stages(path))) for path in argv]
        copies = [save(path) for path, _, _ in merged]
        for (path, text, conflicts), copy in zip(merged, copies):
            print(f'{path}: {"127 or more" if conflicts == 127 else conflicts} conflicts, previous text in {copy}')
            with open(path, 'wb') as f:
                f.write(text)
    except OSError as e:
        fail(str(e))
    return 1 if any(conflicts for _, _, conflicts in merged) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
