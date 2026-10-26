#!/bin/sh
# Usage: entrypoint.sh <filesystem|git|fetch>
set -e

case "$1" in
  filesystem)
    CMD="mcp-server-filesystem /workspace"
    ;;
  git)
    # The seeded sample repo ships without .git; create it on first start.
    git config --global --add safe.directory '*'
    for repo in /workspace/sample-app; do
      if [ -d "$repo" ] && [ ! -d "$repo/.git" ]; then
        git -C "$repo" init -q -b main
        git -C "$repo" add -A
        git -C "$repo" -c user.name="AAIF Demo" -c user.email="demo@aaif.local" \
          commit -q -m "Initial commit of sample app"
      fi
    done
    CMD="mcp-server-git"
    ;;
  fetch)
    CMD="mcp-server-fetch --ignore-robots-txt"
    ;;
  *)
    echo "unknown server: $1" >&2
    exit 1
    ;;
esac

exec supergateway --stdio "$CMD" --outputTransport streamableHttp --stateful \
  --port 8000 --healthEndpoint /healthz
