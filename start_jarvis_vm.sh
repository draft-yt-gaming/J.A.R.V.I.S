#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

export JARVIS_HEADLESS=1
export JARVIS_BIND_HOST=0.0.0.0
export JARVIS_WS_PORT="${JARVIS_WS_PORT:-8765}"
export JARVIS_HTTP_PORT="${JARVIS_HTTP_PORT:-8080}"
export JARVIS_HTTPS_PORT="${JARVIS_HTTPS_PORT:-8443}"

echo "Demarrage de J.A.R.V.I.S en mode VM/web..."
exec ./venv/bin/python main2.py
