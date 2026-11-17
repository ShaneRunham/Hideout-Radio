#!/usr/bin/env python3
"""Vice Radio library scan: measure each song's loudness once and write the station's playlist.

Liquidsoap used to scan every song (a full decode, many are 192 kHz FLAC) right before playing it, which made the
stream fall behind and skip (2026-11-13). Now this runs from radio-scan.timer: new or changed files are measured
with ffmpeg's EBU R128 filter (cached in loudness.json), and library.m3u lists every song with its gain:
    annotate:liq_normalize_track_gain="-3.20 dB":/music/Artist/Album/01 - Song.flac
Gain = -18 LUFS (ReplayGain's level) minus the song's loudness, capped so its true peak stays under -1 dBTP.
library.m3u is only rewritten (in place, so Liquidsoap's file watch sees it) when its contents change.
favourites.txt (one path per line, relative to the music folder, # comments) -> favourites.m3u the same way: the
station slots one of them in every FAV_EVERY own songs (radio.liq), on top of their normal turn in the shuffle.
"""
import json
import os
import re
import subprocess
import sys

MUSIC = "/mnt/storage/media/music"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "loudness.json")
PLAYLIST = os.path.join(HERE, "library.m3u")
FAV_LIST = os.path.join(HERE, "favourites.txt")
FAV_PLAYLIST = os.path.join(HERE, "favourites.m3u")
AUDIO = (".flac", ".mp3", ".m4a", ".ogg", ".opus", ".wav")
TARGET, CEILING = -18.0, -1.0


def measure(path):
    """(integrated LUFS, true peak dBTP) or None."""
    r = subprocess.run(["nice", "-n", "19", "ffmpeg", "-nostdin", "-hide_banner", "-i", path, "-map", "0:a:0",
                        "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    tail = r.stderr[r.stderr.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", tail)
    p = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", tail)
    if not i:
        return None
    return float(i.group(1)), (float(p.group(1)) if p and p.group(1) != "-inf" else -60.0)


def main():
    try:
        cache = json.load(open(CACHE))
    except (OSError, ValueError):
        cache = {}
    files = sorted(os.path.relpath(os.path.join(d, f), MUSIC) for d, _, fs in os.walk(MUSIC)
                   for f in fs if f.lower().endswith(AUDIO) and not f.endswith(".tmp.flac"))
    changed = False
    for rel in files:
        st = os.stat(os.path.join(MUSIC, rel))
        key = f"{st.st_size}:{int(st.st_mtime)}"
        if cache.get(rel, {}).get("key") == key:
            continue
        m = measure(os.path.join(MUSIC, rel))
        if m:
            cache[rel] = {"key": key, "lufs": m[0], "peak": m[1]}
            changed = True
            print(f"{m[0]:6.1f} LUFS {m[1]:5.1f} dBTP  {rel}", flush=True)
    for rel in [r for r in cache if r not in files]:   # removed from the library
        del cache[rel]
        changed = True
    if changed:
        with open(CACHE + ".tmp", "w") as f:
            json.dump(cache, f, indent=0)
        os.replace(CACHE + ".tmp", CACHE)
    def entry(rel):
        c = cache.get(rel)
        gain = min(TARGET - c["lufs"], CEILING - c["peak"]) if c else 0.0
        return f'annotate:liq_normalize_track_gain="{gain:+.2f} dB":/music/{rel}'
    write(PLAYLIST, [entry(rel) for rel in files])
    try:
        favs = [x.strip() for x in open(FAV_LIST) if x.strip() and not x.lstrip().startswith("#")]
    except OSError:
        favs = []
    missing = [x for x in favs if x not in files]
    for x in missing:
        print(f"favourites.txt: not in the library: {x}", flush=True)
    write(FAV_PLAYLIST, [entry(rel) for rel in favs if rel in files])


def write(path, lines):
    text = "\n".join(lines) + "\n" if lines else ""
    try:
        old = open(path).read()
    except OSError:
        old = None
    if text != old:
        with open(path, "w") as f:   # in place: keeps the inode Liquidsoap watches
            f.write(text)
        print(f"{os.path.basename(path)}: {len(lines)} songs", flush=True)


if __name__ == "__main__":
    sys.exit(main())
