#!/usr/bin/env bash
# =============================================================================
# (c) 2021-2026 Jonathan Kamu / Genio Elite. Tous droits réservés.
# deploy.sh — OmniNet Quantum-Core Intelligent Deployment Script
# =============================================================================

set -euo pipefail

# ─── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log_info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
log_success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

# ─── Genio Elite ASCII Banner ─────────────────────────────────────────────────
print_banner() {
  echo -e "${CYAN}"
  cat << 'BANNER'
  ██████╗ ███████╗███╗   ██╗██╗ ██████╗     ███████╗██╗     ██╗████████╗███████╗
 ██╔════╝ ██╔════╝████╗  ██║██║██╔═══██╗    ██╔════╝██║     ██║╚══██╔══╝██╔════╝
 ██║  ███╗█████╗  ██╔██╗ ██║██║██║   ██║    █████╗  ██║     ██║   ██║   █████╗  
 ██║   ██║██╔══╝  ██║╚██╗██║██║██║   ██║    ██╔══╝  ██║     ██║   ██║   ██╔══╝  
 ╚██████╔╝███████╗██║ ╚████║██║╚██████╔╝    ███████╗███████╗██║   ██║   ███████╗
  ╚═════╝ ╚══════╝╚═╝  ╚═══╝╚═╝ ╚═════╝     ╚══════╝╚══════╝╚═╝   ╚═╝   ╚══════╝
                  OmniNet Quantum-Core — Universal Network Orchestrator
                        (c) 2021-2026 Jonathan Kamu / Genio Elite
BANNER
  echo -e "${RESET}"
}

# ─── Step 1: Prerequisites Check ─────────────────────────────────────────────
check_prerequisites() {
  log_info "Checking prerequisites..."
  local missing=0

  for cmd in docker sha256sum jq; do
    if ! command -v "$cmd" &>/dev/null; then
      log_error "Required command not found: $cmd"
      missing=$((missing + 1))
    fi
  done

  # Accept both 'docker-compose' (v1) and 'docker compose' (v2)
  if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null 2>&1; then
    log_error "Neither 'docker-compose' nor 'docker compose' plugin found."
    missing=$((missing + 1))
  fi

  if [ $missing -gt 0 ]; then
    log_error "Please install missing dependencies before deploying."
    exit 1
  fi
  log_success "All prerequisites satisfied."
}

# ─── Step 2: Auto-fix Nested frontend/frontend Structure ─────────────────────
fix_frontend_structure() {
  log_info "Verifying frontend directory structure..."
  local nested="frontend/frontend"

  if [ -d "$nested" ]; then
    log_warn "Detected erroneous nested structure: $nested"
    log_info "Auto-correcting: moving contents of $nested → frontend/"

    # Move all contents (including hidden files) from frontend/frontend to frontend/
    find "$nested" -mindepth 1 -maxdepth 1 | while read -r item; do
      local basename
      basename=$(basename "$item")
      if [ -e "frontend/$basename" ]; then
        log_warn "Conflict: frontend/$basename already exists, skipping."
      else
        mv "$item" "frontend/"
        log_success "Moved: $basename"
      fi
    done

    # Remove the now-empty nested directory
    if [ -z "$(ls -A "$nested")" ]; then
      rmdir "$nested"
      log_success "Removed empty directory: $nested"
    else
      log_warn "Directory $nested is not empty after move — manual review required."
    fi
  else
    log_success "Frontend structure is clean."
  fi
}

# ─── Step 3: Generate Integrity Manifest ─────────────────────────────────────
generate_integrity_manifest() {
  log_info "Generating integrity manifest (SHA-256)..."
  local manifest_path="backend/integrity_manifest.json"
  local critical_files=(
    "backend/license_manager.py"
    "backend/quantum_engine.py"
  )

  local timestamp
  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  local entries="[]"
  for filepath in "${critical_files[@]}"; do
    if [ -f "$filepath" ]; then
      local hash
      hash=$(sha256sum "$filepath" | awk '{print $1}')
      local filename
      filename=$(basename "$filepath")
      entries=$(echo "$entries" | jq \
        --arg f "$filename" \
        --arg p "$filepath" \
        --arg h "$hash" \
        --arg t "$timestamp" \
        '. += [{"file": $f, "path": $p, "sha256": $h, "verified_at": $t}]')
      log_success "Hashed: $filepath → $hash"
    else
      log_warn "Critical file not found, skipping hash: $filepath"
    fi
  done

  local manifest
  manifest=$(jq -n \
    --arg version "1.0" \
    --arg generated_at "$timestamp" \
    --arg project "OmniNet Quantum-Core" \
    --arg copyright "(c) 2021-2026 Jonathan Kamu / Genio Elite" \
    --argjson files "$entries" \
    '{
      "schema_version": $version,
      "project": $project,
      "copyright": $copyright,
      "generated_at": $generated_at,
      "files": $files
    }')

  echo "$manifest" > "$manifest_path"
  log_success "Integrity manifest written to $manifest_path"
}

# ─── Step 4: Environment Check ────────────────────────────────────────────────
check_env_file() {
  log_info "Checking environment configuration..."
  if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
      log_warn ".env not found. Copying from .env.example — please review and update secrets!"
      cp .env.example .env
    else
      log_error "Neither .env nor .env.example found. Cannot proceed."
      exit 1
    fi
  fi
  log_success "Environment file ready."
}

# ─── Step 5: Docker Deployment ───────────────────────────────────────────────
deploy() {
  log_info "Tearing down existing containers..."
  if command -v docker-compose &>/dev/null; then
    docker-compose down --remove-orphans
  else
    docker compose down --remove-orphans
  fi

  log_info "Building and starting services (this may take a few minutes)..."
  if command -v docker-compose &>/dev/null; then
    docker-compose up --build -d
  else
    docker compose up --build -d
  fi

  log_success "All services started."
}

# ─── Step 6: Health Check ─────────────────────────────────────────────────────
wait_for_health() {
  log_info "Waiting for backend API to be healthy..."
  local max_attempts=30
  local attempt=0
  local backend_url="http://localhost/api/health"

  while [ $attempt -lt $max_attempts ]; do
    if curl -sf "$backend_url" &>/dev/null; then
      log_success "Backend API is responding at $backend_url"
      return 0
    fi
    attempt=$((attempt + 1))
    log_info "Attempt $attempt/$max_attempts — waiting 5s..."
    sleep 5
  done

  if command -v docker-compose &>/dev/null; then
    log_warn "Backend did not respond within expected time. Check logs with: docker-compose logs app"
  else
    log_warn "Backend did not respond within expected time. Check logs with: docker compose logs app"
  fi
}

# ─── Main Entry Point ─────────────────────────────────────────────────────────
main() {
  print_banner
  check_prerequisites
  fix_frontend_structure
  check_env_file
  generate_integrity_manifest
  deploy
  wait_for_health

  echo ""
  echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════════╗${RESET}"
  echo -e "${GREEN}${BOLD}║   ✅  OmniNet Quantum-Core est déployé sur http://localhost  ║${RESET}"
  echo -e "${GREEN}${BOLD}║          Propriété de Genio Elite — Bonne utilisation !      ║${RESET}"
  echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════════╝${RESET}"
  echo ""
  echo -e "  ${CYAN}📊 Grafana:${RESET}    http://localhost:3001"
  echo -e "  ${CYAN}🔌 API Docs:${RESET}   http://localhost/api/docs"
  echo -e "  ${CYAN}📡 API Base:${RESET}   http://localhost/api"
  echo ""
}

main "$@"
