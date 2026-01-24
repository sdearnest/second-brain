# SimpleX Bridge - Technical Documentation

The SimpleX Bridge connects SimpleX Chat to n8n, enabling your Second Brain to receive and respond to messages.

---

## Overview

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────┐
│  SimpleX App    │     │  simplex-chat-cli   │     │    n8n      │
│  (Your Phone)   │◄───►│  (WebSocket :5225)  │◄───►│  (Webhook)  │
└─────────────────┘     └─────────────────────┘     └─────────────┘
                                  ▲
                                  │ polls /tail
                                  │ every 2 seconds
                                  ▼
                        ┌─────────────────────┐
                        │   simplex-bridge    │
                        │   (Python script)   │
                        └─────────────────────┘
```

The bridge is a Python script that:
1. **Polls** the SimpleX WebSocket API every 2 seconds
2. **Extracts** incoming text messages
3. **Deduplicates** using persistent state (prevents double-processing)
4. **Forwards** new messages to n8n via webhook
5. **Tracks** which messages have been processed per contact

---

## How It Works

### 1. Polling Loop

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

### 2. Deduplication

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

### 3. Message Extraction

Only **incoming direct messages** are forwarded:

```python
# Must be:
# - Direct chat (not group)
# - Received message (directRcv), not sent
# - Has text content

if chatInfo.type == "direct" and chatDir.type == "directRcv" and text:
    forward_to_n8n()
```

### 4. Webhook Payload

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
