# Boss and part health: the per-class stat table (DAT entry 6)

Found 2026-11-15 while researching Lord of Terror / Hell Atsche struts. Static reading of `iso_extract/SLUS_213.87`
(file offset 0x1000 = address 0x100000, Capstone MIPS64 little-endian). Data dump: `data/class_health.json`.

## The table (confirmed)
- **DAT entry 6** (94,944 bytes). Per entity class there is a **180-byte record** = **3 x 60-byte blocks**.
  Record start = `41000 + (class - 590) * 180` (class = entity-table row, 590 = Yamato). The init routine **0x14c5e0**
  (called from the boss part handlers' first frame) reads it: class index `class - 0x24e` (valid for 0..299),
  `x 0xb4`, plus `block x 0x3c`. The block is chosen from the difficulty byte at 0x2b281b (`diff - 1`, clamped 0..2).
- Per block: **u32 at +4 = hit points** (copied to the object's `+0x34` current / `+0x38` max, only if > 0),
  byte `+0xb` = **speed in knots** (matches the viewer: Wirbelwind 85, Dreadnought 40, Habakkuk 20, Lord of Terror 90),
  byte `+0xa` is another movement value (turning?), `+0xc/+0xd/+0xf` copied to object fields `+0x3c/+0x4e/+0x50`,
  seven u16 at `+0x10` copied too (not decoded).
- **Validation:** the first block's HP equals the in-game viewer's Endurance for **all 20** bosses in `data/boss_viewer.json`
  (Wirbelwind 10000 ... Lord of Terror 320000, Habakkuk 80000).
- **Open:** the second block is exactly 1.5x the first for most classes (Habakkuk is 1.2x, Duel Crater 1.2x), so it is a
  higher difficulty. The third block does not look like HP (Habakkuk 32500, Yamato 1200, Mirror 45000); either it is a
  different record type or my 60-byte split is wrong there. Which in-game difficulty each block is was not checked.

## Boss parts (block 1 / block 2)
| class | name | HP |
|---|---|---|
| 611 | Hell Atsche | 120000 / 180000 |
| 612-615 | Support 1-4 (the struts) | **30000 / 45000 each** |
| 616 | Mirror | 15 / 22 (entity row says 50) |
| 619 | Lord of Terror | 320000 / 480000 |
| 620 | BOS15A | 50000 / 75000 |
| 621 | BOS15B | 50000 / 75000 |
| 601 | Dora Durhi | 30000 / 45000 |
| 602, 603 | Locomotive | 8000 / 12000 |
| 604 | Measurement radar | 200 / 300 |
| 608 | Laser Pod | 150 / 225 |
| 600 | Musspellheim part (row 600) | 65000 / 97500 |
Other bosses: see `data/class_health.json` (all rows 590-629).

## Hell Atsche Supports (kind 0x29, handler 0x18ce58)
- Spawned by the mission hook (0x1f2d64 loop, classes 0x263..0x267), kind byte 0x1f for the body, **0x29 for the four Supports**.
- First frame: parent pointer = `0x11b708(0x263)` (the Hell Atsche body). **If the global byte at 0x299..-0x4cbd is 0 and
  `0x10a370(0x26)` is non-zero, HP = HP x 7 / 10 (30% less)**; the meaning of those two flags was not decoded.
- Each frame: if the **parent's HP (+0x34) is 0 or less**, the parent's `+0xa8` pool is set to 100000 and added to the
  Support's damage counter, so the Supports die with the body. A non-zero `+0xa8` on the parent is applied the same way.
- Separate, unrelated: the hook at 0x1f03c8 spawns class 612 with a hard-coded 10000 HP and kind 9 for some other mission.

## Entity update dispatch (confirmed)
- Per-frame update calls `handler = table[kind]` with the kind byte at object `+0xe`; table base **0x29a900**, one u32 per
  kind (0 = none). The kind is **set by whatever spawns the object**, not derived from the class: Hell Atsche body 0x1f,
  Supports 0x29, Mirrors 0x2a / 0x2b, Habakkuk 0x1a (handler 0x188720), Laser Pod 0x2e.
- Kind 0x28 (handler 0x1876b8) looks up class 0x259 (Dora Durhi) as its parent; it is **not** Lord of Terror.

## Class -> kind mapping (confirmed)
- The spawner function containing the `sb kind,0xe(obj)` at **0x16e2d4** picks the kind from the class with a comparison
  tree at **0x16e74c-0x16e840** (the other tree at 0x1830d8 is unrelated). Examples: Habakkuk 0x25d -> 0x1a, Leviathan 0x269 -> 0x20,
  Ragnarok 0x26a -> 0x21, **Lord of Terror 0x26b -> 0x22**, 0x26e/0x26f -> 0x1d, anything unlisted (including BOS15A/B, 0x26c/0x26d) -> 6 (the generic handler 0x170408).
- Hook table at 0x29af30: Lord of Terror's mission (SPE-G-760, row 76) uses the default hook, so all its behaviour is in this kind handler.

## Lord of Terror (class 619, kind 0x22, handler 0x18ef58)
- Handler = the generic enemy handler (0x170408, called every frame) plus extras: damage taken in state 1 (`0x182fb8` = 1) is also added
  to a counter at `+0xa0`; on destruction it frees a child at `+0xa4`, runs 0x14cba8 and frees itself. A sub-routine 0x18f4c8 fires a weapon
  (looks up weapon id **0x71c = 1820**, rows of 0x90 bytes in the program's weapon table, aims with the range and speed fields); a
  proximity timer (`+0x9c`, 0x38400 ticks) spawns an object of class **0x23** that follows the boss. Movement and aim go through the
  generic code; the boss does not run its own phase machine like Habakkuk.
- So the in-game "very animated" look is **model animation**, not code: the three models carry real keyframe sequences that the
  viewer ignores (it shows frame 0): **BOS15 158 frames, BOS15A 212, BOS15B 181**. Frame-to-frame jumps in BOS15 (body) come before
  frames 2, 5, 7-10, 12, 28, 69, 78-82, 101, so there are several clips (2-6 and 8-11 are short loops; 12-27 and 69-77 equal the rest pose).
  **Clip table decoded (2026-11-15), see "Animation clip table" below.** (Header word +0x14 is NOT the clip table: it holds 5 rows of
  32 bytes of scale floats / state codes that `0x11b350` and `0x182fb8` read.)
- Weapon list from the viewer: Sepia Pulse Cannon, Particle Burst Gun, Photon Gun, Pulse Laser, High X-ray Ordnance, Ring Laser, Long Range SSM; 90 kts.

## Animation clip table (PSC1 header word +0x18; confirmed on BOS15 / BOS15A / BOS15B)
- A table of 8-byte pairs `(u32 offset, u32 count)`, one per **animation index** (offset 0 = unused); the table runs to header word +0x34.
  The index is what the game sets with `0x11b2c8(obj, anim_index, slot)` (controller halfword +4).
- Each offset points to a list of **14-byte steps**: `u16 frame`, `u16 duration` (low 15 bits = ticks, **bit 15 = last step of the clip**),
  10 zero bytes. A clip is therefore a *stepped pose animation*: show frame N for `duration` ticks, then the next step. A last-step duration of
  9999 = hold that pose. The pair's `count` is unknown (for the body dance it equals the clip's total ticks, 80). Tick rate unknown (viewer assumes 60/s).
- Body BOS15 clips: 0 = frames 2-11, 1 = 28-68 (3 ticks each), **2 = 78-83 (20,10,10,20,10,10 ticks) = the dance**, 3 = 101-130 (10 ticks each),
  5 = 137-156; index 4 unused. Frames 0-1, 12-27 and 69-77, 84-100, 131-136 belong to no clip (12-27 are copies of frame 0). BOS15A has 13 clips
  (e.g. 2 = 8-18, 9 = 176-188 ends in a hold), BOS15B 21. Exporter: `tools/export_anim.py`; viewer `web/lot_anim.html`.
- What each animation index MEANS (idle, attack, death...) is not decoded; only the dance was named, by the user's memory of the game.

## Next steps
- Match animation indices to game events: find the callers of `0x11b2c8` / `0x11b308` for class 619 (kind 0x22 handler 0x18ef58 and generic 0x170408).
- Read 0x18f4c8 (weapon fire) and the generic handler 0x170408 for the attack pattern.

- User-identified clip (2026-11-15): body frames **77-84 = the dance** (from memory of the game). Body segments in web/lot_anim.html are hand-picked ranges (0-12, 27-68, 77-84, 100-131, 136-157), not the game's clip table.

## Hell Atsche body: phase machine and clips (kind 31, handler 0x18c240; read 2026-11-15)
Phase byte at `+0xa2`; timer at `+0xac` (counts down by the frame-delta global at 0x29-0x239c; units unknown); clip index written to the controller halfword +4
(`sh clip,4(ctrl)`); "clip finished" = controller flag 0x10 (halfword +2).
| phase | what happens | clip set on entering the next phase |
|---|---|---|
| 0 idle | after the first hit or the player in range (sounds 0x85) a timer of 0x3c00 runs | timer ends: **clip 1** (frame 2, hold) |
| 1 | waits for the clip to finish (flag 0x10) | **clip 2** = frames 2-3-4-5-6-8, the six muzzle vanes opening (sound 0x83) |
| 2 beam | the tower (node 6) and head (node 7) are turned toward the player by code (0x241490), a random aim point near the player is re-picked on a timer, class 0x47 (71) beam objects are spawned; runs until the timer passes 0x6900 minus 128 x `+0xa1` | **clip 3** = frame 8 held open |
| 3 lightning | keeps aiming, spawns class 0x41 (65) objects (lightning) every random 0x780-0xa00 ticks via 0x18cd90; timer 0x2d00 | timer 0x780, then **clip 4** = frames 8-11-12 (vanes closing) |
| 4 / 5 | waits for the clip, random timer, turns tower and head back to angle 0x78 | **clip 5** = frame 21 then frame 1 (return) |
| 6 | timer | back to phase 0 with **clip 1** |
- Clips 10 and 11 (frames 31-38) are not set by this handler.
- Aiming, beam and lightning spawns are code; the clips only move the vanes and similar parts.

## Hell Atsche Supports (kind 41, handler 0x18ce58)
- **Clip 0** (frame 1) intact. **Clip 1** (BOS12A frames 41-51, 30 ticks each, then hold) is set when current health is at or below half the maximum (`+0x34 <= +0x38/2`) and the clip is still 0, with flag 0x10.
- **Clip 2** (BOS12A frames 11-20, 120 ticks each = 20 seconds at 60/s) is set when health reaches 0: sound 0x86, the parent's destroyed-supports counter `+0xa3` is incremented, and debris objects fall (class 0x46 effects at nodes 0x4b/0x4c).
- BOS12B (the other support type) has the same clips 1 and 2; BOS12A also has clip 12 (frames 71-82), which only the hook at 0x1f03c8 starts.

## Vogel Sumera (kind 28, handler 0x189648-0x18ae70)
- Its model has 4 frames and 3 clips (0: frame 3, 1: frame 1, 2: frame 2), set only by the generic damage code below; it has **no firing animation**.
- Code turns nodes 1, 8, 9 and 10 (the two small gun nodes at x = +/-94 and their pivot) and nodes 4-7 (four large ones at x = +/-8396 and +/-10526), spawns classes 0x39, 0x45 and 0x41, and **launches the Laser Pods** (class 0x260 = 608, kind 0x2e, parent pointer +0x98, spawned at node 2 by the function at 0x18aa4c), which confirms the user's statement that the Laser Pods belong to Vogel Sumera.

## Generic damage clips (0x14e1c0-0x14e300, also 0x14f5xx, 0x159a6c)
- Ordinary objects set **clip 1 or 2** when they are destroyed (`sh 1/2,4(ctrl)` chosen by a float comparison, then 0x231618 and 0x14e7c8 effects); both look like death or wreck poses, which one is not known. Clip 0 is the default.

## Viewer
- `web/boss_anim.html` (model picker, deep link `boss_anim.html#chr_1198`), data from `tools/export_anim.py` (all 21 animated superweapon models, `web/models/anim_<id>.bin`, `boss_anim.json`; it replaced `lot_anim.html`).

## Blending between clip steps (read from the code 2026-11-15; viewer implements an assumed version)
- The clip controller (0x231688) divides the time spent in the current step by the step's duration and stores the float in the controller (+0x14); a duration is stored x32 (0x2315e8: `duration << 5`, 9999 = hold). The pose code (around 0x240c80) mixes two values as `a + (b - a) * t`, using a blend factor copied from that field. An instance flag (0x10) replaces the factor with a constant, so some objects snap between steps.
- Not confirmed: which two frames are mixed (the viewer assumes this step's frame towards the next step's frame over the step's duration) and how rotation is mixed (the viewer interpolates each Euler angle along the short way round).
- `tools/export_anim.py` now also writes `web/models/nodes_<id>.bin` (skeleton, per-frame node rotation/position/scale); `web/boss_anim.html` has a "Blend steps" toggle. Checked: blending a frame with itself reproduces the baked pose exactly for every tested frame of the Lord of Terror body.

## Node hierarchy: child lists, not the parent field (2026-11-15, found on BOS05A)
- A PSC1 node record has a child-list pointer (absolute file offset, node numbers, 0xff-terminated) and a parent halfword whose bit 15 was read as "has a parent". For many models (BOS00-05, BOS05A, Habakkuk, BOS08, BOS10, BOS11) the bit is clear on nodes that the child lists make children of the hull, and node positions are **relative to the child-list parent**. Using the parent field left the bridge and weapons behind when the hull node animates (BOS05A node 0 sinks 98,304 units while its guns' own tracks move +98,072 to cancel it, which only makes sense if they inherit the hull).
- `tools/psc1.py`: `child_parents(part)`, `hier_parents(part)` (child lists first, old rule only for nodes in no child list) and `node_transforms` / `bake` with `children=True` as the **default**; `children=False` gives the old rule. Validation: of 395 dock / in-game weapon model pairs the new rule brings 11 closer together (the very ones hand-fixed in `tools/model_fixes.py`, which is now redundant) and makes none worse. Yamato's barrels (second-level nodes) sat at mid-ship under the old rule and now sit at their turrets.
- **Models page fixed 2026-11-15:** `tools/reexport_hierarchy.py` rewrote the rest-pose `web/models/<id>.bin` and `size` of the **191 models** that change (13 bosses, Yamato / Musashi, most destroyers, cruisers, battleships ...). `data/model_audit.json`, `notes/model_audit.md` and `notes/model_placement.md` still describe the old rule (regenerated 2026-11-15: `tools/audit_models.py` and `tools/write_model_report.py` were rerun, so those files now use the new rule). Not rerun: `export_pose.py` poses and the composite (Hell Atsche is unaffected).

## Credits tile and links
- `web/img/credits_dance.webp` (40 frames, 600x240, 30 fps loop, 290 KB) is the Lord of Terror dance clip 2 blended and looped (last step blends back to the first), rendered with `bossAnimShot()` in `web/boss_anim.html`; `credits_dance.jpg` is the still for reduced-motion. Shown on the Credits card of `web/index.html`.
- `web/bosses.html` links each animated model's viewer caption to `boss_anim.html#<model id>`, plus a general link in the intro.

