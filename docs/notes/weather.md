# Weather, time of day, sea palette and sky: what is decoded (2026-11-16)

Tools: `tools/decode_weather.py` (writes `data/weather.json` and the dock page's `web/water/dock_clock.json`, `web/water/sea_map16.bin`),
`tools/mips_emu.py` (a small MIPS / R5900 interpreter). The time-of-day blend is NOT re-implemented by hand: the decoder **runs the game's own
code** (SLUS_213.87 `0x148b78`, `0x146390`, `0x146318`) on the game's own tables and records what comes out. Address = file offset + 0xff000.

## CONFIRMED (and how)
1. **Source of the weather tables = DAT.BIN entry 2** (7,360 bytes). Loader `0x103ba0` reads file id 6002 (id / 1000 -> archive table at 0x2a6b90 -> DAT.BIN, base 6000 -> entry 2),
   relocates the header offsets into the globals 0x2ae678-0x2ae6a8. Sections (header `(count, offset)` pairs at 0x10 + 8k):
   | global | offset | records | content |
   |---|---|---|---|
   | 0x2ae680 | 2484 | 13 x 3 bytes | **time keys** (hour, minute, phase) |
   | 0x2ae688 | 3460 | 13 x 36 B | **day** colour record per weather 0-12 |
   | 0x2ae68c | 4652 | 13 x 36 B | **night** colour record per weather |
   | 0x2ae690 / 0x2ae694 | 3928 / 4108 | 5 x 36 B (weathers 0-4 only) | **evening** / **morning** (dusk, dawn) records (labelled by which clock window the code uses them in) |
   | 0x2ae698 / 0x2ae69c | 4288 / 5120 | 13 x 28 B = 7 floats | day / night float records |
   | 0x2ae684 | 2524 | 13 x 72 B = 9 (float, float) | per-weather colour-adjust pairs (used by `0x236a40`: scales a colour's luma-based saturation / brightness) |
   | 0x2ae67c | 1620 | 3 sets x 8 phases x 9 colour dwords (B,G,R,A) | **per-phase light colours** |
   | 0x2ae678 | 1524 | 3 x 8 floats (radians 60, 40, 25, 10, 0, -2, -4, -90 degrees) | sun height limits, used by `0x14682c`; role not decoded |
   Verified: the emulated `0x148b78` returns exactly the day record's colours at 12:00 and the night record x 0.5 at 02:00 for all 13 weathers (`verification` in `data/weather.json`).
2. **The clock.** Globals 0x2b27c0 hour, 0x2b27bf minute, 0x2b27b8 frame counter. `T = hour*360000 + minute*6000 + frames*100/1920`. Key times (DAT 2 sec. 2484), phase in brackets:
   00:00 (4), 05:50 (4), 06:00 (5), 06:10 (6), 06:20 (7), 06:30 (0), 10:00 (0), 17:30 (0), 17:40 (1), 17:50 (2), 18:00 (3), 18:10 (4), 25:00 (4).
   Between two keys the game uses phase A, phase B and `f = (T - Ta) * 1024 / (Tb - Ta)` (code `0x146634`). This is the 8-phase day cycle.
3. **Sea palette = the game's own runtime palette, MAP.BIN entries 16-22** (24,576 B each = 3 sets x 8 phase palettes x 1024 B, B,G,R,A, alpha about 0x60-0xa0).
   Loader `0x103590` reads file id `0x10 + [0x2b285d]` and splits it into 24 palettes. Palette used = `block[set*8192 + phase*1024]`, blended `A + trunc((B-A)*f/1024)` per byte
   (`0x146318` -> `0x146250`; the blend was checked byte for byte by running the game's routine, `sea_palette_blend_matches_game_routine_0x146318`). `set` = the weather record's dword 4
   (day table: weathers 0-1 -> set 0, 2 and 5 -> set 1, 3, 4, 6, 7 -> set 2, 8-12 -> none (-1)). The phase colours match the cycle (mean colours of MAP 16 set 0: day blue-grey, warm, orange,
   dark red, night blue, warm-bright, grey, grey-blue), and set 2 is the grey overcast set.
4. **The map table fields (DAT 4 records, 40 B from byte 612), read by `0x104518`**: byte +36 -> 0x2b285f (clamped to 15), byte +37 -> 0x2b285e = **light set 0-2** (selects the 8-phase colour block
   of sec. 1620 and the 8 sun limits), byte +38 -> 0x2b285d = **sea file index** (MAP entry 0x10 + value). So my earlier guess "low byte = palette row, high byte = tile group" was WRONG. Dock records
   67-74: byte36 15, light set 0, sea file 0 -> MAP 16. Value 7 (some maps) would point at MAP 23, which is not a palette block (unexplained). Byte +36 is used in the cloud / layer drawing routine
   `0x147b70` as `15 - value` (docks: 15 -> no layers); its meaning is not decoded.
5. **Mission clock.** Mission script (BEV 206-281) block 0 records: kind 3 = start (hour, minute), kind 4 = a second time (all in `data/weather.json` "missions"). The loader copies kind 3 to stage+0x10 / 0x11,
   which seed the clock (`0x1399d4`). Kinds 5, 6, 8 (stage+0x15, 0x14, 0x16) exist in the parser but no mission uses them, so 0x2b27c6 = 0.
6. **Darkening at night**: colours 0-2 of the blended record are multiplied by `min(2*(0x2b27c6 + 0x2b284b), 12)/12` (`0x1489e0`); the light colours of phase 4 by `(min(0x2b27c6,4)*128+128)/1024`
   (`0x146534`). `0x2b284b` is set to 3 by the briefing code when 0x2b27c6 = 0 (`0x1d0848`), else loaded from a saved setting (gp-0x3130). `decode_weather.py` evaluates with 27c6 = 0, 284b = 3.
7. **Weather change**: the weather byte 0x2b27c2 (0-12) cross-fades (1024-step blend `0x147de0`) between the previous and new set; weather is picked at random (`0x14c3e0`) from 13 weights per slot and
   re-picked every 0xe100-0x1c200 frames; a script command (`0x134498`) can set hour / minute / weather. Debug strings `no weather data`, `free_misson weather table err` go with the stage weights below.
8. **Weather records, structure** (36 B, dwords): 0 light colour 0, 1 "flash" colour (blended with 0x202020 by the lightning level at gp-0x7188 up to 0x400), 2 colour 2, 3 colour with an extra byte
   (6, 7, 8, 10, 12, 24 for weathers 5-12), 4 sea palette set (-1 none), 5-7 flags / ints (weathers 5-7: 300, 1000, 3000 = rain levels?; 11, 12: -800 / -3000), 8 particle colour with alpha 0x25-0x70.
   Float record: [0] 1000 -> 400 (a distance; stored to the model renderer's float, used in `0x147b98` cloud-layer maths), [1] 450 -> 250, [2] 100 -> -100, ... see `data/weather.json`.

## NOT decoded / unconfirmed (do not treat as fact)
- **Which weather a mission or the dock has.** The 13 weights per slot (stage struct +0x1d, 9 slots) come from a trailing table of BEV 204 that is EMPTY in this game data (count 0), so I did not find where
  they come from. The dock page assumes weather 0 (clear).
- **Fog.** No fog colour or fog distance was identified. The floats (1000 / 450 / 100 ...) and colours 0-2 exist per weather and time, but I could not tie them to fog. Draw-distance use of float 0 is plausible, not shown.
- **Sky.** The 9 per-phase light colours (slots 0-5 form a smooth 6-colour ramp: at noon dark blue-purple (48,48,124) to (120,129,217); slots 6, 7 constants, slot 8 an extra tint) are decoded and the game's
  routine `0x146390` evaluates them for any clock time, but the consumer is a graphics packet I did not follow, so "sky gradient" is only my reading of the ramp's shape.
- Which colour is lighting vs fog vs clear colour (colour 0 / 1 / 2); the byte order of the 36-byte records was assumed B,G,R like all game palettes (consistent with the sea blocks).
- The briefing's START option (Dusk / Noon / Dawn / Night): the code at `0x1d0710-0x1d0930` normalises the start time to :30 steps; the mapping of the four names to hours was not found.
- How the sea tile group and the tile scrolling are chosen; wave / foam behaviour; rain / snow / lightning drawing; lamp switching rule at night (the dock page's lamps-on rule is mine).
- MAP.BIN 0, 3, 6, 9, 12 (16 alt palettes per tile group, used by the old `water.js` rows 0-15): not the runtime palettes; their role is unknown.

## Dock page (`web/drydock.html`) after this decode
Clock slider (0-1439 min) + presets Noon 12:00, Dusk 17:50, Dawn 06:10, Night 20:00 (the preset hours are mine). The sea uses the game's palette for that minute (decoded). The two checkboxes are
game data with an UNCONFIRMED role and are labelled so: sky = the 6-colour ramp, dim = brightness of colour 0 relative to noon. Lamps at phases 3, 4 and night = my rule. Page not viewed in a browser by this session
(syntax checked with node only; the browser pane refused localhost).

## Second pass (same day): lighting, haze, clock speed, briefing label
CONFIRMED by reading the code (not by emulation unless stated):
- **Environment struct at 0x29dbb8 ("E")**, filled by `0x147de0` from the blended weather: E+0x15c = colour 0, E+0x158 = flash colour (the weather's dword 1 blended with 0x202020 by the lightning level),
  E+0xbc / 0xc0 = float 0 / 1, E+0x144 = float 3, E+0x160 = float 4 as a byte. The scene packet builder (0x2252xx) sends E+0x14c..0x154 (a direction: the sun / light vector, set from sin / cos of a sun angle at
  0x149b00 via 0x1099a8 into E+0x14c) together with colours E+0x158 / E+0x15c to the model renderer, so colour 0 / flash are very probably the directional light colours of models (the page's "dim" uses colour 0).
- **Haze colour = slot 4 of the 9 phase colours** (`0x2c1380` & 0xffffff -> E+0x13c, `0x148274`). `0x147908` draws 640-pixel-wide horizon strips (sprites with alpha ramps, y from the projected horizon) in that colour: the horizon haze band.
  The page now uses slot 4 as the water's distance-fade colour (that use is my assumption; the band itself is confirmed).
- **Clock speed**: `0x149cb0`: every frame `counter += frame_delta * [0x2b27bc]`; at 1920 the seconds byte (0x2b27be) increments, then minutes (0x2b27bf), hours (0x2b27c0). 0x2b27bc comes from the mission's kind-5 record
  (stage+0x15, `0x139a2c`) which no mission script has, plus many other writers (script commands); so the real in-mission clock speed was NOT resolved (it may be frozen at the start time).
- **Briefing START label**: `0x1d0790-0x1d07a8` calls `0x138658(hour, stage data)` and stores 0-3 at +0x266: the Dusk / Noon / Dawn / Night text is a **label computed from the mission's start hour** (thresholds stored in the stage data), not a
  setting. Thresholds not extracted. The code at 0x1d0890-0x1d0928 only nudges the start time away from :00 / midnight boundaries.
STILL UNKNOWN: fog distances (none found; there may be no GS fog), what draws the sky above the horizon band (the 6-colour ramp's consumer was not found), per-mission / dock weather, sun-angle vs clock formula, the lamp rule,
rain / snow / lightning drawing (records exist: particle sprites DAT 2 @5540, weather dwords 5-8), wave strength.

## Third pass (2026-11-16): fog, sky, briefing label, weather effects - DECODED
- **Fog colour = GS FOGCOL (register 0x3d)**, written from E+0x13c (haze = phase colour slot 4) at `0x2252bc` (A+D pair at 0x2d69e0/0x2d69e8, template set at `0x225c54`, default 0xb4c8dc). Byte order: the word's byte 2 -> FCR, so the tables are B,G,R (also proven by the sprite packet builder `0x247810`, which swaps bytes 0 and 2 before sending to the GS).
- **Fog distance**: scene setup `0x224f80` builds the GS fog factor from near = E+0x140 and far = E+0x144: stores `-255/(far-near)` and `255*far/(far-near)` (linear: F = 255 at near, 0 at far) plus a 1/z form `-255n/(f-n)`, `255nf/(f-n)` into the VU1 constant block 0x29a760 (+0x60..+0x6c). far = weather float 3 (clear day 990, night 700, fog weathers 400 ...), near is forced to 0 after each weather update (`0x1482b4`), so the linear form applies (the 1/z form is degenerate at near 0; which form the VU1 program uses was NOT read). Init defaults (`0x1045f4`): near 200, far 700, haze 0xa7a29b. During a lightning flash (`0x147230`) near = 100, far = 2 x 1980. Which objects set the FOG bit was not checked (the model renderer `0x244100` has a per-model fog flag +0x352 and its own scale 128/-48).
- **Sky = 2D vertical gradient** drawn by `0x146660`: the 8 values at DAT 2 sec. 1524 are the **elevations of the colour stops** (60, 40, 25, 10, 0, -2, -4, -90 degrees; set chosen by map byte +37), colour stop i = phase colour slot i (0..7). Elevation -> screen y linearly from the camera pitch +/- half FOV (0.5236/zoom), 448 lines, strips of 10 x 64 px with top/bottom colours. VERIFIED by running `0x146660` in tools/mips_emu.py (sin/cos/atan2 hooked): at noon, pitch 0 the strips are 40->25 deg slot1->slot2, 25->10 slot2->3, 10->0 slot3->4, 0->-2 slot4->5, -2->-4 slot5->6(black). So slot 4 is both the horizon colour and the fog colour. Slot 8 is not used by this routine. Stars: 32 random points drawn when the clock is before 06:00 or after 18:00 (`0x146a98`).
- **Horizon haze bands** `0x1478a8`: 64 px gradient above and 24 px below the projected horizon (point at distance E+0xbc = float 0) in the haze colour, plus 15 - (map byte +36) extra distance bands (docks: none). Weathers 4 and 7 also run a lightning branch there.
- **Ambient light**: `0x225150` sends (colour0 + flash colour) x float4 / 128 per channel to VU1; colour0 / flash (E+0x15c / 0x158) also go with the light direction E+0x14c (sun vector, set from angles at 0x149b00). float 4 = 128 normally.
- **Briefing START label** (VERIFIED by emulating `0x138658` on DAT 18): thresholds in DAT 18 at the offset stored at +0x404 (0xb9c): 5, 12, 16, 19. Start hour 05-11 -> index 0, 12-15 -> 1, 16-18 -> 2, 19-04 -> 3; text = DAT 18 string 0x12 + index (`0x1c0998` uses entry k-1): "Dusk", "Noon", "Dawn", "Night". So the English text calls MORNING "Dusk" and EVENING "Dawn" (swapped localisation; check in game: FAR_C_010 starts 10:00 and should show "Dusk"). It is a label, not a choice.
- **Weather effects** (record dword 6 = effect type, dword 7 = particle count, dword 8 = particle colour, dword 3 = mist colour + density byte): type 2 (weathers 5, 6, 7: 300 / 1000 / 3000 drops, fall speed 1.0) = **rain** (spawner `0x129558`, "max_rain ovr"); type 1 (weathers 8, 9, 10; mist density 6 / 12 / 24, fog far 400) = **fog / mist**; type 3 (weathers 11, 12: count 800 / 3000 with speed 0.2) = slow particles, probably **snow** (inferred from the speed). Weather 4 (and 4 / 7 in the haze routine) starts the lightning state machine (`0x147ed0`, `0x14864c`, `0x147230`: random timer, flash light, sun vector randomised). Labels "rain / fog / snow / thunder" are inferences from these parameters.
- **Clock speed**: counter += frame_delta x [0x2b27bc]; 1920 per game second. Writers of 0x2b27bc: 0x1007b0, 0x104b70, 0x139a2c (mission kind-5 record, absent), 0x1900e0, 0x1973c0-0x197494, 0x1c1110, 0x1c1e10, 0x1c7dd0, 0x1c83d0, 0x1d0738 (dock/briefing: 0), 0x1e68b8, 0x1f3420. Not all read yet; in-mission speed still open.
- **Per-mission weather**: still open. Tried: BEV 204 trailing table (empty), mission scripts kinds 0-8 (only 3 / 4 used), DAT 4 record bytes, script command `0x134498` (kind 22 handler sets hour / minute / weather from an event struct). Next lead: the event struct behind kind-22 records (`lw 8(a2)` list) and the stage-struct weights' other writers; init `0x14c468` has no direct caller (function pointer table not found).
- NOT DONE in this pass: wiring fog distance and the decoded sky gradient into web/drydock.html (the page still shows the earlier ramp as an "unconfirmed" sky, which is now known to be correct in shape except that the stops are at 60/40/25/10/0/-2/-4 degrees and slot 4 is the fog colour).

## Fourth pass (2026-11-17): sun, light level, clock speed, page wiring
- **Sun / light direction** (`0x149990-0x149b00`, constants at 0x2af564-0x2af570): with clock T (units: 360000 per hour), azimuth a = -2*pi*T/8640000 - pi/2, tilt e = -(pi/4)*sin(a); E+0x14c = cos e cos a, E+0x150 = cos e sin a, E+0x154 = sin e (a light vector: 45 degrees down at noon, horizontal at 06:00 / 18:00). A second light (0x2c1360, angle a - pi, flag 0x2854 bit 0x400) is enabled in a day window; its role (moon / fill) not decoded.
- **Light level** gp-0x7188 = min(1024, distance in clock units to 05:45 or 18:15 x 1024 / 6000): 0 exactly at 05:45 and 18:15, full one game minute away. At full level the weather's colour 1 (white for clear: 238,255,255) is the sun colour and float 4 the light scale; below full it fades to 0x202020 / 0 - the moment the light vector switches. The first pass of decode_weather.py ran with level 0 (wrong); now fixed, verification still passes.
- **Ambient / light colours per phase**: colour0 and colour1 come from the day / night / evening / morning records blended by the clock (all in data/weather.json timeline and web/water/clock_all.json).
- **Clock speed**: per frame counter += frame_delta x [0x2b27bc]; 1920 = 1 game second. Writers: 60 at boot (0x1007b0) and stage init (0x104b70); mission start overwrites it with stage+0x15 (kind-5 record, absent in all missions; whether stage+0x15 is pre-set is NOT known); 0 in the dock / briefing (0x1d0738) and other menus (0x1900e0, 0x1c1110, 0x1c1e10, 0x1c7dd0, 0x1c83d0, 0x1e68b8, 0x1f3420) = **clock frozen there**; 120 / 90 / 80 / 60 at 0x1973c0-0x197494 (another mode, not identified). frame_delta (0x29dc64 at run time) not read, so real-time speed is not stated.
- **Dock clock and weather**: the dock / briefing module (0x1d0710) sets the clock from stage+0x10 / 0x11 = the selected mission's start time (nudged off :00 at 11:00, 12:00, 23:00, 00:00) and freezes it (scale 0), then calls the weather setter with stage+0xfc (the picked weather). So the dock shows the next mission's start time and weather; which weather that is stays unknown (weights not found).
- **Lamps**: no lamp switch found. Candidates: the 05:45 / 18:15 switch, the star window (before 06:00 / after 18:00), or bit 0x400 of 0x2b2854. The page uses its own rule (on before 06:00 and from 17:50).

### web/drydock.html now (tested in the browser pane, 2026-11-17, no console errors; screenshots at 12:00, 17:50, 20:00, 06:10 and weather 9)
- Clock slider (2-minute steps) + presets at the game's phase keys; Weather selector 0-12 (names are my inference); data = web/water/clock_all.json from the game's own routine.
- Decoded and drawn: sea palette (MAP 16, set from the weather; -1 keeps the previous set like the game), sky gradient (stops 60 / 40 / 25 / 10 / 0 / -2 / -4 / -90 degrees, phase colours), linear fog from 0 to far (weather float 3 x 4096 model units) in the horizon colour, for the dock, props and sea. Which objects the game really fogs was not checked.
- Approximate use of decoded values (labelled): dock and props scaled by the brightness of the game's ambient ((colour0 + colour1) x float4 / 128) relative to clear noon. Lamps: my rule.
- The earlier "Dawn screenshot showed Dusk" was a stale select display; the 06:10 preset now shows its own palette, sky and label.

## Fifth pass (2026-11-17): per-mission weather, "preset / random", stage defaults
CONFIRMED (code read):
- **Stage init `0x137100`** (every campaign stage < 0x53 before its mission script BEV 206 + n is loaded via 0x1373c8): clears the stage struct and sets
  +0x14 = 4 (-> 0x2b27c6 "night light level"), +0x10 = 12 (default start hour), **+0x1d = 100 (weather slot 0: weather 0 = 100 %)**, +0x12 = -1, **+0x15 = 60 (clock speed)**.
  Consequences: the mission clock RUNS at speed 60 (counter += frame_delta x 60, 1920 per game second) unless a script changes it; 0x2b27c6 = 4, so the briefing sets
  0x2b284b = 1 and nights are darkened x 10/12 (colours 0-2) and x 0.625 (phase-4 light colours). decode_weather.py now uses 27c6 = 4 / 284b = 1 (the earlier 0 / 3 was wrong);
  its verification (noon = day table, 02:00 = night table x 10/12 for all 13 weathers) passes.
- **Weather pick** (`0x14c468` / `0x14c4f8` -> `0x14c3e0`): rand(0..99) against the cumulative 13 weights of slot stage+0x1c (weights at stage+0x1d + 13 x slot); with all weights 0 it returns 0.
  Re-pick every 0xe100-0x1c200 frames only when flag 0x2b27ae bit 8 is set (`0x14c530`) - a candidate for the "random weather" mode.
- **Slot command**: script record **kind 37** (u16 param < 9) sets the slot (`0x13d670`, dispatcher `0x13be90` jump table 0x2a7a74). It occurs only in BEV 204 event blocks (16 records, slots 0 / 1 / 2).
- **A screen with a frozen clock (`0x1f3598`)** offers 4 times = table 0x2b2050 (06, 13, 18, 22 h; labels Dusk / Noon / Dawn / Night by the same DAT 18 strings) and 6 weathers (options 0-5 -> weathers 0, 3, 6, 10, 12, 7); it
  writes weight 100 to the chosen weather in slot 0 and calls the weather setter. Options live at gp-0x7a08 / gp-0x7a07, cycled by `0x118050` (mod 4 / mod 6). I read it as the dock's VIEW VESSEL screen (not confirmed).
NOT FOUND - per-mission PRESET weather (the user says every mission has one, plus a Randomize setting). Angles tried:
  1. BEV 204 trailing 0xd8-byte weight table read by `0x1379e0`: count 0 in this data.
  2. Mission script block 0 records: only kinds 1-4 occur (no 5 / 6 / 8, no weather).
  3. Kind-37 slot command: only in BEV 204 and it selects slots 1 / 2, whose weights are never written by any code I found (writers of stage+0x1d..: 0x137160, 0x1f36ac only).
  4. DAT tables scanned for 13-byte rows summing to 100: DAT 2 section 5748 (9 rows x 8 x 5 percentages) turned out to be an AI table (read at 0x1725cc, indexed by difficulty 0x2b281b).
  5. Script command 0x134498 (record kind 22) can set hour / minute / weather from a record reached through a pointer patched at load; the target data was not resolved.
  Next leads: (a) the kind-22 / 0x134498 path (find the loader that patches record +8 pointers and dump the target records per mission), (b) the options-screen code that sets 0x2b27ae bit 8 (Randomize)
  and DAT 18 / DAT 15 strings for it ("WEATHER", "Preset", "Random" are DAT 18 strings, the latter in the training section), (c) run the mission-start path in the emulator with a mission script loaded.
  With the data as decoded, a campaign mission starts with weather 0 unless that missing piece changes it.
- Page: Mission picker (start time + decoded briefing label; weather set to 0 and labelled as not decoded), Viewer selects (the 0x1f3598 options), Clock presets show "(other)" when the clock is set elsewhere.
  Tested in the browser pane (?r=13): no console errors; FAR_C_010 sets 10:00 ("Dusk" label), PAC_G_150 22:00 ("Night").
- Angle 6 (Randomize flag): bit 8 of 0x2b27ae (periodic weather re-pick) and bit 0x10 (run the pick each frame) are set UNCONDITIONALLY at stage start (`0x10da4c`, right after the map record loader 0x104518) and in two other start paths (0x197c68, 0x1c7ce8 / 0x1c8188), not by an option. So every stage re-picks its weather from the slot weights every 0xe100-0x1c200 frames; with the default weights that is always weather 0. No player "Randomize" option variable was found yet.

## Sixth pass (2026-11-17): the user remembers heavy fog in the Hell Atsche mission (FAR_C_660, mission 66)
- **Per-mission map** (new, confirmed): the mission hooks (default 0x1e7050, Hell Atsche 0x1f2c98) load the map index from a byte table at DAT 2 header 0xe4 (offset 7184, 84 bytes) indexed by the mission number 0x2b28a4. Hell Atsche -> map record 17 (light set 2, sea file 4 = MAP 20, byte36 15 = no haze bands). All missions are in data/weather.json "missions".
- **Map floats +28 / +32** (new, confirmed): copied by 0x1046d8 / 0x1046c8 to gp-0x7178 / gp-0x7174, the two multipliers of the 9 per-weather colour-adjust pairs (0x236a40: saturation / brightness of the sky / light colours). Hell Atsche map: 0.75 / 0.9 (greyer, darker sky colours). Other map fields: +0x1a halfword -> 0x2b2804, byte +0x27 OR-ed into the flag word 0x2b2854.
- **Weights re-checked by emulation**: running the game's BEV 204 parser 0x1379e0 in tools/mips_emu.py (file load + decompressor hooked) for missions 1, 23, 46, 66, 71 leaves the stage weights at {weather 0: 100}; no error message. BEV 204 is a single LZ stream (5428 of 5432 bytes used, 29348 out) ending in a zero count. In BEV 204, mission 66 switches to weather slot 1 (kind 37), but no code writes slot-1 weights (scan of all stores into stage+0x1e..0x91).
- Hell Atsche hook 0x1f2c98: no weather / clock writes. BEV 271 (its script): no weather records (kind 22 only the standard (1,1,1)). BEV 121 + n (BEV 187 for this mission) is passed to the map loader but is not a script in the mission format; not decoded.
- CONFLICT: the user remembers heavy fog; the decoded data path gives weather 0. Either the fog weather comes from a path I have not found (most likely the kind-22 / 0x134498 pointer path or BEV 121 + n), or the look comes from the map's greyer sky (light set 2, colour adjust 0.75 / 0.9). What would settle it: a PCSX2 save state (EE RAM) taken during that mission: the byte at 0x2b27c2 is the active weather and the stage struct (pointer at 0x2b2824) holds the weights.

## Seventh pass (2026-11-17): per-mission weather FOUND - event-VM scripts (the user's Hell Atsche fog memory was right)
CONFIRMED (code read + the game's own loader run in tools/mips_emu.py; tool: `tools/event_weather.py`, output `data/weather.json` "event_weather" and per mission "event_weather" / "weather_from_event_on_load"):
- **Event table** 0x28d648: u16 triplets (event id, file id, flag), ends at -1. Event 10 -> BEV 305 ... event 761 -> BEV 359. Read by 0x13e1d8 and by the record converter 0x139124 (mission-script records kind 27 / sub 11 carry the event id; at load it is replaced by the file id).
- **Pre-load**: stage begin 0x1048b0 calls the mission hook with a0 = 0 (0x104eb4) -> 0x10dc48 -> 0x139570, which loads every kind-27/11 event script of the mission with 0x130268(file, -2) (parser 0x12a000; task table gp-0x74a8; task +8 = node pointers, +0x10 = file id).
- **Weather command** = event-VM node kind 22, handler 0x134498 (called by the node callback 0x1314b0 at 0x131e78). Event 4 / 8 (sent while the script loads): first child; event 0x200: child [node+0x10]. Child fields (s16 from child+8): +2 hour (<24), +4 minute (<60), +6 weather (<13; else unchanged), +8 fade seconds (>0 -> 0x147da0(weather, s x 60), else 0x147da0(weather, 1)), +0xa value -> float gp-0x316c = max(0, (v/100 - 0.5) x 0.05 / 2.5) (0 -> -1.0; role not decoded), +0xc 1..3 -> 0x2b27c5.
- **Results** (emulated load, 0x147da0 hooked):
  | mission | event -> script | on load | later steps |
  |---|---|---|---|
  | MED_I_411 | 411 -> BEV 329 | - | weather 12, fade 2 s |
  | EUR_J_483 | 480 -> BEV 330 | weather 12 | - |
  | EUR_N_510 | 510 -> BEV 332 | - | weather 7, fade 1 s, value 10 |
  | FAR_C_660 Hell Atsche | 660 -> BEV 346 | **weather 8** (mist: fog far 400 instead of 990) | - |
  | FAR_A_680 | 681 -> BEV 353 | weather 11 | - |
  | ARC_Z_690 | 690 -> BEV 354 | weather 11 | weather 4, weather 4 |
  | (no mission script found) | 562 -> BEV 337, 622 -> BEV 342 | weather 0 | 4 / 10, 0 |
  Hell Atsche's briefing also says "Today, a fog is over the vicinity of the strait". Event 660 is the mission's first cutscene block (block 5, after the briefing and a radio block; "That shadow... it's an oil rig, right, sir?").
- Other scripts with kind 22 (BEV 0, 3, 6, 7, 114, 115, 304) are not in the event table (304 = 10:00 weather 0 is loaded by code at 0x139b54; BEV 0 / 7 set 17:40 / 17:56).
NOT SETTLED - timing: in 0x1048b0 the pre-load (hook(0) at 0x104eb4) comes BEFORE the stage-start weather init 0x104f60 -> 0x147888 -> 0x14c468, which on a first start (stage+0xfd = 0) picks from the stage weights (weather 0) and writes 0x2b27c2 directly. Read literally, that resets the loaded weather, and the event weather would then show only when the event's script runs (event 8 / 0x200). If 0x147da0 found a blend running during the pre-load it queues the weather (gp-0x7010 / -0x700c) instead; the queue is only consumed at the end of a blend. A PCSX2 save state from the first seconds of FAR_C_660 would settle it. The user remembers fog from the start.
- Also confirmed: stage+0xfd is cleared with the stage struct (0x1372e0 alloc + memset 0x448 at 0x137104); 0x14c468 sets it to 1 after the first pick, so on a retry the current weather is kept ("$$weath_cont").
- Dock page: the Mission picker now sets the weather the mission's event script sets on load (FAR_C_660 -> 8), labelled with this caveat. Tested in the browser pane (?r=14): no console errors; FAR_C_660 -> 09:00, weather 8.

## Eighth pass (2026-11-17): weather effects on the dock page; does weather apply at the dock?
- **Dock weather (code read, partly)**: the dock has no weather table of its own. The routines that load the dock map records (0x43 + type: 0x1c1a68 / 0x1c1a9c, 0x1c7bf8 / 0x1c7c2c, 0x1d0018 / 0x1d004c, 0x1e5b40) do not run the stage weather pick. 0x1c7d10.. sets the clock to the stage's start time (stage+0x10 / +0x11), stops the clock (0x2b27bc = 0) and calls 0x147da0(stage+0xfc = the mission's picked weather, 1); 0x1d0778.. sets 11:30 and the same mission weather; 0x1c1ac0 only sets bit 0x20 of 0x2b27ae (no re-pick) and leaves the weather as it was. So dock scenes show the current mission's weather (or whatever was active); which dock scene each routine is was not identified. The weather effects code (0x1478a8 / rain spawner 0x129558) was not seen to check the map, so rain / snow can show at the dock (not verified in the game). A separate routine at 0x1c0510 (map record 12, not a dock) forces 12:00, weather 0 and clears the re-pick bits.
- **Dock page effects** (`web/drydock.html`, "weather effects" checkbox; data in `web/water/clock_all.json` "effects" from `tools/decode_weather.py`):
  DECODED inputs: effect type per weather, particle count (rain 300 / 1000 / 3000, snow? 800 / 3000), particle colour + alpha (B,G,R,A, 0x80 = 1.0; day and night records, blended by how far the clock is into phase 4), fall-speed ratio rain 1.0 : snow 0.2, lightning in weathers 4 and 7, fog near 100 / far 2 x 1980 during a flash.
  MY choices: particles fill a box of 0.7 x camera distance around the camera; fall speed 1.3 box heights per second x the ratio; rain streak length; flake size and sideways drift; flash every 4-12 s, 0.25 s long, brightening with an ambient light.
  Tested in the browser pane (?r=17): weather 7 at 12:00 and 20:00 (rain, lightning flashes fire), weather 12 (snow), no console errors.
