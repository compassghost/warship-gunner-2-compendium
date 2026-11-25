# Hell Atsche (FAR-C-660) - what the executable says

Source: `iso_extract/SLUS_213.87` (PS2 ELF, one load segment: file offset 0x1000 = address 0x100000, R5900 code, no symbols or strings).
Disassembled with Capstone in MIPS64 little-endian mode (`sd`/`ld` decode; the 128-bit multimedia instructions show as `.word`). All addresses below are in-game addresses.

## Per-mission hook table
- 82 function pointers at **0x29af30** onward, one per row of the mission table (DAT entry 31, strings 539 `dummy` .. 621). Index = string number - 539, so 0x29af30 is the dummy row and 0x29af34 is FAR-C-010.
- Most rows point at the default `0x1e7050`; rows with their own script point elsewhere (the Hell Atsche row, index 66, is at 0x29b038 -> **0x1f2c98**; FAR-A-670 Leviathan is 0x1f2f98; SPE-A-700 is 0x1f3038).
- Each hook is called with a phase number in `$a0`.

## Hell Atsche hook (0x1f2c98)
- **Phase 0 (stage load):** allocates the stage state, registers a callback (0x1f2f70, which sets flag 0x100 on the first object of the stage state when run) and adds entity class **0x263 = 611 (Hell Atsche)** as the mission objective (`0x107420`).
- **Phase 1 (stage start):**
  1. Creates 5 entities of classes 0x263 .. 0x267 (611-615: Hell Atsche, Support 1-4) with ids 5000 + i (`0x1388 + i`), positions taken from the mission's object table, flag 0x100 on their data, flag 8 on halfword 0x12, and increments three stage counters (+0x322, +0x40a, +0x324 in the stage state, the same ones other enemies bump). Hell Atsche gets kind byte (offset 0xe) **0x1f**, the four Supports **0x29**.
  2. Creates **64 entities of class 0x268 = 616 (Mirror)**, ids 6000 + i (`0x1770 + i`), each placed from a 28-byte record of the mission's object table (position plus a heading halfword at +0xe). Each gets kind byte **0x2a**, flag 0x100 on the entity, flag 1 on its model sub-object and flag 1 on halfword 0x10. **They do not bump the stage counters.**
  3. Walks every entity of class 0xcf = 207 (**Fuel Tanks**) already on the map and sets its kind byte to **0x2b**.
- **Phases 2, 3, 5, 7:** call nothing stage specific except phase 7 (0x13bd38, stage clean-up).

So the stage is: 1 Hell Atsche + 4 Supports + 64 Mirrors (the "kites" of the walkthrough) + all Fuel Tanks, with the Mirrors placed from mission data and excluded from the stage counters.

## Do the Mirrors do anything?
Evidence found (static, nothing was run):
- Entity row 616 has class flags 1032, the same as trees, buildings, storehouses, the DECOY and Fuel Tanks (scenery class), and movement class 64, the same as aircraft. Hell Atsche (8193) and the Supports (1) are different classes.
- Nothing else in the executable tests for class 616 (the only 0x268 in code that is a class id is in this spawn loop), and the Mirror is not in the boss lists that map class -> icon / name (those list 606-610, 617-619 and others).
- The Mirrors skip the counters that the other four units bump.
- The walkthrough says "Destroying them does nothing".
Not found: any code that reads the kind byte 0x2a. The kind byte (offset 0xe of the entity record) is read in only 43 places in the whole program, none of which compares to 0x2a, so the Mirrors' kind does not select special logic there. The beam / laser behaviour itself (BF122, BF124 are beam-like models) was not located.
Conclusion: the evidence points to the Mirrors being scenery-class flying props with no gameplay effect of their own; this is not proven, because the code that moves them or draws the beam was not found.

## Follow-up findings (second pass)
- **Entity class row, u32 at byte 16 = hit points** (read from DAT entry 3 array 3, 24-byte stride): Yamato 5000, ZERO fighter 5, DECOY 1, Fuel Tanks 30, **Mirror 50**, Laser Pod 50; the superweapon bodies and the Supports read 0, so their health comes from somewhere else. By the table the Mirrors and Fuel Tanks are ordinary destructible objects, so "invincible" would have to come from a flag, not from the class row.
- The entity record's byte at offset 0xe (what the hook sets to 0x1f / 0x29 / 0x2a / 0x2b) is a **state / mode code**, not an AI selector: it is read in only 43 places, mostly as `6` or `7` -> set to `0x30` (0x30 = finished / removed; the entity loop at 0x155a18 skips it), plus a few tests for `0xe` and `0x12`. No code compares it with 0x2a or 0x2b and no jump table is indexed by it. So 0x29-0x2b are probably "inert / scripted" states, and the real behaviour is not keyed on them.
- The executable does have debug strings, including `stage_evt_open (stg_mess / stg_txt / stg_evs)`, `stage_trg_open`, `MAP OBJ OVR`, `laser_aloc WEAP_MAKE no wpar`, `hata kaa/kab/body`. The stage loader is around 0x13a000. A stage is therefore driven by four per-stage files (messages, text, **triggers**, **event scripts**), so the fight (waking up, firing) is probably scripted by triggers and events rather than hard-coded in the hook above. BEV entries 203 and 204 (28 KB and 29 KB, different layout from the 206-281 mission scripts) may be the trigger tables; they were not decoded.
- Lasers are allocated through a weapon-parameter table (`laser_aloc`, `WEAP_MAKE`); the Hell Atsche main laser was not tied to any entry.

## Where the 5 + 64 positions come from (third pass)
- Every map mesh in MAP.BIN (the PSM0 entries) contains a **map object table**: 16-byte records `[u32 id][f32 x][f32 y][f32 w]` with ids from **4900** upward, in runs of consecutive ids (w is 1.0 or a small number, probably scale or heading). Example: MAP entry 253, ids 4900.. start at 0x1c9ea; entry 125, id 5998 at 0x1fc8a.
- The hook function's `0x10e220(id)` call looks a record up in this table. So Hell Atsche and the Supports are placed at the records with ids **5000-5004** and the 64 Mirrors at the records with ids **6000-6063** of whatever map the mission uses. Ids 5000-5004 and 6000-6063 exist in nearly every map (ids 5000-5004 are normally five records within about 100 units of each other; 6000-6063 are a block of 64 slots that is a tight cluster on some maps and a long row along a coast on others), so they are generic spawn slots that other missions use for fleets; the Mirrors are simply put on whichever 64 slots the Hell Atsche map defines.
- Which map record the mission uses is still unknown (the mission -> map link was not found), so the actual mirror layout cannot be read yet. Candidate maps for FAR-C (Sea of Okhotsk) are records 15-18 (MAP entries 240, 253/255, 268): their 6000-6063 slots are spread over x -570..840 / y 710..765 (253/255) and x 9..1520 / y 770..830 (268), i.e. a long row, not a ring.
- `0x105568` / `0x1056b0` print the debug lines "set route" and "next map %d st%d-%d" from a 12-byte-per-row route table; the value in it is a mission number (divided by 100 into campaign stage and remainder), not a map record.

## Fourth pass: the mirrors form a wall; stage script structure
- The user observed in game that the Mirrors form a **wall**, not a ring. That fits the map data: the only candidate maps whose slots 6000-6063 lie in one long straight row are MAP entries 253 / 255 (x -570..840, y 710..765) and 268 (x 9..1520, y 770..830), both in the right-hand coast group (records 16/17 and 18) that matches "Sea of Okhotsk". Entry 253/255 is the better fit for a wall of width 1400 at constant y.
- BEV mission scripts (206-281) are variable-length records: `op` byte + 11 argument bytes + 4 payload bytes; for the text-carrying ops (0x01 mission code, 0x02 title, 0x0d dialogue) the payload is an inline NUL-terminated string padded to 4 bytes (`#g0300` etc. are speaker/portrait codes, `#n` newline). The Hell Atsche script, as far as the first 0x620 bytes go, is the intro cut-scene only: picture loads (op 0x19 with EVT id 15001+n), portraits, and the dialogue about the Tatar Strait and the missing recon ships.
- The event / trigger interpreter is at **0x13be78**: it dispatches `op - 0x1b` (13 values, jump table at 0x2a7a74) for **condition ops 0x1b-0x27**. The handlers read ranges of target ids (`lo`, `hi` halfwords) and count how many have their "destroyed" bit set in a per-stage flag array (`[state + 0x28]`, bit 0), then compare with a threshold (ops 0x14 / 0x15 seen in the same code for "all" / "count"). In other words stage logic is of the form "when N of targets lo..hi are destroyed, do X". The two big BEV entries 203 and 204 contain such condition records (ops 0x1b, 0x1f, 0x21, 0x28 appear in 204); which file belongs to which mission was not worked out.
- Consequence for the Mirrors: any "destroy the targets" test is a range of target ids; the Mirrors are never tested by the mission objective (the objective is the class 0x263 entity) and do not bump the stage counters, which is consistent with "destroying them does nothing".

## Map confirmed by the user: records 16/17 (MAP entries 255 / 253)
The user identified the Sea of Okhotsk map in game as **records 16/17** (the guesses below that favoured records 13 and 18 were wrong; the overlay test that seemed to rule 16/17 out was misleading because most of the table's thousands of points are terrain cells, not spawn slots). From entry 253's object table (entry 255 has the same layout with small differences):
- Hell Atsche + Supports, ids 5000-5004: a short row at **y = 360, x = -1360, -1320, -1280, -1240, -1200** (third value 37, 43, 32, 19, 10).
- Mirrors, ids 6000-6063, not one long wall but **two tight blocks**: ids 6000-6033 (34 mirrors) at x ~ -570..-478, y ~ 710..765, and ids 6034-6063 (30 mirrors) at x ~ 765..840, y ~ 710..760. The blocks are about 1300 apart east-west and about 350-400 north of the boss row; the western block is ~700 east of the boss row, the eastern ~2000. The third value (0.5-16) varies per mirror (size or spacing).
- Overlay picture on the record 16 minimap (scale assumed +-2000 world units = image): `web/maps/hell_atsche_overlay_0.png`.

## Map guess, revised (superseded by the confirmation above)
The walkthrough "Location" (Sea of Okhotsk for FAR-C) is the map's name. The EL2 route in the walkthrough passes "the north island" and "the east main land" with the platform in the middle, which matches **record 18 (MAP entry 268)** (land at the top centre plus a long coast on the right) better than records 16/17, which only show a strip of land on the right. Record 18's slots 6000-6063 are also a straight row (x 9..1520, y 770-830). Treat record 18 as the best guess; still unconfirmed.

## Moving parts of the main body (user-confirmed)
- Nodes 8-19 of BOS12 are six two-piece vanes (front panel 40 vertices, rear panel 66, hinged ~1,400 units apart) spaced every 60 degrees around the cannon's muzzle. In the animation poses the front piece swings out 45-140 degrees and the rear piece folds back about 120 degrees. **In game they open like a flower and the laser fires out between them** (user, who played the stage).
- The tower stack (nodes 2-4) and head (node 7) only rotate about their pitch axis in the stored poses (frames 32-38: tower leans forward up to 70 degrees, head -38..+27); there is no yaw in the animation data, so aiming is driven from code. The Supports are static in the fight and sit as four touching deck slabs (a square) with the tower through the middle; the fortress viewer is `web/fortress.html`.
- The unnamed parts BF121 / BF122 / BF124 are probably the beam and its effects (not placed).

## Mirror formation (from a user-supplied in-game picture)
- The Mirrors are launched from pods (which pods is not known; see the correction at the end of this section) and then fly into a formation: a curved wall spanning **1/6 of a circle (60 degrees)**, **16 mirrors per row, stacked 4 high (64 total), the rows almost touching**. Each Mirror is a flat dart model (chr_1202, 504 x 1774 x 712).
- The slot table in the map file gives the *starting* positions (two blocks); the wall is formed by the game's own movement, so the arc radius and the arc's position relative to the boss are not in the data. The fortress viewer (`web/fortress.html`) draws it with defaults of 60 degrees, 16 per row, row gap 780 and radius 30000, all adjustable.
- **Correction (user, 2026-11-15): the "Laser Pod" (entity class row 608, model chr_1187 BF090) belongs to Vogel Sumera, not Hell Atsche.** The entity table agrees: boss parts follow their boss (Dora Durhi 601 -> Locomotives 602 / 603 -> Measurement radar 604; Vogel Sumera 607 -> **Laser Pod 608**; Hell Atsche 611 -> Supports 612-615 -> Mirror 616), and the model grouping in `web/models/bosses.json` already had it under Vogel Sumera. An earlier version of this note called that grouping wrong; it was right, and the Bosses page no longer moves it. What the Mirrors are launched from is therefore still unidentified (the pods in the user's picture may be something else).

## Not done
- The behaviour of the main body and Supports (firing pattern, the laser that follows the player's bow) is in code that dispatches on something other than the kind byte; not found.
- The mission script (BEV entry 271) opcodes were not decoded; its unit-table part is unrelated to the 5 + 64 units above, which come from the mission object table (ids 5000+ and 6000+).
- Meaning of entity flag bits (0x100, 0x12 & 8, 0x10 & 1) was not worked out.
