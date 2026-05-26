#!/usr/bin/env bash
set -euo pipefail
bundle="${1:-QuickBrush.glyphsTool}"
exe="$bundle/Contents/MacOS/plugin"
plist="$bundle/Contents/Info.plist"

if [[ ! -f "$plist" ]]; then
  echo "Missing Info.plist: $plist" >&2
  exit 1
fi
if [[ ! -f "$exe" ]]; then
  echo "Missing executable: $exe" >&2
  exit 1
fi
if [[ ! -x "$exe" ]]; then
  echo "Executable is present but not executable, fixing chmod +x"
  chmod +x "$exe"
fi

python3 - "$plist" <<'PY'
import plistlib,sys
p=sys.argv[1]
with open(p,'rb') as f:
    d=plistlib.load(f)
assert d.get('CFBundleExecutable')=='plugin', 'CFBundleExecutable must be plugin'
assert 'PyMainFileNames' in d and 'plugin.py' in d['PyMainFileNames'], 'PyMainFileNames must include plugin.py'
assert 'Principal Classes' in d and len(d['Principal Classes']) > 0, 'Principal Classes must define at least one plugin class'
print('Plist keys look good')
PY

echo "Bundle looks valid: $bundle"
