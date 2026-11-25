# Archive entry kinds: inventory and decoders (2026-11-17)

Tools: `tools/inventory_archives.py` (counts by magic), `tools/decode_unknown.py` (bundles, DSN 36 / 39 export, `streams()`).
Outputs: `data/dsn36_sprites/` (907 PNG + sprites.json), `data/dsn39_hulls/` (145 hull pictures, masks, hulls.json).

## HEADLINE: the design-screen pictures are found (CONFIRMED)
| What | Where | Format |
|---|---|---|
| **907 part / structure line-art sprites** | **DSN 36** (data) + **DSN 38** (offset table) | bundle of 907 back-to-back LZ streams; each = `SHTXFS`, u16 w, h at offset 6, BGRA palette at 12, 8bpp pixels. **Palette size is variable** (correction, thanks to the designer-code session): entries = (decompressed length - 12 - w*h) / 4, 128..256 entries; pixels start at 12 + 4*entries (252 of 907 sprites have fewer than 256 entries; my first reading assumed 256 and cut 4 rows, which was wrong and showed these side-view sprites truncated). 40 of them use index 255 (one row of w pixels) beyond their palette: drawn transparent. User hypothesis (2026-11-17): these index-255 pixels are the **collision mesh** (unverified; they start at row 0-2 of the sprite in all 40, so they are an outline/line group at the top, not clearly a single row). White line art on transparent / black. |
| **907 footprint masks** | **DSN 37** (123,352 bytes = 907 x 136) | **raw, not LZ.** `wg2.decompress` misreads the first bytes as a 4,116-byte stream (that is why DSN 37 looked like "a full mask"). Record k: u8 w, u8 h, 2 zero bytes, 4 margin bytes, then 32 u32 LE row bitmaps (row y = u32 at +8+4y, pixel x set if bit 31-x). This IS the 0x88-byte shape table the executable reads (`+4 + index*0x88`). |
| **145 hull blueprints** | **DSN 39** (data) + **DSN 40** (offset table, 146 words, last = end sentinel) | bundle of 145 LZ streams; each decompresses to 160 x 85 raw bytes (zone mask, below) followed by a second LZ stream = `SHTXFS` 640 x 344 (340 rows stored) with the hull side view (top) and plan view (bottom), white line art with grid lines. |

* Offset tables DSN 38 / 40 are stored uncompressed (first u32 = 0, so `wg2.decompress` returns b'': the "empty" entries 38 and 40).
* **Sprite index = shape index = picture index of the part record** (DAT 7 u16[7..10]). Checked: 406 = 100cm gun, 407 = 80cm, 408-410 = 61 / 56cm x1-3, 411-414 = 46 / 45.7 / 50.8cm, 415-418, 419-422, 423-426, 427-430, 431-434, 435-437 = 12.7 / 10cm, 450 = 25mm machine gun. The sprite shows the turret from above with barrels pointing right (the white bar on the right of many sprites is not understood: possibly a range / reach marker). Mask k outlines sprite k (verified 406-450: same silhouette, mask pixel x counted from the MSB makes barrels point right like the sprite).
* **Hull picture k = hull id `DAT 8 record k, u16[0]`** (DAT 8 = hull table, 40-byte records; u16[17] = k for k < 145; ids 0-4 Jpn DD I-V, 100.. Jpn CA, ..., 4400 last). Item 0 mask extent x 25-134 (Jpn Destroyer I), item 4 13-146 (Destroyer V): grows with hull level. Last records 145-149 of DAT 8 are not hulls.
* Hull mask: 160 columns x 85 rows, 1 byte per cell, 1 cell = 4 picture pixels. Upper block = side view, lower block = plan view. Byte values are single bits along the ship: 32 (bow-most?) 16 / 8 / 4 / 2 / 1 as bands of columns (identical in every row of a band), 127 appears too. Probably longitudinal zones; what each bit means is NOT decoded. Hull outline (plan width per x) is directly readable from the mask: the designer's "plan outline" approximation can be replaced.
* Not done: the mapping sprite index -> part is by the part record (known); the meaning of the margin bytes in the shape record; the bits of the hull mask.

## Multi-stream entries (CONFIRMED)
An archive entry can be several LZ streams back to back; the next stream starts right after the `00` end token (no padding). `wg2.decompress` only returns the first, `decode_unknown.streams()` walks them.
* **MAP 1, 2, 4, 5, 7, 8, 10, 11, 13, 14**: 32 SHTXFS frames each (128 x 128, MAP 13: 128 x 64) = **water animation frames** (see water notes).
* **DSN 17, 50-53 and CHR 15, 16, 20-22, 23, 40**: `'WL01'`-tagged: the first stream is a 1,872-byte `0x30` fill plus a `03 02 02 00 ...` literal that holds an `SHTXST` (palette alpha 0xff, not 256 x 256) and then **five more `SHTXST` 256 x 256 textures** (66,568 bytes each; CHR 23 has none). Briefing-room / wall texture sets. Not part pictures.
* DSN 36 / 39 are the same idea with an external offset table.

## Inventory (entries by decompressed magic)
* BEV 359: no magic (mission scripts / camera scripts, u16 count header; known).
* CHR 1,827: PSC1 755, SHTXFS 562, SHTXST 421, PTC 67, 8002c001 UI layouts 8, WL01 bundles 8, others 9 (see below).
* DAT 41: tables (known). DSN 231: SHTXFS 177, 8002c001 38, WL01 5, small lists, raw tables, 2 offset tables.
* EFC 3: SHTXST 1, PSC1 1, EEF 1. EVT 423: SHTXFS 395, PSC1 18, PTC 9, SHTXST 1.
* MAP 811: SHTXST 462, SHTXFS 162, PSM0 75, PSC1 75, PSB5 24 (sky-dome spheres, noted before), raw RGBA 13 (below).
* MDT_SHIP 580 / MDT_WEPH 790 / MDT_WEPL 790: exactly PSC1 + SHTXFS pairs.
* PRV 14: SHTX 1, SHTX3I 10, PSC4 1, PSB4 1, PSM6 1.

## Other kinds
* **UI lists (`80 02 c0 01` = 640 x 448): 38 DSN + 9 CHR.** Header 12 bytes (u16 640, u16 448, 8 zero bytes), then **28-byte records**: u16 tag, x, y, w, h, u, v, w2, h2, u16 flags, 4 bytes `80 80 80 80` (RGBA), 4 zero bytes - screen placement rectangle plus source rectangle (DSN 7: tag 0x27, dest (304, 368) 20 x 20, source (192, 224)). Other lists have **16-byte records** (u16 u, v, w, h, u32 0, `80 80 80 80`): atlas frame rectangles (DSN 34, 35, 49, 158, 168, 189; CHR 30, 33, 35, 1692, 1694). These are menu layouts, no pictures. A few (DSN 14, 22) use a slightly different 32-bit tag / extra pair; not fully classified. They are the designer-sprites session's area.
* **PTC (CHR 67, EVT 9)**: `'PTC\0'`, then three bytes counts, then a particle emitter block of floats (100.0, 128.0, 150.0 ...), then an `'SPA'` block with a source bitmap path (`D:\PRJ\Gunner2\GRP\SYS\sys04.bmp`) and a name `NO NAME` (254 entries all `NO NAME`). Particle effect definitions (not decoded further).
* **EEF (EFC 2)**: `'EEF\0'` effect definition with source path `D:\Gunner2\GRP\EFC\ef001.bmp` (3 effects, floats such as 0.4 / -0.4 / 0.005). EFC 0 = SHTXST, EFC 1 = PSC1.
* **PRV**: `SHTX` + 4-byte tag: **4-byte header, 1,024-byte BGRA palette (alpha 0..0x80 range, x2), 256 x 256 8bpp pixels** (66,564 bytes). PRV 0 = effect sprite sheet (sparks, flames, lightning), PRV 4-13 (`SHTX3IR`) = identical-looking UI sheet with a Chinese-style panel, a ball and a cave / ice mask. PSC4 / PSB4 / PSM6 (PRV 1-3) = older-generation variants of the model formats (PSM6 = 578 KB map mesh); header u32s at 4..: `10 / 0x7ac / 0x1638 / 0xa2` etc. Not decoded.
* **MAP raw RGBA** (entries 0, 3, 6, 9, 12 = 16,384 bytes; 15-22 = 24,576 bytes): horizontal colour bands = **palette banks** (16 or 24 palettes x 256 BGRA entries, alpha 0xff). Water palette sets; not pictures.
* **CHR 0** (711,983 bytes): offset table of 1,097 u32 (start of data 0x1125; entries not monotonic after index 109) over a byte-coded stream (`51 28 00 00 50 b1 00 01 30 47 00 02 ...`). Format not worked out; looks like animation / motion or sprite command data. **CHR 2** (34,400): vertex-like records (`7b 09 47 e0 3b f6 00 00`) with a small header, a headerless vertex / path table. Not decoded.
* **DSN 41** (580 bytes of floats `bd2914f8` ...): not decoded (design-screen related, loaded by 0x198d40).

## Unknown / open
* Meaning of hull mask bits and of the margin bytes of the shape records; the white bars on sprites.
* CHR 0, CHR 2, PTC / EEF field layout, PRV PSC4 / PSB4 / PSM6, the UI-list tags.
