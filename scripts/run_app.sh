#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VENV_DIR="${VENV_DIR:-$PROJECT_ROOT/.venv}"
PYTHON_BIN="${PYTHON_BIN:-$VENV_DIR/bin/python}"
PIP_BIN="${PIP_BIN:-$VENV_DIR/bin/pip}"
PID_DIR="$PROJECT_ROOT/tmp"
PID_FILE="$PID_DIR/runserver.pid"
LOG_FILE="$PID_DIR/runserver.log"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
ENV_FILE="$PROJECT_ROOT/.env"
ENV_EXAMPLE_FILE="$PROJECT_ROOT/.env.example"
REQ_FILE="$PROJECT_ROOT/requirements.txt"
MEDICINES_CSV="$PROJECT_ROOT/medicines.csv"

step() {
  echo "[$(date +"%H:%M:%S")] $*"
}

fail() {
  echo "Error: $*" >&2
  exit 1
}

require_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || fail "Required command not found: $cmd"
}

wait_for_health() {
  local url="$1"
  local attempts="${2:-20}"
  local delay="${3:-0.5}"
  local i

  for ((i=1; i<=attempts; i++)); do
    if curl --silent --show-error --fail "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

ensure_env_key() {
  local key="$1"
  local value="$2"

  if grep -Eq "^${key}=" "$ENV_FILE"; then
    sed -i.bak "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
  else
    printf '\n%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

mkdir -p "$PID_DIR"

step "Checking required system commands..."
require_cmd python3
require_cmd curl

if [[ ! -d "$VENV_DIR" ]]; then
  step "Virtualenv not found. Creating at $VENV_DIR ..."
  python3 -m venv "$VENV_DIR" || fail "Failed to create virtualenv at $VENV_DIR"
fi

[[ -x "$PYTHON_BIN" ]] || fail "Python executable not found in virtualenv: $PYTHON_BIN"

if [[ ! -x "$PIP_BIN" ]]; then
  step "pip missing in virtualenv. Bootstrapping pip..."
  "$PYTHON_BIN" -m ensurepip --upgrade || fail "Failed to bootstrap pip in virtualenv"
fi

[[ -f "$REQ_FILE" ]] || fail "requirements file not found: $REQ_FILE"

step "Upgrading pip/setuptools/wheel..."
"$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel || fail "Failed to upgrade pip tooling"

step "Installing Python dependencies from requirements.txt ..."
"$PYTHON_BIN" -m pip install -r "$REQ_FILE" || fail "Failed to install dependencies"

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$ENV_EXAMPLE_FILE" ]]; then
    step "Creating .env from .env.example ..."
    cp "$ENV_EXAMPLE_FILE" "$ENV_FILE" || fail "Failed to copy .env.example to .env"
  else
    step "Creating minimal .env ..."
    touch "$ENV_FILE" || fail "Failed to create .env"
  fi

  step "Applying local-safe .env defaults for first run ..."
  ensure_env_key "DEBUG" "True"
  ensure_env_key "ALLOWED_HOSTS" "127.0.0.1,localhost"
  ensure_env_key "CORS_ALLOW_ALL_ORIGINS" "True"
fi

if [[ -f "$PID_FILE" ]]; then
  existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
    step "Server already running with PID $existing_pid"
    step "Use scripts/stop_app.sh to stop it first."
    exit 0
  fi
  step "Removing stale PID file: $PID_FILE"
  rm -f "$PID_FILE"
fi

step "Applying database migrations ..."
"$PYTHON_BIN" "$PROJECT_ROOT/manage.py" migrate --noinput || fail "Migration failed"

if [[ -f "$MEDICINES_CSV" ]]; then
  step "Importing medicines catalog from medicines.csv ..."
  "$PYTHON_BIN" "$PROJECT_ROOT/manage.py" import_medicines --path "$MEDICINES_CSV" || fail "Medicine import failed"
else
  fail "Medicines CSV not found: $MEDICINES_CSV"
fi

step "Starting Django server at http://$HOST:$PORT/ ..."
cd "$PROJECT_ROOT"
nohup "$PYTHON_BIN" manage.py runserver "$HOST:$PORT" --noreload > "$LOG_FILE" 2>&1 &
server_pid=$!
echo "$server_pid" > "$PID_FILE"

sleep 1
if kill -0 "$server_pid" 2>/dev/null && wait_for_health "http://$HOST:$PORT/demo/health/" 20 0.5; then
  step "Server started with PID $server_pid"
  step "PID file: $PID_FILE"
  step "Log file: $LOG_FILE"
  step "Health: curl -s http://$HOST:$PORT/demo/health/"
else
  step "Server failed to start or health check did not pass. Check log: $LOG_FILE"
  if kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
  exit 1
fi
