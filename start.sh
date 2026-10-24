#!/bin/bash
# Procur.AI - start semua service (semua bind ke localhost)
ROOT="$(cd "$(dirname "$0")" && pwd)"
LANGFLOW_DIR="${LANGFLOW_DIR:-$HOME/langflow}"   # folder instalasi Langflow (punya pyproject.toml)

GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'

port_busy() { ss -ltn "sport = :$1" 2>/dev/null | grep -q LISTEN; }

# start_bg <nama> <folder> <perintah...>
# setsid = grup proses sendiri, jadi stop.sh bisa mematikan semua anaknya sekaligus
start_bg() {
  local name="$1" dir="$2"; shift 2
  setsid bash -c 'cd "$1" || exit 1; shift; exec "$@"' _ "$dir" "$@" \
    > "/tmp/procur-$name.log" 2>&1 < /dev/null &
  echo $! > "/tmp/procur-$name.pid"
}

# wait_for <label> <url> <detik> <nama-log>
wait_for() {
  for _ in $(seq 1 "$3"); do
    if curl -fs -o /dev/null "$2"; then
      echo -e "  ${GREEN}OK${NC}    $1"; return 0
    fi
    sleep 1
  done
  echo -e "  ${RED}GAGAL${NC} $1 belum merespons. Cek /tmp/procur-$4.log"
  return 1
}

echo -e "${BLUE}=== Memulai Procur.AI Stack ===${NC}"
cd "$ROOT" || exit 1

[ -d "$LANGFLOW_DIR" ] || { echo -e "${RED}Folder Langflow tidak ada: $LANGFLOW_DIR (set LANGFLOW_DIR)${NC}"; exit 1; }
[ -x backend/.venv/bin/uvicorn ] || { echo -e "${RED}backend/.venv belum dibuat${NC}"; exit 1; }

for p in 7860 8000 5173; do
  if port_busy "$p"; then
    echo -e "${RED}Port $p sudah dipakai. Jalankan ./stop.sh dulu (atau pkill -f 'langflow run').${NC}"
    exit 1
  fi
done

echo -e "${GREEN}[1/4] PostgreSQL (Docker)...${NC}"
docker compose up -d || exit 1

echo -e "${GREEN}[2/4] Langflow (127.0.0.1:7860)...${NC}"
start_bg langflow "$LANGFLOW_DIR" uv run langflow run --host 127.0.0.1 --port 7860

echo -e "${GREEN}[3/4] Backend (127.0.0.1:8000)...${NC}"
start_bg backend "$ROOT/backend" .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

echo -e "${GREEN}[4/4] Frontend (5173)...${NC}"
start_bg frontend "$ROOT/frontend" npm run dev

echo -e "${BLUE}Menunggu service siap...${NC}"
FAIL=0
wait_for "Backend"  http://127.0.0.1:8000/api/health        30  backend   || FAIL=1
wait_for "Frontend" http://localhost:5173                   30  frontend  || FAIL=1
wait_for "Langflow" http://127.0.0.1:7860/api/v1/version    120 langflow  || FAIL=1

echo -e "${BLUE}==================================================${NC}"
if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}Semua service siap.${NC}"
else
  echo -e "${RED}Ada service yang gagal start (lihat pesan di atas).${NC}"
fi
echo "Frontend: http://localhost:5173"
echo "Backend API: http://localhost:8000/docs"
echo "Langflow: http://localhost:7860"
echo "Log: /tmp/procur-*.log | Matikan: ./stop.sh"
echo -e "${BLUE}==================================================${NC}"
exit "$FAIL"