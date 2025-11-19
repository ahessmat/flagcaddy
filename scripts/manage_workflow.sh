#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$BASE_DIR/data/pids"
LOG_DIR="$BASE_DIR/logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

PYTHON_BIN=${PYTHON_BIN:-}
if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x "$BASE_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$BASE_DIR/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

FLASK_BIN=${FLASK_BIN:-}
if [[ -z "${FLASK_BIN}" ]]; then
  if [[ -x "$BASE_DIR/.venv/bin/flask" ]]; then
    FLASK_BIN="$BASE_DIR/.venv/bin/flask"
  else
    FLASK_BIN="flask"
  fi
fi

start_process() {
  local name="$1"; shift
  local pid_file="$PID_DIR/$name.pid"
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name already running (PID $(cat "$pid_file"))"
    return
  fi
  echo "Starting $name ..."
  nohup "$@" >"$LOG_DIR/$name.log" 2>&1 &
  echo $! >"$pid_file"
  disown || true
}

stop_process() {
  local name="$1"
  local pid_file="$PID_DIR/$name.pid"
  if [[ ! -f "$pid_file" ]]; then
    echo "$name not running"
    return
  fi
  local pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "Stopping $name (PID $pid) ..."
    kill "$pid" || true
    wait "$pid" 2>/dev/null || true
  else
    echo "$name pid $pid not active"
  fi
  rm -f "$pid_file"
}

status_process() {
  local name="$1"
  local pid_file="$PID_DIR/$name.pid"
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name running (PID $(cat "$pid_file"))"
  else
    echo "$name stopped"
  fi
}

start_all() {
  start_process "log_to_notes" "$PYTHON_BIN" "$BASE_DIR/scripts/log_to_notes.py" --loop --interval 15
  start_process "notes_to_actions" "$PYTHON_BIN" "$BASE_DIR/scripts/notes_to_actions.py" --loop --interval 30
  start_process "flask_app" env FLASK_APP=web/app.py "$FLASK_BIN" run --host 0.0.0.0 --port 5000 --no-reload
}

stop_all() {
  stop_process "flask_app"
  stop_process "notes_to_actions"
  stop_process "log_to_notes"
}

status_all() {
  status_process "log_to_notes"
  status_process "notes_to_actions"
  status_process "flask_app"
  echo "Log files live under $LOG_DIR"
}

case "${1:-}" in
  start)
    start_all
    ;;
  stop)
    stop_all
    ;;
  status)
    status_all
    ;;
  restart)
    stop_all
    start_all
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}" >&2
    exit 1
    ;;
 esac
