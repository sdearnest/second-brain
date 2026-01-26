# Clawdbot Security Hardening Guide for Second Brain

## Overview

This guide covers integrating Clawdbot into your Second Brain system with proper security hardening for use with local Ollama/Gemma 3 12B.

**Key Principle:** Gemma 3 12B has weaker prompt injection resistance than frontier models. We restrict dangerous tools and sandbox all executions.

---

## Quick Start

```bash
# Run the setup script
./scripts/setup-clawdbot.sh
```

The script handles everything: cloning source, building Docker image, creating config, and starting Clawdbot.

---

## Architecture

```
SimpleX App → SimpleX Bridge → n8n → Clawdbot Gateway → Ollama (Gemma 3 12B)
                                         ↓
                                   Sandboxed Execution
```

Clawdbot runs as an internal service on `second-brain-net`. It's invoked by n8n for AI reasoning tasks, not as a standalone messaging endpoint.

---

## Configuration Schema (Important!)

Clawdbot's config schema is **strict**. Here are the gotchas we discovered:

| Issue | Wrong | Correct |
|-------|-------|---------|
| CPU limit | `"cpus": "1.0"` | `"cpus": 1.0` (number, not string) |
| Bind address | `"bind": "0.0.0.0"` | `"bind": "lan"` (enum only) |
| Tools location | `agents.defaults.tools` | `agents.list[].tools` |
| Channels disable | `"enabled": false` | Just omit the channel |
| Model config | Root-level `"model"` | `agents.defaults.model` or `models.providers` |
| Memory config | Root-level `"memory"` | Not a config key - memory is a plugin |
| Session pruning | `"session.pruning"` | Does not exist |

### Valid `gateway.bind` Values

- `"auto"` - Automatic detection
- `"lan"` - Local network (recommended for Docker)
- `"loopback"` - localhost only
- `"tailnet"` - Tailscale network
- `"custom"` - Custom binding

---

## Working Configuration

### clawdbot.json

```json
{
  "gateway": {
    "mode": "local",
    "port": 18789,
    "bind": "lan",
    "auth": {
      "mode": "token"
    },
    "controlUi": {
      "enabled": false
    }
  },

  "logging": {
    "level": "info",
    "redactSensitive": "tools",
    "redactPatterns": [
      "password",
      "token",
      "secret",
      "authorization",
      "bearer"
    ]
  },

  "agents": {
    "defaults": {
      "model": {
        "primary": "ollama/gemma3:12b"
      },
      "workspace": "/workspace",
      "sandbox": {
        "mode": "all",
        "scope": "session",
        "workspaceAccess": "ro",
        "docker": {
          "image": "clawdbot-sandbox:bookworm-slim",
          "network": "none",
          "user": "1000:1000",
          "memory": "512m",
          "cpus": 1.0,
          "pidsLimit": 100
        }
      }
    },
    "list": [
      {
        "id": "second-brain",
        "workspace": "/workspace/second-brain",
        "identity": {
          "name": "Second Brain Assistant",
          "emoji": "🧠"
        },
        "tools": {
          "profile": "minimal",
          "allow": [
            "read",
            "memory"
          ],
          "deny": [
            "write",
            "edit",
            "apply_patch",
            "exec",
            "process",
            "browser",
            "web_search",
            "web_fetch"
          ],
          "elevated": {
            "enabled": false
          }
        }
      }
    ]
  },

  "models": {
    "providers": {
      "ollama": {
        "baseUrl": "http://ollama:11434",
        "models": [
          {
            "id": "gemma3:12b",
            "name": "Gemma 3 12B",
            "contextWindow": 8192,
            "maxTokens": 4096
          }
        ]
      }
    }
  }
}
```

### docker-compose.clawdbot.yml

```yaml
# Clawdbot integration for Second Brain
# Built from source: https://github.com/clawdbot/clawdbot
#
# Usage: docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml up -d

services:
  clawdbot-gateway:
    image: clawdbot:local
    container_name: clawdbot-gateway
    restart: unless-stopped
    environment:
      - HOME=/home/node
      - NODE_ENV=production
      - CLAWDBOT_CONFIG_PATH=/config/clawdbot.json
      - CLAWDBOT_STATE_DIR=/state
      - CLAWDBOT_WORKSPACE_DIR=/workspace
      - CLAWDBOT_GATEWAY_TOKEN=${CLAWDBOT_GATEWAY_TOKEN:?Required}
      - CLAWDBOT_HOOKS_TOKEN=${CLAWDBOT_HOOKS_TOKEN}
      - CLAWDBOT_DISABLE_BONJOUR=1
      - OLLAMA_HOST=ollama
      - OLLAMA_PORT=11434
      - TZ=${TZ:-Europe/London}
    volumes:
      - ./data/clawdbot/config:/config:ro
      - ./data/clawdbot/state:/state
      - ./data/clawdbot/workspace:/workspace
      - ./data/vault:/vault:ro
    networks:
      - second-brain-net
    depends_on:
      ollama:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:18789/__clawdbot__/canvas/ | grep -q Clawdbot"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    command:
      [
        "node",
        "dist/index.js",
        "gateway",
        "--bind",
        "lan",
        "--port",
        "18789"
      ]

networks:
  second-brain-net:
    name: second-brain-net
    driver: bridge
```

**Important Notes:**
- No `external: true` for network - it's defined in main compose file
- `--bind lan` not `--bind 0.0.0.0`
- Healthcheck uses `/__clawdbot__/canvas/` (no `/health` endpoint)
- No memory limits - Clawdbot needs ~2GB+ RAM or it OOMs

---

## Security Settings Explained

### Tools Configuration

| Tool | Status | Why |
|------|--------|-----|
| `read` | ✅ ALLOW | Read files in workspace |
| `memory` | ✅ ALLOW | Remember facts across sessions |
| `write` | ❌ DENY | File modification |
| `edit` | ❌ DENY | File editing |
| `apply_patch` | ❌ DENY | Code patching |
| `exec` | ❌ DENY | Shell execution |
| `process` | ❌ DENY | Process management |
| `browser` | ❌ DENY | Browser automation |
| `web_search` | ❌ DENY | Exfiltration risk |
| `web_fetch` | ❌ DENY | Fetch external content |
| `elevated` | ❌ DENY | Host-level access |

### Sandbox Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| `mode` | `"all"` | Every session sandboxed |
| `scope` | `"session"` | Per-session containers |
| `workspaceAccess` | `"ro"` | Read-only workspace |
| `network` | `"none"` | No network in sandbox |
| `memory` | `"512m"` | Memory limit per sandbox |
| `pidsLimit` | `100` | Process limit |

### Channels

All messaging channels (WhatsApp, Telegram, Discord, etc.) are **disabled by omission**. Your SimpleX interface handles all user interaction through n8n.

---

## File Permissions

```bash
# Required for security audit to pass
chmod 700 data/clawdbot/config
chmod 600 data/clawdbot/config/clawdbot.json
chmod 700 data/clawdbot/state
chmod 755 data/clawdbot/workspace
```

---

## Building from Source

Clawdbot doesn't have an official Docker image yet. Build locally:

```bash
# Clone
git clone https://github.com/clawdbot/clawdbot.git ~/projects/clawdbot

# Build (takes 5-10 minutes)
cd ~/projects/clawdbot
docker build -t clawdbot:local .

# Also build sandbox image
docker build -t clawdbot-sandbox:bookworm-slim - << 'EOF'
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && rm -rf /var/lib/apt/lists/*
USER 1000:1000
WORKDIR /workspace
EOF
```

---

## Useful Commands

```bash
# Start
docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml up -d clawdbot-gateway

# Stop
docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml stop clawdbot-gateway

# Logs
docker logs -f clawdbot-gateway

# Status
docker exec clawdbot-gateway node dist/index.js status

# Security audit
docker exec clawdbot-gateway node dist/index.js security audit --deep

# Rebuild after source update
cd ~/projects/clawdbot && git pull && docker build -t clawdbot:local .
```

---

## Verifying Installation

```bash
# Check container is running
docker ps | grep clawdbot

# Check gateway is responding
docker exec clawdbot-gateway curl -s http://localhost:18789/__clawdbot__/canvas/ | head -5

# Check status
docker exec clawdbot-gateway node dist/index.js status
```

Expected status output:
```
Gateway: local · ws://127.0.0.1:18789 · reachable · auth token
Agents: 2 · default second-brain
Memory: enabled (plugin memory-core)
```

---

## Connecting to n8n

Clawdbot uses **WebSocket**, not REST API. To integrate with n8n:

1. Use a WebSocket node to connect to `ws://clawdbot-gateway:18789`
2. Authenticate with `CLAWDBOT_GATEWAY_TOKEN`
3. Send messages in Clawdbot's protocol format

(See separate n8n integration guide for detailed workflow setup)

---

## Troubleshooting

### Config Invalid Errors

Check the [Configuration Schema](#configuration-schema-important) section. Common issues:
- `cpus` as string instead of number
- Invalid `bind` value
- `tools` in wrong location

### Out of Memory

Don't set memory limits in docker-compose. Clawdbot needs 2GB+ RAM.

### Gateway Token Mismatch

Ensure `CLAWDBOT_GATEWAY_TOKEN` in `.env` matches what the container sees:
```bash
docker exec clawdbot-gateway printenv | grep CLAWDBOT_GATEWAY_TOKEN
```

### Network Issues

Ensure all containers are on `second-brain-net`:
```bash
docker network inspect second-brain-net
```

---

## Security Checklist

- [ ] Config file permissions are 600
- [ ] All messaging channels disabled (omitted from config)
- [ ] Sandbox mode is "all"
- [ ] Dangerous tools in deny list
- [ ] elevated.enabled is false
- [ ] No ports exposed to host (internal network only)
- [ ] Gateway auth mode is "token"
- [ ] controlUi is disabled

---

*Last updated: January 2026*
