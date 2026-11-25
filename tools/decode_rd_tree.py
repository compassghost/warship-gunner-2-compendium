"""Decode the R&D tech tree from DAT.BIN (decompressed entry 31 in this project's numbering; the game calls it id 6032,
because its entry index 0 is the archive's mask word). Output: data/tree_raw.json.

Layout of the master table (all little-endian):
  u16 sizes[34]            chips per group, including the group's root chip (index 0)
  u32 T48[34]   @0x48      offset of the group's array of 64-byte chip records (one per chip)
  u32 T114[34]  @0x114     offset of the group's row table: (size-1) x 32 bytes = rows of up to 16 chip indices (-1 terminated), in drawing order
  u32 T19c[34]  @0x19c     offset of the group's array of 128-byte ancestor lists: every chip that must be developed before this one (transitive), -1 terminated
64-byte chip record (i16 fields): [3]=index in group, [4]=type (1 diameter/level, 2 normal, 3 branch, +0x100 flag = hidden until unlocked, observed),
  [5]=turns, [6]=cost low 16 bits, [7]=cost high 16 bits (cost = [6] | [7]<<16), [22]=x column, [23]=y row (999 = not placed), [24..31]=neighbour chips (first is the parent), -1 terminated.
Global chip number = sum(sizes of earlier groups) + index in group (the game's own helper at 0x213F78)."""
import struct, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import wg2

GROUPS = ['MAIN', 'AMMO', 'HI ANGLE', 'MACHINE', 'RAPID', 'PROTO', 'TORPEDO', 'EXPLOSIVE', 'MISSILE', 'ROCKET', 'FLARE', 'ORGANIC', 'OPTICAL',
          'PLASMA', 'MAGNETIC', 'PULSE', 'A-MATTER', 'HULLS', 'BRIDGE', 'AFT', 'FACILITY', 'POWER', 'ROTATION', 'PURGE', 'ATTACK', 'DEFENSE',
          'STEERING', 'ENIGMA', 'FIGHTER', 'INTERCEPT', 'BOMBER', 'SCOUT', 'HELI', 'SPECIAL']
ROOT = os.path.join(os.path.dirname(__file__), '..')

def load():
    f = open(os.path.join(ROOT, 'iso_extract/DAT.BIN'), 'rb'); idx = wg2.read_index(f)
    o, s = idx[31]; f.seek(o)
    return wg2.decompress(f.read(s))[0]

def main():
    b = load()
    w = lambda o: struct.unpack_from('<I', b, o)[0]
    sizes = struct.unpack_from('<34H', b, 0)
    T48 = [w(0x48 + 4 * i) for i in range(34)]; T114 = [w(0x114 + 4 * i) for i in range(34)]; T19c = [w(0x19c + 4 * i) for i in range(34)]
    chips = []; base = 0
    for g, n in enumerate(sizes):
        rows = []
        for r in range(n - 1):
            x = struct.unpack_from('<16h', b, T114[g] + 32 * r)
            rows.append([v for v in x if v >= 0])
        for i in range(n):
            rec = struct.unpack_from('<32h', b, T48[g] + 64 * i)
            anc = [v for v in struct.unpack_from('<64h', b, T19c[g] + 128 * i) if v >= 0]
            nb = []
            for v in rec[24:32]:
                if v < 0: break
                nb.append(v)
            placed = rec[22] != 999 and rec[23] != 999
            chips.append(dict(chip=base + i, group=g, group_name=GROUPS[g], index=i, type=rec[4] & 0xff, hidden=bool(rec[4] & 0x100),
                              turns=rec[5], cost=(rec[6] & 0xffff) | ((rec[7] & 0xffff) << 16), x=rec[22] if placed else None, y=rec[23] if placed else None,
                              neighbours=nb, parent=nb[0] if (nb and i > 0) else None, ancestors=anc,
                              raw_name_fields=[rec[8], rec[10], rec[12], rec[14]], cond_raw=list(rec[16:22]), item_id=rec[3]))
        base += n
    out = dict(groups=[dict(index=g, name=GROUPS[g], size=sizes[g]) for g in range(34)], chips=chips, total=base)
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, 'data/tree_raw.json'), 'w'), indent=0)
    print('groups', len(sizes), 'chips', base)
    print('sizes:', dict(zip(GROUPS, sizes)))

main()


