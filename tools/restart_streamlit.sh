#!/usr/bin/env bash
# Restart the team13 Streamlit app on port 8501 (same URL path), logging to ~/app.log.
cd /data/hackathon/team13 || exit 1
# match only the python process itself (anchored), never shells whose command text mentions it
for pid in $(pgrep -f "^$HOME/venv/bin/python3? $HOME/venv/bin/streamlit run app.py"); do
  [ "$pid" != "$$" ] && kill "$pid" 2>/dev/null
done
sleep 2
nohup "$HOME/venv/bin/streamlit" run app.py \
  --server.port 8501 --server.address 0.0.0.0 \
  --server.baseUrlPath i/GSCmyWGuBKr2fXRa \
  --server.enableCORS false --server.enableXsrfProtection false \
  --server.runOnSave true --server.headless true >> "$HOME/app.log" 2>&1 &
echo "started pid $!"
