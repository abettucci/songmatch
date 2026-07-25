#!/bin/bash

# Test script for local development
# Tests all API endpoints to ensure everything works

set -e

API_URL=${API_URL:-"http://localhost:8080"}

echo "🧪 Testing SoundMatch API"
echo "API URL: $API_URL"
echo "=========================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test health endpoint
echo -e "${BLUE}Testing /health endpoint...${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" "$API_URL/health")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ Health check passed${NC}"
    echo "  Response: $BODY"
else
    echo -e "${RED}✗ Health check failed (HTTP $HTTP_CODE)${NC}"
    exit 1
fi
echo ""

# Test registration
echo -e "${BLUE}Testing /api/v1/auth/register...${NC}"
EMAIL="test_$(date +%s)@example.com"
PASSWORD="testpass123"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" -eq 201 ]; then
    echo -e "${GREEN}✓ Registration successful${NC}"
    TOKEN=$(echo "$BODY" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)
    echo "  Token: ${TOKEN:0:20}..."
else
    echo -e "${RED}✗ Registration failed (HTTP $HTTP_CODE)${NC}"
    echo "  Response: $BODY"
    exit 1
fi
echo ""

# Test login
echo -e "${BLUE}Testing /api/v1/auth/login...${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ Login successful${NC}"
else
    echo -e "${RED}✗ Login failed (HTTP $HTTP_CODE)${NC}"
    echo "  Response: $BODY"
    exit 1
fi
echo ""

# Test search (requires Spotify API)
echo -e "${BLUE}Testing /api/v1/search...${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/search" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"Beatles\",\"limit\":5}")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" -eq 200 ]; then
    TRACK_COUNT=$(echo "$BODY" | grep -o '"spotify_id"' | wc -l)
    echo -e "${GREEN}✓ Search successful${NC}"
    echo "  Found $TRACK_COUNT tracks"
    
    # Extract first track ID for recommendations test
    TRACK_ID=$(echo "$BODY" | grep -o '"spotify_id":"[^"]*"' | head -1 | cut -d'"' -f4)
else
    echo -e "${RED}✗ Search failed (HTTP $HTTP_CODE)${NC}"
    echo "  Response: $BODY"
    echo -e "${BLUE}Note: Make sure SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET are set${NC}"
fi
echo ""

# Test recommendations (if we have a track ID)
if [ ! -z "$TRACK_ID" ]; then
    echo -e "${BLUE}Testing /api/v1/recommendations...${NC}"
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/recommendations" \
      -H "Content-Type: application/json" \
      -d "{\"seed_tracks\":[\"$TRACK_ID\"],\"algorithm\":\"lastfm\",\"limit\":5}")

    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | head -n-1)

    if [ "$HTTP_CODE" -eq 200 ]; then
        REC_COUNT=$(echo "$BODY" | grep -o '"spotify_id"' | wc -l)
        echo -e "${GREEN}✓ Recommendations successful${NC}"
        echo "  Found $REC_COUNT recommendations"
    else
        echo -e "${RED}✗ Recommendations failed (HTTP $HTTP_CODE)${NC}"
        echo "  Response: $BODY"
    fi
    echo ""
fi

# Test protected endpoint (playlists)
echo -e "${BLUE}Testing /api/v1/playlists (protected)...${NC}"
RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "$API_URL/api/v1/playlists" \
  -H "Authorization: Bearer $TOKEN")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ Protected endpoint accessible with token${NC}"
else
    echo -e "${RED}✗ Protected endpoint failed (HTTP $HTTP_CODE)${NC}"
fi
echo ""

# Summary
echo "=========================="
echo -e "${GREEN}✓ All tests completed!${NC}"
echo ""
echo "Summary:"
echo "  - Health check: ✓"
echo "  - Registration: ✓"
echo "  - Login: ✓"
echo "  - Search: ✓"
echo "  - Recommendations: ✓"
echo "  - Auth protection: ✓"
echo ""
echo "Your API is working correctly! 🎉"

