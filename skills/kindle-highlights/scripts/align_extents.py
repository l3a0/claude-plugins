#!/usr/bin/env python3
"""Align the notebook scrape with the Mac Kindle app's exact highlight extents -> aligned.json (Step 4).

Run from the RUN DIRECTORY (the folder that holds pages/<asin>_highlights.json from extract_highlights.js):

    python3 align_extents.py <ASIN> [--highlights pages/<asin>_highlights.json] [--db <ksdk_annotation_v1.db>] [--gap 3000]

The app database (bundle com.amazon.Lassen) syncs every highlight's character-precise start/end position,
export limit or not. Open the book in the app first (`open -a "Amazon Kindle" "kindle://book?action=open&asin=<ASIN>"`)
and wait ~30 s for the sync. The database is copied aside before reading. Sorted by position, its rows line up
1:1 with the scraped highlights sorted by location; this script attaches start/end/extent to each highlight,
writes aligned.json, and prints the checks that make the rest of the pipeline trustworthy:

  * extent == len(text) within +-2 on the fully exported highlights (the alignment proof),
  * how many highlights are truncated / hidden and where the hidden run starts,
  * the blocked highlights clustered by position gap, with the sweep span each cluster needs.
"""
import argparse, collections, glob, json, os, shutil, sqlite3, sys

RUN_DIR = os.getcwd()


def find_db():
    hits = glob.glob(os.path.expanduser('~/Library/Containers/com.amazon.Lassen/Data/Library/KSDK/amzn1.account.*/ksdk_annotation_v1.db'))
    if not hits:
        sys.exit('no ksdk_annotation_v1.db found: is the current Mac Kindle app (com.amazon.Lassen) installed and signed in?')
    if len(hits) > 1:
        sys.exit('several Kindle accounts on this Mac. Pass the one holding the book with --db:\n  ' + '\n  '.join(hits))
    return hits[0]


def load_db_rows(db_path, asin):
    os.makedirs(os.path.join(RUN_DIR, 'db'), exist_ok=True)
    local = os.path.join(RUN_DIR, 'db', 'ksdk_annotation_v1.db')
    shutil.copy(db_path, local)
    if os.path.exists(db_path + '-wal'):
        shutil.copy(db_path + '-wal', local + '-wal')
    rows = []
    for (aid, payload) in sqlite3.connect(local).execute("select annotation_id, serialized_payload from server_view where dataset_id like ?", (asin + '%',)):
        j = json.loads(payload)
        if j.get('type') != 'HIGHLIGHT':
            continue
        rows.append({'id': aid, 'start': j['start_position']['shortPosition'], 'end': j['end_position']['shortPosition']})
    rows.sort(key=lambda r: (r['start'], r['end']))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('asin')
    ap.add_argument('--highlights', default=None)
    ap.add_argument('--db', default=None)
    ap.add_argument('--gap', type=int, default=3000, help='cluster blocked highlights whose start is within this many positions of the previous end')
    o = ap.parse_args()
    hl_path = o.highlights or os.path.join(RUN_DIR, 'pages', f'{o.asin}_highlights.json')
    if not os.path.exists(hl_path):
        sys.exit(f'no scrape at {hl_path}: run extract_highlights.js first, then copy the download here or pass --highlights <path>')
    payload = json.load(open(hl_path))
    H = sorted(payload['highlights'], key=lambda h: h['loc'])
    D = load_db_rows(o.db or find_db(), o.asin)
    print(f'notebook rows {len(H)}   app-db highlights {len(D)}')
    if len(H) != len(D):
        if not D:
            print(f'no highlights in the app database for ASIN {o.asin}: check the ASIN, and open the book in the Kindle app so it syncs.')
        else:
            print('COUNT MISMATCH: re-open the book in the Kindle app and wait for the sync, or re-scrape the notebook (paginate until the token empties).')
        sys.exit(2)
    diffs = []
    for h, d in zip(H, D):
        h['start'], h['end'], h['extent'] = d['start'], d['end'], d['end'] - d['start'] + 1
        if h['text'] and not h['truncated'] and not h['hidden']:
            r = h['extent'] - len(h['text'])
            diffs.append(r)
            if abs(r) > 2:
                print(f"  extent/len off by {r:+d} at loc {h['loc']} (len {len(h['text'])}, extent {h['extent']}): usually a display equation, a '( f )' spacing quirk, or a misalignment if many rows disagree")
    hist = collections.Counter(diffs).most_common(6)
    print(f'full rows {len(diffs)}   residual histogram {hist}')
    blk = [h for h in H if h['truncated'] or h['hidden']]
    hid = [h for h in H if h['hidden']]
    print(f"blocked {len(blk)}: truncated {len(blk) - len(hid)}, hidden {len(hid)}" + (f"  (hidden run: loc {hid[0]['loc']} .. {hid[-1]['loc']})" if hid else ''))
    clusters = []
    for h in blk:
        if clusters and h['start'] - clusters[-1][-1]['end'] < o.gap:
            clusters[-1].append(h)
        else:
            clusters.append([h])
    span = sum(c[-1]['end'] - c[0]['start'] for c in clusters)
    print(f"{len(clusters)} blocked clusters, span sum {span} positions of {D[-1]['end'] - D[0]['start']} (~{span // 5500 + len(clusters)} two-column screens at font index 4)")
    for c in clusters:
        print(f"  cluster start {c[0]['start']} (loc {c[0]['loc']}) .. end {c[-1]['end']} (loc {c[-1]['loc']}): {len(c)} highlights, {sum(1 for h in c if h['hidden'])} hidden")
    json.dump({'book': payload.get('book', {}), 'highlights': H}, open(os.path.join(RUN_DIR, 'aligned.json'), 'w'), indent=0, ensure_ascii=False)
    print('wrote aligned.json')
    print('note: db/ now holds a copy of the account annotation database, which covers every book. Delete it when the run is done.')


if __name__ == '__main__':
    main()
