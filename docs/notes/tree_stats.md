# Tech tree stat panels from the game's own tables (2026-11-24)

Code: `tools/game_stats.py` (decoders), `tools/build_tree.py` (writes `tree.json` and `weapon_stats.json`). Earlier versions of the tree page took these numbers from fan guides; every number below is now read from `DAT.BIN`. (`DAT` entry numbers are this project's 0-based numbering.)

## The key finding: parts and systems name their chip
Every record of the **part table (DAT 7**, 1,120 records x 144 bytes, first u32 = part id) carries **u16[30] = tree group number and u16[31] = chip index** in that group (65535 / 0 = none). The **system table (DAT 9**, 0x44-byte records) carries **u16[32] = group, u16[33] = chip**. So no name matching or guide alignment is needed to attach stats to chips. A chip can own several parts (mount variants, ship classes, nations). Checked: all 220 guide-listed weapon chips, 105 engine chips, 139 system / facility chips and 239 aircraft find their records this way.

## Weapons (groups MAIN .. A-MATTER)
Part u16 fields: **[32] damage per barrel, [55] rounds per barrel, [56] reload, [57] dispersion, [58] range, [17..20] weight for 1..4 barrels** (0 = no such mount).
- Base mount: 1 barrel, except hi-angle guns and torpedoes whose listed mount is the twin (2 barrels) when it exists. Damage and rounds are multiplied by the barrel count (a torpedo chip's rounds = 2 x [55]), weight = u16[16 + n].
- **Targets:** u16[67] bit 1 = surface, bit 3 = air, bit 0 = submarine; u16[68] bit 1 = auto-fire, bit 6 = underwater.
- **Ship classes:** u16[5] & 255 is a bit set, bit 0 DD, 1 CA, 2 BB, 3 CV, 4 BC, 5 FF, 6 SS. A chip's set is the **union over all its mount variants** (the lowest part id alone is wrong: e.g. the 15.5 cm gun has a DD-capable variant of its own).
- Result: 220 of 220 guide rows reproduced (one weight differs: ORGANIC 3, game 100, guide 1000, probably a guide typo). The game also gives stats for the 66 cal-length chips (50..75 Cal) the guide did not list.

## Hulls (DAT 8, 145 x 40 bytes)
u16[0] = hull id, **u32 at byte 12 = maximum weight** (u16[6] | u16[7] << 16), **u16[8] = hull weight, u16[9] = endurance, byte 30 = aircraft, byte 31 = turn radius, byte 32 = system slots** (131 of 131 tested hulls agree on weight and endurance and aircraft and slots; turn radius agrees on 129, the two others differ from the guide by 1 and the game's value is used).
Hull id -> chip name: nation x 1000 + type x 100 + level - 1 (nations Jpn, U.S., U.K., Ger; types Destroyer, Cruiser, Battleship, Carrier, Battlecarrier, Submarine, Frigate); 4000+ are the special hulls (named in `game_stats.SPECIAL`), 700 = Jpn Destroyer VI.

## Engines (parts linked as above)
- **Boilers** (part kind u8[6] = 20): id 20000 + 100 x class (0 DD, 1 CA, 2 BB, 3 CV) + level (0..12); **[32] output, [17] weight**. Reactors: kind 21 (nuclear, 204xx and sub reactors 208xx) and 22 (fusion, 205xx); gas turbines kind 23 (206xx, [32] output and **[33] efficiency** = 100); submarine diesels kind 24 (207xx).
- **Turbines / motors** (kind 25 / 26, 210xx / 211xx / 212xx): **[33] efficiency, [17] weight**.
- **Smokestacks** (kind 27): id 22000 + 1000 x nation + 100 x class (0 DD, 1 CA, 2 BB) + level; **purge = u16[34] & 255, weight [17]**.
- A level chip such as "Boiler I" has no part of its own; its panel lists the class chips below it.

## Systems (DAT 9) and facilities
- Record: **u16[30] weight**, s16[6..10] = endurance, radar, sonar, steering, command; s16[11..23] = 13 percent effects labelled by DAT 15 strings 160-172 (speed increase, command, aim correction, loading efficiency, fire proof, leak proof, beam defense, shell defense, jamming rate, fire proof rate, leak proof rate, lock-on jamming, anti jamming (a level, not a percent)); s16[24] = range increase %; the following words hold packed level bytes (forward / backward thrust, emergency turn, weapon automation, AEGIS, information) that are **not decoded**. Labels for the five plain effects are DAT 15 strings 155-159.
- **Description text** is DAT 15 string **1187 + (u16[31] & 255)** (strings 1188-1418 are the `#Y4#=` descriptions). Several levels of a system share one text. A few systems have no text in the game (e.g. the fish detector); text on the game's menus says "Moｒe" with a full-width letter, normalised by NFKC.
- **Facilities** are DAT 7 parts of kinds 14-19 (elevator 14, launcher 15, searchlight 16, heliport 17, catapult 18, ammunition depot 19) with u16[31] = chip index in FACILITY; weight = [17]. Description strings by chip: 1212 (launchers), 1346 catapult, 1213 elevator, 1341 / 1342 heliports, 1345 ammunition depot. The take-off time effects ("-30" ...) were not found in the part record and are not shown.
- Large Heliport weighs 1500 t in the game; a guide lists 150.

## Aircraft (DAT 6 array 0, 132 bytes = 3 x 44, chip pairs in DAT 32)
Unchanged from `notes/formats.md` ("Item stats: aircraft"); 239 of 239 match the guides. **Aircraft weapon names** come from DAT 14: weapon id 9000 + n -> string 266 + n for ids 9000-9021, 9028-9032 -> strings 288-292, and the lasers 9023 / 9025-9027 -> strings 169 / 170-172 (Pulse Laser, Particle Gun, Particle Burst Gun, Guided Particle Gun; checked against aircraft loadouts). 9022 -> string 168 (Laser Pointer) is a guess: no aircraft uses 9022 or 9024.

## Not decoded
Packed level words of systems; the facility take-off-time numbers; weapon ids 9022 and 9024 as names; whether a part's u16[4] / [3] byte fields beyond those used here matter in the game.
