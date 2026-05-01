#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
PID_DIR="$PROJECT_ROOT/tmp"
PID_FILE="$PID_DIR/runserver.pid"
HOST="127.0.0.1"
PORT="8000"

mkdir -p "$PID_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Error: Python virtualenv not found at $PYTHON_BIN"
  echo "Create it first: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

if [[ -f "$PID_FILE" ]]; then
  existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
    echo "Server already running with PID $existing_pid"
    echo "Use scripts/stop_app.sh to stop it first."
    exit 0
  fi
  echo "Removing stale PID file: $PID_FILE"
  rm -f "$PID_FILE"
fi

echo "Applying migrations..."
"$PYTHON_BIN" "$PROJECT_ROOT/manage.py" migrate

echo "Starting Django server at http://$HOST:$PORT/..."
cd "$PROJECT_ROOT"
# Use --noreload so PID tracking remains stable (no reloader parent/child split).
nohup "$PYTHON_BIN" manage.py runserver "$HOST:$PORT" --noreload > "$PID_DIR/runserver.log" 2>&1 &
server_pid=$!
echo "$server_pid" > "$PID_FILE"

sleep 1
if kill -0 "$server_pid" 2>/dev/null; then
  echo "Server started with PID $server_pid"
  echo "PID file: $PID_FILE"
  echo "Log file: $PID_DIR/runserver.log"
else
  echo "Server failed to start. Check log: $PID_DIR/runserver.log"
  rm -f "$PID_FILE"
  exit 1
fi
