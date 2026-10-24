#!/bin/bash

echo "=== Mematikan Procur.AI Stack ==="

# Mematikan Frontend
if [ -f /tmp/procur-frontend.pid ]; then
    kill $(cat /tmp/procur-frontend.pid) 2>/dev/null
    rm /tmp/procur-frontend.pid
    echo "Frontend dimatikan."
fi

# Mematikan Backend
if [ -f /tmp/procur-backend.pid ]; then
    kill $(cat /tmp/procur-backend.pid) 2>/dev/null
    rm /tmp/procur-backend.pid
    echo "Backend dimatikan."
fi

# Mematikan Langflow
if [ -f /tmp/procur-langflow.pid ]; then
    kill $(cat /tmp/procur-langflow.pid) 2>/dev/null
    rm /tmp/procur-langflow.pid
    echo "Langflow dimatikan."
fi

# Mematikan Docker
docker compose down
echo "Database (Docker) dimatikan."

echo "Semua service telah dihentikan."