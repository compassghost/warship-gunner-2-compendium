"""Extract the ship flags/pennants from CHR.BIN to PNG (with alpha) + a JSON index for the web viewer.
Usage: python tools/extract_flags.py   (needs: pip install pillow; iso_extract/ present)"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(__file__))
import wg2
import flag_unlocks
from PIL import Image

ROOT = os.path.join(os.path.dirname(__file__), '..')
FIRST, LAST = 1762, 1826          # CHR.BIN entries holding 64x64 flag textures
UNUSED = range(1820, 1827)        # blank placeholder slots
HI_OFFSET = 66                    # 256x128 flag textures: entry = 64x64 entry - 66
NAMED = 32                       # 1762..1793 have names in the text table; 1794..1819 are the unnamed signal-flag set

PHONETIC = ['Alfa', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel', 'India', 'Juliett', 'Kilo', 'Lima', 'Mike',
            'November', 'Oscar', 'Papa', 'Quebec', 'Romeo', 'Sierra', 'Tango', 'Uniform', 'Victor', 'Whiskey', 'X-ray', 'Yankee', 'Zulu']

def text_table_names():
    f = open(os.path.join(ROOT, 'iso_extract/DAT.BIN'), 'rb')
    idx = wg2.read_index(f); o, s = idx[14]; f.seek(o)
    data = wg2.decompress(f.read(s))[0]
    start = data.index(b'Kingdom of Wilkia')
    names = []
    for part in data[start:start + 1200].split(b'\0'):
        if not part: continue
        t = re.sub(rb'#[A-Za-z]\d*', b'', part).decode('ascii', 'replace').strip()  # strip colour codes like #u85 / #Z
        names.append(t)
        if len(names) == NAMED: break
    return names

def main():
    names = text_table_names()
    f = open(os.path.join(ROOT, 'iso_extract/CHR.BIN'), 'rb'); idx = wg2.read_index(f)
    out = os.path.join(ROOT, 'web/flags'); os.makedirs(out, exist_ok=True)
    items = []
    for n, e in enumerate(range(FIRST, LAST + 1)):
        if e in UNUSED: continue
        o, s = idx[e]; f.seek(o)
        w, h, rgba = wg2.decode_shtx(wg2.decompress(f.read(s))[0])
        Image.frombytes('RGBA', (w, h), rgba).save(os.path.join(out, f'{e}.png'))
        if n < NAMED: name, src = names[n], 'game text table (DAT.BIN #14)'
        else:
            k = n - NAMED
            name, src = f'Signal Flag {chr(65 + k)} ({PHONETIC[k]})', 'unnamed in game data; identified visually as the international signal flag for this letter'
        kind, how, effect = flag_unlocks.UNLOCKS[n + 1] if n < NAMED else flag_unlocks.SIGNAL
        # the quarters' flag wall uses 256x128 versions with cloth shading, stored 66 entries earlier in the same order (1696..1753); 1754-1760 are blank
        hid = e - HI_OFFSET
        ho, hs = idx[hid]; f.seek(ho)
        hw, hh, hrgba = wg2.decode_shtx(wg2.decompress(f.read(hs))[0])
        os.makedirs(os.path.join(out, 'hi'), exist_ok=True)
        Image.frombytes('RGBA', (hw, hh), hrgba).save(os.path.join(out, 'hi', f'{hid}.png'))
        items.append({'id': e, 'file': f'flags/{e}.png', 'hires': f'flags/hi/{hid}.png', 'hires_id': hid, 'hires_width': hw, 'hires_height': hh,
                      'name': name, 'width': w, 'height': h, 'name_source': src,
                      'unlock_kind': kind, 'unlock': how, 'effect': effect, 'unlock_source': flag_unlocks.SRC})
    with open(os.path.join(ROOT, 'web/flags.json'), 'w', encoding='utf8') as j:
        json.dump(items, j, indent=1)
    print(len(items), 'flags written')

main()

