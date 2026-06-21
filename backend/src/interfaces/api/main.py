from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.init_db import init_db

from interfaces.api.routers import admin, assets, metrics, news, auth, rules

app = FastAPI(
    title="TFG Finance API",
    description="Sistema de análisis financiero — Backend",
    version="0.1.0",
)

# Definir explícitamente los orígenes permitidos en desarrollo
# En producción, esto se leerá de las variables de entorno (settings.CORS_ORIGINS)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # Cambiado: Lista explícita en lugar de "*"
    allow_credentials=True,         # Cambiado: Permitir cookies/auth headers obligatoriamente
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(assets.router)
app.include_router(metrics.router)
app.include_router(news.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(rules.router)

@app.on_event("startup")
async def on_startup():
    await init_db()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}