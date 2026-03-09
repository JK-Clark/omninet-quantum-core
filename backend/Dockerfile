# (c) 2021-2026 Jonathan Kamu / Genio Elite. Tous droits réservés.
# backend/Dockerfile — OmniNet Quantum-Core Backend (FastAPI / Uvicorn)

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
# Enforce correct bcrypt version (wipe any preinstalled)
RUN pip install --upgrade pip \ 
    && pip uninstall -y bcrypt \ 
    && pip install bcrypt==3.2.2 \ 
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Production ───────────────────────────────────────────────────────
FROM python:3.12-slim AS production

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \ 
    && rm -rf /var/lib/apt/lists/*

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]