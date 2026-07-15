# VIDZ GRAB FAST

Acquire only.

VIDZ GRAB FAST downloads or imports one video and writes exactly two finished files into the chosen destination folder:

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

Or double-click `VIDZ GRAB FAST.command` after dependencies have been installed once.

`ffprobe` must be available on `PATH`; it is used only to verify that the acquired file is readable media. Install FFmpeg on macOS with:

```bash
brew install ffmpeg
```

## Contract

Local imports copy the original file and never modify it. Because this module must output `.mp4` and must not transcode, local non-MP4 files are rejected.

URL imports use `yt-dlp` with cache disabled and download into a temporary system folder first. Only the final `.mp4` and `.source.json` are moved into the chosen destination.

Unavailable metadata fields are left empty.
