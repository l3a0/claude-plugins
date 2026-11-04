#!/usr/bin/env python3
"""Three-way merge a file clause by clause, for prose that keeps each paragraph on one long line.

    git merge origin/main        # stops on a conflict in docs/design.md
    python3 -I fine_merge.py "$(git merge-base HEAD origin/main)" origin/main docs/design.md docs/team-charter.md

git merges whole lines, so two sides that touched different sentences of one paragraph conflict on all of it. This
cuts all three versions at every space after . , : ; ? or !, runs git merge-file on the pieces and joins them again,
so only a clause both sides changed conflicts. The arguments are the merge base, the other side and the paths, and
ours is HEAD. A path must be clean or stopped in a merge, so a merge's conflicted file is rewritten and an uncommitted
edit is refused. Run it before any hand edits, since a hand resolution made in a stopped merge is lost.

A conflict keeps its markers at the start of their own lines, inside the paragraph, so rejoin those lines when
resolving it. Each path prints its conflicts and the exit status is 1 when any remain. No path is written unless
every path merged. The price of merging clauses is a clean result that can still read wrong, as when one side renames
a term and the other uses the old name in the next clause, so read the merged paragraphs.
"""
import os
import re
import subprocess
import sys
import tempfile

MARK = b'\x01'
CLAUSE_END = rb'(?<=[.,:;?!])'


def cut(text):
    return re.sub(CLAUSE_END + b' ', b'\n' + MARK + b' ', text)


def join(text):
    # A marker line ends in no clause punctuation, so the piece after it keeps its line.
    return re.sub(CLAUSE_END + b'\n' + MARK, b'', text).replace(MARK, b'')


def show(ref, path):
    # The ./ makes git read the path from the current folder, as open() does, not from the repository root.
    p = subprocess.run(['git', 'show', f'{ref}:./{path}'], capture_output=True)
    if p.returncode:
        sys.exit(f'{path}: {p.stderr.decode(errors="replace").strip()}')
    if MARK in p.stdout:
        sys.exit(f'{path}: {ref} holds the byte this script marks clause breaks with')
    return p.stdout


def merge(base_ref, theirs_ref, path):
    sides = show('HEAD', path), show(base_ref, path), show(theirs_ref, path)
    status = subprocess.run(['git', 'status', '--porcelain', '--', path], capture_output=True).stdout[:2]
    if status not in (b'', b'UU'):
        sys.exit(f'{path}: has uncommitted edits, which this would overwrite')
    with tempfile.TemporaryDirectory() as d:
        files = [os.path.join(d, name) for name in ('ours', 'base', 'theirs')]
        for name, text in zip(files, sides):
            with open(name, 'wb') as f:
                f.write(cut(text))
        p = subprocess.run(['git', 'merge-file', '-p', '-L', 'HEAD', '-L', base_ref, '-L', theirs_ref, *files],
                           capture_output=True)
    # git merge-file exits with its conflict count, capped at 127, or 255 on an error, which leaves nothing on stdout.
    if p.returncode > 127:
        sys.exit(f'{path}: git merge-file failed: {p.stderr.decode(errors="replace").strip()}')
    return join(p.stdout), p.returncode


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    base_ref, theirs_ref, paths = argv[0], argv[1], argv[2:]
    merged = [(path, *merge(base_ref, theirs_ref, path)) for path in paths]
    for path, text, conflicts in merged:
        with open(path, 'wb') as f:
            f.write(text)
        print(f'{path}: {conflicts} conflicts')
    return 1 if any(conflicts for _, _, conflicts in merged) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
