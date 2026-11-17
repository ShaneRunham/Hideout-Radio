# Vice Radio: 24/7 80s station. Shane's own music (from the tablet, on the RAID) shuffled, with a block from a
# free 80s internet station every few songs. 6 s crossfades between songs, no DJ.
# Stream: http://127.0.0.1:3004/vice-radio (tailnet https://fedora.tailnet.ts.net:8447/vice-radio)

settings.log.stdout := true
settings.log.file := false
settings.log.level := 3
# Loudness: scan.py (radio-scan.timer) measures each song once and writes library.m3u with its gain
# (annotate:liq_normalize_track_gain=...); normalize_track_gain applies it. Scanning here, just before each song,
# decoded whole 192 kHz FLACs and made the stream fall behind and skip.
# lyrics tags are too long to recode and only fill the log
settings.request.metadata_decoders.recode.exclude := [...settings.request.metadata_decoders.recode.exclude(), "lyrics", "unsyncedlyrics"]

LOCAL_SONGS = 4     # own songs between visits to an internet station
FAV_EVERY = 20      # one favourite (favourites.txt, via scan.py) after this many shuffled own songs
LIVE_SONGS = 2      # full songs played on the station (after joining the one already playing)
FADE = 6.

# ---- sources ----
def tag(name, s) =
  metadata.map(fun (_) -> [("vice_src", name)], s)
end
def station_name(name, s) =
  metadata.map(fun (_) -> [("vice_station", name)], s)
end

# Whole library shuffled, every song once per round before any repeat; picks up added/removed files
own = playlist(id="local", mode="randomize", reload_mode="watch", "/radio/library.m3u")
# Shane's current favourites (2026-11-17: Kool & The Gang - Fresh) on top of their turn in the shuffle; an empty
# favourites list is never ready, so rotate just keeps playing the shuffle
favs = playlist(id="favourites", mode="randomize", reload_mode="watch", "/radio/favourites.m3u")
local = rotate(weights=[FAV_EVERY, 1], [own, favs])
local = normalize_track_gain(local)
local = tag("local", local)

# Free 80s stations, kept connected (~320 kbps together) and buffered: the crossfade needs to read ahead, which a
# live input can't do on its own. Visits alternate between the two; if one is down the other is used.
# Gains bring each to about -18 LUFS, where ReplayGain puts the own songs (measured 2026-11-13).
# (SomaFM was tried and dropped: it refuses non-player clients.)
eighties_in = input.http(id="80s80s", "https://streams.80s80s.de/web/mp3-192/streams.80s80s.de/")
hits_in = input.http(id="181fm_awesome80s", "http://listen.181fm.com/181-awesome80s_128k.mp3")
# buffer: at a song change the crossfade reads ~12 s ahead (end of one track + start of the next); the 1 s/10 s default
# ran dry there, the station looked "not ready" and the visit ended after one song
eighties = buffer(buffer=12., max=25., station_name("80s80s", amplify(0.45, eighties_in)))           # -11.2 LUFS, -7 dB
hits = buffer(buffer=12., max=25., station_name("181.FM Awesome 80s", amplify(0.52, hits_in)))      # -12.4 LUFS, -5.6 dB
pick = ref(0)
def use_eighties() = pick() mod 2 == 0 and eighties.is_ready() or not hits.is_ready() end
live = switch(track_sensitive=false, [({use_eighties() and eighties.is_ready()}, eighties), ({hits.is_ready()}, hits)])
live = tag("live", live)
# a live stream can't be skipped: leaving inserts a track mark into it instead, so the switch moves on at once
# (sources have .insert_metadata built in since Liquidsoap 2.2; the old insert_metadata() wrapper is deprecated)

# Stations send their ad breaks as titles: "181.fm - 181.FM - THIS STATION WILL CONTINUE AFTER THIS BREAK",
# "181.fm - Music Promo30", "Listen.FM - Listen.FM" (seen 2026-11-13). Any of these ends the visit at once.
def station_id(t) =
  l = string.case(lower=true, t)
  string.contains(substring=".fm", l) or string.contains(substring="80s80s", l) or string.contains(substring="promo", l)
    or string.contains(substring="advert", l) or string.contains(substring="break", l)
end

# ---- schedule ----
# Own songs are counted by track (each file starts with its tags). Station songs are counted by title changes:
# a stream's track marks often come without metadata (and are not songs), so counting tracks ended visits early.
mode = ref("local")
count = ref(0)
joined = ref(false)
live_title = ref("")
radio = switch(track_sensitive=true, [({mode() == "live" and live.is_ready()}, live), ({true}, local)])
sched = radio
def leave_station(why) =
  log.important(label="vice", "#{why}: back to own music")
  mode := "local"
  count := 0
  # now, with the usual crossfade (skip() on a live stream waited for its next song: 19 s once)
  thread.run(fun () -> live.insert_metadata(new_track=true, [("vice_src", "live")]))
end

# now playing (read by /now below), set here when a station visit starts: the joined song's tags went by earlier
now = ref([("title", "")])
started = ref(0.)

def on_new_track(m) =
  log.important(label="vice", "track #{m[\"vice_src\"]} (#{count()}, mode #{mode()}): #{m[\"artist\"]} - #{m[\"title\"]}")
  if m["vice_src"] == "local" and mode() == "live" then
    log.important(label="vice", "station not ready: back to own music")
    # no station was up (or it ran dry mid-visit): back to own music
    now := m
    started := time()
    mode := "local"
    count := 1
  elsif m["vice_src"] == "local" then
    now := m
    started := time()
    count := count() + 1
    if count() == LOCAL_SONGS then
      # last own song before a station visit: switch over when it ends
      mode := "live"
      count := 0
      joined := false
    elsif count() == 1 then
      # back from a station: use the other one next time
      pick := pick() + 1
    end
  elsif mode() == "live" and not joined() then
    # just switched to the station, mid-song: that song counts as 0
    joined := true
    count := 0
    st = if use_eighties() then "80s80s" else "181.FM Awesome 80s" end
    lm = (if use_eighties() then eighties_in.last_metadata() else hits_in.last_metadata() end) ?? []
    live_title := lm["title"]
    now := [("vice_src", "live"), ("vice_station", st), ("title", lm["title"]), ("artist", lm["artist"])]
    if station_id(lm["title"]) then leave_station("joined during a break") end
    started := time()
  end
end
radio.on_track(synchronous=true, on_new_track)

def on_live_meta(m) =
  if mode() == "live" and joined() and m["title"] != "" and m["title"] != live_title() then
    live_title := m["title"]
    if station_id(m["title"]) then
      leave_station("station break (#{m[\"title\"]})")
    else
      now := m
      started := time()
      count := count() + 1
      log.important(label="vice", "station song #{count()}: #{m[\"title\"]}")
      # songs 1..LIVE_SONGS play in full; when the next one starts, go back to own music at its first track mark
      if count() == LIVE_SONGS + 1 then
        mode := "local"
        count := 0
      end
    end
  end
end
live.on_metadata(synchronous=true, on_live_meta)

# ---- transitions ----
# Between own songs and in/out of a station: 6 s crossfade. Between two songs on the same station: leave the
# station's own segue alone (the metadata marks the change only roughly).
def transition(a, b) =
  if a.metadata["vice_src"] != "local" and b.metadata["vice_src"] != "local" then
    # both sides on the station (or a station track mark without tags): its own segue, untouched
    sequence([a.source, b.source])
  else
    add(normalize=false, [fade.out(duration=FADE, a.source), fade.in(duration=FADE, b.source)])
  end
end
radio = cross(duration=FADE, transition, radio)

# ---- now playing: GET /now (JSON) on port 8001 (host 3005), for Vice Home (via vice-tv) and the HA panel ----
# (Set where songs are chosen, not after the crossfade: after a skip the next song's tags never came through it, so
# now-playing stuck on the old song. It updates a few seconds before the change is heard.)
def now_json(_) =
  m = now()
  artist = ref(m["artist"])
  title = ref(m["title"])
  if artist() == "" then
    # stations send "Artist - Title" in one field
    parts = string.split(separator=" - ", title())
    if list.length(parts) > 1 then
      artist := list.hd(parts)
      title := string.concat(separator=" - ", list.tl(parts))
    end
  end
  # album folder relative to /music ("Artist/Album"): the cover's name is derived from it
  d = path.dirname(m["filename"])
  album = if m["vice_src"] == "local" and string.length(d) > 7 then string.sub(d, start=7, length=string.length(d) - 7) else "" end
  http.response(content_type="application/json; charset=utf-8",
    headers=[("Access-Control-Allow-Origin", "*"), ("Cache-Control", "no-store")],
    data=json.stringify({src=m["vice_src"], station=m["vice_station"], artist=artist(), title=title(),
                         album=m["album"], dir=album, since=started()}))
end
harbor.http.register.simple(port=8001, "/now", now_json)  # own port: on 8000 it hides the stream (404)

# ---- skip: POST /skip (the TV through vice-tv, the HA panel through the tailnet) ----
# Own songs: ends this one (the usual 6 s crossfade into the next). On a station visit a stream's song can't be
# skipped, so it ends the visit and goes back to own music. Presses within 4 s of the last count once.
last_skip = ref(0.)
def skip_handler(_) =
  if time() - last_skip() > 4. then
    last_skip := time()
    if mode() == "live" and joined() then
      leave_station("skip")
    else
      log.important(label="vice", "skip: next song")
      sched.skip()
    end
  end
  http.response(content_type="application/json", headers=[("Access-Control-Allow-Origin", "*")], data='{"ok":true}')
end
harbor.http.register.simple(port=8001, method="POST", "/skip", skip_handler)
radio = mksafe(radio)

# burst: a new listener gets ~4 s at once (default 64 KB = 2 s), so players start without waiting for real-time data
output.harbor(%mp3(bitrate=256, samplerate=44100, stereo=true), port=8000, mount="vice-radio", burst=131072, headers=[("Access-Control-Allow-Origin", "*")], radio)  # 256 KB (8 s) reset every client after the first
