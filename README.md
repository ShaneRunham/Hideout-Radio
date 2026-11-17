# 📻 Vice Radio

<img src="https://raw.githubusercontent.com/ShaneRunham/ShaneRunham/main/screens/vice-radio/phone.jpg" alt="Vice Radio playing on the phone remote" width="32%">

A 24/7 80s station running on [Liquidsoap](https://www.liquidsoap.info/). It shuffles my own music library and drops
in a block from a free 80s internet station every few songs, with 6-second crossfades between tracks.

### How it plays

- **My music:** the whole library shuffled, every song once before any repeats; new albums join within 15 minutes
- **Station visits:** after every 4 of my songs it joins a free 80s station (alternating between two), plays the song that's on and two more, then comes back; it leaves early at an ad break
- **Favourites:** songs listed in `favourites.txt` get an extra turn after every 20 of my songs, on top of the shuffle
- **Same volume:** `scan.py` measures each song's loudness once and gives it a gain to -18 LUFS; the stations are turned down to match
- **Skip:** from the TV, the dashboards, the phone or Discord; on a station visit, skip goes back to my music

### Files

- `radio.liq` is the station: sources, the rotation, favourites, crossfades, now-playing (`/now`) and skip (`/skip`)
- `scan.py` (every 15 minutes, `radio-scan.timer`) writes `library.m3u` and `favourites.m3u` with each song's gain
- `downsample.py` keeps very high-resolution files light enough to stream

### Where it plays

On the TV ([VICE Home](https://github.com/ShaneRunham/VICE-Home)), on the dashboards and the phone remote, in Discord
([VICE Bot](https://github.com/ShaneRunham/VICE-Bot)) and anywhere on my Tailscale network.

> A cleaned copy of my private repo, updated automatically.
