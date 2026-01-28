#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
IMPORT_DIR="$REPO_ROOT/ontology/imports"
IMPORT_SPECS=(
  "duo https://raw.githubusercontent.com/EBISPOT/DUO/master/duo.owl"
  "prov https://www.w3.org/ns/prov-o"
)
ROBOT_CMD=${ROBOT_CMD:-$REPO_ROOT/tools/robot.jar}

mkdir -p "$IMPORT_DIR"

if [ ! -x "$ROBOT_CMD" ] && [ ! -f "$ROBOT_CMD" ]; then
  echo "Error: ROBOT jar not found at \"$ROBOT_CMD\". Set ROBOT_CMD to the jar path."
  exit 1
fi

run_robot_convert() {
  local input="$1"
  local output="$2"
  if [ -f "$ROBOT_CMD" ]; then
    java -jar "$ROBOT_CMD" convert -i "$input" -o "$output"
  else
    "$ROBOT_CMD" convert -i "$input" -o "$output"
  fi
}

for spec in "${IMPORT_SPECS[@]}"; do
  set -- $spec
  name="$1"
  url="$2"
  raw_file="$IMPORT_DIR/${name}.download"
  ttl_file="$IMPORT_DIR/${name}.ttl"

  echo "Downloading $name from $url"
  curl_opts=( -L --fail --silent --show-error )
  if [ "$name" = "prov" ]; then
    curl_opts+=( -H "Accept: text/turtle" )
  fi
  curl "${curl_opts[@]}" "$url" -o "$raw_file"

  echo "Converting $raw_file -> $ttl_file"
  run_robot_convert "$raw_file" "$ttl_file"
  rm -f "$raw_file"
done

echo "All imports refreshed in $IMPORT_DIR."
