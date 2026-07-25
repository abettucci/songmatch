# ⚡ Quick Start Guide

Get SoundMatch running in 5 minutes!

## 🎯 Prerequisites

- Go 1.21+ ([Download](https://go.dev))
- Node.js 20+ ([Download](https://nodejs.org))
- PostgreSQL database ([Free: Neon.tech](https://neon.tech))
- Spotify API keys ([Get here](https://developer.spotify.com/dashboard))
- Last.fm API key ([Get here](https://www.last.fm/api/account/create))

## 🚀 Installation

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd sonic-synergy-hub-50-main

# Run automated setup
./setup.sh
```

### 2. Get API Keys

#### Spotify
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click "Create an App"
3. Copy **Client ID** and **Client Secret**

#### Last.fm
1. Go to [Last.fm API](https://www.last.fm/api/account/create)
2. Create an API account
3. Copy the **API Key**

### 3. Configure Backend

Edit `backend/.env`:

```bash
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
LASTFM_API_KEY=your_lastfm_key_here
DATABASE_URL=postgresql://user:pass@host:5432/soundmatch?sslmode=require
```

### 4. Setup Database

#### Option A: Neon (Recommended - Free)

```bash
# 1. Sign up at https://neon.tech
# 2. Create a new project
# 3. Copy the connection string
# 4. Run the schema:

psql "your_neon_connection_string" -f infrastructure/schema.sql
```

#### Option B: Local PostgreSQL

```bash
# Create database
createdb soundmatch

# Run schema
psql soundmatch -f infrastructure/schema.sql

# Update DATABASE_URL in backend/.env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/soundmatch
```

### 5. Start Development

#### Terminal 1 - Backend

```bash
cd backend
go run main.go

# Server running on http://localhost:8080
```

#### Terminal 2 - Frontend

```bash
npm run dev

# Frontend running on http://localhost:5173
```

### 6. Test It!

1. Open http://localhost:5173
2. Click "Sign up" and create an account
3. Search for a song (e.g., "Beatles")
4. Select 2-3 songs as seeds
5. Click "Get Recommendations"
6. Enjoy your music recommendations! 🎵

## 🔧 Troubleshooting

### Backend won't start

```bash
# Check if port 8080 is in use
lsof -ti:8080

# Install dependencies
cd backend
go mod tidy
```

### Frontend can't connect to backend

```bash
# Verify .env.local has correct API URL
cat .env.local

# Should show:
# VITE_API_URL=http://localhost:8080
```

### Database connection failed

```bash
# Test connection
psql $DATABASE_URL -c "SELECT 1;"

# If it fails, check:
# - Connection string format
# - Database exists
# - Network access allowed
```

### Spotify API errors

```bash
# Test Spotify credentials
curl -X POST https://accounts.spotify.com/api/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -u "CLIENT_ID:CLIENT_SECRET"

# Should return an access token
```

## 📱 Using the App

### Search for Songs
- Type artist, song, or album name
- Click on results to add to seeds
- Maximum 5 seed songs

### Get Recommendations
1. Select algorithm:
   - **Last.fm**: Based on user behavior (default)
   - **Custom**: Based on audio features
2. Adjust preferences (optional)
3. Click "Get Recommendations"

### Save Playlists
- Click "Save Playlist" on recommendations
- Name your playlist
- Access from your profile

## 🚀 Deploy to Production

Ready to deploy? See [DEPLOYMENT.md](./DEPLOYMENT.md) for complete instructions.

**Quick deploy with GitHub Actions:**

```bash
# 1. Push to GitHub
git push origin main

# 2. Configure GitHub Secrets (see DEPLOYMENT.md)

# 3. GitHub Actions will automatically deploy!
```

## 📚 More Documentation

- [README.md](./README.md) - Complete documentation
- [DEPLOYMENT.md](./DEPLOYMENT.md) - Production deployment

## 💡 Tips

### Development

```bash
# Watch Go files for changes
cd backend
go install github.com/cosmtrek/air@latest
air

# Frontend hot reload (automatic with Vite)
npm run dev
```

### Testing

```bash
# Test backend
cd backend
go test ./... -v

# Test API endpoints
curl http://localhost:8080/health
```

### Clean Rebuild

```bash
# Backend
cd backend
go clean
rm -f bootstrap function.zip
make build

# Frontend
rm -rf node_modules dist
npm install
npm run build
```

## 🆘 Need Help?

1. Check [DEPLOYMENT.md](./DEPLOYMENT.md) troubleshooting section
2. Review [README_NEW.md](./README_NEW.md) for detailed docs
3. Open an issue on GitHub
4. Check the logs:
   - Backend: Terminal where `go run main.go` is running
   - Frontend: Browser console (F12)

## ⭐ Quick Commands

```bash
# Setup everything
./setup.sh

# Start backend
cd backend && go run main.go

# Start frontend
npm run dev

# Build for production
cd backend && make build
npm run build

# Deploy to AWS
cd infrastructure && terraform apply

# Deploy to Netlify
npm run build && netlify deploy --prod
```

---

**You're all set! Start building amazing music recommendations! 🎵**

