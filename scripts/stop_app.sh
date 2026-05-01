#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$PROJECT_ROOT/tmp/runserver.pid"
PORT="8000"

stop_pid() {
  local pid="$1"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    return 1
  fi

  echo "Stopping server PID $pid..."
  kill "$pid" 2>/dev/null || true

  for _ in {1..20}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "Server stopped."
      return 0
    fi
    sleep 0.2
  done

  echo "PID $pid did not stop after TERM; sending KILL..."
  kill -9 "$pid" 2>/dev/null || true
  sleep 0.2
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "Server stopped after KILL."
    return 0
  fi

  echo "Failed to stop PID $pid"
  return 1
}

stopped=0

if [[ -f "$PID_FILE" ]]; then
  pid_from_file="$(cat "$PID_FILE" 2>/dev/null || true)"
  if stop_pid "$pid_from_file"; then
    stopped=1
  else
    echo "PID file exists but process is not running: $pid_from_file"
  fi
  rm -f "$PID_FILE"
fi

if [[ "$stopped" -eq 0 ]]; then
  fallback_pid=""
  if command -v lsof >/dev/null 2>&1; then
    fallback_pid="$(lsof -t -i TCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
  elif command -v ss >/dev/null 2>&1; then
    fallback_pid="$(ss -ltnp 2>/dev/null | awk -v p=":$PORT" '$4 ~ p {print $NF}' | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | head -n 1 || true)"
  fi

  if [[ -n "$fallback_pid" ]]; then
    echo "Using port-based fallback on :$PORT (PID $fallback_pid)"
    if stop_pid "$fallback_pid"; then
      stopped=1
    fi
  fi
fi

if [[ "$stopped" -eq 1 ]]; then
  echo "Done."
  exit 0
fi

echo "No running Django server found on port $PORT."
exit 0
