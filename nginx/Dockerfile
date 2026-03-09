# (c) 2021-2026 Jonathan Kamu / Genio Elite. Tous droits réservés.
# nginx/Dockerfile — OmniNet Quantum-Core Reverse Proxy (TLS-enabled)

FROM nginx:alpine

# Install openssl for self-signed certificate generation
RUN apk add --no-cache openssl

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy the certificate generation entrypoint script
COPY generate-certs.sh /docker-entrypoint.d/10-generate-certs.sh
RUN chmod +x /docker-entrypoint.d/10-generate-certs.sh

# Default certificate directory (override with NGINX_CERT_DIR env var)
ENV NGINX_CERT_DIR=/etc/nginx/certs

EXPOSE 80 443

# The entrypoint generates self-signed certs if none are present, then starts nginx
ENTRYPOINT ["/bin/sh", "/docker-entrypoint.d/10-generate-certs.sh"]
