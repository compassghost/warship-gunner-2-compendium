# Warship Gunner 2 (PS2) format notes and tools

Research notes and Python tools for the North American PS2 release of *Warship Gunner 2* (SLUS-21387).
The companion site is the [Warship Gunner 2 Compendium](https://missionst.art).

**This repository contains no game data.** No ISO, no extracted models, textures, music, maps or story text.
You need your own copy of the game. The tools read files you extract from your own disc.

License: MIT (code and documentation). See `LICENSE`.

## What is here

| Path | Contents |
|---|---|
| `docs/pipeline.md` | Start here: archive container, compression, textures, the PSC1 model format, animation clips, the dry dock |
| `docs/workflow.md` | How the work was done (AI-assisted reverse engineering) and how results were checked |
| `docs/notes/` | The detailed research notes, in the order things were found. Some entries were later corrected; later sections supersede earlier ones |
| `tools/` | The decoders and exporters (Python 3) |
| `web/` | Viewer scaffold: model viewer, dry dock, bosses, boss animations, water, music player, flags. Code only; the JSON files are empty stubs (see below) |

## Using the tools

1. Extract your disc with 7-Zip into `iso_extract/` next to `tools/`.
2. `pip install -r requirements.txt` (Pillow and capstone are only needed by a few scripts; most use the standard library only).
3. Run a tool from the repository root, for example `python tools/inventory_archives.py`. Outputs go to `data/` (git-ignored) and `web/models/` (generated models and textures are git-ignored; the JSON stubs are tracked).

Start with `tools/wg2.py` (archive index reader, the game's LZ decompressor, SHTX image decoder) and `tools/psc1.py` (model parser).

## The web viewers

The pages in `web/` are the viewer code with no data: the JSON files are empty (`[]` or `{}`) and there are no models, textures or music. Generate the data from your own disc with the tools (`export_models.py`, `export_anim.py`, `build_drydock.py` and so on, which write to `web/models/`), then serve the folder with any static server, for example `python -m http.server --directory web`. Until the data exists the pages show a notice. The tech tree page (`tree.html`) is included. Generate its data with `python tools/decode_rd_tree.py`, `python tools/full_names.py` and `python tools/build_tree.py`: the builder writes `tree.json` (positions, costs, prerequisites, unlock conditions) and `weapon_stats.json`, and fills the hull, engine, system, facility, weapon and aircraft stat panels from the game's own tables (see `docs/notes/tree_stats.md`). It reads no third-party data. Set `WG2_OUT` to write somewhere other than `web/`. The ship designer pages (`designer.html`, `designer3d.html`, `designer_models.html`) are included too: `python tools/model_entities.py`, `python tools/export_models.py` and `python tools/build_designer.py` generate `designer.json` from the game's tables (see `docs/notes/designer_data.md`), and `tools/extract_designer_sprites.py` writes the part pictures. The mission (`campaign.html`), story (`story.html`), world map (`worldmap.html`) and rewards (`rewards.html`) pages are included as UI mock-ups only: their data files are empty stubs and there is no builder for them here, because the original builders read fan guides (mission lists, objectives, rewards, medal requirements) and the story page shows the game's script text. `tools/bev_script.py` documents how the mission scripts (`BEV.BIN` entries 206-281) are laid out if you want to build your own data. `worldmap.html` expects a plain lat/lon world map SVG at `maps/world_simplemaps.svg` (the original uses the free non-commercial map from simplemaps.com, which is not redistributed here).

## What is not here, and why

Some tools in the original project cross-checked decoded values against third-party fan guides, wiki pages and screenshots, or generated
data for a website. Those were left out because they depend on material that is not mine to relicense. The formats they relied on
are still described in the notes (for example the part table layout and the tech-tree master table in `docs/notes/formats.md`).
Several notes mention such tools by name; treat those references as historical.

The fan guides used for cross-checking were GameFAQs guides by their respective authors and are credited, not republished.

## PSP version

All of this comes from the PS2 disc. I have not looked at the PSP release. The two games may share formats, but that is untested.

## Corrections welcome

Open an issue or a pull request if you find a note that is wrong. Several early notes contain corrections inline and are kept as written.
