#!/bin/bash

# SoundMatch - Quick Setup Script
# This script helps you set up the project for local development

set -e

echo "🎵 SoundMatch - Setup Script"
echo "=============================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

# Check Go
if ! command -v go &> /dev/null; then
    echo -e "${YELLOW}⚠️  Go is not installed. Please install Go 1.21+ from https://go.dev${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Go $(go version | awk '{print $3}')${NC}"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${YELLOW}⚠️  Node.js is not installed. Please install Node.js 20+ from https://nodejs.org${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Node.js $(node --version)${NC}"

# Check PostgreSQL client
if ! command -v psql &> /dev/null; then
    echo -e "${YELLOW}⚠️  PostgreSQL client is not installed. Install it to set up the database.${NC}"
fi

echo ""
echo -e "${BLUE}Setting up backend...${NC}"

# Backend setup
cd backend

# Copy .env.example if .env doesn't exist
if [ ! -f .env ]; then
    echo "Creating backend/.env from .env.example..."
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Please edit backend/.env with your API keys and database URL${NC}"
fi

# Download Go dependencies
echo "Installing Go dependencies..."
go mod download
go mod tidy

echo -e "${GREEN}✓ Backend setup complete${NC}"

cd ..

echo ""
echo -e "${BLUE}Setting up frontend...${NC}"

# Frontend setup
# Copy frontend.env.example if .env.local doesn't exist
if [ ! -f .env.local ]; then
    echo "Creating .env.local from frontend.env.example..."
    cp frontend.env.example .env.local
fi

# Install npm dependencies
echo "Installing npm dependencies..."
npm install

echo -e "${GREEN}✓ Frontend setup complete${NC}"

echo ""
echo -e "${BLUE}Setting up infrastructure...${NC}"

cd infrastructure

if [ ! -f terraform.tfvars ]; then
    echo "Creating terraform.tfvars from terraform.tfvars.example..."
    cp terraform.tfvars.example terraform.tfvars
    echo -e "${YELLOW}⚠️  Please edit infrastructure/terraform.tfvars with your configuration${NC}"
fi

cd ..

echo ""
echo "=============================="
echo -e "${GREEN}✓ Setup complete!${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Configure your environment:"
echo "   - Edit backend/.env with your API keys"
echo "   - Edit infrastructure/terraform.tfvars for deployment"
echo ""
echo "2. Set up your database:"
echo "   - Create a PostgreSQL database (recommended: https://neon.tech)"
echo "   - Run: psql \$DATABASE_URL -f infrastructure/schema.sql"
echo ""
echo "3. Start development servers:"
echo "   - Backend:  cd backend && go run main.go"
echo "   - Frontend: npm run dev"
echo ""
echo "4. For production deployment:"
echo "   - See DEPLOYMENT.md for detailed instructions"
echo ""
echo "📚 Documentation:"
echo "   - README.md - Full documentation"
echo "   - DEPLOYMENT.md - Deployment guide"
echo ""
echo "Happy coding! 🎵"

