# How the work was done

Most of the decoding was done in conversation with an AI coding assistant (Claude), driven by me. This page describes the method, since
that is what you asked about and it transfers to other games.

## The loop

1. **Inventory first.** Count entries per archive by their decompressed magic bytes (`tools/inventory_archives.py`). It showed at once that
   `MDT_*` archives are PSC1 + texture pairs and that `CHR.BIN` is mixed.
2. **Read the game's code, not just the data.** The executable is a MIPS ELF. A small disassembly helper (capstone) and a MIPS emulator
   (`tools/mips_emu.py`) were used to read the archive lookup, the decompressor, the tech-tree screen and the design screen. Decoding the data
   from the code that consumes it settled questions that guessing from hex dumps could not (for example the one-off numbering shift between
   file ids and archive entries).
3. **Write a decoder, export to a viewer, look at it.** A wrong UV or node order is obvious in a 3D viewer. Several bugs (palette
   swizzle, UV lookup order, node parent rule) were found that way, not by inspection of bytes.
4. **Verify against something independent.** Examples: tech-tree chip counts against in-game screenshots; stat tables against published guides;
   the designer formulas by running the game's own functions in the emulator and comparing all 530 pre-built designs.
5. **Keep a dated, corrected notes file.** Notes record what is confirmed and what is a hypothesis. When something turns out wrong, the note
   says so rather than being silently rewritten. This is why `notes/formats.md` has inline corrections.

## Habits that mattered

- Ask the assistant to state what it checked and how, and to mark anything unchecked as a hypothesis.
- Prefer an audit script over a one-off look: `tools/audit_models.py` re-checks every model after a change.
- Do not trust a first reading of an offset table. Check the first and last entries and the entry sizes against the file size.
- Keep generated data out of the source tree and regenerate it from the disc.

## Caveats

Assistant-written notes can sound more certain than the evidence. Where a note says "confirmed", it means checked against data or code; where
it says "hypothesis" or "probably", it is not. Please report errors.
