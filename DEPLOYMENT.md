# Despliegue: Vercel + Supabase + Lambda

Esta es la configuración de producción soportada por el repositorio. El frontend ya se publica en **Vercel**; no se usa Netlify. La API FastAPI corre en AWS Lambda con API Gateway y la base PostgreSQL administrada está en **Supabase**. No se crean recursos RDS, VPC ni NAT Gateway.

```
Navegador → Vercel (React) → API Gateway → Lambda (FastAPI) → Supabase Postgres
```

## Antes de empezar

- Una cuenta y proyecto en Supabase.
- El repositorio vinculado al proyecto existente de Vercel.
- Una cuenta AWS configurada solo para Lambda, API Gateway y CloudWatch.
- Credenciales de Spotify y Last.fm.
- `psql`, Terraform y Python 3.11 disponibles localmente.

Nunca copies credenciales a `VITE_*`, al repositorio, ni a logs públicos. `VITE_API_URL` es pública; `DATABASE_URL` no lo es.

## 1. Crear la base en Supabase

1. Crea un proyecto PostgreSQL en Supabase.
2. En **Connect**, copia la URL de **Transaction pooler** y agrega `?sslmode=require` si no viene incluida. Es la adecuada para Lambda porque evita acumular conexiones en cada cold start.
3. Para una base nueva, aplica el esquema completo:

```bash
psql "$DATABASE_URL" -f infrastructure/schema.sql
```

4. Para una instalación que ya tiene el esquema anterior, aplica únicamente cada archivo nuevo de `infrastructure/migrations/`, en orden. Por ejemplo:

```bash
psql "$DATABASE_URL" -f infrastructure/migrations/20260922_add_concert_companions.sql
```

Guarda la URL solamente en el gestor de secretos de AWS/GitHub o en `infrastructure/terraform.tfvars`, archivo que está ignorado por Git.

## 2. Configurar la API

Construye un ZIP de Lambda desde el backend Python:

```bash
cd backend
make build
```

Luego crea el archivo local de variables de Terraform:

```bash
cd ../infrastructure
cp terraform.tfvars.example terraform.tfvars
```

Completa estos valores reales:

- `database_url`: URL del Transaction pooler de Supabase.
- `jwt_secret_key`: valor aleatorio largo, distinto por ambiente.
- `frontend_url`: URL de producción de Vercel, por ejemplo `https://songmatch.vercel.app`.
- `cors_origins`: esa misma URL; agrega dominios adicionales separados por comas solo si son necesarios.
- `spotify_redirect_uri`: URL de callback de la API Gateway. Regístrala exactamente igual en Spotify Developer Dashboard.

Despliega tras revisar el plan:

```bash
terraform init
terraform plan
terraform apply
terraform output -raw api_endpoint
```

La infraestructura actual no adjunta la función a una VPC, precisamente para que alcance Supabase sin un NAT Gateway. Si ya tenías el Terraform antiguo aplicado, revisá cuidadosamente el `terraform plan`: eliminará los recursos RDS/VPC gestionados por ese estado. Hacé un backup antes y confirmá que la aplicación ya apunta a Supabase.

El estado remoto de Terraform se mantiene en el bucket S3 que ya usaba el proyecto; es necesario para que el plan conozca esos recursos existentes. Si ese bucket nunca se creó, configurá primero un backend de estado remoto propio o inicializá Terraform de acuerdo con las prácticas de tu cuenta AWS.

## 3. Configurar Vercel

En el proyecto de Vercel, configurá esta variable para **Production** y volvé a desplegar:

```text
VITE_API_URL=https://tu-api.execute-api.us-east-1.amazonaws.com
```

Vercel construye el frontend desde Git. El workflow de GitHub dejó de desplegar a Netlify y solo verifica que el build sea válido. Para evitar errores CORS, la URL de Vercel debe coincidir con `FRONTEND_URL` y estar incluida en `CORS_ORIGINS` de Lambda.

Los previews de Vercel tienen dominios variables. Para probar autenticación en uno, agregá explícitamente su origen a `cors_origins` y aplicá Terraform de nuevo; no abras CORS a `*`.

## 4. Verificación

```bash
curl -f "https://tu-api.execute-api.us-east-1.amazonaws.com/"
```

Después abrí el dominio de Vercel, registrá un usuario y probá una búsqueda. Si falla la conexión de datos, verificá que `DATABASE_URL` use SSL y que el esquema haya sido aplicado.

## Operación y costos

- Vercel aloja solamente assets del frontend.
- Supabase Free es apropiado para desarrollo/MVP, no para una garantía de disponibilidad: el proyecto puede pausarse por inactividad y su capacidad es limitada. Antes de habilitar usuarios reales, definí backups y el plan de subida.
- Lambda/API Gateway/CloudWatch siguen siendo recursos AWS facturables fuera de sus cuotas gratuitas. No hay costo de RDS, VPC ni NAT Gateway con esta configuración.

Para hacer un backup lógico:

```bash
pg_dump "$DATABASE_URL" > songmatch_backup.sql
```
