#!/usr/bin/env python3
"""One-off (2026-11-13): convert the station's 96/192 kHz FLAC copies to 44.1 kHz/24-bit FLAC (soxr, tags and cover
kept). The stream goes out at 44.1 kHz anyway; resampling hi-res files live, two at once during a crossfade, made the
station fall behind (0.4-0.5 s catch-ups). Originals stay on the tablet's SD card. Safe to rerun: skips 44.1 kHz files.
"""
import os
import subprocess

MUSIC = "/mnt/storage/media/music"
done = 0
for d, _, files in os.walk(MUSIC):
    for f in sorted(files):
        if not f.lower().endswith(".flac"):
            continue
        src = os.path.join(d, f)
        rate = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate",
                               "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip().rstrip(",")
        if rate in ("44100", "48000", ""):
            continue
        tmp = src + ".tmp.flac"
        r = subprocess.run(["nice", "-n", "19", "ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-map", "0", "-map_metadata", "0",
                            "-c:v", "copy", "-c:a", "flac", "-af", "aresample=resampler=soxr:precision=28",
                            "-ar", "44100", "-sample_fmt", "s32", "-bits_per_raw_sample", "24", tmp])
        if r.returncode == 0 and os.path.getsize(tmp) > 0:
            os.replace(tmp, src)
            done += 1
            print(f"{rate} -> 44100  {os.path.relpath(src, MUSIC)}", flush=True)
        elif os.path.exists(tmp):
            os.remove(tmp)
            print(f"FAILED  {os.path.relpath(src, MUSIC)}", flush=True)
print(f"{done} converted", flush=True)
