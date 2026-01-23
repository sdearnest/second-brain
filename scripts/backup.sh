#!/bin/bash
#
# Second Brain - Backup Script
# Creates a timestamped backup of all user data
#
# Usage:
#   ./scripts/backup.sh              # Interactive backup
#   ./scripts/backup.sh --cron       # Silent backup (for cron jobs)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_DIR/data"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="second-brain-backup-$TIMESTAMP"

# Check for silent mode
SILENT=false
if [ "$1" == "--cron" ] || [ "$1" == "--silent" ]; then
    SILENT=true
fi

log() {
    if [ "$SILENT" == "false" ]; then
        echo "$1"
    fi
}

log "╔════════════════════════════════════════════════════════╗"
log "║           Second Brain - Backup Script                 ║"
log "╚════════════════════════════════════════════════════════╝"
log ""

# ============================================
# Check data directory exists
# ============================================
if [ ! -d "$DATA_DIR" ]; then
    echo "❌ Data directory not found: $DATA_DIR"
    exit 1
fi

# ============================================
# Create backup directory
# ============================================
mkdir -p "$BACKUP_DIR"

log "Creating backup: $BACKUP_NAME"
log ""

# ============================================
# Stop services for consistent backup (optional)
# ============================================
# Uncomment if you want to stop services during backup
# log "Stopping services for consistent backup..."
# docker compose -f "$PROJECT_DIR/docker-compose.yml" stop

# ============================================
# Create backup archive
# ============================================
log "Backing up data..."

cd "$PROJECT_DIR"

# Create tar archive with all data
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" \
    --exclude='data/nextcloud-db/*.pid' \
    --exclude='*.log' \
    --exclude='*.tmp' \
    data/ \
    .env 2>/dev/null || true

# ============================================
# Restart services if stopped
# ============================================
# Uncomment if you stopped services above
# log "Restarting services..."
# docker compose -f "$PROJECT_DIR/docker-compose.yml" start

# ============================================
# Calculate backup size
# ============================================
BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_NAME.tar.gz" | cut -f1)

log ""
log "✓ Backup complete!"
log "  Location: $BACKUP_DIR/$BACKUP_NAME.tar.gz"
log "  Size: $BACKUP_SIZE"
log ""

# ============================================
# Cleanup old backups (keep last 7)
# ============================================
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-7}
log "Cleaning up backups older than $RETENTION_DAYS days..."

find "$BACKUP_DIR" -name "second-brain-backup-*.tar.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/second-brain-backup-*.tar.gz 2>/dev/null | wc -l)
log "  Backups retained: $BACKUP_COUNT"
log ""

# ============================================
# Optional: Upload to remote storage
# ============================================
# Load environment for S3 credentials
if [ -f "$PROJECT_DIR/.env" ]; then
    source "$PROJECT_DIR/.env"
fi

if [ -n "$BACKUP_S3_BUCKET" ] && [ -n "$BACKUP_S3_ENDPOINT" ]; then
    log "Uploading to S3..."
    
    if command -v aws &> /dev/null; then
        aws s3 cp "$BACKUP_DIR/$BACKUP_NAME.tar.gz" \
            "s3://$BACKUP_S3_BUCKET/$BACKUP_NAME.tar.gz" \
            --endpoint-url "$BACKUP_S3_ENDPOINT" \
            2>/dev/null && log "✓ Uploaded to S3" || log "⚠ S3 upload failed"
    elif command -v rclone &> /dev/null; then
        rclone copy "$BACKUP_DIR/$BACKUP_NAME.tar.gz" \
            "s3:$BACKUP_S3_BUCKET/" \
            2>/dev/null && log "✓ Uploaded via rclone" || log "⚠ rclone upload failed"
    else
        log "⚠ Neither aws-cli nor rclone found. Skipping remote upload."
    fi
fi

log "════════════════════════════════════════════════════════"
log "Backup completed at $(date)"
log "════════════════════════════════════════════════════════"
