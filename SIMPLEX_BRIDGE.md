# SimpleX Bridge - Technical Documentation

The SimpleX Bridge connects SimpleX Chat to n8n, enabling your Second Brain to receive and respond to messages.

---

## Overview

```
┌─────────────────┐     ┌─────────────────────────────────────┐     ┌─────────────┐
│  SimpleX App    │     │        simplex-chat-cli             │     │    n8n      │
│  (Your Phone)   │◄───►│  ┌───────┐    ┌───────────────┐    │◄───►│  (Webhook)  │
└─────────────────┘     │  │ socat │───►│ simplex-chat  │    │     └─────────────┘
                        │  │:5225  │    │ :5226         │    │
                        │  └───────┘    └───────────────┘    │
                        └─────────────────────────────────────┘
                                          ▲
                                          │ polls /tail
                                          │ every 2 seconds
                                          ▼
                                ┌─────────────────────┐
                                │   simplex-bridge    │
                                │   (Python script)   │
                                └─────────────────────┘
```

**Important:** SimpleX Chat CLI only binds to `127.0.0.1` (localhost) by default. To allow other Docker containers to connect, we use `socat` to proxy from `0.0.0.0:5225` to `127.0.0.1:5226`.

The bridge is a Python script that:
1. **Polls** the SimpleX WebSocket API every 2 seconds
2. **Extracts** incoming text messages
3. **Deduplicates** using persistent state (prevents double-processing)
4. **Forwards** new messages to n8n via webhook
5. **Tracks** which messages have been processed per contact

---

## How It Works

### 1. Socat Proxy (Container Networking Fix)

SimpleX CLI only listens on localhost, which means other containers can't reach it. The `start-simplex.sh` script solves this:

```bash
# SimpleX listens on internal port (localhost only)
INTERNAL_PORT=5226

# Socat forwards from all interfaces to localhost
socat TCP-LISTEN:5225,fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:5226 &

# Start SimpleX on the internal port
simplex-chat -p 5226 ...
```

This allows the bridge container to connect to `simplex-chat-cli:5225`.

### 2. Polling Loop

```python
while running:
    ws = websocket.create_connection(WS_URL)
    resp = ws_cmd(ws, "tail", "/tail")  # Get recent messages
    ws.close()
    
    for message in resp:
        if is_new(message):
            post_to_n8n(message)
            mark_as_seen(message)
    
    time.sleep(2)
```

### 3. Deduplication

Each contact has a "last seen" `itemId` stored in a JSON state file:

```json
{
  "1": 42,    // Contact 1: last processed message ID 42
  "2": 107    // Contact 2: last processed message ID 107
}
```

Messages with `itemId <= last_seen` are skipped. This prevents:
- Double-processing on restart
- Re-sending messages during reconnection
- Duplicate webhooks

### 4. Message Extraction

Only **incoming direct messages** are forwarded:

```python
# Must be:
# - Direct chat (not group)
# - Received message (directRcv), not sent
# - Has text content

if chatInfo.type == "direct" and chatDir.type == "directRcv" and text:
    forward_to_n8n()
```

### 5. Webhook Payload

Messages are sent to n8n as JSON:

```json
{
  "source": "simplex",
  "contactId": 1,
  "displayName": "John",
  "text": "what's on my calendar tomorrow?",
  "itemId": 43,
  "itemTs": "2026-01-23T10:30:00Z",
  "createdAt": "2026-01-23T10:30:00Z",
  "chatDir": {"type": "directRcv"},
  "ts": 1737628200.123
}
```

---

## Configuration

All settings via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SIMPLEX_WS_URL` | (required) | WebSocket URL, e.g., `ws://simplex-chat-cli:5225` |
| `N8N_WEBHOOK_URL` | (required) | n8n webhook endpoint |
| `SIMPLEX_STATE_FILE` | `/app/scripts/state/simplex_last_seen.json` | Deduplication state file |
| `SIMPLEX_POLL_SECONDS` | `2` | Poll interval in seconds |
| `SIMPLEX_WS_TIMEOUT` | `10` | WebSocket timeout in seconds |
| `SIMPLEX_WEBHOOK_RETRIES` | `3` | Max retry attempts for webhook |
| `SIMPLEX_WEBHOOK_BACKOFF` | `2` | Exponential backoff base (seconds) |
| `SIMPLEX_HEALTH_CHECK` | `1` | Run health checks on startup |
| `SIMPLEX_DEBUG_WS_EVENTS` | `0` | Log all WebSocket events |

---

## Reliability Features

### Atomic State Writes

State is saved using tmp-file + rename pattern to prevent corruption:

```python
def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_FILE)  # Atomic on POSIX
```

### Webhook Retry with Backoff

Failed webhooks retry with exponential backoff:

```
Attempt 1: immediate
Attempt 2: wait 2 seconds
Attempt 3: wait 4 seconds
```

4xx errors (except 429) are not retried.

### Graceful Shutdown

Handles `SIGTERM` and `SIGINT` cleanly:

```python
def shutdown_handler(signum, frame):
    global running
    running = False

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)
```

Docker stop commands trigger clean exit.

### Connection Resilience

- Reconnects automatically if WebSocket drops
- After 10 consecutive errors, backs off for longer
- Never crashes permanently—keeps retrying

---

## Startup Health Checks

On startup, the bridge verifies:

1. **SimpleX API** - WebSocket connection works
2. **n8n** - TCP connection to webhook host works

```
==================================================
Running startup health checks...
==================================================
  ✓ SimpleX API (ws://simplex-chat-cli:5225): OK
  ✓ n8n (http://n8n:5678/webhook/simplex-in): OK
==================================================
All health checks passed!
==================================================
```

---

## Logs

Normal operation:

```
[OK] Posted: contactId=1 itemId=43 from="John" text='what's on my calendar tomorrow?' | Response: {"success":true}
```

Errors:

```
[WARN] Webhook POST failed (attempt 1/3): HTTPError 503
       Retrying in 2.0s...
[ERROR] Connection issue (3/10): TimeoutError('No response within 10s')
```

---

## Troubleshooting

### "Connection refused" errors

**Symptom:** Bridge shows `ConnectionRefusedError(111, 'Connection refused')`

**Cause:** SimpleX only binds to localhost by default.

**Solution:** Ensure `start-simplex.sh` includes the socat proxy:
```bash
socat TCP-LISTEN:5225,fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:5226 &
```

**Verify fix:**
```bash
# Check socat is running
docker exec simplex-chat-cli ps aux | grep socat

# Check ports - should show 0.0.0.0:5225 (not 127.0.0.1)
docker exec simplex-chat-cli cat /proc/net/tcp | head -5

# Test connectivity from bridge
docker exec simplex-bridge python3 -c "
import websocket
ws = websocket.create_connection('ws://simplex-chat-cli:5225', timeout=5)
print('SUCCESS')
ws.close()
"
```

### Bridge started before SimpleX was ready

**Symptom:** Health check fails at startup, then connection errors

**Solution:** Restart the bridge after SimpleX is fully running:
```bash
docker compose restart simplex-bridge
```

### Messages not being forwarded

**Symptom:** Messages received on phone but not showing in bridge logs

**Check:**
1. Is the message from a direct chat (not a group)?
2. Is it an incoming message (not one you sent)?
3. Check the state file - message ID might already be marked as seen

**Reset state:**
```bash
rm data/simplex-bridge/simplex_last_seen.json
docker compose restart simplex-bridge
```

### Containers not on same network

**Symptom:** DNS resolution fails or connection refused

**Check:**
```bash
# Verify both containers are on the same network
docker network inspect second-brain-net --format='{{range .Containers}}{{.Name}} {{end}}'

# Test DNS resolution from bridge
docker exec simplex-bridge python3 -c "
import socket
print(socket.gethostbyname('simplex-chat-cli'))
"
```

---

## Debugging

Enable verbose logging:

```bash
# In .env
SIMPLEX_DEBUG_WS_EVENTS=1
```

Or check logs:

```bash
docker compose logs -f simplex-bridge
```

Test WebSocket manually:

```bash
docker exec simplex-bridge python3 -c "
import websocket
import json

ws = websocket.create_connection('ws://simplex-chat-cli:5225', timeout=10)
ws.send(json.dumps({'corrId': 'test', 'cmd': '/tail'}))
print(ws.recv())
ws.close()
"
```

---

## State File Location

The state file persists across restarts:

```
data/simplex-bridge/simplex_last_seen.json
```

To reset (reprocess all messages):

```bash
rm data/simplex-bridge/simplex_last_seen.json
docker compose restart simplex-bridge
```

---

## Security Notes

- Bridge runs inside Docker network—not exposed externally
- No authentication on WebSocket (internal only)
- Webhook URL should be internal Docker network address
- State file contains only message IDs, not message content
- Socat only listens on the Docker network, not the host
