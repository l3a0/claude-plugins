#!/usr/bin/env python3
"""Dictionary QA over the recovered text: the OCR slips the extent check cannot see (same-length substitutions).

Run from the RUN DIRECTORY after finalize.py:

    python3 qa_words.py [completions_final.json]

Four sweeps, each printed with context so every hit can be checked against its page crop
(inspect_highlight.py <loc>):

  1. non-dictionary words (inflections accepted, ALL-CAPS tickers skipped, words present in the notebook's own
     exported text skipped),
  2. joined words: a non-word that splits into two known words ("exchangetraded" = a line-end hyphen the join
     dropped, "pressuresomebody" = a lost em dash),
  3. first-letter loss: a non-word that becomes a word with one leading letter ("ortfolio", "opefully" = a crop
     margin too tight, or a drop cap the OCR skipped),
  4. hidden highlights whose recovered text starts lowercase (a chapter opener's drop cap is a separate glyph
     the OCR misses: "ven though" -> "Even though").

Set KINDLE_DICT to use a word list other than /usr/share/dict/words.
"""
import collections, json, os, re, sys

RUN_DIR = os.getcwd()
DICT = os.environ.get('KINDLE_DICT', '/usr/share/dict/words')
WORDS = set(w.strip().lower() for w in open(DICT)) if os.path.exists(DICT) else set()
C = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(RUN_DIR, 'completions_final.json')))
A = json.load(open(os.path.join(RUN_DIR, 'aligned.json')))
H = {str(h['loc']): h for h in A['highlights']}
truth = ' '.join(h['text'] for h in A['highlights'] if h['text'])
TRUTH_WORDS = set(w.lower() for w in re.findall(r"[A-Za-z']+", truth))
SUFFIXES = ('s', 'es', 'ed', 'd', 'ing', 'ly', 'er', 'ers', 'est', 'ment', 'ments', 'ness', 'ies', 'ally', 'ised', 'ized')


def known(x):
    x = x.lower().strip("'")
    if x in WORDS or x in TRUTH_WORDS:
        return True
    for suf in SUFFIXES:
        if x.endswith(suf):
            stem = x[:-len(suf)]
            if stem in WORDS or stem + 'e' in WORDS or stem + 'y' in WORDS:
                return True
    return False


def ctx(t, m, width=40):
    return '…' + t[max(0, m.start() - width):m.end() + width].replace('\n', ' ') + '…'


print('=== 1. non-dictionary words')
occ = collections.defaultdict(list)
for loc, t in C.items():
    for m in re.finditer(r"[A-Za-z][A-Za-z']*", t):
        w = m.group()
        if len(w) <= 1 or known(w) or re.fullmatch(r"[A-Z]+", w):
            continue
        occ[w].append((loc, ctx(t, m)))
for w, xs in sorted(occ.items(), key=lambda kv: (-len(kv[1]), kv[0])):
    print(f"{w!r} x{len(xs)}")
    for loc, c in xs[:3]:
        print(f"     {loc}: {c}")

print('=== 2. joined-word candidates (non-word = word + word)')
for loc, t in C.items():
    for w in sorted(set(re.findall(r"\b[a-z]{9,}\b", t))):
        if known(w):
            continue
        for i in range(4, len(w) - 3):
            if known(w[:i]) and known(w[i:]):
                print(f"  {loc}: {w} = {w[:i]} + {w[i:]}")
                break

print('=== 3. first-letter-loss candidates (non-word that becomes a word with one leading letter)')
for loc, t in C.items():
    for w in sorted(set(re.findall(r"\b[a-z]{4,}\b", t))):
        if known(w):
            continue
        cands = [c + w for c in 'abcdefghijklmnopqrstuvwxyz' if known(c + w)]
        if cands:
            print(f"  {loc}: {w} -> {cands}")

print('=== 4. hidden highlights whose recovered text starts lowercase (drop cap?)')
for loc, t in C.items():
    if H[loc]['hidden'] and t[:1].islower():
        print(f"  {loc}: {t[:60]!r}")
