# 🎵 START HERE - SoundMatch

## 📂 Project Structure

```
sonic-synergy-hub/
│
├── 🔧 backend/                 # Backend en Go
│   ├── main.go                 # Punto de entrada Lambda
│   ├── internal/
│   │   ├── api/                # Handlers HTTP
│   │   ├── db/                 # Cliente PostgreSQL
│   │   ├── recommendations/    # Algoritmos de recomendación
│   │   ├── security/           # Auth & rate limiting
│   │   └── spotify/            # Cliente Spotify API
│   └── Makefile                # Comandos de build
│
├── 🏢 infrastructure/          # Terraform (AWS)
│   ├── main.tf                 # Recursos AWS
│   ├── schema.sql              # Schema de la DB
│   └── terraform.tfvars.example
│
├── ⚙️ .github/workflows/       # CI/CD
│   ├── deploy.yaml             # Deploy backend
│   └── deploy-frontend.yaml    # Deploy frontend
│
├── 🎨 src/                     # React Frontend
│   ├── lib/api-client.ts       # Cliente API REST
│   ├── hooks/useAuth.tsx       # Hook de autenticación
│   ├── pages/
│   │   ├── Dashboard.tsx       # Página principal
│   │   └── Auth.tsx            # Login/Register
│   └── components/
│       ├── SongSearch.tsx      # Búsqueda de canciones
│       └── SongRecommendations.tsx
│
└── 📝 Documentación
    ├── START_HERE.md          # 👈 Este archivo
    ├── QUICKSTART.md
    └── README.md
```

---

## 🚀 Inicio Rápido (5 minutos)

### 1️⃣ Instalar Dependencias

```bash
# Ejecuta el script de setup automático
./setup.sh
```

### 2️⃣ Obtener Credenciales

**Spotify API** (2 minutos)
- Ve a: https://developer.spotify.com/dashboard
- Crea una app → Copia Client ID y Client Secret

**Last.fm API** (1 minuto)
- Ve a: https://www.last.fm/api/account/create
- Crea cuenta → Copia API Key

**Base de Datos** (2 minutos - GRATIS)
- Ve a: https://neon.tech
- Crea proyecto → Copia connection string

### 3️⃣ Configurar

```bash
# Edita backend/.env
nano backend/.env

# Pega tus credenciales:
SPOTIFY_CLIENT_ID=tu_client_id
SPOTIFY_CLIENT_SECRET=tu_client_secret
LASTFM_API_KEY=tu_api_key
DATABASE_URL=tu_connection_string
```

### 4️⃣ Inicializar Base de Datos

```bash
psql $DATABASE_URL -f infrastructure/schema.sql
```

### 5️⃣ ¡Ejecutar!

```bash
# Terminal 1 - Backend
cd backend
go run main.go

# Terminal 2 - Frontend
npm run dev

# Abre: http://localhost:5173
```

---

## 📚 Documentación

| Archivo | Para qué sirve |
|---------|---------------|
| **QUICKSTART.md** | 👈 Empieza aquí - Guía de 5 minutos |
| **README.md** | Documentación completa del proyecto |
| **DEPLOYMENT.md** | Guía de despliegue a producción |

---

## 🎯 Funcionalidades

### ✅ Implementadas

- ✅ Búsqueda de canciones (Spotify)
- ✅ Recomendaciones con Last.fm (collaborative filtering)
- ✅ Recomendaciones personalizadas (content-based)
- ✅ Análisis de audio features
- ✅ Autenticación de usuarios (JWT)
- ✅ Gestión de playlists
- ✅ Preview de audio
- ✅ Rate limiting
- ✅ UI moderna y responsive

### 📋 Algoritmos de Recomendación

1. **Last.fm** (Recomendado)
   - Basado en patrones de millones de usuarios
   - Rápido y preciso
   - Ideal para música popular

2. **Custom**
   - Basado en características de audio
   - Funciona para música nueva/underground
   - Control granular sobre features

---

## 🧪 Probar la API

```bash
# Ejecuta el script de testing
./scripts/test-local.sh

# Prueba manualmente
curl http://localhost:8080/health
```

---

## 🌍 Desplegar a Producción

### Opción 1: Automático con GitHub Actions

```bash
# 1. Configura secrets en GitHub
# (Ver DEPLOYMENT.md para lista completa)

# 2. Push a main
git push origin main

# 3. ¡Listo! GitHub Actions despliega automáticamente
```

### Opción 2: Manual con Terraform

```bash
# 1. Build backend
cd backend
make build

# 2. Deploy con Terraform
cd ../infrastructure
terraform init
terraform apply

# 3. Deploy frontend
npm run build
netlify deploy --prod
```

**Ver DEPLOYMENT.md para guía completa paso a paso.**

---

## 💡 Comandos Útiles

```bash
# Development
./setup.sh                      # Setup inicial
cd backend && go run main.go    # Iniciar backend
npm run dev                     # Iniciar frontend

# Testing
./scripts/test-local.sh         # Test API local
cd backend && go test ./...     # Test Go
npm run lint                    # Lint frontend

# Build
cd backend && make build        # Build Lambda
npm run build                   # Build React

# Deploy
cd infrastructure && terraform apply  # Deploy backend
netlify deploy --prod                 # Deploy frontend
```

---

## ❓ FAQ

### ¿Necesito AWS para desarrollo local?
**No.** Puedes desarrollar completamente en local sin AWS. Solo necesitas:
- Go instalado
- PostgreSQL (o Neon gratis)
- Credenciales de Spotify y Last.fm

### ¿Cuánto cuesta en producción?
**$0-5/mes** usando los free tiers de:
- AWS Lambda (1M requests/mes gratis)
- Neon PostgreSQL (3GB gratis)
- Netlify (100GB bandwidth gratis)

---

## 🆘 Problemas Comunes

### Backend no inicia
```bash
# Verifica que Go esté instalado
go version

# Reinstala dependencias
cd backend
go mod tidy
```

### Frontend no conecta al backend
```bash
# Verifica .env.local
cat .env.local
# Debe tener: VITE_API_URL=http://localhost:8080

# Verifica que el backend esté corriendo
curl http://localhost:8080/health
```

### Error de base de datos
```bash
# Verifica la conexión
psql $DATABASE_URL -c "SELECT 1;"

# Reinicia el schema
psql $DATABASE_URL -f infrastructure/schema.sql
```

---

## 📞 Soporte

- 📖 **Documentación**: Lee QUICKSTART.md y README.md
- 🐛 **Bugs**: Abre un issue en GitHub
- 💬 **Preguntas**: GitHub Discussions
- 🔧 **Troubleshooting**: Ver DEPLOYMENT.md

---

## ✅ Checklist de Inicio

- [ ] Ejecutar `./setup.sh`
- [ ] Obtener credenciales de APIs
- [ ] Configurar `backend/.env`
- [ ] Crear base de datos en Neon
- [ ] Ejecutar schema SQL
- [ ] Iniciar backend (`cd backend && go run main.go`)
- [ ] Iniciar frontend (`npm run dev`)
- [ ] Probar en http://localhost:5173
- [ ] Registrar usuario
- [ ] Buscar canciones
- [ ] ¡Obtener recomendaciones! 🎵

---

## 🎉 ¡Todo Listo!

**Próximos pasos:**
1. Lee **QUICKSTART.md** para empezar
2. Experimenta en local
3. Cuando estés listo, lee **DEPLOYMENT.md** para producción

**¡Disfruta tu app de música! 🎵🚀**
