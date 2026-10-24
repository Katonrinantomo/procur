#!/bin/bash

# Warna untuk output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Memulai Procur.AI Stack ===${NC}"

# 1. Start Database (Docker)
echo -e "${GREEN}[1/4] Menyalakan PostgreSQL (Docker)...${NC}"
docker compose up -d

# 2. Start Langflow
echo -e "${GREEN}[2/4] Menyalakan Langflow (Port 7860)...${NC}"
nohup uv run langflow run > /tmp/procur-langflow.log 2>&1 &
echo $! > /tmp/procur-langflow.pid

# 3. Start Backend (FastAPI)
echo -e "${GREEN}[3/4] Menyalakan Backend (Port 8000)...${NC}"
cd backend
source .venv/bin/activate
nohup uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 > /tmp/procur-backend.log 2>&1 &
echo $! > /tmp/procur-backend.pid
cd ..

# 4. Start Frontend (Vite)
echo -e "${GREEN}[4/4] Menyalakan Frontend (Port 5173)...${NC}"
cd frontend
nohup npm run dev > /tmp/procur-frontend.log 2>&1 &
echo $! > /tmp/procur-frontend.pid
cd ..

echo -e "${BLUE}==================================================${NC}"
echo -e "${GREEN}Semua service berjalan di background!${NC}"
echo "Frontend: http://localhost:5173"
echo "Backend API: http://localhost:8000/docs"
echo "Langflow: http://localhost:7860"
echo -e "${BLUE}==================================================${NC}"
echo "Log tersimpan di /tmp/procur-*.log"
echo "Untuk mematikan semuanya, jalankan: ./stop.sh"