"""Parser for the BEV mission scripts (BEV.BIN entries 206-281, one per mission; 204 = shared event script, 203 = another format).
Layout (decoded from the loader at 0x1386e0 and checked: every one of these entries parses exactly to its end):
  u32 nblocks
  block: u16 A (block type), u16 B (record count), u16 unused, u16 C, then 2*C u16 (C ids, C values), pad to 4,
         B flag bytes, pad to 4, then B records
  record: u8 kind, u8 sub, 10 parameter bytes (5 u16), then a NUL-terminated string padded to 4 bytes (empty = 4 zero bytes).
Record kinds seen (kind/sub -> meaning, from the parameters and the text around them):
  01 mission code ('FAR_C_010'), 02 Shift-JIS title, 03/04 two counts, 09/0a/0b/0c message strings, 0d dialogue line ('#gNNNN' = speaker/face)
  0e/00 u16 = 15000 + EVT entry: show that event picture; 0e/01 wait, 0e/02 fade
  1c/05 u16 = frames: fade out the music;  1c/0d u16 = **track number: start that music (DBGM_B%02d / DBG2_B%02d)**
Use:  python tools/bev_script.py     prints every music event."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(__file__))
import wg2
ROOT = os.path.join(os.path.dirname(__file__), '..')
_f = open(os.path.join(ROOT, 'iso_extract', 'BEV.BIN'), 'rb'); _idx = wg2.read_index(_f)
def get(e): o, s = _idx[e]; _f.seek(o); return wg2.decompress(_f.read(s))[0]
def _a4(p): return (p + 3) & ~3
def parse(d):
    n = struct.unpack_from('<I', d, 0)[0]; p = 4; blocks = []
    for _ in range(n):
        A, B, _sk, C = struct.unpack_from('<4H', d, p); p += 8
        extra = struct.unpack_from('<%dH' % (2 * C), d, p) if C else (); p += 4 * C; p = _a4(p)
        flags = list(d[p:p + B]); p += B; p = _a4(p); recs = []      # flags: one byte per record = route mask (bit 1 Tsukuba, bit 2 Braun, bit 4 Werner; 7 = every route)
        for _ in range(B):
            kind, sub = d[p], d[p + 1]; par = struct.unpack_from('<5H', d, p + 2); q = p + 12
            z = d.index(b'\0', q); recs.append(dict(kind=kind, sub=sub, par=par, text=d[q:z])); p = _a4(z + 1)
        blocks.append(dict(A=A, B=B, extra=extra, recs=recs, flags=flags))
    return blocks, p
def mission(e):
    d = get(e); blocks, end = parse(d); assert abs(len(d) - end) <= 8, (e, len(d), end)
    h = blocks[0]['recs']
    return dict(entry=e, code=h[0]['text'].decode(), title_ja=h[1]['text'].decode('shift_jis', 'replace'), blocks=blocks)
def music_events(m):
    """[(block index, block type, record index, track, fade frames before it or None, [EVT entries shown just before], [dialogue lines after])]"""
    out = []
    for bi, b in enumerate(m['blocks']):
        rs = b['recs']
        for ri, r in enumerate(rs):
            if r['kind'] == 0x1c and r['sub'] == 0x0d:
                fade = next((x['par'][0] for x in rs[max(0, ri - 2):ri] if x['kind'] == 0x1c and x['sub'] == 5), None)
                evt = [x['par'][0] - 15000 for x in rs[max(0, ri - 12):ri + 4] if x['kind'] == 0x0e and x['sub'] == 0]
                after = [x['text'].decode('latin1') for x in rs[ri + 1:ri + 14] if x['kind'] == 0x0d and len(x['text']) > 8][:2]
                out.append(dict(block=bi, block_type=b['A'], rec=ri, track=r['par'][0], fade=fade, evt=evt, after=after))
    return out
if __name__ == '__main__':
    for e in range(206, 282):
        m = mission(e)
        for ev in music_events(m): print(m['code'], ev)
