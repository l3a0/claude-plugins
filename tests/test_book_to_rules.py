#!/usr/bin/env python3
"""Tests for skills/book-to-rules/scripts on a synthetic book.

    python3 tests/test_book_to_rules.py

The fixture is invented text in every header form booktext.py reads, printed pages and Kindle screens, so it holds
no book text and runs on the Linux CI runner.
"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, '..', 'skills', 'book-to-rules', 'scripts')
sys.path.insert(0, SCRIPTS)

failures = 0


def check(name, cond):
    global failures
    print(('ok   ' if cond else 'FAIL ') + name)
    failures += not cond


PAGES = """===== pdf 1 | front 0 =====
Front matter about the edition.
===== pdf 2 | p. 1 =====
Chapter one opens with a claim about one writer per fact, which the
book makes once here.
===== pdf 3 | p. 2 =====
A sentence that breaks across the page with a hyphenated compu-
tation and ends on a “curly” quote. The tuning procedure starts
===== pdf 4 | p. 3 =====
measured before and after every change. The last line of this page splits a recon-
[margin]
A margin quote the owner highlighted.
===== pdf 5 | p. 4 =====
ciliation step across the break. Chapter two talks about estimates that converge late,
a high–low range, the ﬁrst ﬁle, and a soft­hyphen.
Repeated sentence for the mapper to find twice.
===== pdf 6 | front =====
Unnumbered front matter from an older run.
===== pdf 7 | p. 5 =====
Page five opens with a unique line for the anchor.
Repeated sentence for the mapper to find twice.
Closing words of page five come after the repeat.
"""

SCREENS = """===== b000 | Page 7 of 90 ● 0% | Location 52 of 900 =====
Preface text on the first screen.
===== b001 | Location 80 of 900 ● 9% =====
Screen two holds the lease and the fencing token.
===== b002 |  =====
A screen whose capture lost its footer.
===== b003 | Location 112 of 900 ● 12% =====
Screen four holds the outbox and the journal.
"""

KPAGES = """===== b000 | Page 160 of 300 ● 50% =====
The first screen of page one sixty.
===== b001 | Page 160 of 300 ● 50% =====
The second screen of the same page holds the claim.
===== b002 | Page 162 of 300 ● 51% =====
A later page entirely.
"""

APPROX = """===== b000 | Page 7 of 90 ● 0% | Location ~100 =====
Estimated screen one about replication lag.
===== b001 | Page 8 of 90 ● 1% | Location ~130 =====
Estimated screen two about quorum reads.
"""


def run(script, *args, cwd=None):
    p = subprocess.run([sys.executable, '-I', os.path.join(SCRIPTS, script), *args], capture_output=True, text=True,
                       cwd=cwd)
    return p.returncode, p.stdout, p.stderr


def oks(out):
    return sum(line.startswith('OK') for line in out.splitlines())


with tempfile.TemporaryDirectory() as d:
    def write(name, text):
        path = os.path.join(d, name)
        open(path, 'w', encoding='utf-8').write(text)
        return path

    pages, screens, kpages, approx = (write(n, t) for n, t in (('book_pages.txt', PAGES), ('book.txt', SCREENS),
                                                              ('kp.txt', KPAGES), ('approx.txt', APPROX)))

    import booktext
    blocks = booktext.load(pages)
    check('loader reads every page form, numbering a bare front from its pdf source',
          [b.cite() for b in blocks] == ['front0', '1', '2', '3', '4', 'front6', '5'])
    check('parse_key reads every key form',
          [booktext.parse_key(k) for k in ('73', 'xiv', 'front2', 'loc1500', 'L1500', 'L~1500', 'kp160')]
          == [('p', '73', False), ('p', 'xiv', False), ('front', 2, False), ('loc', 1500, False),
              ('loc', 1500, False), ('loc', 1500, True), ('kp', 160, False)])
    sb = booktext.load(screens)
    check('an empty label still opens a block', len(sb) == 4 and sb[2].kind == 'label')
    check('a label with a page and a location is cited by location', sb[0].cite() == 'loc52')
    check('a location falls in the screen that starts at or before it, the start itself included',
          booktext.find(sb, 'loc100') == (1, 1) and booktext.find(sb, 'loc80') == (1, 1)
          and booktext.find(sb, 'loc112') == (3, 3))
    check('a location before the first screen or past the last names none',
          booktext.find(sb, 'loc10') is None and booktext.find(sb, 'loc901') is None)
    check('a Kindle page takes every screen that shows it, and a missing page falls back',
          booktext.find(booktext.load(kpages), 'kp160') == (0, 1) and booktext.find(booktext.load(kpages), 'kp161')
          == (0, 1))
    check('an estimated location is read and cited with a tilde', booktext.load(approx)[1].cite() == 'L~130')
    code, _, err = run('pg.py', write('broken.txt', '===== p. 1 =====\nno separator\n===== pdf 2 | p. 2 =====\nx\n'),
                       '2:x y z')
    check('a header-like line that does not parse is reported', 'did not parse' in err)

    code, out, _ = run('pg.py', pages, '1:one writer per fact', '2:a hyphenated computation', '2:a "curly" quote',
                       '2:procedure starts measured before', '3:margin quote the owner')
    check('pg passes a phrase on its page, across a line-end hyphen, a curly quote, a page break and a margin',
          code == 0 and oks(out) == 5)
    code, out, _ = run('pg.py', pages, '3:splits a reconciliation step')
    check('pg passes a phrase that runs from a page with a margin onto the next, across a hyphen', code == 0)
    code, out, _ = run('pg.py', pages, '4:a high-low range, the first file, and a softhyphen')
    check('pg folds an en dash, a ligature and a soft hyphen', code == 0)
    code, out, _ = run('pg.py', pages, '2:measured before and after')
    check('pg flags a citation one page early as NEAR', code == 1 and out.startswith('NEAR') and "'3'" in out)
    code, out, _ = run('pg.py', pages, '3:ciliation step across the break')
    check('pg flags a phrase that only starts on the next page as NEAR', code == 1 and out.startswith('NEAR'))
    code, out, _ = run('pg.py', pages, '2:one writer per fact')
    check('pg flags a citation one page late as NEAR', code == 1 and out.startswith('NEAR') and "'1'" in out)
    code, out, _ = run('pg.py', pages, '4:one writer per fact')
    check('pg flags a citation two pages off as MISS and names the right page',
          code == 1 and out.startswith('MISS') and "['1']" in out)
    code, out, _ = run('pg.py', pages, '99:the outbox holds')
    check('pg flags a page the text lacks as NOKEY', code == 1 and out.startswith('NOKEY'))
    code, out, _ = run('pg.py', pages, '1:', '1:one', ':one writer per')
    check('pg refuses an empty phrase, a one-word phrase and an empty key',
          code == 1 and oks(out) == 0 and 'SHORT' in out and out.count('BAD') == 2)
    code, out, _ = run('pg.py', screens, 'loc100:the fencing token', 'L130:holds the outbox')
    check('pg checks Kindle locations', code == 0 and oks(out) == 2)
    code, out, _ = run('pg.py', kpages, 'kp160:same page holds the claim')
    check('pg checks a Kindle page across its screens', code == 0)
    code, out, _ = run('pg.py', approx, 'L~100:about quorum reads', 'loc100:about quorum reads')
    check('pg accepts a neighbouring screen only for a key written approximate',
          code == 1 and out.startswith('OK~') and 'NEAR' in out)
    cites = write('cites.txt', '# a comment\n1:one writer per\n\n4:estimates that converge\n')
    code, out, _ = run('pg.py', pages, '--file', cites)
    check('pg reads citations from a file and skips comments', code == 0 and '2 of 2 OK' in out)
    code, out, _ = run('pg.py', pages, '--file', write('empty.txt', '# nothing\n'))
    check('pg fails when there is nothing to check', code == 1)

    code, out, _ = run('ctx.py', pages, '4:estimates that converge')
    check('ctx prints the passage around the phrase', 'chapter two talks about estimates' in out)
    code, out, _ = run('ctx.py', pages, '3:splits a reconciliation step')
    check('ctx shows the joined passage pg passed', 'OK:' in out and 'reconciliation step across' in out)
    code, out, _ = run('ctx.py', pages, '4:one writer per')
    check('ctx says where a phrase it cannot find on the page is', 'MISS' in out and "['1']" in out)

    parts = os.path.join(d, 'parts')
    code, out, _ = run('split_parts.py', pages, parts, '1-ch1=1', '2-ch2=4')
    one = open(os.path.join(parts, '1-ch1.txt'), encoding='utf-8').read()
    two = open(os.path.join(parts, '2-ch2.txt'), encoding='utf-8').read()
    check('split keeps headers and splits at the chapter start',
          one.startswith('===== pdf 2 | p. 1 =====') and '| p. 3 =====' in one and 'Chapter two' not in one
          and two.startswith('===== pdf 5 | p. 4 ====='))
    check('split reports the front matter it left out', 'left out 1 blocks' in out)
    code, out, err = run('split_parts.py', pages, parts, '1-a=3', '2-b=1')
    check('split refuses starts out of book order', code != 0 and 'book order' in err)
    code, out, err = run('split_parts.py', pages, parts, '1-a=1', '2-b=1')
    check('split refuses a repeated start', code != 0 and 'book order' in err)
    code, out, _ = run('pg.py', os.path.join(parts, '1-ch1.txt'), '3:margin quote the owner')
    check('a part file is itself checkable', code == 0)

    hl = write('hl.json', json.dumps({'highlights': [
        {'loc': '10', 'text': 'Chapter one opens with a claim about one writer per fact', 'note': 'keep'},
        {'loc': '20', 'text': 'A margin quote the owner highlighted.', 'note': ''},
        {'loc': '30', 'text': 'Nothing in this book says this sentence at all', 'note': ''},
        {'loc': '40', 'text': 'XQZJ damaged by OCR here, then: Chapter two talks about estimates that converge late',
         'note': ''},
        {'loc': '40', 'text': 'Page five opens with a unique line for the anchor.', 'note': ''},
        {'loc': '50', 'text': 'Repeated sentence for the mapper to find twice.', 'note': ''},
        {'loc': '55', 'text': 'Closing words of page five come after the repeat.', 'note': ''},
        {'loc': '60', 'text': 'A margin quote the owner highlighted ZZZZ junk junk', 'note': ''}]}))
    out_json = os.path.join(d, 'hl_pages.json')
    code, out, _ = run('hlmap.py', pages, hl, out_json)
    rows = json.load(open(out_json, encoding='utf-8'))
    check('hlmap maps body and margin highlights, falls back past a damaged start or a damaged end, marks a miss',
          [h['page'] for h in rows] == ['1', '3', '?', '4', '5', '5', '5', '3'] and 'mapped 7 of 8' in out)
    check('hlmap places a repeated match by location order, not at its first copy, and names the other copy',
          rows[5].get('also') == ['4'] and '1 repeats placed by location order' in out)
    check('hlmap flags a match that breaks location order, and not two highlights at one location on two pages',
          rows[7].get('check') == 'out of location order' and '1 out of location order' in out
          and not any(h.get('check') for h in rows[:7]))
    code, out, err = run('hlmap.py', pages, hl, hl)
    check('hlmap refuses to write over its input', code != 0 and 'overwrite' in err)

    clean = write('clean.md', '+ A rule paraphrases the book and cites p. 4.\n')
    copied = write('copied.md', '+ The rule says: Chapter two talks about estimates that converge late.\n')
    code, out, _ = run('overlap.py', pages, clean)
    check('overlap passes a paraphrase', code == 0)
    code, out, _ = run('overlap.py', pages, copied)
    check('overlap flags a run of six words copied from any page', code == 1 and 'copied.md:1: 8 words' in out)

    def git(repo, *args):
        return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.com', '-c',
                               'commit.gpgsign=false', *args], cwd=repo, capture_output=True, text=True)

    def stopped_merge(name, base, ours, theirs, path='doc.md'):
        """A repository whose main and theirs branches changed path, with git's own merge stopped or finished."""
        repo = os.path.join(d, name)
        os.makedirs(os.path.dirname(os.path.join(repo, path)), exist_ok=True)
        full = os.path.join(repo, path)

        def commit(text):
            open(full, 'wb').write(text.encode())
            git(repo, 'add', '.')
            git(repo, 'commit', '-m', 'change')

        git(repo, 'init', '-b', 'main')
        commit(base)
        git(repo, 'checkout', '-b', 'theirs')
        commit(theirs)
        git(repo, 'checkout', 'main')
        commit(ours)
        git(repo, 'merge', 'theirs')
        return repo, full

    def fine_merge(repo, *paths, cwd=None):
        base = git(repo, 'merge-base', 'HEAD', 'theirs').stdout.strip()
        return run('fine_merge.py', base, 'theirs', *paths, cwd=cwd or repo)

    def read(path):
        return open(path, 'rb').read().decode()

    para = 'First claim here, second claim here, third claim here, fourth claim here.'
    repo, doc = stopped_merge('apart', f'{para}\nA second paragraph.\n',
                              f'{para.replace("First", "Opening")}\nA second paragraph.\n',
                              f'{para.replace("third", "other")}\nA second paragraph.\n')
    check('fine_merge starts from a paragraph git itself stops on', '<<<<<<<' in read(doc))
    code, out, _ = fine_merge(repo, 'doc.md')
    check('fine_merge joins changes to two clauses of one paragraph, with the file\'s line breaks intact',
          code == 0 and 'doc.md: 0 conflicts' in out and read(doc)
          == 'Opening claim here, second claim here, other claim here, fourth claim here.\nA second paragraph.\n')

    repo, doc = stopped_merge('appended', f'{para}\n', f'{para} A fifth sentence on the end.\n',
                              f'{para.replace("third", "other")}\n')
    code, out, _ = fine_merge(repo, 'doc.md')
    check('fine_merge joins a sentence added to a paragraph\'s end with a change to a clause just before the last',
          code == 0 and read(doc)
          == 'First claim here, second claim here, other claim here, fourth claim here. A fifth sentence on the end.\n')

    repo, doc = stopped_merge('same', f'{para}\n', f'{para.replace("second", "ours")}\n',
                              f'{para.replace("second", "mine")}\n')
    code, out, _ = fine_merge(repo, 'doc.md')
    lines = read(doc).split('\n')
    check('fine_merge keeps a clause both sides changed in conflict, each marker at the start of its own line',
          code == 1 and 'doc.md: 1 conflicts' in out
          and lines == ['First claim here,', '<<<<<<< HEAD', ' ours claim here,', '=======', ' mine claim here,',
                        '>>>>>>> theirs', ' third claim here, fourth claim here.', ''])
    git(repo, 'add', 'doc.md')
    check('git sees those markers as leftover conflict markers', 'conflict marker' in git(repo, 'diff', '--cached',
                                                                                         '--check').stdout)

    prose = 'Ends a clause; asks why? Says so! Keeps  two spaces, a trailing one. \r\nand\u00a0more: \u2014 caf\u00e9.'
    repo, doc = stopped_merge('exact', prose, prose, prose)
    code, out, _ = run('fine_merge.py', 'HEAD', 'HEAD', 'doc.md', cwd=repo)
    check('fine_merge rebuilds an unchanged file byte for byte, with no line end on its last line',
          code == 0 and open(doc, 'rb').read() == prose.encode())

    marks = 'One; two, three? four! five: six.'
    repo, doc = stopped_merge('marks', f'{marks}\n', f'{marks.replace("One", "1")}\n',
                              f'{marks.replace("four", "4")}\n')
    code, out, _ = fine_merge(repo, 'doc.md')
    check('fine_merge cuts at a semicolon, a question mark and an exclamation mark too',
          code == 0 and read(doc) == '1; two, three? 4! five: six.\n')

    repo, doc = stopped_merge('marks2', 'One; two\n', '1; two\n', 'One; 2\n')
    code, out, _ = fine_merge(repo, 'doc.md')
    check('fine_merge conflicts on two neighbouring clauses, since no unchanged clause sits between them',
          code == 1 and '<<<<<<< HEAD' in read(doc))

    repo, doc = stopped_merge('nested', f'{para}\n', f'{para.replace("First", "Opening")}\n',
                              f'{para.replace("third", "other")}\n', path='docs/doc.md')
    code, out, _ = fine_merge(repo, 'doc.md', cwd=os.path.join(repo, 'docs'))
    check('fine_merge reads a path from the current folder, not the repository root',
          code == 0 and 'other claim' in read(doc) and 'Opening' in read(doc))

    repo, doc = stopped_merge('edits', f'{para}\n', f'{para.replace("First", "Opening")}\n', f'{para}\n')
    open(doc, 'wb').write(b'an edit nobody committed\n')
    code, _, err = fine_merge(repo, 'doc.md')
    check('fine_merge refuses to overwrite an uncommitted edit',
          code != 0 and 'uncommitted' in err and read(doc) == 'an edit nobody committed\n')

    repo, doc = stopped_merge('binary', f'{para}\n', f'{para.replace("First", "Opening")}\n', 'not\0text\n')
    before = read(doc)
    code, _, err = fine_merge(repo, 'doc.md')
    check('fine_merge leaves the file alone when git merge-file fails', code != 0 and 'failed' in err
          and read(doc) == before)

    repo, doc = stopped_merge('marked', f'{para}\n', f'{para.replace("First", "Opening")}\n', 'a\x01b\n')
    before = read(doc)
    code, _, err = fine_merge(repo, 'doc.md')
    check('fine_merge refuses text holding its own clause mark', code != 0 and 'marks clause breaks' in err
          and read(doc) == before)

    repo, doc = stopped_merge('partial', f'{para}\n', f'{para.replace("First", "Opening")}\n',
                              f'{para.replace("third", "other")}\n')
    before = read(doc)
    code, _, err = fine_merge(repo, 'doc.md', 'missing.md')
    check('fine_merge writes no path unless every path merged', code != 0 and 'missing.md' in err
          and read(doc) == before)
    code, _, err = run('fine_merge.py', 'HEAD', 'theirs', cwd=repo)
    check('fine_merge asks for at least one path', code != 0 and 'fine_merge.py' in err)

print('all passed' if not failures else f'{failures} failed')
sys.exit(1 if failures else 0)
