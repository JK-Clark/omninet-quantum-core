# (c) 2021-2026 Jonathan Kamu / Genio Elite. Tous droits réservés.
# backend/main.py — OmniNet Quantum-Core FastAPI Application

from fastapi import FastAPI

BANNER = r"""
  ██████╗ ███████╗███╗   ██╗██╗ ██████╗     ███████╗██╗     ██╗████████╗███████╗
 ██╔════╝ ██╔════╝████╗  ██║██║██╔═══██╗    ██╔════╝██║     ██║╚══██╔══╝██╔════╝
 ██║  ███╗█████╗  ██╔██╗ ██║██║██║   ██║    █████╗  ██║     ██║   ██║   █████╗  
 ██║   ██║██╔══╝  ██║╚██╗██║██║██║   ██║    ██╔══╝  ██║     ██║   ██║   ██╔══╝  
 ╚██████╔╝███████╗██║ ╚████║██║╚██████╔╝    ███████╗███████╗██║   ██║   ███████╗
  ╚═════╝ ╚══════╝╚═╝  ╚═══╝╚═╝ ╚═════╝     ╚══════╝╚══════╝╚═╝   ╚═╝   ╚══════╝
                  OmniNet Quantum-Core — Universal Network Orchestrator
                        (c) 2021-2026 Jonathan Kamu / Genio Elite
"""

app = FastAPI(title="OmniNet Quantum-Core", version="1.0.0")


@app.on_event("startup")
async def on_startup() -> None:
    print(BANNER, flush=True)


@app.get("/")
async def read_root():
    return {"Hello": "World"}


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
