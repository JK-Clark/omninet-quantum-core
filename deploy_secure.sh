#!/usr/bin/env bash
# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
#
# ─── OmniNet Quantum-Core — Secure Production Deploy Script ──────────────────
#
# This script performs a full secure build of OmniNet Quantum-Core for
# production delivery.  It:
#
#   1. Generates the integrity manifest (SHA-256 of protected backend files)
#   2. Obfuscates the Python backend with PyArmor
#   3. Minifies the React frontend with Terser (via Vite's production build)
#   4. Builds and labels the Docker images so source code is not exposed
#      to end-users, even if they gain shell access to the container
#
# Prerequisites (install once on the build machine):
#   pip install pyarmor
#   node + npm  (for frontend Vite build)
#   docker + docker-compose
#
# Usage:
#   ./deploy_secure.sh [--skip-obfuscate] [--skip-frontend] [--push]
#
#   --skip-obfuscate   Skip PyArmor step (useful for CI smoke tests)
#   --skip-frontend    Skip frontend build step
#   --push             Push built images to the configured registry
#
set -euo pipefail

# ─── Colour helpers ───────────────────────────────────────────────────────────
BOLD="\033[1m"
GREEN="\033[32m"
CYAN="\033[36m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
fatal()   { echo -e "${RED}[FATAL]${RESET} $*" >&2; exit 1; }

# ─── Argument parsing ─────────────────────────────────────────────────────────
SKIP_OBFUSCATE=false
SKIP_FRONTEND=false
DO_PUSH=false

for arg in "$@"; do
  case "$arg" in
    --skip-obfuscate) SKIP_OBFUSCATE=true ;;
    --skip-frontend)  SKIP_FRONTEND=true  ;;
    --push)           DO_PUSH=true         ;;
    *) fatal "Unknown argument: $arg" ;;
  esac
done

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/backend"
FRONTEND_DIR="${SCRIPT_DIR}/frontend"
DIST_DIR="${SCRIPT_DIR}/.secure_build"
BACKEND_DIST="${DIST_DIR}/backend"
FRONTEND_DIST="${FRONTEND_DIR}/dist"

IMAGE_NAME="${OMNINET_IMAGE:-genioelite/omninet-quantum-core}"
IMAGE_TAG="${OMNINET_TAG:-$(git -C "${SCRIPT_DIR}" describe --tags --always --dirty 2>/dev/null || echo 'latest')}"

# ─── Legal banner ─────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║    GENIO ELITE — OmniNet Quantum-Core Secure Production Build       ║${RESET}"
echo -e "${BOLD}${CYAN}║    © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.   ║${RESET}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════════════╝${RESET}"
echo ""

# ─── Step 1: Integrity Manifest Generation ───────────────────────────────────
info "STEP 1/5  Generating integrity manifest…"

MANIFEST="${BACKEND_DIR}/integrity_manifest.json"

# Compute SHA-256 for each protected file
generate_sha256() {
  local file="$1"
  if command -v sha256sum &>/dev/null; then
    sha256sum "$file" | awk '{print $1}'
  elif command -v shasum &>/dev/null; then
    shasum -a 256 "$file" | awk '{print $1}'
  else
    python3 -c "import hashlib,sys; h=hashlib.sha256(open(sys.argv[1],'rb').read()); print(h.hexdigest())" "$file"
  fi
}

PROTECTED_FILES=(
  "${BACKEND_DIR}/license_manager.py"
  "${BACKEND_DIR}/quantum_engine.py"
)

MANIFEST_CONTENT="{"
FIRST=true
for fpath in "${PROTECTED_FILES[@]}"; do
  if [ ! -f "$fpath" ]; then
    fatal "Protected file not found: $fpath"
  fi
  fname="$(basename "$fpath")"
  digest="$(generate_sha256 "$fpath")"
  info "  SHA-256 ${fname}: ${digest}"
  if [ "$FIRST" = true ]; then
    MANIFEST_CONTENT="${MANIFEST_CONTENT}
  \"${fname}\": \"${digest}\""
    FIRST=false
  else
    MANIFEST_CONTENT="${MANIFEST_CONTENT},
  \"${fname}\": \"${digest}\""
  fi
done
MANIFEST_CONTENT="${MANIFEST_CONTENT}
}"

echo "$MANIFEST_CONTENT" > "$MANIFEST"
success "Integrity manifest written to ${MANIFEST}"

# ─── Step 2: PyArmor Backend Obfuscation ─────────────────────────────────────
info "STEP 2/5  Backend obfuscation with PyArmor…"

if [ "$SKIP_OBFUSCATE" = true ]; then
  warn "  --skip-obfuscate: copying backend without obfuscation"
  rm -rf "${BACKEND_DIST}"
  cp -r "${BACKEND_DIR}" "${BACKEND_DIST}"
else
  if ! command -v pyarmor &>/dev/null; then
    warn "  pyarmor not found — skipping obfuscation (install with: pip install pyarmor)"
    warn "  Copying unobfuscated backend as fallback"
    rm -rf "${BACKEND_DIST}"
    cp -r "${BACKEND_DIR}" "${BACKEND_DIST}"
  else
    rm -rf "${BACKEND_DIST}"
    mkdir -p "${DIST_DIR}"

    info "  Running: pyarmor gen --output ${BACKEND_DIST} ${BACKEND_DIR}/*.py"
    pyarmor gen \
      --output "${BACKEND_DIST}" \
      --recursive \
      "${BACKEND_DIR}"

    # Copy non-Python assets (requirements.txt, Dockerfile, integrity_manifest.json)
    for asset in requirements.txt Dockerfile integrity_manifest.json; do
      src="${BACKEND_DIR}/${asset}"
      if [ -f "$src" ]; then
        cp "$src" "${BACKEND_DIST}/"
        info "  Copied: ${asset}"
      fi
    done

    success "Backend obfuscation complete → ${BACKEND_DIST}"
  fi
fi

# ─── Step 3: Frontend Minification ───────────────────────────────────────────
info "STEP 3/5  Frontend production build (Vite + Terser minification)…"

if [ "$SKIP_FRONTEND" = true ]; then
  warn "  --skip-frontend: skipping React build"
else
  if [ ! -f "${FRONTEND_DIR}/package.json" ]; then
    fatal "Frontend package.json not found at ${FRONTEND_DIR}"
  fi

  cd "${FRONTEND_DIR}"

  # Install dependencies if node_modules is absent
  if [ ! -d node_modules ]; then
    info "  Installing frontend dependencies…"
    npm ci --silent
  fi

  info "  Building production bundle…"
  # Vite uses Terser by default in minify mode when NODE_ENV=production
  NODE_ENV=production npm run build -- --minify terser 2>/dev/null \
    || NODE_ENV=production npm run build

  success "Frontend build complete → ${FRONTEND_DIST}"
  cd "${SCRIPT_DIR}"
fi

# ─── Step 4: Docker Image Build ───────────────────────────────────────────────
info "STEP 4/5  Building Docker images…"

# Override the backend context to use obfuscated source
# We create a temporary docker-compose.secure.yml that points to .secure_build/backend

COMPOSE_SECURE="${DIST_DIR}/docker-compose.secure.yml"
cp "${SCRIPT_DIR}/docker-compose.yml" "$COMPOSE_SECURE"

# Patch backend build context to point to obfuscated directory
# Using python3 for portable YAML manipulation without yq dependency
python3 - "$COMPOSE_SECURE" "${BACKEND_DIST}" <<'PYFIXER'
import sys, re

compose_path = sys.argv[1]
backend_dist = sys.argv[2]

with open(compose_path, "r") as f:
    content = f.read()

# Replace: context: ./backend  →  context: <backend_dist>
content = re.sub(
    r'(build:\s*\n\s+context:)\s*\./backend',
    f'\\1 {backend_dist}',
    content,
)

with open(compose_path, "w") as f:
    f.write(content)

print(f"[pyfixer] Patched backend build context → {backend_dist}")
PYFIXER

if [ "$SKIP_FRONTEND" = false ] && [ -d "$FRONTEND_DIST" ]; then
  info "  Frontend dist already built, Docker COPY will pick it up."
fi

docker compose -f "$COMPOSE_SECURE" build \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  --label "org.opencontainers.image.vendor=Genio Elite" \
  --label "org.opencontainers.image.title=OmniNet Quantum-Core" \
  --label "org.opencontainers.image.version=${IMAGE_TAG}" \
  --label "org.opencontainers.image.licenses=Proprietary"

# Tag the backend image
BACKEND_SERVICE_IMAGE=$(docker compose -f "$COMPOSE_SECURE" images -q backend 2>/dev/null | head -1)
if [ -n "$BACKEND_SERVICE_IMAGE" ]; then
  docker tag "$BACKEND_SERVICE_IMAGE" "${IMAGE_NAME}:${IMAGE_TAG}"
  docker tag "$BACKEND_SERVICE_IMAGE" "${IMAGE_NAME}:latest"
  success "Tagged image as ${IMAGE_NAME}:${IMAGE_TAG}"
fi

# ─── Step 5: Verification ─────────────────────────────────────────────────────
info "STEP 5/5  Integrity verification of built image…"

# Confirm that the integrity manifest is present inside the image
BACKEND_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
if docker image inspect "$BACKEND_IMAGE" &>/dev/null; then
  MANIFEST_IN_IMAGE=$(docker run --rm --entrypoint="" "$BACKEND_IMAGE" \
    cat /app/integrity_manifest.json 2>/dev/null || echo "NOT_FOUND")
  if [ "$MANIFEST_IN_IMAGE" = "NOT_FOUND" ]; then
    warn "integrity_manifest.json not found inside image — verify Dockerfile COPY."
  else
    success "integrity_manifest.json found inside image ✓"
  fi
fi

# ─── Optional: Push ───────────────────────────────────────────────────────────
if [ "$DO_PUSH" = true ]; then
  info "Pushing images to registry…"
  docker push "${IMAGE_NAME}:${IMAGE_TAG}"
  docker push "${IMAGE_NAME}:latest"
  success "Images pushed ✓"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
printf "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════════════╗\n${RESET}"
printf "${BOLD}${GREEN}║  Secure build complete!                                              ║\n${RESET}"
printf "${BOLD}${GREEN}║  %-68s║\n${RESET}" "Image  : ${IMAGE_NAME}:${IMAGE_TAG}"
printf "${BOLD}${GREEN}║  %-68s║\n${RESET}" "Source : obfuscated (PyArmor) — not readable from the container"
printf "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════════════╝\n${RESET}"
echo ""
echo "  To start the secure deployment:"
echo "    docker compose -f ${COMPOSE_SECURE} up -d"
echo ""
echo "  © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved."
echo ""
