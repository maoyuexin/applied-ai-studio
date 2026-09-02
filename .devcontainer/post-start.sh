#!/usr/bin/env bash
# Start the application after every Codespaces container start, including resume.

set -euo pipefail

LOG_FILE="${TMPDIR:-/tmp}/applied-ai-studio-dev.log"

stack_is_healthy() {
  curl --fail --silent --max-time 2 http://127.0.0.1:5173/ >/dev/null \
    && curl --fail --silent --max-time 2 http://127.0.0.1:4310/health >/dev/null \
    && curl --silent --max-time 2 http://127.0.0.1:4320/ >/dev/null \
    && curl --fail --silent --max-time 2 http://127.0.0.1:4330/health >/dev/null \
    && curl --fail --silent --max-time 2 http://127.0.0.1:4340/health >/dev/null \
    && curl --fail --silent --max-time 2 http://127.0.0.1:4350/health >/dev/null
}

if stack_is_healthy; then
  echo "==> Applied AI Studio is already running on port 5173"
  exit 0
fi

# Refuse to layer a new process group over a partial stack. The preflight prints
# the occupied service names and the recovery instructions.
node scripts/dev-preflight.mjs

echo "==> Starting Applied AI Studio automatically"
: >"${LOG_FILE}"
# Codespaces sends SIGHUP to the lifecycle process group when this script exits.
# The Node helper creates a new session so the supervised stack survives it.
app_pid="$(node scripts/start-dev-detached.mjs "${LOG_FILE}")"

for _ in {1..60}; do
  if stack_is_healthy; then
    echo "==> Applied AI Studio is ready on port 5173"
    echo "    startup log: ${LOG_FILE}"
    exit 0
  fi

  if ! kill -0 "${app_pid}" 2>/dev/null; then
    break
  fi

  sleep 1
done

echo ""
echo "Applied AI Studio did not become ready. Recent startup output:"
tail -n 40 "${LOG_FILE}" || true
exit 1