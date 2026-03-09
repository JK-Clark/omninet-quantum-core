#!/bin/sh
# (c) 2021-2026 Jonathan Kamu / Genio Elite. Tous droits réservés.
# nginx/generate-certs.sh — Generate self-signed TLS certificates for OmniNet Quantum-Core
#
# Usage: called automatically by the nginx Dockerfile ENTRYPOINT.
# In production, mount real Let's Encrypt certificates at NGINX_CERT_DIR and
# this script will detect them and skip generation.

set -e

CERT_DIR="${NGINX_CERT_DIR:-/etc/nginx/certs}"
CERT_FILE="${CERT_DIR}/server.crt"
KEY_FILE="${CERT_DIR}/server.key"

mkdir -p "${CERT_DIR}"

if [ -f "${CERT_FILE}" ] && [ -f "${KEY_FILE}" ]; then
    echo "[nginx/generate-certs.sh] Certificates already present at ${CERT_DIR} — skipping generation."
else
    echo "[nginx/generate-certs.sh] Generating self-signed TLS certificate in ${CERT_DIR}..."
    openssl req -x509 \
        -nodes \
        -days 365 \
        -newkey rsa:4096 \
        -keyout "${KEY_FILE}" \
        -out "${CERT_FILE}" \
        -subj "/C=CA/ST=Quebec/L=Montreal/O=Genio Elite/OU=OmniNet/CN=omninet.local" \
        -addext "subjectAltName=DNS:omninet.local,DNS:localhost,IP:127.0.0.1" \
        2>/dev/null
    chmod 600 "${KEY_FILE}"
    chmod 644 "${CERT_FILE}"
    echo "[nginx/generate-certs.sh] Self-signed certificate generated."
    echo "[nginx/generate-certs.sh] WARNING: Replace with real certificates before production use."
fi

# Start nginx
exec nginx -g "daemon off;"
