#!/bin/bash
#
# SimpleX Chat CLI startup script
# Starts simplex-chat with WebSocket API enabled for n8n bridge integration
#

set -e

# Configuration from environment
SIMPLEX_PORT="${SIMPLEX_PORT:-5225}"
SIMPLEX_LOG_LEVEL="${SIMPLEX_LOG_LEVEL:-warn}"
SIMPLEX_PROFILE_DIR="${SIMPLEX_PROFILE_DIR:-/home/simplex/.simplex}"
SIMPLEX_BOT_NAME="${SIMPLEX_BOT_NAME:-second-brain}"

echo "============================================"
echo "SimpleX Chat CLI Starting"
echo "============================================"
echo "Port: $SIMPLEX_PORT"
echo "Log Level: $SIMPLEX_LOG_LEVEL"
echo "Profile Dir: $SIMPLEX_PROFILE_DIR"
echo "Bot Name: $SIMPLEX_BOT_NAME"
echo "============================================"

# Ensure profile directory exists
mkdir -p "$SIMPLEX_PROFILE_DIR"

# Check if this is first run (no database exists)
if [ ! -f "$SIMPLEX_PROFILE_DIR/simplex_v1_chat.db" ]; then
    echo ""
    echo "First run detected - SimpleX will create a new profile"
    echo "After startup, connect to this bot from your SimpleX app"
    echo ""
fi

# Start simplex-chat with WebSocket API
# -p: WebSocket API port
# -d: Database/profile directory
exec /usr/local/bin/simplex-chat \
    -p "$SIMPLEX_PORT" \
    -d "$SIMPLEX_PROFILE_DIR" \
    --log-level "$SIMPLEX_LOG_LEVEL"
