# Design screen: what the executable does (SLUS_213.87), pass 1 (2026-11-17)

Tools: `tools/designer_emu.py` (runs the game's own functions in `tools/mips_emu.py` with the real DAT tables), `tools/designer_vp.py` (VP% port), `tools/designer_stats.py`
(weight / speed port with a self-check against the executable), `tools/fnlist.py`, `fnscan.py`, `fnstore.py` (function list, struct-offset scan, lui+imm xref finder), `tools/mdis.py`.
Everything marked CONFIRMED was checked on all 530 blueprint designs of DAT entry 26 (`python tools/designer_stats.py`, `python tools/designer_vp.py`).

## 1. File ids -> archive entries (why DSN 37 looked wrong before)
File id n: archive = byte table at 0x2a6b90[n / 1000], base = halfword table at 0x28b638 (0x290000 - 0x49c8); entry = n - base - 1 (index as `wg2.read_index` numbers them).
Archive of ids 11000+ is DSN.BIN. The design-screen loader 0x198d40 reads these RAW (flag 0 in 0x1fbb08 = no LZ decompress), not decompressed:
| id | entry | struct field | content |
|---|---|---|---|
| 0x2b1d | DSN 36 | +0xc | concatenated game-LZ streams, one SHTXFS image per shape index (see 3) |
| 0x2b1e | DSN 37 | +4 | **the shape table: 907 records x 0x88 bytes (123,352 bytes), RAW**. The earlier "4,116 bytes, all ones" was the wrong thing: that is the LZ-decompressed first bytes of an uncompressed entry |
| 0x2b1f | DSN 38 | +0x14 | 908 u32 offsets into DSN 36 (the last is 0) |
| 0x2b20 | DSN 39 | +8 | 146 LZ streams (~16 KB each, sprites of another set), offsets in DSN 40 (+0x10) |
DAT tables are loaded at 0x103f10: gp-0x7df0 part table (DAT 7), gp-0x7dec hull table (DAT 8, 0x28-byte rows, 145), gp-0x7de8 = DAT 8 + 0x16a8 (armor plating rows, 12 bytes),
gp-0x7de4 DAT 9 (0x44-byte rows = the SYSTEM records), gp-0x7de0 DAT 10 (257 u16 speed curve). (DAT file id n+6001 -> entry n.)

## 2. Shape records (DSN 37) — CONFIRMED structure
0x88 bytes: [0] width, [1] height (cells), [4] box x0, [5] box y0, [6] box w, [7] box h, [8..0x87] 32 u32 row bitmaps (MSB = column 0), [2..3] = 0.
`0x1a5bc0(dst, src, rotation 0..3 (0, 90, 180, 270 clockwise), flags (1 = flip y, 2 = flip x))` rotates / flips the record (box fields, bitmap) ; `0x1a5b70(b13, b14) -> (rotation, flag)`:
b13 != 0 -> (2, 0); b14 = 1 -> (0, flip y); 2 -> (3, 0); 3 -> (1, 0); else (0, 0).
Part record (DAT 7, 144 B) **u16[7..10] = PICTURE shape** by barrels-1; **u16[13..16] = MAGAZINE / vital-box shape** chosen by the mount's b12 byte (magazine depth variant 0..3).
Mount (DAT 26 design, 16 B at 0x20 + 16 i): u32 part id, u16 x, u16 level (z), u16 y, u8 b8 (slot category: 10 boiler, 11 turbine, ... see 0x1a6228), u8 barrels-1, u8 b12 (magazine variant),
u8 b13 (1 = faces aft), u8 b14 (side: 1 flip, 2 / 3 rotated), u8 b15. In the work struct the same 0x12-byte entries are at +0x47bd4 (x, level, y, part TABLE index, ... byte 0xe = deleted).
Example sizes: boiler 20100 / 20200 magazine shape 399 = 4 x 6, 20300 -> 401 = 6 x 6, turbine 21100 -> 402, 21000 -> 400 = 6 x 4, bridge 10200 -> 116 = 10 x 21 (box row 20, 9 x 1), gun 61cm -> 3 / 4 / 5 (21 x 10 / 12 / 14, box 9 x 7).
This reproduces the engine box sizes the designer had inferred from game designs (4 x 6, 6 x 6, 6 x 4 ...). The box heights/levels for the side view are the shape [1]/[7] fields (not yet verified against `level`).

## 3. Part pictures (CONFIRMED)
Picture for shape index i: LZ stream at DSN36 + offs[i] (`wg2.decompress`), result = SHTXFS image: u16 w, h at byte 6, 12-byte header, palette of (len - 12 - w*h) / 4 RGBA entries, then w*h 8-bit indices.
w = 4 x shape width px, h = 4 x shape height (+ up to 4). 1-bit line art; the 0 palette entry is the line colour, the dotted rectangle is the magazine box. (Another session extracted them to data/dsn36_sprites/.)
The builder draws sprites (blit of these textures), the 136-byte bitmaps are the collision / extent masks.

## 4. VP% — CONFIRMED 530 / 530 (tools/designer_vp.py)
0x19b650 loops the mounts (skipping deleted), keeps those that pass 0x286700 ("has a vital box"):
part byte4 (= u16[2] low byte) 1 (weapons): u16[68] bit 0 SET (main guns, torpedoes, missiles, rockets: yes; hi-angle, CIWS / machine guns: no); byte4 2: part kind (u8[6]) in {12, 13, 19, 27} (bridges, funnels, kind 19);
byte4 3 (engine parts): always; others no. Per vital mount:
- pass 1: magazine shape u16[13 + b12], rotation 0, flip x if b13: lo = x + box_x0, hi = lo + (box_w or width) - 1
- pass 2: picture shape rotated by (b13, b14): lo2 = x + box_x0', hi2 = lo + (box_w' or width')  (uses pass-1 lo)
min lo / max hi over all, **VP% = trunc((hi - lo + 1) * 100.0 / hull_length)**, hull_length = hull record byte 0xb (cells; 144 for Jpn BB I, hull 200). It is stored in the design at +0x678.
So bridges and funnels (kind 12 / 13 / 27) count, hi-angle guns and AA do not, consistent with the user's "vital length" rule.

## 5. Weight — CONFIRMED 530 / 530
weight = hull u16[8] + sum(part u16[17 + barrels - 1]) + sum(system record u16[0x3c]) + armor (+ 200 if design byte 0x67a != 0).
armor = plating[idx] * 2 * VP / 100 (integer), x 80 / 100 (integer) when VP < 54 (core; full from 54), idx = design byte 0x1e; plating row = DAT 8 + 0x16a8 + 12 idx, u32[2].
Armor index -> size: 0 none, 1 10cm, 2 12, 3 14, 4 15, 5 20, 6 25, 7 31, 8 36, 9 38, 10 41, 11 43, 12 46, 13 51, 14 56, 15 61, 16 80 cm; plating weights 80 .. 102000 t (= shipguide table). The row also holds
side armor (u32[0] low half) and deck armor (high half) and keel (u32[1]) exactly as in the guide table.
WEIGHT LIMIT = hull u32 at byte 0xc = u16[6] | u16[7] << 16 (40000 for hull 4200 Gigantic Battlecarrier, matches the screenshot; the Supercarrier, hull 4300, is the only hull with u16[7] = 1: 4464 + 65536 = 70000 t, found 2026-11-17 when the web page showed 4464; the exit check 0x1a0f28 reads the whole word). Hull weight = u16[8].
PARTS MAX = 100 constant: the add-mount code (0x19fec4, 0x19edf8, 0x1a4e48) refuses when mount count would exceed 100 (`slti ..., 0x65`).

## 6. Speed — CONFIRMED 530 / 530
Mounts are grouped by slot category b8 (0x1a6228): category 10 = boilers, 11 = turbines (first group = first (part, barrels) combination met; counts per group).
HP = boiler.u16[32] x n_boilers x eff / 100 with eff = turbine.u16[33] x n_turbines (if the boiler record kind u8[6] is 0x17, eff = boiler.u16[33] alone).
t = trunc(10 x HP / weight); t = t x 12 / 10 first when the boiler kind is 0x15 (propulsion); t clamped to 1..256.
**knots = t x (100 - curve[t] / 100) / 100**, curve = DAT 10 (257 u16: 0 up to t = 25, 100, 180, 250, 340, 500, ... 7475 at t = 256).  Cap: 256 x (1 - 0.7475) = **64.64 kt** (the guide's 64.6).
Then systems: speed += speed x (sum of system record u16[0x16]) / 100. (0x19c1f0 also folds other system fields into the ship stats; not decoded.)
Float constants are at 0x2b1888..: 320, 164, 10, 100 (VP), 10 and 100 (speed), 100 (system %), 4, 5, 1.

## 7. System slot records (DAT 9, 0x44 bytes) — partly decoded
Sum routine 0x1f53b0 adds: [0xc..0x15] 5 u16, [0x16..0x2f] 13 u16, [0x32..0x37] 6 bytes, ORs [8] / [0x38] / [0x3a] / [0x3b], adds [0x3c] (weight).
Design +0x664 holds 10 system ids (halfwords, -1 = empty).

## 9. Pass 2 (2026-11-17, request from the boss-indicator session): hull pictures, placement on screen, collision, mask, mirroring
Self-checks: `python tools/designer_voxels.py` (0 hull-mask failures over all 17,212 mounts of the 530 game designs, 0 voxel overlaps). Table: `data/designer_hull_pictures.json`.

### 9.1 Hull picture for a hull — CONFIRMED (code 0x199b50 + the hull-mask check below)
The loader 0x199b50 takes the hull table row and reads **hull record byte 0xa (= u16[5] & 0xff)** as the stream number: `DSN 39 offset = u32[DSN 40 + 4 * byte]`, LZ-decodes it into the 160 x 85 zone grid (copies 0x3520 bytes) and then
the nested 640 x 340 picture. So **picture index = (hull u16[5]) & 255** (not the DAT 8 row). It is a bijection onto 0..144. Examples: ids 0-4 -> 0-4, 100-109 -> 5-14, 200-207 -> 15-22, 300-304 -> 23-27, 400-402 -> 28-30,
1000-1003 -> 31-34 ..., 500 / 501 -> 126 / 127, 600 / 601 -> 134 / 135, 700 -> 125. The high byte of u16[5] is the hull length in cells (byte 0xb). The ship is centred in the 160-column grid (columns (160 - L) / 2 ...).
Check: the picture's non-zero column span equals the length byte for 107 / 145 hulls and is within 1-4 cells for most others (submarines / special hulls differ more: the length byte is a nominal value).
Proof that the mapping is right: with it, every one of the 17,212 mounts of the 530 game designs passes the game's own hull-mask test (9.4), which would be impossible with a wrong picture.
Full table in data/designer_hull_pictures.json (hull id -> picture, length, max weight, hull weight).

### 9.2 Screen placement — CONFIRMED (0x19a980 draws a mount, 0x19d800 picks one)
The design grid IS the hull picture grid: the 640 x 340 picture / 160 x 85 zone grid, 4 px per cell, is drawn with its top-left at screen (0, 27) (screen 640 x 448).
- side view: sprite top-left x = 4 * x, y = 27 + 4 * level  (grid row = level; rows 0..32 = side area)
- plan view: sprite top-left x = 4 * x, y = 27 + 4 * (33 + y) = 159 + 4 * y  (grid row = 33 + y; rows 33..84 = plan area, y 0..51; centre line y = 26)
- sprite (0x19a470 -> 0x1fc4d0): width = 4 * shape width, height = 4 * shape height of the transformed shape; side sprite = picture of shape A = part u16[13 + b12], plan sprite = picture of shape B = part u16[7 + barrels - 1];
  rotation / flip come from 0x1a5b70(b13, b14) (side picture: flip x only when b13; plan picture: full facing). So the anchor is the top-left of the transformed sprite, which is also the shape origin (0, 0).
- cursor / crosshair: 0x1a0318 puts the mount so that the cursor sits at the CENTRE of the shape's box: x = cursor_x - (box_x0 + box_w / 2), level = cursor_row - (box_y0 + box_h / 2) (side), same for y with shape B (0x1a0408 / 0x1a0518).
- picking (0x19d800): cursor (float) * constant at 0x2b18d0 -> cell (col, row); row <= 32 = side view, row >= 33 = plan view (y = row - 33); looks the cell up in the 3D volume below (side view: first mount along y, plan view:
  first mount along level), so the sprite you click is the mount owning that voxel.
- draw order (0x19a650 / 0x19a980): first the mounts whose state byte (work struct +0x10) != 1, parts of class 0xa / 0xb (boilers / turbines, part byte 5) in separate passes, then the state-1 (selected) mounts last.
  Each mount draws the side sprite (at 4 x, 27 + 4 level) and the plan sprite (at 4 x, 159 + 4 y), tinted by a packed colour (state 0..4): normal parts 0x703c3c3c (0x7070706d in the other view mode 199b38 == 0),
  state 1 = 0x7083d60c, state 2 = 0x80406605, state 3 = 0x80640b0b (probably red = invalid), state 4 from a palette table at *(0x2b - 0x19d0) + 0x194; boilers state 0 = 0x805a440b, turbines state 0 =
  palette *(0x2b - 0x19d0) + 0xc8, state 4 palette + 0x194. NOT decoded: byte order of the packed words (A = top byte 0x70 / 0x80 is certain), which words are the user's orange / cyan, what states 1..4 are.

### 9.3 Occupancy / collision — CONFIRMED (0x19d098 stamps, 0x19cdc0 tests)
The game keeps a 3D voxel volume (x 160 x level 33 x y 48; index y * 5280 + level * 160 + x, at work struct + 0x3e15). A mount covers voxel (x + col, level + a_row, y + b_row) for every column col where shape A (side silhouette,
rows = level) has bit (a_row, col) AND shape B (plan silhouette, rows = y) has bit (b_row, col). Both shapes are the 0x88 bitmaps (bit 31 - col = column) after the 0x1a5bc0 transform. Stamped value = mount number + 1.
Adding a mount fails (error 8) if any of its voxels already holds a positive value (a negative value is a soft blocker, error 8 unless the caller allows it). CHECK: stamping all mounts of all 530 game designs gives **0 overlaps**,
while bounding boxes of the same shapes overlap 74,620 times, so this is the real rule (and the earlier "boxes collide only on the same level" observation is this: the level rows are part of the voxel test).

### 9.4 Placement limits (0x19d008 returns the first failing error; codes decoded from the code)
1. 0x19c7e8 error 1: hull class (hull byte 5 -> mask via 0x1a6000) AND part byte 0xa == 0 = the part does not fit this hull class. Parts with u16[6] & 2: must sit at y + shape height == 26 (-> returns 2). Bridge (kind 12) / aft bridge (kind 13)
   must be forward / aft of the category 0x15 / 0x14 mounts (returns 3 / 4).
2. 0x19c968 errors 5 / 6: **hull zone mask**. Part byte 0xb (= u16[5] >> 8) is a zone bit mask; the hull grid byte (zone flags) of every cell of the shape BOX must AND to non-zero. Side: cells of shape A inside its box at grid
   row = level + row, column x + col (skipped when part u16[6] & 0x80); plan: cells of shape B inside its box at row 33 + y + row. CHECKED 0 failures on 17,212 game mounts (tools/designer_voxels.py mask_ok).
   The zone byte bits are used only as a mask: the part's allowed bits come from the part record; the NAMES of the bits (bow, ..., hull section) stay unnamed.
3. 0x19cc08 error 7 (part u16[6] & 0x40): the cells of shape A OUTSIDE its box (turret / superstructure above the deck) must lie on grid cells that are 0 (nothing of the hull there).
4. 0x19cdc0 error 8: voxel collision (9.3).
Mirroring: y' = 52 - y - h (h = height of the transformed plan shape B), i.e. mirror about the centre line y = 26; the partner uses the flipped side bytes (b14 1 / 0, b15 2 / 1, see designer.md). Measured on the 530 designs: 11,572 mounts have a
mirror partner, 4,034 sit exactly on the centre line (2 y + h = 52), 1,606 are single off-centre (mostly carrier side AA 1118 / 1114 / 1117, 1419-1438 missiles, 19203, hi-angle 1028-1035). The UI code that creates the partner was not located yet.
Not mirrored in the data: bridges, funnels, engines on the centre line; side-mounted AA on carriers (single).

### 9.5 Still open after pass 2 (colours, VP bar and mirror creation are answered in section 10)
- Names of the zone bits; error codes 3 / 4 conditions only skimmed; the exact RGB of the two palette entries; the HUD text positions other than the VP bar; the 0x1a07c8 snap.

## 10. Pass 3 (2026-11-17): VP bar, colours, mount states, mirror creation, HUD
### 10.1 VP bar — CONFIRMED (0x19b2a0)
Drawn when VP > 0 with 0x1fbfb0 (filled rectangle): lo / hi = the span stored at work struct +0x3e10 / +0x3e12 (the min / max x from the VP loop, section 4), x px = 4 * lo .. 4 * hi, **y = 400 px** (UI rect record 28 of DSN 10,
u16 at +8; the hull picture ends at y = 367), **height 3**, colour **0x80cb5f5f** (packed A R G B = 0x80, 0xcb, 0x5f, 0x5f: salmon red, matches the tutorial picture DSN 198). End ticks: 3 px wide, 6 px tall at (4 lo, 394) and (4 hi - 3, 394).
Label above it at y = 400 - 20 = 380, centred on (4 lo + 4 hi) / 2, text from the format string at text-block offset 0x9bc (VP < 54, core) or 0x9c4 (VP >= 54, full) with the VP value; the tutorial picture shows "VP:36%".
The HUD plate (DSN 197 tutorial picture): "HULL WEIGHT 1424 / 2300t", "ARMOR RATING ANTI-10cm Full" (Full in orange) / "ANTI-10cm Core" (Core in green). So the armor rating label = "ANTI-" + size (section 5 table) + Full / Core (VP >= 54).
### 10.2 Colours and mount states — CONFIRMED structure, colours decoded
Packed colour words are **A R G B** (0x80cb5f5f is the red bar). Tint colours of the sprites (0x19a980), by mount state byte (work struct +0x10), set by 0x19c328 (run after every change):
state 1 = the mount under the cursor (and its mirror partner), 4 = the mount being carried (mem +0xf != 0), 3 = invalid (mem +0xe error code != 0), 0 = valid, 2 = not set by 0x19c328.
- ordinary parts: state 0 0x703c3c3c (grey, 0x7070706d when the view flag 199b38 == 0), 1 0x7083d60c (yellow-green: the "yellow when selected"), 2 0x80406605, 3 0x80640b0b (dark red), 4 palette entry (*(0x2b - 0x19d0) + 0x194)
- boilers (part byte 5 == 0xa): state 0 0x805a440b (orange); turbines (0xb): state 0 palette *(0x2b - 0x19d0) + 0xc8 (the cyan), 1..4 as above with the same palette for state 4.
Draw order (0x19a650): everything whose state != 1 first (boilers / turbines in their own passes, after the others), selected mounts last; each mount draws side then plan sprite (section 9.2).
NOT decoded: the actual RGB of the two palette entries (they come from a table in a loaded file).
### 10.3 Pair role and mirror creation — CONFIRMED (0x19e808 place, 0x1a22e0 partner)
b15 (mem +0xd) is the pair role: 0 single, 1 = master, 2 = partner; **pairs are adjacent entries** (master first, partner right after, mem +0x12). The error code of the master is copied to its partner (0x19c328).
When a part is dropped (0x19e808): if part u16[6] & 4 (mirror-able) a partner is created: same part, x, level, barrels, b12, b13; b14 = (master b14 == 0) when u16[6] & 0x100 (the part has a flip variant), b15 = 2, master b15 = 1.
0x1a22e0 computes the partner y: centre_y = y + box centre offset (0x1a0518: box_y0 + box_h / 2, floor); if centre_y == 26 (the centre line) NO partner is made (part stays single, b15 0); otherwise the partner box centre is 52 - centre_y,
partner y = 52 - centre_y - offset of the flipped shape; with u16[6] & 0x80 the result is snapped by 0x1a07c8. Master b14 on drop = (cursor row < 26) when u16[6] & 0x100. Parts of kind 2 / 3 with u16[6] & 4 get b14 = 2 (cursor x < 80) or 3 (x >= 80): turned fore / aft.
CHECK on the 530 designs: 3,448 master / partner pairs (b15 1 then 2, same part, x, level): centres sum to 52 in 3,270 (95 %), 51 in 175, 53 in 3 (rounding of odd box sizes; the exact snap is in 0x1a07c8, not decoded).
Part u16[6] flag bits: 0x2 fixed-row part (y + height == 26), 0x4 mirror-able, 0x40 hull-overhang check (error 7), 0x80 skip side mask / snap, 0x100 flip variant.

## 11. Pass 4 (2026-11-17): error codes and messages, hull class table, cursor, systems, texts
New tools: `tools/designer_place.py` runs the game's own validator 0x19d008 (errors 1-8) in the emulator for every mount of every stock design, in the order the screen re-validates them (0x19c328: clear voxels, test, stamp when valid):
**result: all 17,212 stock mounts return error 0** (so the rules below, and the stock data, agree with the real code). `data/designer_text_dat15.txt` = the whole design-screen text table (DAT entry 15, index<TAB>string, with its markup codes).
### 11.1 Error codes and their on-screen messages — CONFIRMED (message table at 0x2a8770: ids 827..834 = errors 1..8, shown by 0x1a2480 when a carried part is dropped; the smallest error code of the carried mounts wins; a beep follows)
| err | condition (0x19d008 -> 0x19c7e8, 0x19c968, 0x19cc08, 0x19cdc0) | message (DAT 15 index) |
|---|---|---|
| 1 | (part byte 0xa = `u16[5] & 255`) AND (hull class mask) == 0 | "Part is not matching hull type." (827) |
| 2 | part `u16[6] & 2` and (y + h == 26 or y == 26), h = RAW height (byte 1) of the plan picture shape `u16[7 + barrels - 1]`, y = plan y | "Not enough width for side-by-side deployment." (828) |
| 3 | forward bridge (part kind 12): the mount of category b8 = 0x15 (aft bridge, first one) has x greater than this x (valid mount only) | "FWD bridge is placed after AFT bridge." (829) |
| 4 | aft bridge (kind 13): the mount of category 0x14 (fwd bridge) has x smaller than this x | "AFT bridge is placed before FWD bridge." (830) |
| 5 | side-view hull mask (section 9.4) | "Part is deployed outside allowed area." (831) |
| 6 | plan-view hull mask | "Part is deployed outside allowed area." (832) |
| 7 | overhang check (part `u16[6] & 0x40`) | "Part's position is in conflict with hull silhouette." (833) |
| 8 | voxel collision (section 9.3) | "Part is overlapping with other part." (834) |
Codes 9, 10 have no message (0); 11 / 12 map to "Back" / "OK" (530 / 531). Others in the text table: 319 "Same part cannot be placed at same location." (0x19ff78, adding an identical part at the same spot), 320 "Limit of parts on board exceeded." (0x19fee4,
count would exceed 100), 314 / 316 "Part not in stock.", 625 "Not enough stock.", 353 "No appropriate hull in stock.", 418 / 419 "No parts available.", 1056 "Not enough system slots".
Error 2 correction: the check is "NOT (y + h == 26 or y == 26)" for flagged parts (370 part records have bit 2: 217 main guns, 153 hi-angle / AA mounts). Ported as "must equal 26" it fails the 4,214 stock flagged mounts; as a prohibition it fails none (0 of 4,214).
(Meaning: such a part may not have a long edge on the centre line, because its mirror partner would not fit side by side.) Error 3 / 4 together force fwd.x >= aft.x (bow at larger x).
### 11.2 Hull class table (0x1a6000) — CONFIRMED
hull record byte 5 (`u16[2] >> 8`): 13 -> mask 0x01, 14 -> 0x02, 15 -> 0x04, 16 -> 0x08, 17 -> 0x10, 18 -> 0x40, 19 -> 0x20 (hull record u16[2] = 0x0d04 for the first hull: byte 5 = 13). A part fits when `(part.u16[5] & 255) & mask != 0`
(data: part byte 0xa is a bit set over the hull classes). The parts menu should list only parts that fit (the game itself only reports error 1 when a part is placed). Class names: 13 DD, 14 CA, 15 BB (from 0x1aa500: DD / CA / BB / ... 0x13 -> 3, 0x10 -> 4, 0x11 -> 5, 0x12 -> 6).
### 11.3 Exit / save validation (0x1b4708) — CONFIRMED order
1. no valid forward bridge (0x1a0e88: a mount with b8 == 0x14 and error 0 must exist) -> "FWD bridge is not correctly placed." (760); 2. speed float (stats +0x10) <= 0 (0x1a0e60) -> "Engine parts are not correctly placed." (761);
3. stats u16 +0x1e (boiler count) minus +0x20 (funnel capacity, sum of u16[34] of category 0xc parts capped 99) > 0 (0x1a0f08) -> "Smokestack(s) is/are not correctly placed." (762); 4. weight (stats u32 +0) > hull max (u32 at hull +0xc) -> "Maximum load has been exceeded. Remove parts or reduce armor." (763);
then 764 "AEGIS system is not installed. Continue?". The STATS screen also warns "UNVENTED BOILERS" (825) and "NO BRIDGE" (826).
### 11.4 Cursor — CONFIRMED (0x19d550 mover, 0x1a25c8 speed toggle)
Cursor position is two floats in px (x at work struct +0xbbc, y at +0xbc0), clamped x 4..636, y 0..324 (px; cell = px * 0.25, a row <= 32 (y px < 132) is the side view, rows 33.. the plan view, plan y = row - 33).
D-pad (bits 0x8000 left, 0x2000 right, 0x1000 up, 0x4000 down): one cell (4 px) per pad event. Analog stick: dead zone 5.0, 16 directions (pi / 8 steps), speed set by the CURSOR mode byte (+0xbbb) cycled by pad bit 0 in order 0 SLOW -> 1 NORMAL -> 2 FAST -> 0
(texts 819 "CURSOR", 820 "SLOW", 821 "NORMAL", 822 "FAST"): per-axis speed constants 1.0 / 1.0 (SLOW), 2.0 / 3.0 (NORMAL), 4.0 / 4.0 (FAST) px, scaled by a frame factor (u float at +0xb0 of the pad block) and 1/32.
Level and y of a carried part: cursor in the side area sets the level (row, remembered at +0xbdc); cursor in the plan area sets y (row - 33, +0xbe0); the other coordinate keeps its last value (so a part is placed at last side row / last plan row). The part is positioned so that the
cursor is on the CENTRE of the shape box (0x1a0518: x = cursor - (box_x0 + box_w / 2) etc.).
Pad buttons in 0x19dc88: 0x40 pick up / drop (square / cross), 0x100 cancel, 0x30 hand clear, 0x80 delete?, 0x8 / 0x4 mode toggles (view toggle `0xbba`); exact button names not verified.
### 11.5 Picking and partners — partly CONFIRMED
Picking = voxel look-up (9.2). Picking a master (b15 == 1) marks BOTH mounts carried (+0xf = 1 on it and on the next entry, 0x19de38 / 0x19de48); picking the partner (b15 == 2) carries the pair as well. On drop (0x19e808) the pair is rebuilt: master + partner via 0x1a22e0
(section 10.3), so moving the master moves the partner (its y is recomputed, it is not stored independently); a carried pair that is dropped on a centre-line spot becomes a single (no partner when the box centre is y 26); dropping the hand clears both.
CONFIRMED BY THE USER (2026-11-17, from play): carrying a mirrored part moves both halves, deleting deletes both halves, and a mirrored pair counts as TWO parts for the 100-part limit (matches the code: the limit tests the mount count 0x2dc, and each half is a mount).
### 11.6 Systems and the stats the HUD shows — CONFIRMED structure
DAT 9 record (0x44 bytes, u16 id first) fields summed by 0x1f53b0 into the design stats, with the label order of the text table (DAT 15 155-174, "STATS" rows 59-95): [0xc] ENDURANCE, [0xe] RADAR, [0x10] SONAR, [0x12] STEERING, [0x14] COMMAND (5 u16), then 13 u16 at [0x16..]
percent effects in label order: [0x16] SPEED INCREASE % (CONFIRMED: speed *= 1 + x / 100), [0x18] COMMAND % (CONFIRMED: command += command / 100 * x), [0x1a] AIM CORRECTION %, [0x1c] LOADING EFFICIENCY %, then FIRE PROOF, LEAK PROOF, BEAM DEFENSE, SHELL DEFENSE, JAMMING RATE,
FIRE PROOF RATE, LEAK PROOF RATE, LOCK-ON JAMMING, ANTI JAMMING / RANGE INCREASE / FORWARD THRUST (the order of the last ones is a GUESS from the label order). [0x3c] = weight (CONFIRMED, tools/designer_stats.py weight 530 / 530). 0x19c1f0 applies:
ENDURANCE = max(100, hull endurance + [0xc]); steering byte = hull steering + [0x12]; command = bridge command + [0x14] (+ [0x18] %); radar / sonar = bridge values + [0xe] / [0x10].
STATS screen (SELECT) rows from the text table: HULL TYPE, HULL WEIGHT, ENDURANCE (~iHp), ARMOR (side ~iDl / deck ~iDk plating = the armor row u32[0] low / high half), VP RATIO, PW SOURCE, OUTPUT (HP), PROPULSION, EFFICIENCY, SPEED, FIXTURE (STANDALONE / COMBINED),
FWD BRIDGE, AFT BRIDGE, SEARCHLIGHT, COMMAND, RADAR, SONAR, WPN 1-7, SYS 1-10; tabs EVALUATION / SIMULATION (TIME, WEATHER, START SIMULATION). Not located in code: the layout positions of these rows.
System slots (functionality): hull record `u16[19]` = number of system slots (the guide's "SS" column). Every stock design has at most that many systems once the two default ids 200 and 300 (present in all 530 designs, at +0x664 slots 0 / 1) are not counted (530 / 530;
only 4 designs fill the slots exactly), so treat 200 / 300 as free base systems and the rest as limited by `u16[19]` ("Not enough system slots", text 1056 otherwise). Slot cost per system was not found (assumed 1 each).
The user decided not to clone the HUD layout (2026-11-17): only the functionality above is needed.
### 11.7 HUD / not found
The HUD rows ("WEIGHT LIMIT", "ARMOR RATING", "SPEED", "PARTS MAX", "CURSOR SLOW / NORMAL / FAST", the hull plate) are drawn through the text-markup renderer (0x1a28d0, 0x1981f8, text ids 257 / 290-293 / 587 / 588 / 714 / 819-822 with codes like #M55 / #u100 / ~iVp%): their screen
positions are not immediate constants in the executable (not found in this pass). The strings are in data/designer_text_dat15.txt; the tutorial pictures DSN 192-198 show the real arrangement (plate top-left: HULL WEIGHT x / maxt, ARMOR RATING ANTI-<size>cm Full (orange) / Core (green)).
The tutorial pictures also confirm: boiler boxes orange outline, turbine boxes cyan outline, VP bar with two upward ticks and "VP:nn%" centred above it.

## 12. Pass 5 (2026-11-17): aircraft and systems panels
Data: `data/designer_aircraft_systems.json` (tools/designer_aircraft_systems.py): 141 system records with names / effects, 259 aircraft records with names.
CORRECTION to 11.6: the hull's system slot count is **hull record byte 0x20 (= bytes[32])**, NOT u16[19] (that test was vacuous). Hull record bytes 30 / 31 / 32 = **Ai (aircraft capacity), TR (turn radius), SS (system slots)** (checked against the guide table: 145 / 143 / 145 of 145 hulls).
### 12.1 Aircraft slots — CONFIRMED (0x19b990 work->design copy, 0x1a3248 / 0x1a32d0 / 0x1a3350, work struct +0x82f4)
Design +0x67c: 7 slots x 4 bytes = `i16 aircraft` (DAT 6 array 0 RECORD INDEX r, 0..258; 0xffff = empty), `u8 count`, `u8 flag` (the work copy stores chip id = 0x14b + r and sets flag = (a2 != 0); stock designs: 0; meaning not decoded). Slots are used from 0 but order is free (0x1a3208 swaps two slots).
Capacity: **sum of the counts of all slots <= hull Ai (byte 0x1e of the hull record)** — it counts PLANES, not slots (0x1a3350: remaining = Ai - sum(count of the other slots); 0x1a32d0 returns count when id > 0). Checked: 530 / 530 stock designs obey it
(only the 12 carrier designs use any: slot 0 = one scout type, count 2 / 3 / 5 for carriers I / II / III; Ai is 10 / 13 / 15). Aircraft do NOT add to the design weight (those 12 designs match the weight formula without them).
The aircraft panel is enabled when (0x1a29c8) hull Ai != 0 and (hull class index 3 / 4 / 5 (hull byte 5 = 0x13 / 0x10 / 0x11)) or the design has a facility part of kind 15 (launcher) or 17 (heliport); text 420 "Aircraft will also be removed." is shown when a change (hull / facility removal) would drop them.
### 12.2 Aircraft menu — CONFIRMED logic (0x1a3798 list builder, mask 0x1a2c30 / 0x1a2aa8)
Candidates: chip ids 0x14b .. 0x24d (r = id - 0x14b, DAT 6 array 0, `0x1a33c0` returns the MIDDLE 44-byte sub-record at +0x2c); an aircraft is listed when its chip is owned (0x10a7d0(chip) != 0, the same ownership test as the tech tree),
sub-record `u16[0] >> 8` (kind: 1 fighter / 2 bomber / 3 scout per item_stats) < 10, and its gear class `u16[9] >> 8` (0 landing gear, 1 floats, 2 VTOL, 3 helicopter, 4 UFO) is allowed by the hull mask M:
gear 0 needs M & 1, gear 1 needs M & 2, gear 2-4 need M & 4. M by hull class index (hull byte 5: 0xd DD 0, 0xe CA 1, 0xf BB 2, 0x13 3, 0x10 4, 0x11 5, 0x12 6): class 4 / 5 -> 5 (land + heli); class 1 / 2 -> 6 (floats + heli); class 0 / 3 -> 4 (heli);
class 6 -> 0. The version used for availability (0x1a2aa8) instead scans the design: facility part kind 15 (launcher) -> M |= 2, kind 17 (heliport) -> M |= 4 (so a BB / CA needs a launcher for seaplanes and a heliport for helicopters) and class 4 / 5 -> 5, class 3 -> 4, class 6 -> 0.
At most 20 entries are collected; the list is two-level: first the kind categories (text 597 "Anti-Ship" ...), then the planes. Names = tree chip names (tools/designer_aircraft_systems.py gives name / group / kind / gear per record). Texts: 337 AIRCRAFT, 648 / 774 header, 850 REMOVE ALL AIRCRAFT, 857 No aircraft available, 858 Removing all aircraft.
Fields shown for a plane: DAT 15 150-153 (TAKE-OFF TIME, VISIBILITY, AMMO PLUS, AIRCRAFT count) and the DAT 6 sub-record numbers (item_stats.py: range [2], endurance [4], speed [5], weapons [15], [16] ...); exact row layout not decoded.
Facility limits applied when adding parts (0x19fd20, counts include the mirrored partner): heliport (kind 17) max 1, elevator (kind 14) max 4, catapult (kind 18) max 4, launcher (kind 15) max 4, searchlight (kind 16) max 4 on DD (class 0xd) / SS (0x12) else 6,
turbines (kind 25 / 26) max 2 on hull classes 0xd / 0x12 / 0x13 else 4. Messages 321-325 "No more than N <part>" (N substituted).
### 12.3 Systems — CONFIRMED structure
Design +0x664: 10 x i16 system ids (-1 empty) = work +0x82e0. **Slots >= hull SS (byte 0x20) are disabled** (the menu marks entries SS..9 unavailable: "－－－" / "No slot available." (596)); every stock design fills slots contiguously from 0 and never exceeds SS (529 / 530; the exception is the secret SDF hull 700 with 10 systems and SS 9).
Slot 0 = id 200 (Sonar I) in all 530 designs and slot 1 = id 300 in 524: they are ordinary systems occupying slots, not free ones. One slot per system (the slot index = list position; there is no per-system cost field; the cost is 1).
DAT 9 record = 0x44 bytes (see the JSON): id, tech-tree group (u16[32]: 24 ATTACK, 25 DEFENSE, 26 STEERING, 27 ENIGMA) + chip (u16[33]) -> name via web/tree.json (id 200 = ATTACK chip 33 "Sonar I", 1105 "Heat-Seeking System", 1106 / 1107 "Eltr Positioning System I / II");
records 100-1408 (74) = ATTACK, 10000-10507 DEFENSE-type, 20000-21005 STEERING (9), 30000-30013 ENIGMA / specials (30012 / 30013 have no chip). Effects (signed u16): [6] ENDURANCE, [7] RADAR, [8] SONAR, [9] STEERING, [10] COMMAND, [11..29] percent effects (see 11.6), [30] weight (t, added to the design weight; CONFIRMED).
Duplicates: the game replaces instead of stacking: text 811 "<old> has been replaced with <new>" (REPLACE buttons 414 / 861) and the tip 1080 "Some systems perform several duties at once. However, you have to remove systems with the same function to be able to select these systems."
So two systems with the same FUNCTION cannot both be installed; the function field is most likely the record's `u16[4]` mask (1, 2, 4, 8, 16 for the 100 / 200 / 300 / 400 / 500 series, 64 for 10200, ...) — GUESS, not found in the code; identical ids cannot repeat.
Slot order can be changed (swap, 0x1aff08). ENIGMA systems (30xxx) are the Enigmatech alpha .. zeta chips. NOT decoded: which systems are offered per hull class / nation (the list is the owned chips of groups ATTACK / DEFENSE / STEERING / ENIGMA; no hull filter found), the "REMOVE ALL SYSTEMS" confirm text 407 / 410, the function-mask test.

## 13. Pass 6 (2026-11-17): PURGE, COMMAND, RADAR, SONAR (and systems rules)
`tools/designer_stats.py` now also returns command / radar / sonar / purge / boilers / unvented / endurance / steering, **530 / 530 identical to the game's own code** (`python tools/designer_stats.py`).
Systems availability (user, 2026-11-17, matches the code: no hull / nation filter found): every hull class can use every system; the hull's SS (byte 0x20) only limits how many.
### 13.1 Formulas — CONFIRMED (0x19bbe8 / 0x1f53b0 / 0x19c1f0)
- Bridge values: the first mount of category b8 = 20 (forward bridge) and the first of b8 = 21 (aft bridge) are summed: command0 = bridge `u16[35]`, radar0 = `u16[41]`, sonar0 = `u16[42]` (stats +0x16 / +0x18 / +0x1a).
- Systems (sums over the 10 slots): **COMMAND = command0 + sum(sys[0x14]) + trunc(command0 * sum(sys[0x18]) / 100)** (the % applies to the BRIDGE value only, not to the system bonus), **RADAR = radar0 + sum(sys[0xe])**, **SONAR = sonar0 + sum(sys[0x10])**; each at least 1.
  (guide: "Systems that give a bonus as a percentage are calculated on the base value", same for speed: speed += base speed * sum(sys[0x16]) / 100, additive.)
- ENDURANCE = max(100, hull `u16[9]` + sum(sys[0xc])); STEERING = max(1, hull byte 0x1f (turn radius value) + sum(sys[0x12])). (hull `u16[9..14]` are six endurance steps, the code uses `u16[9]` here; any armor dependence is applied elsewhere.)
- **PURGE**: smokestack parts (kind 27, category b8 = 12) carry `u16[34]` = the number of boilers they vent (guide table "Smokestacks listed as Purge": Jpn DD 1 = 1 ... CA / BB / CV up to 10). capacity = min(99, sum over distinct smokestack types of `u16[34]` * count), or 99 when a forward / aft bridge has `u16[43]` != 0
  (the carrier islands 10300 / 10400 and their variants: "bridges with purge"). Needed vents = the number of boilers in the first boiler group when the boiler part kind is 0x14 (nuclear / fusion reactors, kind 0x17 / 0x15, need none).
  The exit check (0x1a0f08) refuses the design when boilers - capacity > 0 ("Smokestack(s) is/are not correctly placed."), the STATS screen flags "UNVENTED BOILERS n". All 530 stock designs satisfy it. PURGE relates only to boilers (confirmed by the user, 2026-11-17); it has no other design-screen effect; the in-game help text 1359: "The number of boilers purged by the smokestack can be checked by looking at the PURGE".
### 13.2 What they DO (design screen: CONFIRMED; in battle: from the guides / user, not located in the executable)
- Evaluation ranks (the S-rank medal screen, 0x1f4f80): COMMAND rank score uses **avg = trunc((COMMAND + RADAR + SONAR) / 3)** (0x1f6098): avg >= 95 -> 10 (S), >= 80 -> 8, >= 50 -> 6, >= 20 -> 4, else 1. So radar and sonar also raise the Command rank; the guide's "command >= 235 for S" fits avg 95 with about 25 + 25 of radar / sonar from the bridges.
  MOBILITY rank (0x1f6100) compares the final SPEED with 4 thresholds that depend on the hull class: classes DD / CA / CV-type (0xd, 0xe, 0x13): 10 / 20 / 35 / 50 kt, BB-type (0xf, 0x10, 0x11): 10 / 20 / 30 / 40 kt, SS (0x12): 10 / 18 / 26 / 35 kt; scores 1 / 4 / 6 / 8 / 10 for speed below 10 / 20 / third / fourth / above
  (the guide's "speed >= 40 for S" on a battleship). The overall rank (0x1f61d0, stored at stats +0x15) maps the SUM of the six category scores (each 1 / 4 / 6 / 8 / 10, so 6..60) to an index: >= 60 -> 0 (S: all six at 10), >= 50 -> 1, >= 30 -> 2, >= 10 -> 3, else 4; the six are 0x1f5a58 / 0x1f5b10 / 0x1f5cd8 / 0x1f5e68 / 0x1f6098 / 0x1f6100 (offensive, anti-air, armor, response, command, mobility).
  **All six decoded (pass 9), tools/designer_rank.py = python port, identical to the game's functions for all 530 stock designs and for a fuzz of mutated designs (see below); the rules are in its docstring.** Summary:
  - Weapon slots: a mount's b8 (byte 0xa) 0..6 = the player's WPN 1..7 slot the weapon is assigned to in the design screen (web/designer.html "weapons list: 7 slots"; in stock designs WPN 1 mostly holds the main guns and WPN 7 the machine guns / CIWS, but the choice is free); the eval struct keeps per category ONE representative part = the part with the LOWEST row index of the DAT 7 table (and the barrel factor of the mount that first brought it: barrels 1..5 -> 1..5, 6+ -> 7, 0x1f4cd0). No summing: the biggest single weapon decides.
  - OFFENSIVE: best part.u16[32] * barrel factor over parts with kind (byte 6) != 3: >= 10000 -> 10, >= 1000 -> 8, >= 500 -> 6, >= 250 -> 4, else 1 (one Magnetic Pulse Cannon 15000 or Gun 10000 gives 10; a 3-barrel 61cm gun is 512 x 3 = 1536 -> 8, a 100cm gun 2250 x 2 -> 8).
  - ARMOR: the same best value over parts with kind not 6 / 7 -> gun class 1..15 (thresholds 7 9 11 19 37 49 102 124 151 181 215 295 395 512), minus the design's plating index (design byte 0x1e, 0 counts as 1): 0 -> 10, -4..3 -> 8, -8..5 -> 6, -13..9 -> 4, else 1. Armor must MATCH the biggest gun; overkill is penalised as well as too little.
  - ANTI-AIR: L = highest system record byte +0x35 (Auto Countermeasures I / II / III = 1 / 2 / 3; the extra auto-fire slots), base 0 / 2 / 4 for L 0 / 1 / >= 2; n = mounts of parts with byte 4 == 1 and u16[67] bit 3 (anti-air flag; machine guns, CIWS, rapid fire, high-angle, main guns...), bonus 0 / 1 / 2 / 4 / 5 for n = 0 / 1-5 / 6-10 / 11-19 / 20+; e = 1 if one of those weapons sits in a slot category b8 >= 6 - L. raw = base + bonus + e -> >= 9: 10, >= 7: 8, >= 5: 6, >= 2: 4, else 1.
  - RESPONSE: weapon target bits u16[67]: bit 1 (2) = anti-ship (guide "S"), bit 3 (8) = anti-air ("A"), bit 0 (1) = anti-sub ("U"), bits 0x20 / 0x40 = other (rapid fire / machine gun / some missiles); s = 1 if a system has (record byte +0x3b & 7) != 0 (Night / Thermal / Digital Vision, Multi-Purpose Radar, Eltr Positioning System I / II); raw = s + e + 2 per bit present among {2, 8, 1, 0x60}, minus 2 unless ship, air AND sub are all present; same raw -> score table as anti-air.
  - COMMAND: avg of command / radar / sonar (above). MOBILITY: speed limits by hull class index (hull byte 5: 13 DD 0, 14 CA 1, 15 BB 2, 0x13 3, 0x10 4, 0x11 5, 0x12 SS 6): rows 10/20/35/50 (0, 1, 3), 10/20/30/40 (2, 4, 5), 10/18/26/35 (6); grades 1 / 4 / 6 / 8 / 10.
  - The evaluation reads only as many of the design's 10 system slots as the hull has (hull byte 0x20; the loop at 0x1f50xx stops there), so a system in a slot beyond that adds nothing to anti-air / response.
  - Check: python tools/designer_rank.py = 530 / 530 designs identical for all six categories and the overall index; a fuzz of 350 random mutants (parts, slot categories, barrel counts, systems, plating; the game's own stats fed to both sides) = 0 mismatches and every score 1 / 4 / 6 / 8 / 10 seen. The guide's S-ship (1 Magnetic Pulse Cannon, 10 machine guns + Auto Countermeasures II, 61cm plating, 1 anti-sub missile, command 235, 40 kt) works out to ten in every category: the 10 guns together with the cannon and the missile make n >= 11 (bonus 4) for anti-air; it is the count of ALL anti-air-capable weapons, not machine guns only.
  - mips_emu.py gained lwl / lwr / swl / swr for this (mobility copies its tables with unaligned moves).
- COMMAND in battle (user belief + weaponsguide): higher command improves the accuracy of weapons against moving targets (engagement mode, R2, fires all auto-fire weapons), and "is believed" to let guns target more enemies at once. Text 1309-1316 (systems): "Increases command capability" for targeting / predicting systems; 1343 (submarine bridge): "Raises search and command capacities".
- RADAR / SONAR in battle (user belief + text): detection ("search") capability: radar finds surface / air targets, sonar finds submerged ones (text 1312 / 1307 "improves surface and underwater target detection", 1349 sonar "raises underwater search ability", 1442 flag "decreases enemy radar accuracy by 10%"); CONFIRMED BY THE USER (2026-11-17, from play): the radar and sonar circles get larger in game as the RADAR / SONAR value rises (the radius scale is not decoded). The battle code that converts the value into a radius was not located (the design stats struct is built by 0x1f4f10 for menus; the in-battle ship setup 0x14c5e0 reads the hull table directly).
- Sonar 1 (id 200) and Radar 1 (id 300) occupy slots 0 / 1 of every stock design; the other systems with a family mask `u16[4]` (1, 2, 4, 8, ... 32768, one bit per family: 100-series = bit 1 Electronic Targeting, 200 Sonar = 2, 300 Radar = 4, 400 Firing Delay = 8, 500 Auto Reload = 16, EM Shield 32, Eltr Jamming 64, Fire Extinguisher 128, Bilge Pump 256, Auto Countermeasures 512, AEGIS 1024, Gravity 2048, ... ).
  Two systems whose masks share a bit cannot both be installed (installing one REPLACES the other, text 811; guide: "two versions of the same system cannot be added", e.g. Sonar 1 + Sonar 2); mask 0 systems (Enigmatech, Night Vision, Fire Control ...) are exempt and combine freely; a few multi-function systems carry two bits (2080 = EM Shield + Gravity) so they need all those families free (tip 1080). The mask-vs-family correspondence is CONFIRMED by the data (every family has exactly one bit, each bit one family); the exact replace code was not read.

## 14. Pass 7 (2026-11-17): battle code for radar / sonar / command / purge
### 14.1 Loaded once at mission start — CONFIRMED
The player ship's stats are computed ONCE when the mission starts: the battle-start function 0x10d9e8 calls 0x1f4f48 (-> 0x19bbe8, the same function as the design screen) into the struct at 0x28dd40, and the ship creation code 0x15d510 copies from it into the ship object:
object +0x34 / +0x38 = endurance (HP), +0x3c = steering, **+0x4c = COMMAND, +0x4e = RADAR, +0x50 = SONAR**, +0x52 / +0x54 / +0x56 = armor side / deck / keel (from the armor row, plating index), +0x7c.. = the 10 system ids. Enemy ships fill the same offsets from their hull records (0x14c5e0). Ships are an array at *(0x2b292c), stride 0x318; the player is `*(0x2b28e8)->byte 0xd`.
### 14.2 Radar / sonar radius — CONFIRMED
The HUD radar setup 0x1252a8 (called once from the battle HUD init 0x1180f8 / 0x11c798) caches **radar radius = RADAR x 32 world units** (float at HUD struct +0x3624, squared at +0x3628) and **sonar radius = SONAR x 32** (+0x362c, squared +0x3630); the drawn radar circle is that radius times the minimap scale (constant at 0x2b - 0x10e8, 0x125594).
Each frame a contact is "detected" when its squared distance to the player is <= radius squared; targets with flag bit 0x20 (submerged) are tested against the SONAR circle, all others against the RADAR circle (0x125cd0..0x125d30). The mission event conditions (0x13be78, e.g. "get into sonar range of the German sub") use the same rule: `dist^2 <= (value << 5)^2`, sonar for targets flagged 2.
So a Radar value of 30 gives a 960-unit radar circle (the unit scale of the world vs metres was not measured).
### 14.3 Command — PARTLY
COMMAND is stored in ship +0x4c (player and enemies). The only consumer found is the end-of-mission record (0x1e7f7c copies it into the save data at +0x298). The accuracy / lock-on code that uses it in engagement mode was not located (it reads a ship struct through other pointers); the guide and your play experience say it improves accuracy against moving targets.
### 14.4 Purge — CONFIRMED
Only the design screen uses it (boilers need vents). Only part kind 0x14 (the 52 traditional boilers 20000-20312) counts as needing a smokestack; kinds 0x15 (20400-20804), 0x16 (20500-20503), 0x17 (20600-20612), 0x18 (20700-20704) are the nuclear / fusion / other reactors and need none (user, 2026-11-17). Quirk of the code: only the FIRST boiler group (first (part, barrels) met in category 10)
is looked at, so a design whose first group is a reactor and a later group is traditional boilers is not flagged.

## 15. Edge parts: the plan-view side snap (0x1a07c8) — 2026-11-17
Parts with `u16[6] & 0x80` (carrier side machine guns 1114-1120, hi-angle 1028-1041 side variants, 30 / 20 mm CIWS 1126-1128, missiles on carriers, carrier islands) are snapped by 0x1a07c8 flush against the hull's plan edge:
scan plan rows y = 0..51 over the part's box columns (x + box_x0 .. + box_w) for hull cells (any non-zero zone byte); top = first such row (initial 25), bottom = last (initial 26).
**Port side (cursor above the plan midline, y < 26): flip b14 = 1 (when the part has a flip variant, `u16[6] & 0x100`) and y = top - box_y0; starboard (below): b14 = 0 and y = bottom + 1 - (box_y0 + box_h).** The side comes from the cursor row at the drop (0x19e808: `cursor y < 26 -> b14 = 1`).
Always single parts (b15 = 0, no partner). Check on the 530 stock designs: 1,122 of 1,312 flag-0x80 mounts equal this formula exactly (the rest are within 1 row; other flag bits add small corrections in the same function).
Level (side view): for these parts `level + box_y0` equals the FIRST hull row (side area rows 0-32) over the part's own box columns in every one of the 1,312 stock mounts (offset 0), not the hull-wide median deck row: on a stepped carrier deck (Supercarrier: flight deck first row 21 up to column ~143, lower deck 26 beyond) a gun left of the step sits on the flight deck, one right of it on the lower deck, and the sprite (top bar = deck line, gun and stem hanging below) starts at that row.
Not in the game's data: the 35 / 20 mm CIWS 1121-1125 (flags 0x24F, mirror-able, no 0x80) are normal mirrored pairs in the stock designs; the web page snaps all CIWS this way because the user asked for it.

Carrier islands (forward bridge kind 12 with `u16[6] & 0x20`, e.g. 10300 / 11300 / 12300 / 13300, flags 0x28): 0x1a07c8 puts them flush against the starboard edge, `y = last plan row + 1 - (box y0 + box height)`, regardless of the cursor side (stock CV bridges: 23 flush starboard on plain hulls, none on the centre line; a few more on odd hulls differ). The ordinary BB / CA / DD bridges (flags 0x49) stay on the centre line.
Engines (slot byte 10 boilers / reactors, 11 turbines): two valid placements, never mirrored (b15 = 0 in all 4,152 stock engine mounts): **centre-line** (plan box centred on y 26: 611 mounts) or **centre-adjacent** (box bottom edge on the line = above it: 1,778; box top edge on the line = below it: 1,763). No other y occurs in the stock designs. (User, 2026-11-17; verified on the stock data.)

## 16. System special effects, auto-fire slots, level limits, unidentified items (2026-11-17, user requests)
DAT 9 record words beyond the 13 percent effects (u16 index in the 0x44-byte record): **u16[26] = auto-fire weapon slots x 256** (Auto Countermeasures I / II / III = 256 / 512 / 768 -> 1 / 2 / 3 extra slots: WPN 6; 6 + 5; 6 + 5 + 4 — the user's statement, which matches the numbers),
**u16[27] = AEGIS level** (I / II / III = 1 / 2 / 3: the multi-lock-on for guided weapons), u16[28] flag bits (Fish Detection System = 2: fish appear; Mine Detector = 0x4000; the Enigmatech eta / theta / iota / kappa 512 / 1024 / 2048 / 4120; GPS / INS has u16[24] = 20),
**u16[29] = vision bits** (Night Vision 256, Thermal Vision 512, Digital Enhancement 1024: all three are night vision, user). Auto-fire slots: WPN 7 always, the others only through Auto Countermeasures (the page's blue weapon rows).
Level up / down limits (tools/designer_levels.py over the 530 stock designs; rise = rows above the usual resting level of the side picture): main guns 2 up / 3 down, hi-angle guns and machine guns 4 up / 1 down, CIWS 3 / 0, missiles 3 / 2, proto and rapid fire 3, torpedoes 2 / 1, explosive and rocket 0 / 3 (the page uses these as hard limits; data/designer_level_limits.json holds the per side picture maximum).
Parts menus (user rules): a power source choice converts all existing power sources (boilers -> fusion reactors, no mixing; same for propulsion), a normal elevator and a side elevator cannot be mixed, searchlights are one row with a count (up to 6), the left lists show counts (x1, x6) not x positions.
Unidentified: tools/build_unidentified.py renders thumbnails of the 7 aircraft models that no research chip points at (J_BM_06, E_FG_14, E_VT_01, U_HE_03, O_BM_00-02) and lists the 9 unnamed aircraft records (0, 1, 2, 139, 150, 236, 250, 251, 252) in web/unidentified.html.

## 8. Open / not done (pass 1 list; the collision rule and drawing placement are answered in section 9)
- Drawing code: the functions that blit sprites in the design screen (0x19dc88 / 0x19e2e0 / 0x19ecd8 call 0x1a25c8, 0x1a4e18 ...) were not read yet. The picture data is identified (section 3).
- Orange / cyan vital box sizes in side view and the collision rule: the magazine shapes (section 2) carry w x h and a box; the `level` field vs box top/bottom is NOT verified.
  Experiment (not conclusive): treating the magazine box (shape box x0 / y0 / w / h) as a plan rectangle at (x, y) and testing all vital mounts of the 530 designs pairwise gives 1,330 overlaps (498 on the same level),
  so either the box is not a plan rectangle anchored at (x, y), or the game allows overlap there. The collision test in the game (add-mount check at 0x19fec4.. / 0x1a05f8 / 0x1a07c8) was not decoded yet.
- ARMOR RATING label ("46cm Full") = armor index -> size (section 5) + (VP >= 54 ? Full : Core): inferred from the guide, the HUD code not read.
- Ground truth screenshots (user designs) cannot be reproduced without their mount lists; the formulas were validated against the game's own code on its 530 designs instead.
