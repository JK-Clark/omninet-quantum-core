#!/usr/bin/env bash
set -euo pipefail

# ─── OmniNet Quantum-Core — One-command deploy script ─────────────────────────

BOLD="\033[1m"
GREEN="\033[32m"
CYAN="\033[36m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}"
cat << 'BANNER'
  ██████╗ ███╗   ███╗███╗   ██╗██╗███╗   ██╗███████╗████████╗
  ██╔═══██╗████╗ ████║████╗  ██║██║████╗  ██║██╔════╝╚══██╔══╝
  ██║   ██║██╔████╔██║██╔██╗ ██║██║██╔██╗ ██║█████╗     ██║
  ██║   ██║██║╚██╔╝██║██║╚██╗██║██║██║╚██╗██║██╔══╝     ██║
  ╚██████╔╝██║ ╚═╝ ██║██║ ╚████║██║██║ ╚████║███████╗   ██║
   ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝╚═╝  ╚═══╝╚══════╝   ╚═╝
BANNER
echo -e "${RESET}"
echo -e "${BOLD}OmniNet Quantum-Core — Production Deploy${RESET}"
echo ""

# 1. Copy .env if missing
if [ ! -f ".env" ]; then
  echo -e "${GREEN}Creating .env from .env.example...${RESET}"
  cp .env.example .env
  echo "  Edit .env and change all *_change_me values before production use!"
fi

# 2. Build + start
echo -e "${GREEN}Building and starting services...${RESET}"
docker compose pull --ignore-buildable 2>/dev/null || true
docker compose up --build -d

# 3. Wait for backend health
echo -e "${GREEN}Waiting for backend health check...${RESET}"
TRIES=0
until docker compose exec backend curl -sf http://localhost:8000/api/health > /dev/null 2>&1; do
  TRIES=$((TRIES + 1))
  if [ "$TRIES" -ge 30 ]; then
    echo "Backend did not become healthy. Check logs: docker compose logs backend"
    exit 1
  fi
  sleep 3
done

echo ""
echo -e "${BOLD}${GREEN}OmniNet Quantum-Core is running!${RESET}"
echo ""
echo "  Dashboard  -> http://localhost"
echo "  API docs   -> http://localhost/api/docs"
echo "  Prometheus -> http://localhost:9090"
echo "  Grafana    -> http://localhost:3001"
echo ""
