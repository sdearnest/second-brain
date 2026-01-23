#!/bin/bash
#
# Second Brain - First-time Setup Script
# Creates directories, generates .env from template, and starts services
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "╔════════════════════════════════════════════════════════╗"
echo "║           Second Brain - Setup Script                  ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# ============================================
# Check prerequisites
# ============================================
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✓ Docker and Docker Compose found"
echo ""

# ============================================
# Create data directories
# ============================================
echo "Creating data directories..."

mkdir -p data/n8n
mkdir -p data/nextcloud/html
mkdir -p data/nextcloud/data
mkdir -p data/nextcloud-db
mkdir -p data/vault/People
mkdir -p data/vault/Projects
mkdir -p data/vault/Ideas
mkdir -p data/vault/Admin
mkdir -p "data/vault/Inbox Log"
mkdir -p "data/vault/Daily Notes"
mkdir -p data/simplex
mkdir -p data/simplex-bridge

echo "✓ Data directories created"
echo ""

# ============================================
# Create .env file
# ============================================
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    
    if [ -f .env.example ]; then
        cp .env.example .env
        
        # Generate random passwords
        N8N_PASS=$(openssl rand -base64 16 | tr -d '=/+' | head -c 20)
        NC_DB_PASS=$(openssl rand -base64 16 | tr -d '=/+' | head -c 20)
        NC_ROOT_PASS=$(openssl rand -base64 16 | tr -d '=/+' | head -c 20)
        
        # Replace placeholders (works on both Linux and macOS)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/CHANGE_THIS_PASSWORD/$N8N_PASS/g" .env
            sed -i '' "s/CHANGE_THIS_DB_PASSWORD/$NC_DB_PASS/g" .env
            sed -i '' "s/CHANGE_THIS_ROOT_PASSWORD/$NC_ROOT_PASS/g" .env
        else
            # Linux
            sed -i "s/CHANGE_THIS_PASSWORD/$N8N_PASS/g" .env
            sed -i "s/CHANGE_THIS_DB_PASSWORD/$NC_DB_PASS/g" .env
            sed -i "s/CHANGE_THIS_ROOT_PASSWORD/$NC_ROOT_PASS/g" .env
        fi
        
        echo "✓ .env file created with generated passwords"
        echo ""
        echo "⚠️  IMPORTANT: Edit .env to set your Nextcloud app password:"
        echo "   NEXTCLOUD_PASSWORD=YOUR_NEXTCLOUD_APP_PASSWORD"
        echo ""
    else
        echo "❌ .env.example not found!"
        exit 1
    fi
else
    echo "✓ .env file already exists"
fi
echo ""

# ============================================
# Fix permissions
# ============================================
echo "Setting permissions..."

# Make scripts executable
chmod +x scripts/*.sh 2>/dev/null || true
chmod +x scripts/*.py 2>/dev/null || true
chmod +x simplex/start-simplex.sh 2>/dev/null || true

# Set proper ownership for data directories
# (may need sudo depending on setup)
if [ "$EUID" -eq 0 ]; then
    chown -R 1000:1000 data/n8n 2>/dev/null || true
    chown -R 33:33 data/nextcloud 2>/dev/null || true
    chown -R 1001:1001 data/simplex 2>/dev/null || true
fi

echo "✓ Permissions set"
echo ""

# ============================================
# Build and start services
# ============================================
echo "Building Docker images..."
docker compose build

echo ""
echo "Starting services..."
docker compose up -d

echo ""
echo "Waiting for services to start..."
sleep 10

# ============================================
# Health check
# ============================================
echo ""
echo "Running health checks..."

# Check n8n
if curl -s -o /dev/null -w "%{http_code}" http://localhost:5678/healthz | grep -q "200"; then
    echo "✓ n8n is running at http://localhost:5678"
else
    echo "⚠ n8n may still be starting..."
fi

# Check Nextcloud
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8088/status.php 2>/dev/null | grep -q "200\|302"; then
    echo "✓ Nextcloud is running at http://localhost:8088"
else
    echo "⚠ Nextcloud may still be starting (first run takes a few minutes)..."
fi

# Check Obsidian API
if curl -s http://localhost:8765/health | grep -q "healthy"; then
    echo "✓ Obsidian API is running at http://localhost:8765"
else
    echo "⚠ Obsidian API may still be starting..."
fi

# ============================================
# Summary
# ============================================
echo ""
echo "════════════════════════════════════════════════════════"
echo "                    Setup Complete!"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Services:"
echo "  • n8n:          http://localhost:5678"
echo "  • Nextcloud:    http://localhost:8088"
echo "  • Obsidian API: http://localhost:8765"
echo "  • SimpleX:      ws://localhost:5225"
echo ""
echo "Next steps:"
echo "  1. Complete Nextcloud setup at http://localhost:8088"
echo "  2. Create a Nextcloud app password for n8n"
echo "  3. Add the app password to .env (NEXTCLOUD_PASSWORD)"
echo "  4. Import your n8n workflows"
echo "  5. Connect SimpleX Chat to your bot"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f          # View all logs"
echo "  docker compose logs -f n8n      # View n8n logs"
echo "  docker compose restart          # Restart all services"
echo "  ./scripts/backup.sh             # Backup your data"
echo ""
