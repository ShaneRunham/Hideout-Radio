# 📻 Vice Radio

A 24/7 80s station running on [Liquidsoap](https://www.liquidsoap.info/). It shuffles my own music library and drops
in a block from a free 80s internet station every few songs, with 6-second crossfades between tracks.

### How it works

- `radio.liq` is the station: sources, the rotation between my songs and the internet station, crossfades and the stream
- `scan.py` (every 15 minutes, `radio-scan.timer`) measures each new song's loudness once and writes the playlist with
  its gain, so every song plays at the same volume
- `downsample.py` keeps very high-resolution files light enough to stream

It plays on the TV ([VICE Home](https://github.com/ShaneRunham/VICE-Home)), in Discord
([VICE Bot](https://github.com/ShaneRunham/VICE-Bot)) and anywhere on my Tailscale network.

> A cleaned copy of my private repo, updated automatically.
