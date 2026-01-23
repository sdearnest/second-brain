#!/usr/bin/env python3
"""
SimpleX → n8n Bridge
Polls SimpleX Chat WebSocket API and forwards incoming messages to n8n webhook.

Features:
- corrId-aware request/response handling (ignores async events)
- Per-contact deduplication using persistent itemId tracking
- Atomic state file writes
- Graceful shutdown on SIGTERM/SIGINT
- Startup health checks
- Webhook retry with exponential backoff
- Connection resilience
"""

import json
import time
import os
import signal
import sys
import socket
from urllib.parse import urlparse
import urllib.request
import urllib.error

try:
    import websocket
except ImportError:
    print("ERROR: websocket-client not installed. Run: pip install websocket-client")
    sys.exit(1)


# ============================================================
# Configuration (ENV ONLY — no hardcoding)
# ============================================================

WS_URL = os.environ.get("SIMPLEX_WS_URL", "")
WEBHOOK = os.environ.get("N8N_WEBHOOK_URL", "")

if not WS_URL:
    print("ERROR: SIMPLEX_WS_URL environment variable is required")
    sys.exit(1)

if not WEBHOOK:
    print("ERROR: N8N_WEBHOOK_URL environment variable is required")
    sys.exit(1)

STATE_FILE = os.environ.get(
    "SIMPLEX_STATE_FILE",
    "/app/scripts/state/simplex_last_seen.json",
)

POLL_SECONDS = float(os.environ.get("SIMPLEX_POLL_SECONDS", "2"))
WS_TIMEOUT = float(os.environ.get("SIMPLEX_WS_TIMEOUT", "10"))
DEBUG_WS_EVENTS = os.environ.get("SIMPLEX_DEBUG_WS_EVENTS", "0") == "1"
WEBHOOK_MAX_RETRIES = int(os.environ.get("SIMPLEX_WEBHOOK_RETRIES", "3"))
WEBHOOK_RETRY_BACKOFF = float(os.environ.get("SIMPLEX_WEBHOOK_BACKOFF", "2"))
HEALTH_CHECK_ON_START = os.environ.get("SIMPLEX_HEALTH_CHECK", "1") == "1"


# ============================================================
# Graceful Shutdown Handler
# ============================================================

running = True


def shutdown_handler(signum, frame):
    """Handle SIGTERM/SIGINT for clean Docker stops."""
    global running
    sig_name = signal.Signals(signum).name
    print(f"\n[{sig_name}] Shutdown signal received, exiting gracefully...")
    running = False


signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


# ============================================================
# Utilities
# ============================================================

def ensure_state_dir():
    """Create state directory if it doesn't exist."""
    state_dir = os.path.dirname(STATE_FILE)
    if state_dir:
        os.makedirs(state_dir, exist_ok=True)


def load_state():
    """
    Load deduplication state from file.
    Returns dict of contactId (str) -> last seen itemId (int).
    Handles corruption gracefully by returning empty state.
    """
    try:
        with open(STATE_FILE, "r") as f:
            raw = f.read().strip()
            if not raw:
                return {}
            data = json.loads(raw)
            # Validate structure: should be dict of str -> int
            if not isinstance(data, dict):
                raise ValueError("State must be a dict")
            # Normalize keys to str, values to int
            return {str(k): int(v) for k, v in data.items()}
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        print(f"[WARN] State file corrupted ({type(e).__name__}: {e}), starting fresh")
        return {}
    except Exception as e:
        print(f"[WARN] State load error: {repr(e)}, starting fresh")
        return {}


def save_state(state):
    """Atomically save state to file (tmp + rename pattern)."""
    tmp = STATE_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, STATE_FILE)
    except Exception as e:
        print(f"[ERROR] Failed to save state: {repr(e)}")
        # Try to clean up tmp file
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def post(payload):
    """POST JSON payload to webhook."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode("utf-8", "ignore")


def post_with_retry(payload, max_retries=None, backoff=None):
    """
    POST with exponential backoff retry.
    Returns response on success, raises on final failure.
    """
    if max_retries is None:
        max_retries = WEBHOOK_MAX_RETRIES
    if backoff is None:
        backoff = WEBHOOK_RETRY_BACKOFF

    last_error = None
    for attempt in range(max_retries):
        try:
            return post(payload)
        except urllib.error.HTTPError as e:
            # Don't retry client errors (4xx) except 429 (rate limit)
            if 400 <= e.code < 500 and e.code != 429:
                print(f"[ERROR] Webhook returned {e.code}, not retrying")
                raise
            last_error = e
        except Exception as e:
            last_error = e

        if attempt < max_retries - 1:
            wait_time = backoff * (2 ** attempt)
            print(f"[WARN] Webhook POST failed (attempt {attempt + 1}/{max_retries}): {repr(last_error)}")
            print(f"       Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)

    print(f"[ERROR] Webhook POST failed after {max_retries} attempts")
    raise last_error


# ============================================================
# SimpleX WebSocket helpers
# ============================================================

def ws_cmd(ws, corr_id, command, timeout=None):
    """
    Send a command and wait ONLY for matching corrId.
    Ignores async events safely (e.g., contactsDisconnected).
    """
    if timeout is None:
        timeout = WS_TIMEOUT

    try:
        ws.send(json.dumps({"corrId": corr_id, "cmd": command}))
    except websocket.WebSocketConnectionClosedException:
        raise ConnectionError("WebSocket closed before send")
    except Exception as e:
        raise ConnectionError(f"WebSocket send failed: {repr(e)}")

    end = time.time() + timeout

    while time.time() < end:
        remaining = end - time.time()
        if remaining <= 0:
            break

        try:
            ws.settimeout(remaining)
            msg = ws.recv()
        except websocket.WebSocketTimeoutException:
            break
        except websocket.WebSocketConnectionClosedException:
            raise ConnectionError("WebSocket closed while waiting for response")
        except Exception as e:
            raise ConnectionError(f"WebSocket recv failed: {repr(e)}")

        try:
            j = json.loads(msg)
        except json.JSONDecodeError:
            continue

        if j.get("corrId") == corr_id:
            return j

        # Log async events if debugging enabled
        if DEBUG_WS_EVENTS:
            r = j.get("resp") or {}
            if isinstance(r, dict) and "type" in r:
                print(f"[DEBUG] WS async event: {r.get('type')}")

    raise TimeoutError(f"No response for corrId={corr_id} cmd={command!r} within {timeout}s")


def extract_message(ci):
    """
    Normalize a SimpleX chatItem into a flat structure.
    Returns None if not a direct incoming text message.
    """
    chatInfo = ci.get("chatInfo") or {}
    if chatInfo.get("type") != "direct":
        return None

    contact = chatInfo.get("contact") or {}
    contact_id = contact.get("contactId")
    display_name = (contact.get("localDisplayName") or "").strip()

    chatItem = ci.get("chatItem") or {}
    chat_dir = chatItem.get("chatDir") or {}
    chat_dir_type = (chat_dir.get("type") or "").strip()

    meta = chatItem.get("meta") or {}
    item_id = meta.get("itemId")
    item_ts = meta.get("itemTs")
    created_at = meta.get("createdAt")

    content = chatItem.get("content") or {}
    msg_content = content.get("msgContent") or {}
    text = msg_content.get("text")

    # Only process received messages, not sent
    if chat_dir_type != "directRcv":
        return None

    # Must have essential fields
    if not text or contact_id is None or item_id is None:
        return None

    return {
        "contactId": int(contact_id),
        "displayName": display_name,
        "text": str(text),
        "itemId": int(item_id),
        "itemTs": item_ts,
        "createdAt": created_at,
        "chatDir": chat_dir_type,
        "raw": ci,
    }


# ============================================================
# Health Checks
# ============================================================

def check_simplex_api():
    """Verify SimpleX WebSocket API is reachable and responding."""
    try:
        ws = websocket.create_connection(WS_URL, timeout=5)
        ws.settimeout(5)
        # Send a simple command to verify API is working
        ws_cmd(ws, "health-check", "/help", timeout=5)
        ws.close()
        return True, "OK"
    except Exception as e:
        return False, str(e)


def check_n8n_reachable():
    """Verify n8n is reachable (TCP connectivity only, not webhook validity)."""
    try:
        parsed = urlparse(WEBHOOK)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        sock = socket.create_connection((host, port), timeout=5)
        sock.close()
        return True, "OK"
    except Exception as e:
        return False, str(e)


def run_health_checks():
    """
    Run all health checks on startup.
    Returns True if all checks pass.
    """
    print("=" * 50)
    print("Running startup health checks...")
    print("=" * 50)

    all_ok = True

    # Check SimpleX API
    simplex_ok, simplex_msg = check_simplex_api()
    status = "✓" if simplex_ok else "✗"
    print(f"  {status} SimpleX API ({WS_URL}): {simplex_msg}")
    if not simplex_ok:
        all_ok = False

    # Check n8n
    n8n_ok, n8n_msg = check_n8n_reachable()
    status = "✓" if n8n_ok else "✗"
    print(f"  {status} n8n ({WEBHOOK}): {n8n_msg}")
    if not n8n_ok:
        all_ok = False

    print("=" * 50)

    if all_ok:
        print("All health checks passed!")
    else:
        print("WARNING: Some health checks failed!")
        print("The bridge will still start, but may not work correctly.")

    print("=" * 50)
    return all_ok


# ============================================================
# Main loop
# ============================================================

def main():
    global running

    print()
    print("╔════════════════════════════════════════════════╗")
    print("║       SimpleX → n8n Bridge Starting            ║")
    print("╚════════════════════════════════════════════════╝")
    print()
    print(f"Configuration:")
    print(f"  SIMPLEX_WS_URL:     {WS_URL}")
    print(f"  N8N_WEBHOOK_URL:    {WEBHOOK}")
    print(f"  STATE_FILE:         {STATE_FILE}")
    print(f"  POLL_SECONDS:       {POLL_SECONDS}")
    print(f"  WS_TIMEOUT:         {WS_TIMEOUT}")
    print(f"  WEBHOOK_RETRIES:    {WEBHOOK_MAX_RETRIES}")
    print(f"  DEBUG_WS_EVENTS:    {DEBUG_WS_EVENTS}")
    print()

    # Run health checks if enabled
    if HEALTH_CHECK_ON_START:
        run_health_checks()
        print()

    # Ensure state directory exists
    ensure_state_dir()

    # Load existing state
    state = load_state()
    if state:
        print(f"Loaded state for {len(state)} contact(s):")
        for cid, last_id in state.items():
            print(f"  Contact {cid}: last seen itemId={last_id}")
    else:
        print("No previous state found, starting fresh")
    print()

    print("Entering main loop (Ctrl+C to stop)...")
    print("-" * 50)

    consecutive_errors = 0
    max_consecutive_errors = 10

    while running:
        try:
            # Create WebSocket connection
            ws = websocket.create_connection(WS_URL, timeout=WS_TIMEOUT)
            ws.settimeout(WS_TIMEOUT)

            # Fetch recent messages
            resp = ws_cmd(ws, "tail", "/tail", timeout=WS_TIMEOUT)
            ws.close()

            # Reset error counter on successful poll
            consecutive_errors = 0

            # Extract chat items
            chat_items = (resp.get("resp") or {}).get("chatItems") or []
            messages = []

            for ci in chat_items:
                msg = extract_message(ci)
                if msg:
                    messages.append(msg)

            if not messages:
                if DEBUG_WS_EVENTS:
                    print("[DEBUG] No incoming messages in /tail response")
                time.sleep(POLL_SECONDS)
                continue

            # Sort oldest → newest by itemId
            messages.sort(key=lambda m: m["itemId"])

            # Process and emit new messages
            emitted = 0
            for msg in messages:
                if not running:
                    break

                cid = str(msg["contactId"])
                last_seen = int(state.get(cid, 0))

                # Skip already-processed messages
                if msg["itemId"] <= last_seen:
                    continue

                # Build webhook payload
                payload = {
                    "source": "simplex",
                    "contactId": msg["contactId"],
                    "displayName": msg["displayName"],
                    "chatDir": {"type": msg["chatDir"]},
                    "text": msg["text"],
                    "itemId": msg["itemId"],
                    "itemTs": msg["itemTs"],
                    "createdAt": msg["createdAt"],
                    "raw_item": msg["raw"],
                    "ts": time.time(),
                }

                # Post to webhook with retry
                try:
                    result = post_with_retry(payload)
                    print(
                        f"[OK] Posted: contactId={msg['contactId']} "
                        f"itemId={msg['itemId']} "
                        f"from=\"{msg['displayName']}\" "
                        f"text={msg['text']!r:.50} | Response: {result[:100]}"
                    )
                except Exception as e:
                    print(
                        f"[FAIL] Could not post: contactId={msg['contactId']} "
                        f"itemId={msg['itemId']} | Error: {repr(e)}"
                    )
                    # Don't update state if webhook failed
                    # Message will be retried next poll
                    continue

                # Update state only after successful webhook
                state[cid] = msg["itemId"]
                save_state(state)
                emitted += 1

            if emitted == 0 and messages:
                print("[INFO] No new messages (all deduplicated)")

        except (ConnectionError, TimeoutError) as e:
            consecutive_errors += 1
            print(f"[ERROR] Connection issue ({consecutive_errors}/{max_consecutive_errors}): {repr(e)}")

            if consecutive_errors >= max_consecutive_errors:
                print("[WARN] Too many consecutive errors, waiting longer...")
                time.sleep(POLL_SECONDS * 5)
                consecutive_errors = 0

        except Exception as e:
            consecutive_errors += 1
            print(f"[ERROR] Bridge error ({consecutive_errors}/{max_consecutive_errors}): {repr(e)}")

            if consecutive_errors >= max_consecutive_errors:
                print("[WARN] Too many consecutive errors, waiting longer...")
                time.sleep(POLL_SECONDS * 5)
                consecutive_errors = 0

        # Wait before next poll (if still running)
        if running:
            time.sleep(POLL_SECONDS)

    print()
    print("-" * 50)
    print("Bridge stopped cleanly. Goodbye!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
