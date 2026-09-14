#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <package.tgz>" >&2
  exit 2
fi

tarball_dir=$(cd "$(dirname "$1")" && pwd -P)
tarball="$tarball_dir/$(basename "$1")"
if [[ ! -f "$tarball" ]]; then
  echo "package tarball not found: $tarball" >&2
  exit 2
fi

smoke_root=$(mktemp -d "${TMPDIR:-/tmp}/memory-agent-package-smoke.XXXXXX")
cleanup() {
  rm -rf -- "$smoke_root"
}
trap cleanup EXIT

contents="$smoke_root/package-contents.txt"
tar -tzf "$tarball" >"$contents"
if ! grep -qx 'package/bin/memory-agent.mjs' "$contents"; then
  echo "memory-agent bin is missing from the package" >&2
  exit 1
fi
if ! grep -qx 'package/scripts/project-agent/project_agent.py' "$contents"; then
  echo "project-agent host is missing from the package" >&2
  exit 1
fi
if ! grep -qx 'package/dist/project-agent-store.mjs' "$contents"; then
  echo "precompiled project-agent store bridge is missing from the package" >&2
  exit 1
fi
if grep -q '/benchmarks/' "$contents"; then
  echo "benchmark artifacts must not be shipped in the runtime package" >&2
  exit 1
fi
if grep -Eq '(^|/)tests?/|\.test\.|/test_[^/]*$' "$contents"; then
  echo "test sources must not be shipped in the runtime package" >&2
  exit 1
fi

consumer="$smoke_root/consumer"
workspace="$smoke_root/workspace"
state="$smoke_root/state"
mkdir -p "$consumer" "$workspace"
git -C "$workspace" init -q

npm install --prefix "$consumer" --package-lock=false --ignore-scripts \
  --no-audit --no-fund "$tarball" >/dev/null

agent="$consumer/node_modules/.bin/memory-agent"
"$agent" --help >"$smoke_root/help.txt"
run_agent() {
  local output=$1
  shift
  if ! "$agent" "$@" >"$output"; then
    cat "$output" >&2
    return 1
  fi
}
common=(--workspace "$workspace" --state "$state" --project package-smoke)
run_agent "$smoke_root/remember.json" "${common[@]}" \
  remember 'Keep explicit zero retry values.'
run_agent "$smoke_root/context.json" "${common[@]}" \
  context --paths src/client.py
run_agent "$smoke_root/history.json" "${common[@]}" history

(
  cd "$consumer"
  NODE_NO_WARNINGS=1 node --input-type=module -e \
    "const m = await import('@tencentdb-agent-memory/memory-tencentdb-v2/memory-feedback');
     if (typeof m.ProjectMemory !== 'function') process.exit(1);"
)

python3 - "$smoke_root/remember.json" "$smoke_root/context.json" "$smoke_root/history.json" <<'PY'
import json
from pathlib import Path
import sys

remember, context, history = (json.loads(Path(path).read_text()) for path in sys.argv[1:])
expected = 'Keep explicit zero retry values.'
assert remember['observation']['text'] == expected
assert remember['calls'] == []
assert context['mode'] == 'raw'
assert json.loads(context['text'])['text'] == expected
assert history['observations'][0]['text'] == expected
PY

echo "memory-agent package smoke passed"
