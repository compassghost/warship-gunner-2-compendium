"""Extract the game's music (DBGM/B01-B27.W and DBG2/B30-B47.W, 44 tracks) to standard WAV files in music/, plus data/music.json.
File format ('LPCM', found in this project): 0x800-byte header = 'LPCM', u32 total sample frames, u32 loop start, u32 loop end (frame indices, end inclusive),
rest zero; then raw interleaved signed 16-bit little-endian stereo, 4 bytes per frame, frames x 4 bytes. Sample rate 48000 Hz (B11 is exactly 5,280,000 frames = 110.000 s).
The loop points are written into each WAV as a 'smpl' chunk (players that honour it loop seamlessly) and listed in data/music.json.
Run: python tools/extract_music.py [output_dir]      Needs no third-party packages."""
import os, sys, struct, glob, json
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC = os.path.join(ROOT, 'iso_extract')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'music')
RATE, CH, BITS = 48000, 2, 16

def wav_header(frames, loop):
    data = frames * CH * BITS // 8
    fmt = struct.pack('<HHIIHH', 1, CH, RATE, RATE * CH * BITS // 8, CH * BITS // 8, BITS)
    smpl = struct.pack('<9I', 0, 0, 1_000_000_000 // RATE, 60, 0, 0, 0, 1, 0) + struct.pack('<6I', 0, 0, loop[0], loop[1], 0, 0)      # one forward loop, play count 0 = endless
    body = b'WAVE' + b'fmt ' + struct.pack('<I', len(fmt)) + fmt + b'smpl' + struct.pack('<I', len(smpl)) + smpl + b'data' + struct.pack('<I', data)
    return b'RIFF' + struct.pack('<I', len(body) + data) + body

def main():
    os.makedirs(OUT, exist_ok=True); manifest = []
    for path in sorted(glob.glob(os.path.join(SRC, 'DBGM', '*.W')) + glob.glob(os.path.join(SRC, 'DBG2', '*.W'))):
        folder, base = os.path.basename(os.path.dirname(path)), os.path.splitext(os.path.basename(path))[0]
        with open(path, 'rb') as f:
            head = f.read(0x800); magic, frames, ls, le = struct.unpack_from('<4sIII', head, 0)
            assert magic == b'LPCM', path
            name = '%s_%s.wav' % (folder, base)
            with open(os.path.join(OUT, name), 'wb') as o:
                o.write(wav_header(frames, (ls, le))); left = frames * 4
                while left:
                    chunk = f.read(min(left, 1 << 20)); assert chunk, 'short file ' + path
                    o.write(chunk); left -= len(chunk)
        manifest.append(dict(file=name, source='%s/%s.W' % (folder, base), frames=frames, seconds=round(frames / RATE, 3), loop_start=ls, loop_end=le,
                             loop_start_s=round(ls / RATE, 3), loop_end_s=round(le / RATE, 3), size_mb=round((frames * 4 + 44) / 1048576, 1)))
        print(name, manifest[-1]['seconds'], 's', 'loop %.1f-%.1f s' % (ls / RATE, le / RATE), flush=True)
    json.dump(dict(rate=RATE, channels=CH, bits=BITS, tracks=manifest), open(os.path.join(ROOT, 'data/music.json'), 'w'), indent=1)
    print(len(manifest), 'tracks,', round(sum(m['seconds'] for m in manifest) / 60, 1), 'minutes,', round(sum(m['size_mb'] for m in manifest)), 'MB ->', OUT)

main()
