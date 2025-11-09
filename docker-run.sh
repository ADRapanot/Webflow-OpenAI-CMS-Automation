#!/bin/bash

# Webflow CMS Automation - Docker Helper Script

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Webflow CMS Automation - Docker Setup    ║${NC}"
echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠ No .env file found${NC}"
    echo ""
    echo "Creating .env file template..."
    cat > .env << 'EOF'
# Required Environment Variables
OPENAI_API_KEY=your_openai_api_key_here
WEBFLOW_TOKEN=your_webflow_token_here

# Optional
PORT=5000
EOF
    echo -e "${GREEN}✓ Created .env file${NC}"
    echo ""
    echo -e "${RED}Please edit .env file with your actual API keys before continuing!${NC}"
    echo "Then run this script again."
    exit 1
fi

# Verify required environment variables are set
source .env

if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "your_openai_api_key_here" ]; then
    echo -e "${RED}✗ OPENAI_API_KEY not set in .env file${NC}"
    exit 1
fi

if [ -z "$WEBFLOW_TOKEN" ] || [ "$WEBFLOW_TOKEN" = "your_webflow_token_here" ]; then
    echo -e "${RED}✗ WEBFLOW_TOKEN not set in .env file${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Environment variables validated${NC}"
echo ""

# Create necessary directories
echo "Creating directories..."
mkdir -p images best_match content
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Build Docker image
echo -e "${BLUE}Building Docker image...${NC}"
docker build -t webflow-cms-automation .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
else
    echo -e "${RED}✗ Docker build failed${NC}"
    exit 1
fi
echo ""

# Stop and remove existing container if running
if [ "$(docker ps -aq -f name=webflow-cms-automation)" ]; then
    echo "Stopping existing container..."
    docker stop webflow-cms-automation 2>/dev/null || true
    docker rm webflow-cms-automation 2>/dev/null || true
    echo -e "${GREEN}✓ Existing container removed${NC}"
    echo ""
fi

# Run container
echo -e "${BLUE}Starting container...${NC}"
docker run -d \
    --name webflow-cms-automation \
    -p 5000:5000 \
    -e OPENAI_API_KEY="$OPENAI_API_KEY" \
    -e WEBFLOW_TOKEN="$WEBFLOW_TOKEN" \
    -e PORT=5000 \
    -v "$(pwd)/content:/app/content" \
    -v "$(pwd)/best_match:/app/best_match" \
    --restart unless-stopped \
    webflow-cms-automation

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Container started successfully${NC}"
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          Deployment Successful! 🚀         ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Server is running at: http://localhost:5000"
    echo "Health check: http://localhost:5000/health"
    echo ""
    echo "Useful commands:"
    echo "  View logs:    docker logs -f webflow-cms-automation"
    echo "  Stop server:  docker stop webflow-cms-automation"
    echo "  Start server: docker start webflow-cms-automation"
    echo "  Restart:      docker restart webflow-cms-automation"
    echo "  Remove:       docker rm -f webflow-cms-automation"
    echo ""
    
    # Wait a moment and check health
    echo "Checking health..."
    sleep 5
    
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Server is healthy and responding${NC}"
    else
        echo -e "${YELLOW}⚠ Server may still be starting up...${NC}"
        echo "Run: docker logs webflow-cms-automation"
    fi
else
    echo -e "${RED}✗ Failed to start container${NC}"
    exit 1
fi



