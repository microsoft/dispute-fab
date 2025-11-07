#!/usr/bin/env bash
# Start backend (FastAPI via uvicorn) and frontend (Vite) using local .env configuration.
# Backend runs on port 8000, frontend on port 5173.
# Safe frontend .env is generated before launch.
#
# Documentation: See docs/HANDOFF.md for deployment guide
# Architecture: See docs/ARCHITECTURE.md for system overview
set -euo pipefail

# Support start (default) or stop command.
ACTION="${1:-start}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/scripts/logs"

if [[ "$ACTION" == "stop" ]]; then
  mkdir -p "$LOG_DIR"
  echo "[run-services] Stopping services..."
  for svc in backend frontend; do
    PID_FILE="$LOG_DIR/${svc}.pid"
    if [[ -f "$PID_FILE" ]]; then
      PID="$(cat "$PID_FILE")"
      if ps -p "$PID" > /dev/null 2>&1; then
        echo "[run-services] Stopping $svc (PID $PID)"
        kill "$PID" || true
        # Wait briefly for termination
        for i in {1..10}; do
          if ps -p "$PID" > /dev/null 2>&1; then sleep 0.3; else break; fi
        done
        if ps -p "$PID" > /dev/null 2>&1; then
          echo "[run-services] $svc did not exit gracefully, sending SIGKILL"
          kill -9 "$PID" || true
        fi
      else
        echo "[run-services] $svc PID $PID not running"
      fi
      rm -f "$PID_FILE"
    else
      echo "[run-services] No PID file for $svc"
    fi
  done
  echo "[run-services] Stop complete."
  exit 0
fi
cd "$ROOT_DIR"

# Check if virtual environment is activated
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo "[run-services] ⚠️  Virtual environment not detected!" >&2
  echo "[run-services]    Run: source .venv/bin/activate" >&2
  echo "[run-services]    (On Windows: .venv\\Scripts\\activate)" >&2
  exit 1
fi

# Check if Python dependencies are installed
if ! python -c "import pandas, fastapi, openai, azure.identity" 2>/dev/null; then
  echo "[run-services] ⚠️  Python dependencies not installed!" >&2
  echo "[run-services]    Run: pip install -r requirements.txt" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "[run-services] .env not found. Please create it first." >&2
  exit 1
fi

# Load backend env (includes secrets, do NOT echo them)
set -a
source .env
set +a

# Generate frontend env (no secrets)
bash scripts/sync-env.sh

# Copy latest classification results to frontend public directory
if [[ -f "$ROOT_DIR/outputs/all_vendors_classification_results.csv" ]]; then
  echo "[run-services] Copying latest classification results to frontend..."
  mkdir -p "$ROOT_DIR/frontend/public/outputs"
  cp "$ROOT_DIR/outputs/all_vendors_classification_results.csv" "$ROOT_DIR/frontend/public/outputs/"
  echo "[run-services] ✓ Results file copied to frontend/public/outputs/"
else
  echo "[run-services] ⚠️  Error: outputs/all_vendors_classification_results.csv not found" >&2
  echo "[run-services]    You must generate classification results first:" >&2
  echo "[run-services]    Run: python process_all_vendors.py" >&2
  echo "" >&2
  exit 1
fi

mkdir -p "$LOG_DIR"

# Start backend
echo "[run-services] Starting backend on http://localhost:8000"
UVICORN_BIN="$(command -v uvicorn || true)"
if [[ -z "$UVICORN_BIN" ]]; then
  # Try venv path
  if [[ -f ".venv/bin/uvicorn" ]]; then
    UVICORN_BIN=".venv/bin/uvicorn"
  else
    echo "[run-services] ERROR: uvicorn not found. Run: pip install -r requirements.txt" >&2
    exit 1
  fi
fi
nohup "$UVICORN_BIN" api_server:app --reload --port 8000 > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$LOG_DIR/backend.pid"

# Start frontend
echo "[run-services] Starting frontend (Vite) on http://localhost:5173"
cd frontend
if [[ ! -d node_modules ]]; then
  echo "[run-services] Installing frontend dependencies (first run)";
  npm install --no-audit --no-fund
fi
nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$LOG_DIR/frontend.pid"

cd "$ROOT_DIR"

echo "[run-services] Backend PID: $BACKEND_PID | Frontend PID: $FRONTEND_PID"
echo "[run-services] Logs: tail -f $LOG_DIR/backend.log  |  tail -f $LOG_DIR/frontend.log"
echo "[run-services] To stop: kill $(cat $LOG_DIR/backend.pid) $(cat $LOG_DIR/frontend.pid)"
