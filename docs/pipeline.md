# Pipeline overview

How to get from a disc to a textured, posed model, and where the dry dock and animation data sit.
Every statement here was checked against the data or against the game's own code in `SLUS_213.87`. Code is in `tools/`; the longer
write-ups are in `notes/`. "Entry" numbers are 0-based positions in an archive. Game-internal ids sometimes run one higher
(see "Numbering" in `notes/formats.md`).

## 1. Disc and archives

Plain ISO9660. Game data is in `*.BIN` / `*.BLN` archives (BEV, CHR, DAT, DSN, EFC, EVT, MAP, MDT_SHIP, MDT_WEPH, MDT_WEPL, PRV).
The executable is loaded at 0x100000 (file offset 0x1000).

Archive header, four little-endian u32: `count, base (0x800), unit, shift`, followed by `count + 1` u32 words.
`word[0]` is the size mask. For entry `j` (1..count): `offset = (word[j] >> shift) * base`, `size = (word[j] & mask) * unit`.
Code: `tools/wg2.py: read_index`. Derived from the game's lookup routine at 0x101118.

## 2. Compression

Every entry is compressed with one small LZ variant (the game's routine is at 0x22E640; code `wg2.decompress`):

| Token | Meaning |
|---|---|
| `00` | end |
| `01-1F` | literal run of n bytes |
| `20-3F` | literal run, 13-bit length |
| `40-4F` / `50-5F` | byte fill, length 4+ |
| `60-7F` | continue the previous back-reference |
| `80-FF` | back-reference, length `c>>5` (4-7), 13-bit distance |

An entry can hold several streams back to back (no padding); `tools/decode_unknown.py: streams()` walks them.
Some archives keep their offset tables outside the compressed data (DSN 38 and 40).

## 3. Textures (SHTX)

Decompressed layout of `SHTXFS`: 6 tag bytes, bytes 10 and 11 hold log2 width and height, a 256-entry palette stored B,G,R,A in plain
linear order (there is no CSM1 bit-swizzle), then width x height 8-bit indices. Variants exist with fewer palette entries
(the design-screen sprites) and `SHTXST` (8-byte header, alpha 0..128). Code: `wg2.decode_shtx`, `export_models.texture`.

## 4. Models (PSC1)

`CHR.BIN`, `MDT_SHIP.BIN`, `MDT_WEPH.BIN` and `MDT_WEPL.BIN` hold `PSC1` models. The `MDT_*` archives are exactly PSC1 + SHTXFS pairs.
The full header and record layouts are in the docstring of `tools/psc1.py` and in `notes/model_audit.md`. In short:

- A model has up to several **part slots** (full-detail mesh, lower levels of detail, and an untextured collision hull in slot 4).
- A part has vertices (10-byte records, s16 xyz, or 16-byte records with s32 xyz when header flag 8 is set), 24-byte face records and
  20-byte UV records.
- A face is a quad `a, b, c, e` (a triangle when `e == c`). Its **UV record is looked up through the face's index at +14**; UV records are
  shared between faces. Reading them in face order scrambles the texture.
- UVs are u16 pairs divided by 16384, with v counted down from the top of the image.
- The model is a **node tree**. Each node owns a run of vertices stored relative to the node. World position = parent transform applied to
  `rotation * vertex * scale + position * POS_SCALE`. Rotations are s16 with 65536 = one turn, applied Rz * Ry * Rx.
- The tree to walk is the one in the child lists (0xff-terminated), not the node record's parent field.
- Frame 0 of each node's animation track is the rest pose. Other frames are animation steps (rotors, turrets) or damage states
  (scale 0 hides a node).

`tools/export_models.py` shows the whole step: parse, bake the rest pose, write vertices, quads and UVs, attach the texture.

## 5. Texture mapping step

A model does not use "the next entry" as its texture. The game has a model resource table (`DAT.BIN` entry 3, array 2; the symptom and the
fix are in `notes/model_audit.md`, the table's place in the item numbering in `notes/formats.md`) that names the texture entry for each model,
and `tools/model_entities.py` reads it. The code is the reference for the record layout. The neighbouring-entry guess is wrong for a number of models.

## 6. Animation

Animation frames are stored per node as (position index, rotation index) pairs. For the large boss models the header also carries a clip
table: pairs of `(u32 offset, u32 count)` at the offset in header word +0x18 (table ends at +0x34), each pointing to 14-byte steps
`u16 frame, u16 duration` (low 15 bits = ticks, bit 15 = last step of the clip). A clip is therefore a stepped pose animation.
A duration of 9999 on the last step means "hold". The tick rate is not known; 60 per second looks right.

**Blending (the tween between steps).** The game's clip controller (0x231688) divides the time spent in the current step by the step's duration
and stores that float; the pose code (around 0x240c80) mixes two values as `a + (b - a) * t`. Some objects have a flag that replaces `t` with a
constant, so they snap between steps. What is *not* confirmed: which two frames are mixed (the viewer blends this step's frame towards the next
step's frame over the step's duration) and how rotation is mixed (the viewer interpolates each Euler angle the short way round).
`tools/export_anim.py` writes the skeleton (`nodes_<id>.bin`) so a viewer can blend per node instead of per vertex, and `web/boss_anim.html`
implements the "Blend steps" toggle. Details and the code addresses: `notes/boss_health_table.md`, section "Blending between clip steps". See `tools/export_anim.py`
and `notes/boss_health_table.md` for how the game picks the clip index.

## 7. Dry dock

The dock is the floating dock in the story. Which of the eight docks is shown depends on story progress (see `notes/drydock_selection.md`).
The docks are map meshes in `MAP.BIN`, and their scenery placements are in a section of the same mesh. Notes: `notes/drydock.md`.
Code: `tools/build_drydock.py`, `tools/build_dock_objects.py`.

## 8. Design screen

The ship designer's pictures live in `DSN.BIN` (part sprites, footprint masks, hull blueprints) and its rules are in the executable.
`notes/archive_formats.md` documents the pictures. `notes/designer_code.md` documents the VP, weight, speed and armour formulas as read from the
game's code. `tools/designer_emu.py` and `tools/mips_emu.py` run the game's own functions to check the decoded formulas.

## Not decoded

Open items are listed at the end of the individual notes. The main ones: the meaning of the hull-mask bits in the design screen, the
`CHR.BIN` entry 0 / 2 formats, PTC and EEF particle and effect fields, the older PSC4/PSB4/PSM6 variants in `PRV.BIN`, and any swing-wing
data for aircraft (none was found).
