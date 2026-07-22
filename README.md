# VIDZ GRAB FAST

Acquire only.

VIDZ GRAB FAST downloads videos from pasted URLs and writes exactly two finished files per video into the chosen destination folder:

```text
clean_name.mp4
clean_name.source.json
```

It does not scan, analyze, transcribe, tag, filter, organize, rename by AI, create thumbnails, create databases, or integrate with VIDZ FLTR/PLAY. The only metadata file is the provenance JSON.

## Run

```bash
cd "/Users/faltot/Documents/Claude/Projects/RUSH OPERATOR/vidz_grab_fast"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

Or double-click `VIDZ GRAB FAST.command` after dependencies have been installed once. The desktop UI is intentionally limited to URLS, artist name, output folder, and GRAB.

Paste one URL per line. YouTube playlists are expanded into individual videos before download. The app accepts up to 150 videos in one run. Pressing Enter inside URLS adds a new line; only the GRAB button starts acquisition.

To create or refresh the macOS desktop app:

```bash
./scripts/create_desktop_app.command
```

That creates `~/Desktop/VIDZ GRAB FAST.app`.

`ffprobe` must be available on `PATH`; it is used only to verify that the acquired file is readable media. Install FFmpeg on macOS with:

```bash
brew install ffmpeg
```

## Audio Companion

Direct MP3 download is technically simpler if the only goal is audio. For the VIDZ/RUSH chain, the cleaner production rule is:

```text
VIDZ GRAB FAST  -> acquire MP4 master + provenance
VIDZ AUDIO FAST -> derive MP3 from that MP4
```

This keeps GRAB impossible to confuse with SCAN, FLTR, PLAY, or any editing tool. GRAB still only acquires video and preserves origin. VIDZ AUDIO FAST is a separate utility that converts a folder of `.mp4` files into:

```text
clean_name.mp3
clean_name.audio.source.json
```

The audio source JSON embeds the original `.source.json` when it exists. It does not analyze, tag, scan, transcribe, or rename by AI.

Run the audio companion with:

```bash
python run_audio.py
```

Or double-click `VIDZ AUDIO FAST.command`.

To create or refresh the macOS desktop app:

```bash
./scripts/create_audio_desktop_app.command
```

That creates `~/Desktop/VIDZ AUDIO FAST.app`.

## SONO PLAY LITE

SONO PLAY LITE is the light playback companion for audio folders. Choose a sound folder, press `BPM`, then press `PLAY`. The app analyzes local audio tempo and plays the list from lowest BPM to highest BPM, so the energy climbs.

Supported inputs:

```text
mp3, wav, flac, aiff, aac, m4a, mp4
```

This is a lite player: BPM analysis, sorted queue, sequential playback. It does not tag, rewrite, normalize, beatmatch, crossfade, or alter the source files.

Run it with:

```bash
python run_sono.py
```

Or double-click `SONO PLAY LITE.command`.

To create or refresh the macOS desktop app:

```bash
./scripts/create_sono_desktop_app.command
```

That creates `~/Desktop/SONO PLAY LITE.app`.

## Contract

URL imports use `yt-dlp` with cache disabled and download into a temporary system folder first. Only the final `.mp4` and `.source.json` are moved into the chosen destination.

Unavailable metadata fields are left empty.
