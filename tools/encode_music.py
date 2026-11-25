"""Encode the extracted music for the web player and write web/music/tracks.json.
  python tools/encode_music.py --ffmpeg PATH [--opus 96] [--aac 128] [--only DBGM_B27]   encode music/*.wav -> web/music/opus/*.ogg (Opus) and web/music/aac/*.m4a (AAC)
  python tools/encode_music.py --manifest-only                                           just rebuild tracks.json from the files that exist
The manifest lists each track's loop points (from data/music.json) and which encoded files exist; the player picks Opus, then AAC, then WAV (testing only).
Opus and Ogg Vorbis are gapless; AAC is the fallback for browsers without Opus (older Safari). Needs ffmpeg for encoding (not for --manifest-only)."""
import os, sys, json, subprocess, argparse
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
WEB = os.path.join(ROOT, 'web', 'music')
ap = argparse.ArgumentParser()
ap.add_argument('--ffmpeg'); ap.add_argument('--opus', type=int, default=96); ap.add_argument('--aac', type=int, default=128)
ap.add_argument('--only'); ap.add_argument('--manifest-only', action='store_true'); ap.add_argument('--no-aac', action='store_true')
a = ap.parse_args()
M = json.load(open(os.path.join(ROOT, 'data', 'music.json')))
for sub in ('opus', 'aac', 'wav'): os.makedirs(os.path.join(WEB, sub), exist_ok=True)

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise SystemExit('ffmpeg failed: ' + ' '.join(cmd) + '\n' + r.stderr[-800:])

if not a.manifest_only:
    ff = a.ffmpeg or 'ffmpeg'
    for t in M['tracks']:
        stem = os.path.splitext(t['file'])[0]
        if a.only and stem != a.only: continue
        src = os.path.join(ROOT, 'music', t['file'])
        run([ff, '-y', '-loglevel', 'error', '-i', src, '-map_metadata', '-1', '-c:a', 'libopus', '-b:a', '%dk' % a.opus, '-vbr', 'on', '-application', 'audio', os.path.join(WEB, 'opus', stem + '.ogg')])
        if not a.no_aac: run([ff, '-y', '-loglevel', 'error', '-i', src, '-map_metadata', '-1', '-c:a', 'aac', '-b:a', '%dk' % a.aac, '-movflags', '+faststart', os.path.join(WEB, 'aac', stem + '.m4a')])
        print(stem, 'encoded', flush=True)

tracks = []
for t in M['tracks']:
    stem = os.path.splitext(t['file'])[0]; files = {}
    for kind, sub, ext in (('opus', 'opus', '.ogg'), ('aac', 'aac', '.m4a'), ('wav', 'wav', '.wav')):
        if os.path.exists(os.path.join(WEB, sub, stem + ext)): files[kind] = '%s/%s%s' % (sub, stem, ext)
    if not files: continue
    tracks.append(dict(id=stem, group=stem.split('_')[0], n=stem.split('_')[1], frames=t['frames'], seconds=t['seconds'], loop_start=t['loop_start'], loop_end=t['loop_end'], files=files))
json.dump(dict(rate=M['rate'], tracks=tracks), open(os.path.join(WEB, 'tracks.json'), 'w'), separators=(',', ':'))
tot = {k: sum(os.path.getsize(os.path.join(WEB, t['files'][k])) for t in tracks if k in t['files']) for k in ('opus', 'aac', 'wav')}
print(len(tracks), 'tracks in the manifest;', {k: '%.1f MB' % (v / 1048576) for k, v in tot.items() if v})
