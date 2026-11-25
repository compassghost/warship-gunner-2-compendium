"""Inventory every entry of every game archive by magic / size class.
Run: python tools/inventory_archives.py [out.json]   (cache of decompressed first 64 bytes + sizes)"""
import os, sys, json, struct, collections
sys.path.insert(0, os.path.dirname(__file__))
import wg2
ROOT = os.path.join(os.path.dirname(__file__), '..')
ARCS = ['BEV', 'CHR', 'DAT', 'DSN', 'EFC', 'EVT', 'MAP', 'MDT_SHIP', 'MDT_WEPH', 'MDT_WEPL', 'PRV']

def magic(d):
    if not d: return 'EMPTY'
    h = d[:8]
    for m in (b'SHTXFS', b'SHTXST', b'SHTX3I', b'SHTX', b'PSC1', b'PSM0', b'PSC4', b'PSB5', b'PSB4', b'PSM6', b'PTC', b'EEF', b'EFC', b'LPCM'):
        if h.startswith(m): return m.decode()
    if h[1:4] in (b'PSC', b'SHT', b'PTC') or h[2:5] == b'SHT': return 'x+' + h[1:5].decode('latin1')
    return 'hex:' + h[:4].hex()

def run():
    res = {}
    for a in ARCS:
        f = open(os.path.join(ROOT, 'iso_extract', a + '.BIN'), 'rb'); idx = wg2.read_index(f)
        rows = []
        for i, (o, s) in enumerate(idx):
            f.seek(o); raw = f.read(s)
            try: d, used = wg2.decompress(raw) if raw else (b'', 0); err = None
            except Exception as e: d, err = b'', repr(e)
            rows.append(dict(i=i, off=o, stored=s, size=len(d), magic=magic(d) if not err else 'ERR', err=err, head=d[:64].hex()))
        res[a] = rows
    return res

if __name__ == '__main__':
    res = run()
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'data', 'archive_inventory.json')
    json.dump(res, open(out, 'w'))
    for a, rows in res.items():
        c = collections.Counter(r['magic'] for r in rows)
        print(a, len(rows), dict(c.most_common()))
