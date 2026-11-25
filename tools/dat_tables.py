"""DAT.BIN helpers. Most decompressed DAT entries share one layout (found by inspection, see notes/formats.md):
  u32 n, u32 total, u32 start, then n pairs (u32 offset, u32 count), data from `start`.
Each pair describes one array: `count` records starting at `offset`; record size = (next offset - offset) / count.
String tables are the special case where every pair has count 1 and the record is one NUL-terminated string."""
import struct

def is_generic(b):
    if len(b) < 12: return False
    n, total, start = struct.unpack_from('<3I', b, 0)
    return n > 0 and start == 12 + 8 * n and total <= len(b) + 8

def arrays(b):
    n, total, start = struct.unpack_from('<3I', b, 0)
    pairs = [struct.unpack_from('<2I', b, 12 + 8 * k) for k in range(n)]
    out = []
    for k, (o, c) in enumerate(pairs):
        end = pairs[k + 1][0] if k + 1 < n else total + 4
        per = (end - o) // c if c else None
        out.append({'index': k, 'offset': o, 'count': c, 'record_size': per, 'end': end})
    return out

def strings(b, encoding='cp932'):
    """For string-table entries (all counts == 1)."""
    n, _, _ = struct.unpack_from('<3I', b, 0)
    res = []
    for k in range(n):
        o, _ = struct.unpack_from('<2I', b, 12 + 8 * k)
        res.append(b[o:b.index(b'\0', o)].decode(encoding, 'replace'))
    return res
