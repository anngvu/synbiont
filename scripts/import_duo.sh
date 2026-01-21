#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
IMPORT_DIR="$REPO_ROOT/ontology/imports"
TARGET_FILE="$IMPORT_DIR/duo.owl"
SOURCE_URL="https://raw.githubusercontent.com/EBISPOT/DUO/master/duo.owl"

mkdir -p "$IMPORT_DIR"

echo "Downloading $SOURCE_URL -> $TARGET_FILE"
# -L follow redirects, -o write to file, --fail for non-200 statuses
curl -L --fail --silent --show-error "$SOURCE_URL" -o "$TARGET_FILE"

echo "Done."
