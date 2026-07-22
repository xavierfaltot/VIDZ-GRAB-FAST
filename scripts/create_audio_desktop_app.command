#!/bin/zsh
set -e

APP_NAME="VIDZ AUDIO FAST"
REPO_DIR="${0:A:h:h}"
APP_DIR="$HOME/Desktop/$APP_NAME.app"

mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
cp "$REPO_DIR/src/vidz_grab_fast/assets/vidz_grab_fast_logo.png" "$APP_DIR/Contents/Resources/VIDZ_AUDIO_FAST.png"

cat > "$APP_DIR/Contents/MacOS/$APP_NAME" <<SCRIPT
#!/bin/zsh
set -e
cd "$REPO_DIR"
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi
if ! ".venv/bin/python" -c "import PySide6.QtWidgets" >/dev/null 2>&1; then
  ".venv/bin/python" -m pip install -r requirements.txt
fi
exec ".venv/bin/python" run_audio.py
SCRIPT
chmod +x "$APP_DIR/Contents/MacOS/$APP_NAME"

cat > "$APP_DIR/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDisplayName</key>
  <string>$APP_NAME</string>
  <key>CFBundleExecutable</key>
  <string>$APP_NAME</string>
  <key>CFBundleIconFile</key>
  <string>VIDZ_AUDIO_FAST.png</string>
  <key>CFBundleIdentifier</key>
  <string>com.rushoperator.vidzaudiofast</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

touch "$APP_DIR"
echo "Created $APP_DIR"
