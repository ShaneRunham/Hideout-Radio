#!/usr/bin/env python3
"""Vice Radio library scan: measure each song's loudness once and write the station's playlist.

Liquidsoap used to scan every song (a full decode, many are 192 kHz FLAC) right before playing it, which made the
stream fall behind and skip (2026-11-13). Now this runs from radio-scan.timer: new or changed files are measured
with ffmpeg's EBU R128 filter (cached in loudness.json), and library.m3u lists every song with its gain:
    annotate:liq_normalize_track_gain="-3.20 dB":/music/Artist/Album/01 - Song.flac
Gain = -18 LUFS (ReplayGain's level) minus the song's loudness, capped so its true peak stays under -1 dBTP.
library.m3u is only rewritten (in place, so Liquidsoap's file watch sees it) when its contents change.
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
    lines = []
    for rel in files:
        c = cache.get(rel)
        gain = min(TARGET - c["lufs"], CEILING - c["peak"]) if c else 0.0
        lines.append(f'annotate:liq_normalize_track_gain="{gain:+.2f} dB":/music/{rel}')
    text = "\n".join(lines) + "\n"
    try:
        old = open(PLAYLIST).read()
    except OSError:
        old = None
    if text != old:
        with open(PLAYLIST, "w") as f:   # in place: keeps the inode Liquidsoap watches
            f.write(text)
        print(f"library.m3u: {len(lines)} songs", flush=True)


if __name__ == "__main__":
    sys.exit(main())
