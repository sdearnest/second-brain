# Clawdbot Security Hardening Guide for Second Brain Integration

## Executive Summary

This guide provides a comprehensive security hardening plan for integrating Clawdbot into your existing Second Brain system. Given your architecture's use of local Ollama/Gemma 3 12B (which has weaker prompt injection resistance than frontier models) and access to personal calendar, notes, and potentially shell execution, security hardening is critical.

**Key Principle:** Start with the smallest access that still works, then widen it as you gain confidence. Design so that even if the model is manipulated, the blast radius is limited.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Docker Network Integration](#2-docker-network-integration)
3. [Clawdbot Gateway Configuration](#3-clawdbot-gateway-configuration)
4. [n8n ↔ Clawdbot Integration](#4-n8n--clawdbot-integration)
5. [Tool Execution Restrictions](#5-tool-execution-restrictions)
6. [Inbound Access Control](#6-inbound-access-control)
7. [Ollama Integration](#7-ollama-integration)
8. [File Permissions and Volume Mounts](#8-file-permissions-and-volume-mounts)
9. [Logging and Secrets](#9-logging-and-secrets)
10. [Backup Integration](#10-backup-integration)
11. [Monitoring and Incident Response](#11-monitoring-and-incident-response)
12. [Configuration Files](#12-configuration-files)
13. [Security Checklist](#13-security-checklist)
14. [Setup Commands](#14-setup-commands)
15. [Quick Setup Script](#15-quick-setup-script)

---

## 1. Architecture Overview

### Current Second Brain Architecture
```
SimpleX App (phone)
    → SimpleX Chat CLI (WebSocket via socat proxy)
    → SimpleX Bridge (polls /tail, forwards to n8n)
    → n8n webhook (http://n8n:5678/webhook/simplex-in)
    → n8n workflows → Calendar/Notes/Search/Delete Agents
    → Nextcloud CalDAV / Obsidian API
    → Responses back through SimpleX
```

### Proposed Integration with Clawdbot
```
┌─────────────────────────────────────────────────────────────────────┐
│                        second-brain-net                              │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │   SimpleX    │    │    n8n       │    │     Clawdbot         │   │
│  │   Bridge     │───▶│  (5678)      │◀──▶│    Gateway           │   │
│  │              │    │              │    │    (18789)           │   │
│  └──────────────┘    └──────────────┘    └──────────────────────┘   │
│         │                   │                      │                 │
│         ▼                   ▼                      ▼                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │  SimpleX CLI │    │  Nextcloud   │    │      Ollama          │   │
│  │   (5225)     │    │   (8088)     │    │     (11434)          │   │
│  └──────────────┘    └──────────────┘    └──────────────────────┘   │
│                             │                                        │
│                      ┌──────────────┐                                │
│                      │ Obsidian API │                                │
│                      │   (8765)     │                                │
│                      └──────────────┘                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Integration Philosophy

Clawdbot should **coexist** with your existing n8n workflows, not replace them:

1. **Primary Path (Recommended):** SimpleX → n8n → Your existing workflows
2. **Secondary Path:** n8n triggers Clawdbot for specific AI-heavy tasks
3. **Clawdbot as Tool Provider:** Exposes capabilities n8n can invoke via HTTP

---

## 2. Docker Network Integration

### Adding Clawdbot to second-brain-net

**Critical Principle:** All inter-container communication should use container names (not localhost), and only essential ports should be exposed to the host.

#### docker-compose.clawdbot.yml (Overlay File)

```yaml
# Clawdbot integration for Second Brain
# Usage: docker compose -f docker-compose.yml -f docker-compose.clawdbot.yml up -d

services:
  # ============================================
  # CLAWDBOT GATEWAY
  # ============================================
  clawdbot-gateway:
    image: ghcr.io/clawdbot/clawdbot:latest
    container_name: clawdbot-gateway
    restart: unless-stopped
    # NO ports exposed to host - internal only
    # Access via n8n webhooks or Tailscale if needed
    environment:
      - NODE_ENV=production
      - CLAWDBOT_CONFIG_PATH=/config/clawdbot.json
      - CLAWDBOT_STATE_DIR=/state
      - CLAWDBOT_WORKSPACE_DIR=/workspace
      # Gateway auth - REQUIRED
      - CLAWDBOT_GATEWAY_TOKEN=${CLAWDBOT_GATEWAY_TOKEN:?CLAWDBOT_GATEWAY_TOKEN required}
      # Ollama configuration
      - OLLAMA_HOST=ollama
      - OLLAMA_PORT=11434
      # Disable external discovery
      - CLAWDBOT_DISABLE_BONJOUR=1
      - TZ=${TZ:-Europe/London}
    volumes:
      - ./data/clawdbot/config:/config:ro
      - ./data/clawdbot/state:/state
      - ./data/clawdbot/workspace:/workspace
      # Read-only access to Second Brain data for context
      - ./data/vault:/vault:ro
    networks:
      - second-brain-net
    depends_on:
      ollama:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "node", "dist/index.js", "health", "--token", "${CLAWDBOT_GATEWAY_TOKEN}"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    # Security: Run as non-root
    user: "1000:1000"
    # Security: Read-only root filesystem
    read_only: true
    tmpfs:
      - /tmp:size=100M,mode=1777
    # Security: Drop all capabilities, add only what's needed
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true

networks:
  second-brain-net:
    external: true
```

### Port Exposure Strategy

| Service | Container Port | Host Exposure | Reason |
|---------|---------------|---------------|--------|
| clawdbot-gateway | 18789 | **NONE** | Internal only; n8n accesses via container network |
| ollama | 11434 | Optional (localhost) | Already exposed for development |
| n8n | 5678 | Yes (localhost) | Required for UI access |
| nextcloud | 8088 | Yes (localhost) | Required for web UI |

**Why no host exposure for Clawdbot?**
- Your SimpleX interface handles all user interaction
- n8n is your orchestration layer
- Clawdbot is invoked internally via HTTP/WebSocket
- Reduces attack surface significantly

---

## 3. Clawdbot Gateway Configuration

### clawdbot.json (Security-Hardened with Memory Support)

Create this file at `./data/clawdbot/config/clawdbot.json`:

```json
{
  "gateway": {
    "mode": "local",
    "bind": "0.0.0.0",
    "port": 18789,
    "auth": {
      "mode": "token"
    },
    "controlUi": {
      "enabled": false
    }
  },

  "discovery": {
    "mdns": {
      "mode": "off"
    }
  },

  "channels": {
    "whatsapp": { "enabled": false },
    "telegram": { "enabled": false },
    "discord": { "enabled": false },
    "slack": { "enabled": false },
    "signal": { "enabled": false },
    "imessage": { "enabled": false }
  },

  "model": {
    "provider": "ollama",
    "model": "gemma3:12b",
    "baseUrl": "http://ollama:11434"
  },

  "agents": {
    "defaults": {
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
          "cpus": "1.0",
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
        "sandbox": {
          "mode": "all",
          "workspaceAccess": "ro"
        },
        "tools": {
          "profile": "minimal",
          "allow": [
            "read",
            "sessions_list",
            "sessions_history",
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
            "web_fetch",
            "canvas",
            "nodes",
            "cron",
            "discord",
            "gateway",
            "elevated"
          ]
        }
      }
    ]
  },

  "tools": {
    "allow": ["read", "sessions_list", "sessions_history", "memory"],
    "deny": [
      "browser",
      "canvas",
      "nodes",
      "cron",
      "discord",
      "gateway",
      "exec",
      "write",
      "edit",
      "apply_patch",
      "process",
      "web_search",
      "web_fetch",
      "elevated"
    ],
    "elevated": {
      "enabled": false
    }
  },

  "hooks": {
    "enabled": true,
    "token": "${CLAWDBOT_HOOKS_TOKEN}"
  },

  "logging": {
    "level": "info",
    "redactSensitive": "tools",
    "redactPatterns": [
      "password",
      "token",
      "secret",
      "api[_-]?key",
      "authorization"
    ]
  },

  "session": {
    "dmScope": "per-channel-peer",
    "pruning": {
      "enabled": false
    }
  },

  "memory": {
    "enabled": true,
    "indexing": {
      "enabled": true
    }
  }
}
```

### Memory Configuration Explained

| Setting | Value | Purpose |
|---------|-------|---------|
| `memory.enabled` | `true` | Enables explicit "remember this" commands |
| `memory.indexing.enabled` | `true` | Allows semantic search of memories |
| `session.pruning.enabled` | `false` | **Never delete sessions - forever memory** |
| `tools.allow` includes `memory` | ✅ | Allows memory read/write operations |

### What Memory Preserves

1. **Session Transcripts** - Full conversation history stored in `/state/sessions/`
2. **Explicit Memories** - Facts you tell it to remember via the `memory` tool
3. **Session Context** - Recent conversation loaded into each request
4. **Per-User Isolation** - Each user gets their own session context

### Critical Security Settings Explained

| Setting | Value | Reason |
|---------|-------|--------|
| `channels.*` | All disabled | SimpleX is your interface; no need for Clawdbot channels |
| `sandbox.mode` | `"all"` | Every session runs in Docker isolation |
| `sandbox.workspaceAccess` | `"ro"` | Read-only filesystem access |
| `sandbox.docker.network` | `"none"` | No network access from sandbox |
| `tools.deny` | Comprehensive list | Blocks dangerous tools with Gemma 3 |
| `tools.elevated.enabled` | `false` | No host-level exec escapes |
| `discovery.mdns.mode` | `"off"` | No local network broadcasting |
| `controlUi.enabled` | `false` | No web dashboard exposure |

---

## 4. n8n ↔ Clawdbot Integration

### Architecture Decision: Webhook-Based Integration

Rather than having Clawdbot as a standalone messaging endpoint, integrate it as a **tool** that n8n can invoke for specific AI tasks.

### n8n → Clawdbot (Triggering Clawdbot Actions)

Create a reusable HTTP Request node configuration:

#### Clawdbot HTTP Credential (in n8n)

```json
{
  "name": "Clawdbot API",
  "type": "httpHeaderAuth",
  "data": {
    "name": "Authorization",
    "value": "Bearer ${CLAWDBOT_GATEWAY_TOKEN}"
  }
}
```

#### Example n8n Workflow: Invoke Clawdbot for Complex Reasoning

```javascript
// Code node to prepare Clawdbot request
const userMessage = $input.first().json.body.text;
const contactId = $input.first().json.body.contactId;

return {
  method: 'POST',
  url: 'http://clawdbot-gateway:18789/api/v1/chat',
  headers: {
    'Authorization': `Bearer ${$env.CLAWDBOT_GATEWAY_TOKEN}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    agentId: 'second-brain',
    sessionId: `simplex-${contactId}`,
    message: userMessage,
    stream: false
  })
};
```

### Clawdbot → n8n (Clawdbot Triggering Workflows)

Configure Clawdbot hooks to call n8n webhooks:

#### In clawdbot.json, add webhook configuration:

```json
{
  "automation": {
    "webhook": {
      "enabled": true,
      "endpoints": [
        {
          "id": "n8n-calendar",
          "url": "http://n8n:5678/webhook/clawdbot-calendar",
          "events": ["message.calendar"],
          "headers": {
            "X-Clawdbot-Token": "${CLAWDBOT_HOOKS_TOKEN}"
          }
        },
        {
          "id": "n8n-notes",
          "url": "http://n8n:5678/webhook/clawdbot-notes",
          "events": ["message.notes"],
          "headers": {
            "X-Clawdbot-Token": "${CLAWDBOT_HOOKS_TOKEN}"
          }
        }
      ]
    }
  }
}
```

#### n8n Webhook Node for Clawdbot Events

```javascript
// Webhook validation in n8n Code node
const expectedToken = $env.CLAWDBOT_HOOKS_TOKEN;
const receivedToken = $input.first().json.headers['x-clawdbot-token'];

if (receivedToken !== expectedToken) {
  throw new Error('Invalid webhook token');
}

return $input.first().json.body;
```

### Token Management Between Services

Store tokens in your `.env` file:

```bash
# Clawdbot tokens
CLAWDBOT_GATEWAY_TOKEN=your-long-random-token-here-min-32-chars
CLAWDBOT_HOOKS_TOKEN=another-long-random-token-for-webhooks

# Generate secure tokens:
# openssl rand -hex 32
```

---

## 5. Tool Execution Restrictions

### Why Aggressive Restrictions for Gemma 3 12B?

Gemma 3 12B is more susceptible to prompt injection than frontier models like Claude Opus or GPT-4. The Clawdbot security docs explicitly warn:

> "When running small models, enable sandboxing for all sessions and disable web_search/web_fetch/browser unless inputs are tightly controlled."

### Recommended Tool Configuration

#### Tools to COMPLETELY DISABLE:

| Tool | Risk | Reason to Disable |
|------|------|-------------------|
| `exec` | **CRITICAL** | Shell command execution |
| `process` | **CRITICAL** | Process management |
| `browser` | **HIGH** | Full browser control; can access logged-in sessions |
| `web_search` | **HIGH** | Can be used to exfiltrate data via search queries |
| `web_fetch` | **HIGH** | Can fetch malicious content or exfiltrate data |
| `write` | **HIGH** | File system modification |
| `edit` | **HIGH** | File modification |
| `apply_patch` | **HIGH** | Code modification |
| `canvas` | **MEDIUM** | Visual workspace; unnecessary for your use case |
| `nodes` | **MEDIUM** | Device node management |
| `cron` | **MEDIUM** | Scheduled tasks |
| `elevated` | **CRITICAL** | Host-level execution bypass |

#### Tools SAFE to ALLOW:

| Tool | Risk | Use Case |
|------|------|----------|
| `read` | **LOW** | Reading files in workspace |
| `sessions_list` | **LOW** | Session management |
| `sessions_history` | **LOW** | Conversation history |
| `memory` | **LOW** | Remember/recall facts (required for persistence) |

### Sandbox Configuration Details

```json
{
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "all",
        "scope": "session",
        "workspaceAccess": "ro",
        "docker": {
          "image": "clawdbot-sandbox:bookworm-slim",
          "network": "none",
          "user": "1000:1000",
          "memory": "512m",
          "cpus": "1.0",
          "pidsLimit": 100,
          "readonlyRootfs": true
        }
      }
    }
  }
}
```

**Sandbox Settings Explained:**

| Setting | Value | Security Benefit |
|---------|-------|------------------|
| `mode: "all"` | All sessions sandboxed | No host execution |
| `scope: "session"` | Per-session containers | Session isolation |
| `workspaceAccess: "ro"` | Read-only workspace | Cannot modify files |
| `network: "none"` | No network in sandbox | Cannot exfiltrate data |
| `memory: "512m"` | Memory limit | Prevents resource exhaustion |
| `pidsLimit: 100` | Process limit | Prevents fork bombs |

---

## 6. Inbound Access Control

### Since SimpleX is Your Interface

Clawdbot's channel features (WhatsApp, Telegram, etc.) should be **completely disabled**. Your architecture is:

```
User → SimpleX → Bridge → n8n → (optionally) Clawdbot
```

Not:

```
User → Clawdbot channels (disabled)
```

### Configuration to Disable All Channels

```json
{
  "channels": {
    "whatsapp": { "enabled": false },
    "telegram": { "enabled": false },
    "discord": { "enabled": false },
    "slack": { "enabled": false },
    "signal": { "enabled": false },
    "imessage": { "enabled": false },
    "msteams": { "enabled": false },
    "matrix": { "enabled": false }
  }
}
```

### Gateway Access Control

Since Clawdbot Gateway is only accessed via internal Docker network:

1. **No host port exposure** - Container-to-container only
2. **Token authentication required** - All API calls need bearer token
3. **Control UI disabled** - No web dashboard

```json
{
  "gateway": {
    "bind": "0.0.0.0",
    "auth": {
      "mode": "token"
    },
    "controlUi": {
      "enabled": false
    }
  }
}
```

---

## 7. Ollama Integration

### Pointing Clawdbot at Local Ollama

Since Ollama is already on your `second-brain-net`:

```json
{
  "model": {
    "provider": "ollama",
    "model": "gemma3:12b",
    "baseUrl": "http://ollama:11434",
    "options": {
      "temperature": 0.7,
      "num_ctx": 8192
    }
  }
}
```

### Ollama Security Considerations

1. **No authentication** - Ollama API has no auth; rely on network isolation
2. **Container network only** - Don't expose port 11434 broadly
3. **Resource limits** - Already configured in your `docker-compose.ollama.yml`

### Environment Variables

```bash
# In .env
OLLAMA_HOST=ollama
OLLAMA_PORT=11434
OLLAMA_MODEL=gemma3:12b
```

---

## 8. File Permissions and Volume Mounts

### Directory Structure

```
./data/clawdbot/
├── config/
│   └── clawdbot.json      # 600 - config with secrets
├── state/
│   ├── credentials/       # 700 - channel credentials (none used)
│   ├── memory/            # 700 - memory storage
│   └── sessions/          # 700 - session transcripts
└── workspace/
    └── second-brain/      # 755 - agent workspace
```

### Permissions Script

```bash
#!/bin/bash
# scripts/secure-clawdbot-permissions.sh

CLAWDBOT_DIR="./data/clawdbot"

# Create directories if they don't exist
mkdir -p "$CLAWDBOT_DIR"/{config,state/memory,state/sessions,workspace/second-brain}

# Config directory - restrictive
chmod 700 "$CLAWDBOT_DIR/config"
chmod 600 "$CLAWDBOT_DIR/config/clawdbot.json" 2>/dev/null || true

# State directory - restrictive
chmod 700 "$CLAWDBOT_DIR/state"
chmod 700 "$CLAWDBOT_DIR/state/memory"
chmod 700 "$CLAWDBOT_DIR/state/sessions"

# Workspace - readable
chmod 755 "$CLAWDBOT_DIR/workspace"
chmod 755 "$CLAWDBOT_DIR/workspace/second-brain"

# Ensure correct ownership
chown -R 1000:1000 "$CLAWDBOT_DIR"

echo "✓ Clawdbot permissions secured"
```

### Volume Mount Security

In docker-compose:

```yaml
volumes:
  # Config: read-only mount
  - ./data/clawdbot/config:/config:ro
  
  # State: read-write but restricted to container
  - ./data/clawdbot/state:/state
  
  # Workspace: read-write, limited scope
  - ./data/clawdbot/workspace:/workspace
  
  # Vault access: READ-ONLY
  - ./data/vault:/vault:ro
```

### What NOT to Mount

| Path | Why NOT to Mount |
|------|------------------|
| `/home/user` | Full home directory exposure |
| `/etc` | System configuration |
| `/var/run/docker.sock` | Docker socket = root access |
| `./data/n8n` | n8n workflows and credentials |
| `./data/simplex` | SimpleX chat history |

---

## 9. Logging and Secrets

### Logging Configuration

```json
{
  "logging": {
    "level": "info",
    "redactSensitive": "tools",
    "redactPatterns": [
      "password",
      "token",
      "secret",
      "api[_-]?key",
      "authorization",
      "bearer",
      "NEXTCLOUD_PASSWORD",
      "N8N_BASIC_AUTH"
    ],
    "file": {
      "enabled": true,
      "path": "/state/logs/gateway.log",
      "maxSize": "10m",
      "maxFiles": 5
    }
  }
}
```

### Secret Management

1. **Environment Variables** - Primary method
2. **No secrets in clawdbot.json** - Use `${VAR}` references
3. **Docker secrets** (optional for production)

#### .env additions:

```bash
# Clawdbot secrets
CLAWDBOT_GATEWAY_TOKEN=<generate-with-openssl-rand-hex-32>
CLAWDBOT_HOOKS_TOKEN=<generate-with-openssl-rand-hex-32>
CLAWDBOT_BROWSER_CONTROL_TOKEN=disabled

# Reference these in clawdbot.json as ${CLAWDBOT_*}
```

### Log Rotation

Add to your system crontab or use logrotate:

```bash
# /etc/logrotate.d/clawdbot
/path/to/data/clawdbot/state/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    copytruncate
}
```

---

## 10. Backup Integration

### Adding Clawdbot to Existing Backup Script

Modify your `scripts/backup.sh`:

```bash
#!/bin/bash
# Add after existing backup items

BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# ... existing backup code ...

# Clawdbot backup
echo "Backing up Clawdbot state..."
tar -czf "$BACKUP_DIR/clawdbot-$TIMESTAMP.tar.gz" \
    --exclude='*.log' \
    --exclude='node_modules' \
    ./data/clawdbot/config \
    ./data/clawdbot/state \
    ./data/clawdbot/workspace

echo "✓ Clawdbot backup complete"
```

### Directories to Backup

| Directory | Priority | Contains |
|-----------|----------|----------|
| `data/clawdbot/config/` | **CRITICAL** | Configuration |
| `data/clawdbot/state/` | **CRITICAL** | Session transcripts, memories, credentials |
| `data/clawdbot/workspace/` | **MEDIUM** | Agent workspace files |

### Directories to SKIP

| Directory | Reason |
|-----------|--------|
| `data/clawdbot/state/logs/` | Regenerable, large |
| `data/clawdbot/*/node_modules/` | Reinstallable |
| `data/clawdbot/sandboxes/` | Temporary containers |

---

## 11. Monitoring and Incident Response

### What to Monitor

#### 1. Gateway Health

```bash
# Check gateway is responding
docker exec clawdbot-gateway node dist/index.js health --token "$CLAWDBOT_GATEWAY_TOKEN"
```

#### 2. Suspicious Tool Calls

Monitor logs for:
- Any `exec` attempts (should be blocked)
- Any `write`/`edit` attempts (should be blocked)
- Unusual session activity
- High token usage

```bash
# Watch for blocked tool attempts
docker logs -f clawdbot-gateway 2>&1 | grep -E "(denied|blocked|unauthorized|error)"
```

#### 3. Resource Usage

```bash
# Monitor container resources
docker stats clawdbot-gateway --no-stream
```

### Incident Response Checklist

If you suspect compromise:

1. **IMMEDIATE: Stop the Gateway**
   ```bash
   docker compose stop clawdbot-gateway
   ```

2. **Contain Blast Radius**
   ```bash
   # Disable n8n webhooks to Clawdbot
   # Check n8n workflow executions for anomalies
   ```

3. **Rotate Secrets**
   ```bash
   # Generate new tokens
   openssl rand -hex 32 > /tmp/new-gateway-token
   openssl rand -hex 32 > /tmp/new-hooks-token
   
   # Update .env
   # Update clawdbot.json
   # Update n8n credentials
   ```

4. **Audit Logs**
   ```bash
   # Check recent activity
   grep -E "(tool|exec|write|error)" ./data/clawdbot/state/logs/gateway.log | tail -100
   
   # Check session transcripts
   ls -lt ./data/clawdbot/state/sessions/
   ```

5. **Review Artifacts**
   ```bash
   # Check workspace for unexpected files
   find ./data/clawdbot/workspace -type f -mtime -1
   ```

6. **Run Security Audit**
   ```bash
   docker exec clawdbot-gateway clawdbot security audit --deep
   ```

### Alerting (Optional)

Add to n8n for monitoring:

```javascript
// n8n workflow: Clawdbot Health Check
// Trigger: Cron every 5 minutes

const response = await $http.request({
  method: 'GET',
  url: 'http://clawdbot-gateway:18789/health',
  headers: {
    'Authorization': `Bearer ${$env.CLAWDBOT_GATEWAY_TOKEN}`
  },
  timeout: 5000
});

if (response.status !== 200) {
  // Send alert via SimpleX
  return { alert: true, status: response.status };
}

return { alert: false };
```

---

## 12. Configuration Files

### Complete docker-compose.clawdbot.yml

```yaml
# docker-compose.clawdbot.yml
# Clawdbot integration for Second Brain
# Usage: docker compose -f docker-compose.yml -f docker-compose.clawdbot.yml up -d

version: '3.8'

services:
  clawdbot-gateway:
    image: ghcr.io/clawdbot/clawdbot:latest
    container_name: clawdbot-gateway
    restart: unless-stopped
    environment:
      - NODE_ENV=production
      - CLAWDBOT_CONFIG_PATH=/config/clawdbot.json
      - CLAWDBOT_STATE_DIR=/state
      - CLAWDBOT_WORKSPACE_DIR=/workspace
      - CLAWDBOT_GATEWAY_TOKEN=${CLAWDBOT_GATEWAY_TOKEN:?Required}
      - CLAWDBOT_HOOKS_TOKEN=${CLAWDBOT_HOOKS_TOKEN:?Required}
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
      test: ["CMD", "node", "dist/index.js", "health", "--token", "${CLAWDBOT_GATEWAY_TOKEN}"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    user: "1000:1000"
    read_only: true
    tmpfs:
      - /tmp:size=100M,mode=1777
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '2.0'
        reservations:
          memory: 512M

networks:
  second-brain-net:
    external: true
```

### Complete clawdbot.json

```json
{
  "$schema": "https://docs.clawd.bot/schema/config.json",
  
  "gateway": {
    "mode": "local",
    "bind": "0.0.0.0",
    "port": 18789,
    "auth": {
      "mode": "token"
    },
    "controlUi": {
      "enabled": false
    }
  },

  "discovery": {
    "mdns": {
      "mode": "off"
    }
  },

  "channels": {
    "whatsapp": { "enabled": false },
    "telegram": { "enabled": false },
    "discord": { "enabled": false },
    "slack": { "enabled": false },
    "signal": { "enabled": false },
    "imessage": { "enabled": false },
    "msteams": { "enabled": false },
    "matrix": { "enabled": false }
  },

  "model": {
    "provider": "ollama",
    "model": "gemma3:12b",
    "baseUrl": "http://ollama:11434",
    "options": {
      "temperature": 0.7,
      "num_ctx": 8192
    }
  },

  "agents": {
    "defaults": {
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
          "cpus": "1.0",
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
        "sandbox": {
          "mode": "all",
          "workspaceAccess": "ro"
        },
        "tools": {
          "profile": "minimal",
          "allow": [
            "read",
            "sessions_list",
            "sessions_history",
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
            "web_fetch",
            "canvas",
            "nodes",
            "cron",
            "discord",
            "gateway",
            "elevated"
          ]
        }
      }
    ]
  },

  "tools": {
    "allow": ["read", "sessions_list", "sessions_history", "memory"],
    "deny": [
      "browser",
      "canvas",
      "nodes",
      "cron",
      "discord",
      "gateway",
      "exec",
      "write",
      "edit",
      "apply_patch",
      "process",
      "web_search",
      "web_fetch",
      "elevated"
    ],
    "elevated": {
      "enabled": false
    }
  },

  "hooks": {
    "enabled": true,
    "token": "${CLAWDBOT_HOOKS_TOKEN}"
  },

  "logging": {
    "level": "info",
    "redactSensitive": "tools",
    "redactPatterns": [
      "password",
      "token",
      "secret",
      "api[_-]?key",
      "authorization",
      "bearer"
    ]
  },

  "session": {
    "dmScope": "per-channel-peer",
    "pruning": {
      "enabled": false
    }
  },

  "memory": {
    "enabled": true,
    "indexing": {
      "enabled": true
    }
  }
}
```

### .env Additions

```bash
# ══════════════════════════════════════════════════════════════════
# CLAWDBOT INTEGRATION
# ══════════════════════════════════════════════════════════════════
CLAWDBOT_GATEWAY_TOKEN=<run: openssl rand -hex 32>
CLAWDBOT_HOOKS_TOKEN=<run: openssl rand -hex 32>
```

---

## 13. Security Checklist

### Pre-Deployment Checklist

- [ ] Generated unique `CLAWDBOT_GATEWAY_TOKEN` (min 32 chars)
- [ ] Generated unique `CLAWDBOT_HOOKS_TOKEN` (min 32 chars)
- [ ] Created `./data/clawdbot/` directory structure
- [ ] Set file permissions (700 for config/state, 755 for workspace)
- [ ] Verified clawdbot.json has all channels disabled
- [ ] Verified sandbox mode is "all"
- [ ] Verified dangerous tools are in deny list
- [ ] Verified elevated tools are disabled
- [ ] Verified no ports exposed to host
- [ ] Verified mDNS/Bonjour discovery is off
- [ ] Verified controlUi is disabled
- [ ] Verified memory tool is in allow list

### Post-Deployment Checklist

- [ ] Gateway health check passes
- [ ] n8n can reach Clawdbot via internal network
- [ ] Webhook authentication works
- [ ] Sandbox containers are created correctly
- [ ] Logs show no unauthorized tool attempts
- [ ] Resource limits are being enforced
- [ ] Memory persistence is working

### Regular Audit Checklist (Weekly)

- [ ] Run `clawdbot security audit --deep`
- [ ] Review gateway logs for anomalies
- [ ] Check session transcript sizes
- [ ] Verify backup includes Clawdbot state
- [ ] Test incident response procedures
- [ ] Review and rotate tokens if needed

---

## 14. Setup Commands

### Initial Setup

```bash
# 1. Create directory structure
mkdir -p ./data/clawdbot/{config,state,workspace/second-brain}

# 2. Generate tokens
echo "CLAWDBOT_GATEWAY_TOKEN=$(openssl rand -hex 32)" >> .env
echo "CLAWDBOT_HOOKS_TOKEN=$(openssl rand -hex 32)" >> .env

# 3. Copy configuration
# (copy clawdbot.json from Section 12 to ./data/clawdbot/config/)

# 4. Set permissions
chmod 700 ./data/clawdbot/config
chmod 600 ./data/clawdbot/config/clawdbot.json
chmod 700 ./data/clawdbot/state
chmod 755 ./data/clawdbot/workspace
chown -R 1000:1000 ./data/clawdbot

# 5. Create docker-compose overlay
# (copy docker-compose.clawdbot.yml from Section 12)

# 6. Build sandbox image (one-time)
docker build -t clawdbot-sandbox:bookworm-slim - << 'EOF'
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
USER 1000:1000
WORKDIR /workspace
EOF

# 7. Start services
docker compose -f docker-compose.yml -f docker-compose.clawdbot.yml up -d

# 8. Verify health
docker exec clawdbot-gateway node dist/index.js health --token "$(grep CLAWDBOT_GATEWAY_TOKEN .env | cut -d= -f2)"

# 9. Run security audit
docker exec clawdbot-gateway clawdbot security audit --deep
```

### Ongoing Security Audits

```bash
# Run comprehensive audit
docker exec clawdbot-gateway clawdbot security audit --deep

# Auto-fix common issues
docker exec clawdbot-gateway clawdbot security audit --fix

# Check gateway status
docker exec clawdbot-gateway clawdbot status --all
```

### Token Rotation

```bash
# 1. Generate new tokens
NEW_GATEWAY_TOKEN=$(openssl rand -hex 32)
NEW_HOOKS_TOKEN=$(openssl rand -hex 32)

# 2. Update .env
sed -i "s/CLAWDBOT_GATEWAY_TOKEN=.*/CLAWDBOT_GATEWAY_TOKEN=$NEW_GATEWAY_TOKEN/" .env
sed -i "s/CLAWDBOT_HOOKS_TOKEN=.*/CLAWDBOT_HOOKS_TOKEN=$NEW_HOOKS_TOKEN/" .env

# 3. Update n8n credentials (via UI)

# 4. Restart services
docker compose -f docker-compose.yml -f docker-compose.clawdbot.yml restart clawdbot-gateway

# 5. Verify new tokens work
docker exec clawdbot-gateway node dist/index.js health --token "$NEW_GATEWAY_TOKEN"
```

---

## 15. Quick Setup Script

Save this as `scripts/setup-clawdbot.sh` in your second-brain directory and run it:

```bash
#!/bin/bash
#
# Clawdbot Setup Script for Second Brain
# 
# This script will:
# 1. Create directory structure
# 2. Generate security tokens
# 3. Create configuration files
# 4. Build sandbox image
# 5. Start Clawdbot
#
# Usage: ./scripts/setup-clawdbot.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Clawdbot Setup for Second Brain                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

cd "$PROJECT_ROOT"

# ============================================
# STEP 1: Pre-flight checks
# ============================================
echo -e "${YELLOW}[1/8] Running pre-flight checks...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi
echo "  ✓ Docker found"

# Check docker compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found.${NC}"
    exit 1
fi
echo "  ✓ Docker Compose found"

# Check if second-brain-net exists
if ! docker network inspect second-brain-net &> /dev/null; then
    echo -e "${RED}❌ Docker network 'second-brain-net' not found.${NC}"
    echo "  Please start your Second Brain stack first."
    exit 1
fi
echo "  ✓ second-brain-net network exists"

# Check if Ollama is running
if ! docker ps --format '{{.Names}}' | grep -q "^ollama$"; then
    echo -e "${YELLOW}⚠ Ollama container not running. Clawdbot will fail to start without it.${NC}"
    read -p "  Continue anyway? (y/N): " continue_without_ollama
    if [[ ! "$continue_without_ollama" =~ ^[Yy]$ ]]; then
        echo "  Please start Ollama first:"
        echo "  docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d ollama"
        exit 1
    fi
else
    echo "  ✓ Ollama is running"
fi

echo -e "${GREEN}  Pre-flight checks passed!${NC}"
echo ""

# ============================================
# STEP 2: Create directory structure
# ============================================
echo -e "${YELLOW}[2/8] Creating directory structure...${NC}"

mkdir -p "$PROJECT_ROOT/data/clawdbot/config"
mkdir -p "$PROJECT_ROOT/data/clawdbot/state/memory"
mkdir -p "$PROJECT_ROOT/data/clawdbot/state/sessions"
mkdir -p "$PROJECT_ROOT/data/clawdbot/state/logs"
mkdir -p "$PROJECT_ROOT/data/clawdbot/workspace/second-brain"

echo "  ✓ Created data/clawdbot/config"
echo "  ✓ Created data/clawdbot/state"
echo "  ✓ Created data/clawdbot/workspace"
echo ""

# ============================================
# STEP 3: Generate security tokens
# ============================================
echo -e "${YELLOW}[3/8] Generating security tokens...${NC}"

GATEWAY_TOKEN=$(openssl rand -hex 32)
HOOKS_TOKEN=$(openssl rand -hex 32)

# Check if tokens already exist in .env
if grep -q "CLAWDBOT_GATEWAY_TOKEN" "$PROJECT_ROOT/.env" 2>/dev/null; then
    echo -e "${YELLOW}  ⚠ Clawdbot tokens already exist in .env${NC}"
    read -p "  Overwrite existing tokens? (y/N): " overwrite_tokens
    if [[ "$overwrite_tokens" =~ ^[Yy]$ ]]; then
        sed -i '/CLAWDBOT_GATEWAY_TOKEN/d' "$PROJECT_ROOT/.env"
        sed -i '/CLAWDBOT_HOOKS_TOKEN/d' "$PROJECT_ROOT/.env"
    else
        echo "  Keeping existing tokens."
        GATEWAY_TOKEN=$(grep "CLAWDBOT_GATEWAY_TOKEN" "$PROJECT_ROOT/.env" | cut -d= -f2)
        HOOKS_TOKEN=$(grep "CLAWDBOT_HOOKS_TOKEN" "$PROJECT_ROOT/.env" | cut -d= -f2)
    fi
fi

# Add tokens to .env if not already there
if ! grep -q "CLAWDBOT_GATEWAY_TOKEN" "$PROJECT_ROOT/.env" 2>/dev/null; then
    echo "" >> "$PROJECT_ROOT/.env"
    echo "# ══════════════════════════════════════════════════════════════════" >> "$PROJECT_ROOT/.env"
    echo "# CLAWDBOT INTEGRATION" >> "$PROJECT_ROOT/.env"
    echo "# ══════════════════════════════════════════════════════════════════" >> "$PROJECT_ROOT/.env"
    echo "CLAWDBOT_GATEWAY_TOKEN=$GATEWAY_TOKEN" >> "$PROJECT_ROOT/.env"
    echo "CLAWDBOT_HOOKS_TOKEN=$HOOKS_TOKEN" >> "$PROJECT_ROOT/.env"
    echo "  ✓ Added tokens to .env"
fi
echo ""

# ============================================
# STEP 4: Create clawdbot.json
# ============================================
echo -e "${YELLOW}[4/8] Creating clawdbot.json configuration...${NC}"

cat > "$PROJECT_ROOT/data/clawdbot/config/clawdbot.json" << 'CLAWDBOT_CONFIG'
{
  "gateway": {
    "mode": "local",
    "bind": "0.0.0.0",
    "port": 18789,
    "auth": {
      "mode": "token"
    },
    "controlUi": {
      "enabled": false
    }
  },

  "discovery": {
    "mdns": {
      "mode": "off"
    }
  },

  "channels": {
    "whatsapp": { "enabled": false },
    "telegram": { "enabled": false },
    "discord": { "enabled": false },
    "slack": { "enabled": false },
    "signal": { "enabled": false },
    "imessage": { "enabled": false },
    "msteams": { "enabled": false },
    "matrix": { "enabled": false }
  },

  "model": {
    "provider": "ollama",
    "model": "gemma3:12b",
    "baseUrl": "http://ollama:11434",
    "options": {
      "temperature": 0.7,
      "num_ctx": 8192
    }
  },

  "agents": {
    "defaults": {
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
          "cpus": "1.0",
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
        "sandbox": {
          "mode": "all",
          "workspaceAccess": "ro"
        },
        "tools": {
          "profile": "minimal",
          "allow": [
            "read",
            "sessions_list",
            "sessions_history",
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
            "web_fetch",
            "canvas",
            "nodes",
            "cron",
            "discord",
            "gateway",
            "elevated"
          ]
        }
      }
    ]
  },

  "tools": {
    "allow": ["read", "sessions_list", "sessions_history", "memory"],
    "deny": [
      "browser",
      "canvas",
      "nodes",
      "cron",
      "discord",
      "gateway",
      "exec",
      "write",
      "edit",
      "apply_patch",
      "process",
      "web_search",
      "web_fetch",
      "elevated"
    ],
    "elevated": {
      "enabled": false
    }
  },

  "hooks": {
    "enabled": true
  },

  "logging": {
    "level": "info",
    "redactSensitive": "tools",
    "redactPatterns": [
      "password",
      "token",
      "secret",
      "api[_-]?key",
      "authorization",
      "bearer"
    ]
  },

  "session": {
    "dmScope": "per-channel-peer",
    "pruning": {
      "enabled": true,
      "maxAge": "30d",
      "maxSessions": 100
    }
  },

  "memory": {
    "enabled": true,
    "indexing": {
      "enabled": true
    }
  }
}
CLAWDBOT_CONFIG

echo "  ✓ Created clawdbot.json"
echo ""

# ============================================
# STEP 5: Create docker-compose.clawdbot.yml
# ============================================
echo -e "${YELLOW}[5/8] Creating docker-compose.clawdbot.yml...${NC}"

cat > "$PROJECT_ROOT/docker-compose.clawdbot.yml" << 'COMPOSE_CONFIG'
# Clawdbot integration for Second Brain
# Usage: docker compose -f docker-compose.yml -f docker-compose.clawdbot.yml up -d

services:
  clawdbot-gateway:
    image: ghcr.io/clawdbot/clawdbot:latest
    container_name: clawdbot-gateway
    restart: unless-stopped
    environment:
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
      test: ["CMD-SHELL", "curl -sf http://localhost:18789/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '2.0'
        reservations:
          memory: 512M

networks:
  second-brain-net:
    external: true
COMPOSE_CONFIG

echo "  ✓ Created docker-compose.clawdbot.yml"
echo ""

# ============================================
# STEP 6: Set permissions
# ============================================
echo -e "${YELLOW}[6/8] Setting file permissions...${NC}"

chmod 700 "$PROJECT_ROOT/data/clawdbot/config"
chmod 600 "$PROJECT_ROOT/data/clawdbot/config/clawdbot.json"
chmod 700 "$PROJECT_ROOT/data/clawdbot/state"
chmod 755 "$PROJECT_ROOT/data/clawdbot/workspace"

# Set ownership (try, but don't fail if not root)
if [ "$(id -u)" -eq 0 ]; then
    chown -R 1000:1000 "$PROJECT_ROOT/data/clawdbot"
    echo "  ✓ Set ownership to 1000:1000"
else
    echo "  ⚠ Not running as root, skipping chown (may need manual adjustment)"
fi

echo "  ✓ Set restrictive permissions"
echo ""

# ============================================
# STEP 7: Build sandbox image
# ============================================
echo -e "${YELLOW}[7/8] Building sandbox image...${NC}"

docker build -t clawdbot-sandbox:bookworm-slim - << 'DOCKERFILE'
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
USER 1000:1000
WORKDIR /workspace
DOCKERFILE

echo "  ✓ Built clawdbot-sandbox:bookworm-slim"
echo ""

# ============================================
# STEP 8: Start Clawdbot
# ============================================
echo -e "${YELLOW}[8/8] Starting Clawdbot...${NC}"

cd "$PROJECT_ROOT"

# Check if we should start with Ollama
if docker ps --format '{{.Names}}' | grep -q "^ollama$"; then
    echo "  Starting with Ollama dependency..."
    docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml up -d clawdbot-gateway
else
    echo "  Starting without Ollama (will need manual start)..."
    # Remove depends_on for this run
    docker compose -f docker-compose.yml -f docker-compose.clawdbot.yml up -d clawdbot-gateway 2>/dev/null || {
        echo -e "${YELLOW}  ⚠ Clawdbot may fail to start without Ollama running${NC}"
    }
fi

echo ""

# ============================================
# Verification
# ============================================
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                    Setup Complete!                      ${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

# Wait for container to start
echo "Waiting for Clawdbot to start..."
sleep 10

# Check health
if docker ps --format '{{.Names}}' | grep -q "^clawdbot-gateway$"; then
    echo -e "${GREEN}✓ Clawdbot container is running${NC}"
    
    # Try health check
    HEALTH=$(docker exec clawdbot-gateway curl -sf http://localhost:18789/health 2>/dev/null || echo "pending")
    if [ "$HEALTH" != "pending" ]; then
        echo -e "${GREEN}✓ Clawdbot health check passed${NC}"
    else
        echo -e "${YELLOW}⚠ Health check pending (container still starting)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Clawdbot container not running yet${NC}"
    echo "  Check logs: docker logs clawdbot-gateway"
fi

echo ""
echo "Configuration:"
echo "  • Config file:     data/clawdbot/config/clawdbot.json"
echo "  • State directory: data/clawdbot/state/"
echo "  • Workspace:       data/clawdbot/workspace/"
echo "  • Docker Compose:  docker-compose.clawdbot.yml"
echo ""
echo "Commands:"
echo "  • View logs:       docker logs -f clawdbot-gateway"
echo "  • Check health:    docker exec clawdbot-gateway curl http://localhost:18789/health"
echo "  • Restart:         docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml restart clawdbot-gateway"
echo "  • Stop:            docker compose -f docker-compose.yml -f docker-compose.clawdbot.yml stop clawdbot-gateway"
echo ""
echo -e "${GREEN}Clawdbot is now integrated with your Second Brain! 🧠🦞${NC}"
echo ""
```

---

## Appendix: Decision Matrix

### Should You Even Use Clawdbot?

Given your architecture, consider whether Clawdbot adds value:

| Capability | Your Current Solution | Clawdbot Adds |
|------------|----------------------|---------------|
| Messaging Interface | SimpleX (E2E encrypted) | Nothing (disable channels) |
| Workflow Orchestration | n8n | Minimal (use n8n) |
| Calendar Management | n8n + Nextcloud | Nothing |
| Notes Management | n8n + Obsidian API | Nothing |
| AI Classification | Ollama via n8n | Alternative AI interface |
| Complex Reasoning | Ollama via n8n | Structured agent patterns |
| **Persistent Memory** | ❌ Not built-in | ✅ Session + explicit memory |
| **Multi-turn Context** | Manual via n8n | ✅ Automatic session handling |

**Where Clawdbot adds value:**

1. **Persistent memory** - Remembers context across conversations
2. **Extended thinking/reasoning** - Clawdbot's agent loop for complex multi-step tasks
3. **Session management** - Built-in conversation context management
4. **Skill system** - Markdown-based capability definitions
5. **Future expansion** - If you later want direct channel access

**Recommendation:** With the memory features enabled, Clawdbot provides meaningful value on top of your n8n setup - particularly for maintaining context across conversations and complex reasoning tasks.

---

*Generated for Cypherdoc's Second Brain Project*
*Last Updated: January 2026*
