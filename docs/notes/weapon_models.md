# Weapon part -> MDT_WEPH / MDT_WEPL model mapping

`data/weapon_models.json` is the hand-identified link list between tech-tree weapon parts and weapon models in `MDT_WEPH.BIN` (high-poly, the one the viewer uses) / `MDT_WEPL.BIN` (low-poly twin, same entry index).

## What is solved by the game's own tables, and what is not

- `DAT` entry 3 holds the model resource table and the entity class table (`tools/model_entities.py`). That links most entities (ships, aircraft, structures, bridges, funnels) to a model file by id. The chip table gives each weapon chip only its 1-barrel model.
- Weapon variants are not in those tables: the 2/3/4-barrel mounts, the AA mount variants (A/B/C) and the cal-length siblings (45Cal ... 75Cal share one model) have no table link. These were identified by eye in the viewer and are what the JSON file records.
- `MDT_WEPL` entry n is the low-poly version of `MDT_WEPH` entry n (same file name without the trailing `H`/`L`), so one link covers both.

## File format

```
{ "links": [ { "model": "w_ho_153", "group": "MAIN", "match": "^100\\.0cm Gun( \\d+Cal)?$", "label": "..." }, ... ],
  "no_model": [ ... ] }
```

- `model`: file name without the `H`/`L` suffix. File name prefixes: `w_ho` gun, `w_ko` high-angle gun, `w_ki` machine gun, `w_gy` torpedo, `w_ms` missile.
- `group`: tech-tree group (`MAIN`, `TORPEDO`, `PROTO`, ...).
- `match`: regex tested against the chip's full name as the game's string table gives it. Barrel count is appended as ` 2brls` / ` 3brls` for the barrel variants, `(mount variant X)` for AA variants.
- A link without `group`/`match` only labels a model that no chip owns (a mount variant).
- Example of the barrel scheme: the 46 cm gun is `w_ho_130` / `133` / `136` / `139` for 1 / 2 / 3 / 4 barrels.
- AA mount variants used by `tools/build_designer.py`: machine guns 1107-1113 `w_ki_004`, 1114-1120 `w_ki_008` (carrier side mounts), 1125-1128 `w_ki_012`; high-angle 1028-1041 `w_ko_001`.

`tools/model_entities.py` and `tools/build_designer.py` read the file (optional, so a fresh checkout still runs). Entries were identified by comparing model shape, barrel count and size against the part list; they are observations, not decoded from a table, and a few may be wrong. Corrections welcome.