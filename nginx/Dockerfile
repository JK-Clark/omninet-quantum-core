# (c) 2021-2026 Jonathan Kamu / Genio Elite. Tous droits réservés.
# nginx/Dockerfile — OmniNet Quantum-Core Reverse Proxy

FROM nginx:alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
