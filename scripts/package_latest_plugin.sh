#!/usr/bin/env bash
set -euo pipefail

bundle="${1:-QuickBrush.glyphsTool}"
out_dir="${2:-dist}"
archive_name="${3:-QuickBrush-latest.glyphsTool.zip}"

if [[ ! -d "$bundle" ]]; then
  echo "Bundle directory not found: $bundle" >&2
  exit 1
fi

mkdir -p "$out_dir"
./scripts/verify_bundle.sh "$bundle" >/dev/null

archive_path="$out_dir/$archive_name"
rm -f "$archive_path"

# Export only the plugin bundle, no donor/dev files.
zip -qry "$archive_path" "$bundle"

echo "Created: $archive_path"
