#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p png

render() {
  local name="$1"
  local mmd="src/${name}.mmd"
  local out="png/${name}.png"
  # Build JSON payload: {"code": <mermaid>, "mermaid": {"theme":"default"}}
  local code
  code=$(cat "$mmd")
  # JSON-encode using perl (escape backslash, quotes, newlines)
  local json
  json=$(perl -e '
    local $/;
    my $c = <STDIN>;
    $c =~ s/\\/\\\\/g;
    $c =~ s/"/\\"/g;
    $c =~ s/\n/\\n/g;
    $c =~ s/\r//g;
    $c =~ s/\t/\\t/g;
    print "{\"code\":\"$c\",\"mermaid\":{\"theme\":\"default\"},\"type\":\"png\"}";
  ' < "$mmd")
  # URL-safe base64, no padding stripping needed by mermaid.ink pako? use plain base64 endpoint
  local b64
  b64=$(printf '%s' "$json" | base64 -w0 | tr '+/' '-_' | tr -d '=')
  local url="https://mermaid.ink/img/${b64}?type=png"
  echo "Rendering ${name} ..."
  curl -fsSL "$url" -o "$out"
  echo "  -> ${out} ($(wc -c < "$out") bytes)"
}

for f in 1-general 2-drivers 3-framework 4-servicios 5-his; do
  render "$f"
done
echo "Done."
