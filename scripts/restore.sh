#!/bin/bash
#
# Second Brain - Restore Script
# Restores data from a backup archive
#
# Usage:
#   ./scripts/restore.sh                           # List available backups
#   ./scripts/restore.sh backup-file.tar.gz        # Restore specific backup
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_DIR/data"
BACKUP_DIR="$PROJECT_DIR/backups"

echo "╔════════════════════════════════════════════════════════╗"
echo "║           Second Brain - Restore Script                ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# ============================================
# If no argument, list available backups
# ============================================
if [ -z "$1" ]; then
    echo "Available backups:"
    echo ""
    
    if [ -d "$BACKUP_DIR" ] && [ "$(ls -A $BACKUP_DIR/*.tar.gz 2>/dev/null)" ]; then
        ls -lh "$BACKUP_DIR"/*.tar.gz 2>/dev/null | awk '{print "  " $NF " (" $5 ")"}'
    else
        echo "  No backups found in $BACKUP_DIR"
    fi
    
    echo ""
    echo "Usage: ./scripts/restore.sh <backup-file>"
    echo ""
    echo "Example:"
    echo "  ./scripts/restore.sh backups/second-brain-backup-20260122_120000.tar.gz"
    echo ""
    exit 0
fi

# ============================================
# Validate backup file
# ============================================
BACKUP_FILE="$1"

# If relative path without directory, check backups dir
if [ ! -f "$BACKUP_FILE" ] && [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
    BACKUP_FILE="$BACKUP_DIR/$BACKUP_FILE"
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Backup file: $BACKUP_FILE"
echo ""

# ============================================
# Confirm restore
# ============================================
echo "⚠️  WARNING: This will REPLACE all current data!"
echo ""
read -p "Are you sure you want to restore? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo ""

# ============================================
# Stop services
# ============================================
echo "Stopping services..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" stop 2>/dev/null || true

# ============================================
# Backup current data (just in case)
# ============================================
if [ -d "$DATA_DIR" ]; then
    echo "Creating safety backup of current data..."
    SAFETY_BACKUP="$PROJECT_DIR/data-pre-restore-$(date +%Y%m%d_%H%M%S).tar.gz"
    tar -czf "$SAFETY_BACKUP" data/ 2>/dev/null || true
    echo "  Safety backup: $SAFETY_BACKUP"
fi

# ============================================
# Remove current data
# ============================================
echo "Removing current data..."
rm -rf "$DATA_DIR"

# ============================================
# Extract backup
# ============================================
echo "Extracting backup..."
cd "$PROJECT_DIR"
tar -xzf "$BACKUP_FILE"

# ============================================
# Restore .env if included in backup
# ============================================
if tar -tzf "$BACKUP_FILE" | grep -q "^\.env$"; then
    echo "✓ .env restored from backup"
else
    echo "⚠ .env not in backup - keeping current .env"
fi

# ============================================
# Fix permissions
# ============================================
echo "Fixing permissions..."
if [ "$EUID" -eq 0 ]; then
    chown -R 1000:1000 data/n8n 2>/dev/null || true
    chown -R 33:33 data/nextcloud 2>/dev/null || true
    chown -R 1001:1001 data/simplex 2>/dev/null || true
fi

# ============================================
# Start services
# ============================================
echo "Starting services..."
docker compose -f "$PROJECT_DIR/docker-compose.yml" up -d

echo ""
echo "════════════════════════════════════════════════════════"
echo "                  Restore Complete!"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Services are starting. Check status with:"
echo "  docker compose logs -f"
echo ""
