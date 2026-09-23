# Inicio rápido

## Desarrollo local

```bash
npm install
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Completa en `backend/.env` las credenciales de Spotify y Last.fm. Para levantar PostgreSQL local y la API:

```bash
docker compose up --build
```

En otra terminal, desde la raíz del repositorio:

```bash
cp frontend.env.example .env.local
npm run dev
```

El frontend queda en `http://localhost:5173` y la API en `http://localhost:8080`.

## Base Supabase

Para conectar un proyecto Supabase durante desarrollo, colocá su URL de **Transaction pooler** en `DATABASE_URL`, con `?sslmode=require`, y aplicá el esquema en una base nueva:

```bash
psql "$DATABASE_URL" -f infrastructure/schema.sql
```

No expongas esa URL como variable `VITE_*`.

## Producción

El frontend se publica desde Vercel. La guía completa para conectar Vercel, Lambda y Supabase está en [DEPLOYMENT.md](./DEPLOYMENT.md).
