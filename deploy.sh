#!/usr/bin/env bash
# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
set -euo pipefail

# ─── Color-coded logging ──────────────────────────────────────────────────────
BOLD="\033[1m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

log_info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
log_ok()    { echo -e "${GREEN}[ OK ]${RESET}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error() { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

# ─── Genio Elite ASCII banner ─────────────────────────────────────────────────
echo -e "${BOLD}${CYAN}"
cat << 'BANNER'
  ██████╗ ███╗   ███╗███╗   ██╗██╗███╗   ██╗███████╗████████╗
  ██╔═══██╗████╗ ████║████╗  ██║██║████╗  ██║██╔════╝╚══██╔══╝
  ██║   ██║██╔████╔██║██╔██╗ ██║██║██╔██╗ ██║█████╗     ██║
  ██║   ██║██║╚██╔╝██║██║╚██╗██║██║██║╚██╗██║██╔══╝     ██║
  ╚██████╔╝██║ ╚═╝ ██║██║ ╚████║██║██║ ╚████║███████╗   ██║
   ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝╚═╝  ╚═══╝╚══════╝   ╚═╝
                  Quantum-Core Network Orchestrator
BANNER
echo -e "${RESET}"
echo -e "${BOLD}OmniNet Quantum-Core — Production Deploy${RESET}"
echo ""

# ─── Prerequisites check ──────────────────────────────────────────────────────
log_info "Checking prerequisites..."

check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    log_error "Required tool not found: $1. Please install it and re-run."
    exit 1
  fi
}

check_cmd docker
check_cmd jq
check_cmd sha256sum

# Require Docker Compose v2 (plugin style: 'docker compose')
if ! docker compose version &>/dev/null; then
  log_error "Docker Compose v2 plugin not found. Install it from https://docs.docker.com/compose/install/"
  exit 1
fi

COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || echo "0.0.0")
log_ok "Prerequisites satisfied (Docker Compose ${COMPOSE_VERSION})"

# ─── Auto-copy .env if missing ────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  log_warn ".env not found — copying from .env.example"
  cp .env.example .env
  log_info "Edit .env and change all *_change_me values before production use!"
else
  log_ok ".env already present"
fi

# ─── Bring down any running stack ─────────────────────────────────────────────
log_info "Stopping any running stack..."
docker compose down --remove-orphans 2>/dev/null || true

# ─── Build and start all services ────────────────────────────────────────────
log_info "Building and starting services..."
docker compose up --build -d
log_ok "All services started"

# ─── Health poll loop (30 attempts, 2s interval) ──────────────────────────────
log_info "Waiting for application health at http://localhost/api/health ..."
TRIES=0
MAX_TRIES=30
INTERVAL=2
until curl -sf http://localhost/api/health > /dev/null 2>&1; do
  TRIES=$((TRIES + 1))
  if [ "$TRIES" -ge "$MAX_TRIES" ]; then
    log_error "Application did not become healthy after $((MAX_TRIES * INTERVAL))s."
    log_error "Check container logs: docker compose logs backend"
    exit 1
  fi
  sleep "$INTERVAL"
done

# ─── Success ──────────────────────────────────────────────────────────────────
echo ""
log_ok "OmniNet Quantum-Core is live!"
echo ""
echo -e "  ${BOLD}Dashboard${RESET}  → http://localhost"
echo -e "  ${BOLD}API docs${RESET}   → http://localhost/api/docs"
echo -e "  ${BOLD}Grafana${RESET}    → http://localhost:3000"
echo -e "  ${BOLD}Prometheus${RESET} → http://localhost:9090"
echo ""
