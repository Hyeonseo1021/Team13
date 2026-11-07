#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

# Render supplies PORT. An independent domain serves the app at / by default.
exec python -m streamlit run app.py \
  --server.address 0.0.0.0 \
  --server.port "${PORT:-8501}" \
  --server.baseUrlPath "${T13_BASE_PATH:-}" \
  --server.headless true \
  --server.runOnSave false \
  --server.fileWatcherType none \
  --server.enableXsrfProtection false
