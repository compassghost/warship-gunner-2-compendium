# 3D model audit (2026-11-12)

Scope: every PSC1 model in CHR.BIN, MDT_SHIP.BIN, MDT_WEPH.BIN and MDT_WEPL.BIN (1,835 models, 4,083 part meshes, about 1.4 million faces).
Tools: `tools/psc1.py` (parser, rewritten), `tools/model_entities.py`, `tools/audit_models.py`, `tools/export_models.py`, `tools/write_model_report.py`.
Data: `data/model_audit.json` (per model / per part numbers), `data/model_entities.json`. Companion lists: `notes/model_entities.md`, `notes/model_placement.md`.
Originals of the files changed here are in `backup/models-audit-20261112/`.

## Verdict

The visual errors came from three wrong assumptions in the exporter, not from damaged or undecoded data. All three are fixed and the viewer was re-exported.

| Symptom | Cause | Fix |
|---|---|---|
| Large models only partly textured, wrong patches of texture, grey faces (chr_1198, chr_1216) | UV records were matched to faces in file order. They are shared: each face stores the index of its UV record (u16 at face offset 14). chr_1198 has 939 records for 2,242 faces. | Look the record up through the face. |
| Rotors inside or under helicopters, boss parts piled at the origin, stray plates on ships | A model is a tree of nodes with local vertices; node positions and rotations were ignored. | Apply the rest-pose transform of every node (parent chain). |
| Models with the wrong skin | The texture was taken from the neighbouring archive entry. | Use the game's own model -> texture table (DAT entry 3, array 2). |

## 1. Faces without texture

Counted after the fix, split by what the mesh is for:

- **Visible meshes: 2,800 meshes, 990,005 faces, 641 without a texture (0.065%).** Every one of the 641 is marked as untextured in the data itself:
  - 371 faces have UV index 0xffff together with the flat-shade flag (face flag 0x20). They take a colour from the part's colour table instead of a texture: laser beams (ALA0: blue, purple, green, yellow), glows, black or dark panels, the tip face of missiles. Intentional.
  - 254 faces have bit 15 set on a valid index. 237 of them sit on player ship parts, nearly all on the carrier "bridge" parts (`j_cv_kaa_*`, `u_cv_kaa_*`, `e_cv_kaa_*`), 16 on dock scenery, 1 on a weapon. Bit 15 is the same marker every collision hull uses, so these are read as collision-only surfaces embedded in a visible mesh (most likely the landing deck). Not drawn; this reading is an inference.
  - 16 faces on one dock object (DOBJ033) have bit 15 and an out-of-range index. Same treatment.
- **Collision hulls: 1,283 meshes, 412,492 faces, 99.7% untextured by design.** Almost all are part slot 4 of ships, bosses, map objects and player parts. They are simplified hulls with UV index 0x8000. These were the "untextured" grey models in the viewer; they are now labelled "collision" on the part button.
- Faces with an invalid vertex index: 0. Degenerate faces (fewer than three distinct corners): 91, scattered one or two per model, mostly in low-detail parts.

Conclusion: there are no accidental texture holes in the game data. Faces that are blank are blank on purpose.

## 2. Holes / missing faces

- No face is dropped by the parser any more (0 invalid indices in 1.4 million faces) and quads keep the non-convex split fix from before.
- The holes seen earlier had two causes that are now gone: scrambled UVs landing on transparent texels (the viewer cuts out alpha below 0.4), and parts sitting at the origin instead of closing the gap they belong to (chr_165 BOAT, ship bridges).
- What remains is open geometry by design. Share of boundary edges (edges used by one face only, after welding vertices by position) in the full-detail mesh: aircraft median 5%, player weapons 1%, enemy ships 24%, bosses 18%, effects and boss sub-parts 70%+. Ships are built from open shells (hull without a top under the deck, deck plates, superstructure boxes without a floor), effects are single-sided sheets. This statistic cannot tell an intended opening from a modelling gap, so it is a ranking for visual checks, not proof. Models with the highest share among ships: chr_1316 J_CV_05, chr_1578 U_CB_00, chr_1658 O_CV_00 (carriers: open hangar / deck edges).
- Checked by eye in the viewer after the fix: chr_165, chr_860, chr_1100, chr_1118, chr_1158, chr_1198, chr_1216, chr_1230, chr_1415, mdt_ship_80. The other models were checked by the numbers above only.

## 3. Texture <-> UV agreement

- Texture source is now the game table for all 755 CHR models and for the high-detail MDT models; the low-detail MDT twin (name ending in `L`) is not listed in the table and uses the texture stored directly after it, the same pattern the table shows for its high-detail twin.
- **1,347 of 1,835 models had a different texture under the old neighbour rule** (559 of the 1,045 models shown in the viewer):
  - 68 enemy ships: every British and German ship from chr_1363 (E_DD_01) to chr_1497 (G_SS_02). In that stretch the texture follows the model, so each ship was wearing the previous ship's skin.
  - 289 of 290 player hulls in MDT_SHIP (texture follows the model there too).
  - 116 dock objects (DOCKJ / DOBJ), 8 map objects.
  - 34 superweapon models: BOS05A, BOS06A/B/C, BOS07A, BOS12A/B, BOS15A/B share their parent's texture; BF062, BF063, BF090, BF092, BF093, BF124, BF142, BF143 use a texture that is not adjacent; BF0x3 / BF1x3 and others use the shared effects sheet chr_9.
  - 42 effect models had no texture at all; they use the shared effect sheets chr_7, chr_8, chr_9, chr_13.
- chr_1198 (BOS12 "Hell Atsche"): the texture was right (chr_1197); the mapping was wrong because of the in-order UV matching (939 shared records for 2,242 faces), and its 32 nodes were all drawn at the origin. It now renders as a tower with the cannon on top, fully textured.
- UV coordinates above 1.0 (texture wrap): 2,001 faces in 336 meshes; expected for tiled surfaces, the viewer already repeats.
- Face centres that land on a fully transparent texel: high only where transparency is the point (muzzle flashes, trees, fences, cranes, three boss sub-parts BF121, BF140, BF142). No aircraft, ship or boss body is above 25%.
- Aircraft have two textures before the model (128x128 `SHTXFS`, then 256x256 `SHTXST`). The game table links the 256x256 one. What the 128x128 one is for (low-detail part or menu thumbnail) is not established.

## 4. Model -> entity map

Full list: `notes/model_entities.md` (machine-readable: `data/model_entities.json`, field `entities`, plus `chips` = tech-tree chip keys where a name matches).

- Source: DAT entry 3. Array 2 is the model resource table (model file, texture file). The table that the earlier notes read as 1,072 records of 32 bytes is 1,072 records of 24 bytes: resource index, properties and a pointer to the entity name. Many entities point to the same resource.
- Every model also carries an internal name in its header (`U_HE_03`, `BOS12`, `j_dd_sen_00H`), which decodes as nation (J, E = Britain, G, U, O = other, a = special) + class.
- Coverage: 560 of 755 CHR models have at least one in-game name; 86 models are shared by several entities.
  - Aircraft: 167 models for 254 named aircraft. Examples: chr_1142 O_FG_00 = Duck Interceptor / Fighter / Bomber / Scout; chr_1100 U_HE_03 = RAH-66 Comanche; chr_689 J_BM_06 = I32E-Arawashi (the "F-15-like jet"); chr_989 U_AK_07 = F-63 Super Wasp and F-63E Super Wasp, while chr_977 U_AK_03 = F-63 Wasp. Two aircraft models have no entity (E_FG_14, O_BM_01) and one entity is the placeholder 名称未設定 ("name not set") on O_BM_00. 160 aircraft models link to tech-tree chips by name.
  - Enemy ships: all 230 named by class (chr_1230 = DD Akizuki / DD Otsuki, chr_1415 = BB Hood / BB Frif, chr_1294 = BB Yamato plus three event ships).
  - Superweapons: BOS00 Wirbelwind (also Perfect Platter), BOS01 Dreadnought (also Nautilus), BOS02 Duel Crater, BOS03 Archaeopterix, BOS04 Harima, BOS05 / BOS05A Musspellheim, BOS06 Dora Durhi with BOS06A/B Locomotive and BOS06C Measurement radar, BOS07 Habakkuk, BOS08 Trollsegur, BOS09 Vogel Sumera with BF090 Laser Pod, BOS10 Arahabaki (also Amaterasu), BOS11 Druna Skass (also Mini Druna Skass), BOS12 Hell Atsche with BOS12A/B Support 1-4 and BF120 Mirror, BOS13 Leviathan, BOS14 Ragnarok, BOS15 Lord of Terror.
  - Superweapon parts without a name of their own (33 models: `BFnnp`, `BOSnnp`): the name encodes the boss, e.g. BF062 = part 2 of BOS06. These are weapons, turrets or damaged sections that do not map to a whole entity. Labelled as inferred.
  - Map objects: 114, named by the game (Crane, Radar, Lighthouse, Villa Amagi ...). Dock scenery (121) and most effects have no names.
- Player hulls (MDT_SHIP, 145 hull pairs): the game table has no names. The number of hull models per nation and type equals the number of hull chips per nation and type, so hull `nn` is taken as level `nn + 1` (`j_dd_sen_02H` = Jpn Destroyer 3); 131 link to a HULLS chip this way. The 13 special hulls (`a_*`) are listed as a set (for example `a_bb_sen_00..04` = Drillship, Duckship, Small Battleship, Genuine Drillship, Twin-hull Battleship in unknown order). All of this is inference from counts, marked "≈" in the viewer.
- Player weapons and structures (MDT_WEPH / MDT_WEPL): labelled from the file name only (`w_ho` gun, `w_ko` high-angle, `w_ki` machine gun, `w_gy` torpedo, `w_ms` missile, `kaa` forward bridge, `kab` aft bridge, `ent` funnel ...). Which tech-tree item uses which file is not resolved.

## 5. Multi-part models

Full list of node offsets: `notes/model_placement.md`.

- Format: header tables of positions (s16 x, y, z + scale) and rotations (65536 = full turn); per node a parent index and an animation track of (position index, rotation index) per frame. Frame 0 is the rest pose. One position unit is 2 vertex units (8 in the two models with 32-bit vertices, BOS05 and BOS05A).
- The factor 2 was measured, not read from the game code: of 13 helicopters, 8 put the rotor hub on top of the mast for a factor between 2.01 and 2.04, 3 for 2.09 to 2.25, and 2 gave no usable measurement; 2 was taken as the value. The factor 8 was chosen so that Musspellheim's turrets sit on its deck and its two hulls separate. Both look right in the viewer.
- 601 full-detail meshes have more than one node; in 525 at least one node is moved or rotated: 209 enemy ships (turrets, directors), 166 player weapons (barrels), 73 player ship parts, 23 superweapons, 15 aircraft, 16 map objects.
- Helicopters: main rotor is node 2 under an empty pivot node 1. SH-60J / UH-60J hub at z 488, AS332L 644, EH101 600, CH-47 two rotors at (0, -1220, 482) and (0, 1252, 794), RAH-66 554. Rotors have 4 animation frames (quarter turns).
- Other frames are animation or damage states. Only one node in the whole game is hidden in the rest pose (BOS01 node 15, scale 0). The viewer shows frame 0 only; turret and rotor animation and the damaged states of bosses are not exported.

## Follow-ups from the viewer review (same day)

- **Dock vs in-game model.** In every MDT pair the `H` file is the dock (shipyard) model and the `L` file the model used in the game (user-confirmed). The viewer lists them as "Duckship (Dock)" / "Duckship (In-game)".
- **Special battleship hulls (user-identified):** `a_bb_sen_00` Drillship, `01` Duckship, `02` Small Battleship, `03` Twin-hull Battleship, `04` Genuine Drillship. `a_dd_sen_01` is the Twin-hull Destroyer by width (inferred). Still open: `a_dd_sen_00` / `02` (Small Destroyer vs Mini Destroyer) and `a_ca_sen_00` / `01` (Twin-hull Cruiser vs Special Cruiser).
- **"Drift ice" (流氷).** The game text gives this name to six auxiliary models. Checked in the viewer: chr_1684, chr_1686 and chr_1688 are ice floes; chr_1678, chr_1680 (same hull as Yomotsukaze) and chr_1682 are warships. The three ships are listed as "Auxiliary ship (listed as "Drift ice")" until their real names are known.
- **Transports.** E_CV_07 "YU Collossus" and E_CV_08 "YU Transport" carry carrier model names but are transports; they are classed as Transport (user-confirmed).
- Japanese entity names are shown in English (`JA` table in `tools/model_entities.py`).
- Tech tree page: aircraft and hull chips show a thumbnail viewer (`web/models/chips.json`); system chips show the systems guide text (`tools/system_info.py`); engine chips show output / efficiency / purge / weight (`tools/engine_info.py`); the High Gravity Shield and Ammo-Assembler are yellow "not on tree" chips under DEFENSE and ATTACK (kill awards for 100 and 999 superweapons).

## Superweapons on the campaign page

- `tools/build_bosses.py` writes `web/models/bosses.json`: for each of the 16 superweapons the main model (`BOSnn`) and its components (`BOSnnA/B/C` units, named `BFnn?` parts, unnamed non-effect parts with 90+ vertices). Units that share a model are listed once per entity (Hell Atsche: main + Support 1, 2, 3, 4 + Mirror + three unnamed parts).
- The mission panel (`web/campaign.html`) shows one block per boss of the mission (names from the Boss Rush list, guide spellings such as "Dual Crater" mapped to the game text), each with a thumbnail that opens the model viewer.
- **Assembly is not solved.** The models are not placed relative to each other in the model files (each support is centred on its own origin), so components are shown side by side, not assembled. What the investigation ruled out:
  - `DBGM/*.W` and `DBG2/*.W` are **music** (`LPCM` = linear PCM audio), not mission data.
  - `MAP.BIN` holds map meshes (`PSM0`, `PSC1`) and `PSB5` sky-dome spheres, no unit placements found.
  - `BEV.BIN` entries 206-281 are the **mission scripts**, one per mission in campaign order (entry = 206 + position; first bytes: u32 unit count, mission code string such as `FAR_C_660`, the Shift-JIS mission title, then 16-byte records: opcode, arguments, map-grid coordinates, and the in-mission dialogue text). They contain no entity-table row ids (searched for the Hell Atsche rows 611-616), so the bosses are not spawned by entity row there. Decoding the opcodes was not attempted.
  - The empty nodes of the boss models are muzzle / effect points (Hell Atsche, Dora Durhi, Vogel Sumera, Habakkuk checked), not support attachment points.
  - The entity table does list Hell Atsche (row 611) directly followed by Support 1-4 (612-615) and Mirror (616), which supports the "main body + four supports" structure, but gives no positions.
  Open leads: decode the BEV opcodes (the `0x13 0x0b` records carry coordinates), or look in the executable for boss setup code.

## Not done / open

- The viewer exports CHR and MDT_SHIP only (1,044 models, 100 MB); MDT_WEPH / MDT_WEPL are audited but not exported.
- Flat-coloured faces are drawn grey in the viewer instead of in their table colour.
- Rotation order for nodes that turn about more than one axis is assumed (Z, then Y, then X); nearly all rotations are about a single axis.
- Hull -> chip links for special hulls and all weapon / structure -> item links are open.
