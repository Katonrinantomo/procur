#!/bin/bash
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "=== Mematikan Procur.AI Stack ==="

# Mematikan seluruh grup proses (proses utama + semua anaknya)
stop_group() {
  local name="$1" f="/tmp/procur-$1.pid" pid
  if [ ! -f "$f" ]; then echo "  $name: tidak ada PID file (dilewati)"; return; fi
  pid=$(cat "$f")
  kill -TERM -- "-$pid" 2>/dev/null
  for _ in $(seq 1 10); do pgrep -g "$pid" >/dev/null || break; sleep 1; done
  pgrep -g "$pid" >/dev/null && kill -KILL -- "-$pid" 2>/dev/null
  rm -f "$f"
  echo "  $name dimatikan."
}

stop_group frontend
stop_group backend
stop_group langflow

cd "$ROOT" && docker compose stop
echo "  Database (Docker) dihentikan."

echo "Selesai. Sisa proses (harus kosong):"
ps aux | grep -E "[l]angflow run|[u]vicorn app.main|[v]ite" || echo "  (tidak ada)"