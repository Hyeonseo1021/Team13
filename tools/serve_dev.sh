
  cd /data/hackathon/team13 || exit 1
  exec 9>.dev-server.lock
  flock -n 9 || { echo "이미 실행 중입니다."; exit 1; }
  .venv/bin/python -c "import streamlit" || exit 1

  snapshot() {
  find . -type d \( -name .git -o -name .venv -o -name venv -o -name __pycache__ -o -name data -o \
  -name node_modules \) -prune -o -type f \( -name "*.py" -o -name "*.toml" -o -name "*.html" -o \
  -name "*.css" -o -name "*.js" -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name \
  "*.txt" \) -print0 |
  sort -z | xargs -0 -r sha256sum | sha256sum
  }

  child=""
  cleanup() {
  if [ -n "$child" ]; then
  kill "$child" 2>/dev/null
  wait "$child" 2>/dev/null
  child=""
  fi
  }
  trap "cleanup; exit" TERM INT
  trap cleanup EXIT

  while true; do
  before=$(snapshot)
  echo "서버 시작: 8501"
  .venv/bin/python -m streamlit run app.py \
  --server.address=0.0.0.0 \
  --server.port=8501 \
  --server.baseUrlPath=i/GSCmyWGuBKr2fXRa \
  --server.headless=true 9>&- &
  child=$!

  while kill -0 "$child" 2>/dev/null; do
  sleep 2
  after=$(snapshot)
  if [ "$before" != "$after" ]; then
  echo "코드 변경 감지: 서버 재시작"
  break
  fi
  done

  cleanup
  sleep 2
  done
