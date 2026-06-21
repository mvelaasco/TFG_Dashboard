# TFG Informática — Ingesta, visualización y análisis de datos financieros

## Requisitos

- Docker y Docker Compose
- API keys de [Tiingo](https://www.tiingo.com/) y [Finnhub](https://finnhub.io/)

## Puesta en marcha

```bash
cp backend/.env.example backend/.env   # editar con tus API keys

docker compose up -d                   # levanta todo

Acceder a http://localhost:3000.

Para cargar datos, ir a panel de administración con credenciales:
 - User: admin@tfg.com
 - Password: admin123

Servicios
Puerto	Servicio
3000  Interfaz visual
5555	Monitor Celery (Flower)

