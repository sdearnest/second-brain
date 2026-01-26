# Second Brain - Setup Guide

A complete guide to deploying your self-hosted AI personal assistant.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [First-Time Configuration](#first-time-configuration)
4. [Connecting SimpleX Chat](#connecting-simplex-chat)
5. [Configuring n8n Simplexity Integration](#configuring-n8n-simplexity-integration)
6. [Importing Workflows](#importing-workflows)
7. [Local AI Setup (Ollama)](#local-ai-setup-ollama)
8. [Clawdbot Setup (AI Reasoning)](#clawdbot-setup-ai-reasoning)
9. [Migrating Existing Data](#migrating-existing-data)
10. [Verification](#verification)
11. [Troubleshooting](#troubleshooting)
12. [Useful Commands](#useful-commands)

---

## Prerequisites

### Hardware Requirements

- **Minimum:** 4GB RAM, 2 CPU cores, 20GB storage
- **Recommended:** 8GB RAM, 4 CPU cores, 100GB+ storage
- **For Local AI:** NVIDIA GPU with 12GB+ VRAM, 32GB+ RAM, 50GB+ storage

### Software Requirements

**Install Docker and Docker Compose:**

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y docker.io docker-compose-v2

# Start Docker and enable on boot
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to docker group (avoids needing sudo)
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker
```

**Verify installation:**

```bash
docker --version        # Should show Docker version 24.x or higher
docker compose version  # Should show Docker Compose version v2.x
```

### Git (for cloning the repo)

```bash
sudo apt install -y git
```

---

## Installation

### 1. Clone the Repository

```bash
cd ~
git clone https://github.com/drgoodnight/second-brain.git
cd second-brain
```

### 2. Make Scripts Executable

```bash
chmod +x scripts/*.sh
chmod +x simplex/start-simplex.sh
```

### 3. Run Setup Script

```bash
./scripts/setup.sh
```

This will:
- Create all required data directories
- Generate `.env` file with random passwords
- Build Docker images (including pre-installed community nodes)
- Start all services
- Run health checks

**Expected output:**

```
╔════════════════════════════════════════════════════════╗
║           Second Brain - Setup Script                  ║
╚════════════════════════════════════════════════════════╝

Checking prerequisites...
✓ Docker and Docker Compose found

Creating data directories...
✓ Data directories created

Creating .env file from template...
✓ .env file created with generated passwords

...

════════════════════════════════════════════════════════
                    Setup Complete!
════════════════════════════════════════════════════════

Services:
  • n8n:          http://localhost:5678
  • Nextcloud:    http://localhost:8088
  • Obsidian API: http://localhost:8765
  • SimpleX:      ws://localhost:5225
```

---

## First-Time Configuration

### Step 1: Configure Nextcloud

1. **Open Nextcloud** in your browser:
   ```
   http://localhost:8088
   ```

2. **Create admin account:**
   - Enter a username (e.g., `admin`)
   - Enter a strong password
   - Click "Install"

3. **Wait for installation** (2-5 minutes)
   - Nextcloud will set up the database
   - You may see a loading screen

4. **Install recommended apps OR install Calendar manually:**
   
   **Option A:** Click "Install recommended apps" - this includes Calendar
   
   **Option B:** Skip recommended apps, then install Calendar manually:
   - Click your profile icon (top right)
   - Click "Apps"
   - Go to "Office & text" category
   - Find "Calendar" and click "Install"

### Step 2: Create Nextcloud App Password

This password allows n8n to access your calendar.

1. **Go to Settings:**
   - Click your profile icon (top right)
   - Click "Settings"

2. **Navigate to Security:**
   - Left sidebar → "Security"

3. **Create app password:**
   - Scroll to "Devices & sessions"
   - Enter app name: `n8n`
   - Click "Create new app password"

4. **Copy the password**
   - It looks like: `xxxxx-xxxxx-xxxxx-xxxxx-xxxxx`
   - **Save this somewhere** - you can't see it again!

### Step 3: Add App Password to Environment

```bash
nano ~/second-brain/.env
```

Find this line:
```
NEXTCLOUD_PASSWORD=YOUR_NEXTCLOUD_APP_PASSWORD
```

Replace with your actual password:
```
NEXTCLOUD_PASSWORD=xxxxx-xxxxx-xxxxx-xxxxx-xxxxx
```

Save and exit (Ctrl+X, Y, Enter).

### Step 4: Restart n8n

```bash
cd ~/second-brain
docker compose restart n8n
```

### Step 5: Access n8n

1. **Open n8n:**
   ```
   http://localhost:5678
   ```

2. **Log in with credentials from `.env`:**
   ```bash
   # View your generated credentials
   grep N8N_BASIC_AUTH .env
   ```
   
   Default username is `admin`, password was auto-generated.

---

## Connecting SimpleX Chat

SimpleX Chat is your interface to the Second Brain. **This requires a one-time manual setup.**

### Why Manual Setup?

SimpleX CLI requires an interactive terminal (TTY) to create a user profile. It cannot be automated because it prompts for a display name during first-time setup. This only needs to be done once - after that, the profile persists and the container starts automatically.

### Step 1: Stop the SimpleX Container

After initial `docker compose up -d`, the SimpleX container will show an error because no profile exists yet. This is expected.

```bash
docker compose stop simplex-chat-cli
```

### Step 2: Create the SimpleX Profile (Interactive)

Run SimpleX interactively to create your profile:

```bash
docker compose run -it --rm simplex-chat-cli \
  simplex-chat -d /home/simplex/.simplex/simplex
```

> **Important:** The `-d` flag specifies a database **name prefix**, not a directory. Using `-d /home/simplex/.simplex/simplex` creates the database files inside the mounted volume at `data/simplex/`.

### Step 3: Complete the Setup Prompts

When SimpleX starts, you'll see:

```
SimpleX Chat v6.4.7.1
...
No user profiles found, it will be created now.
Please choose your display name.
It will be sent to your contacts when you connect.
It is only stored on your device and you can change it later.
display name:
```

1. **Enter your bot's display name:**
   ```
   second-brain
   ```

2. **Enable auto-accept for incoming connections:**
   ```
   /auto_accept on
   ```
   
   This is **critical** - without this, you'll need to manually accept every connection request from your phone or other devices.

3. **Create and show your bot address:**
   ```
   /address
   ```
   
   Then show it with:
   ```
   /sa
   ```
   
   You'll see output like:
   ```
   Your chat address:
   https://smp6.simplex.im/a#Am1D1vZgHiCZbKg-aLj8WguJBGgvOAHbj5JSqzUytWM
   ```
   
   **⚠️ IMPORTANT: Copy and save this FULL URL** - you'll need it for:
   - Connecting from your phone's SimpleX app
   - **Configuring the Simplexity API credentials in n8n** (see next section)

4. **Exit SimpleX:**
   ```
   /quit
   ```

### Step 4: Verify Profile Was Created

Check that the database files now exist:

```bash
ls -la data/simplex/
```

You should see files including:
```
simplex_chat.db
simplex_agent.db
simplex_chat.db-shm
simplex_chat.db-wal
```

### Step 5: Start All Services

```bash
docker compose up -d
```

### Step 6: Verify SimpleX is Running

```bash
docker compose logs simplex-chat-cli
```

You should now see:
```
============================================
SimpleX Chat CLI Starting
============================================
Port: 5225
Log Level: warn
Data Dir: /home/simplex/.simplex
DB Prefix: /home/simplex/.simplex/simplex
Bot Name: second-brain
============================================

✓ Profile found: /home/simplex/.simplex/simplex_chat.db

Starting SimpleX Chat with WebSocket API on port 5225...
```

### Step 7: Connect from Your Phone

1. **Install SimpleX Chat** on your phone (iOS App Store / Android Play Store)

2. **Add a new contact:**
   - Tap the **+** button
   - Select "Connect via link" or scan QR code
   - Paste the address you saved in Step 3 (the `https://smp6.simplex.im/...` link)

3. **Accept the connection** when prompted

---

## Configuring n8n Simplexity Integration

(See full instructions in the original SETUP_GUIDE.md)

---

## Importing Workflows

(See full instructions in the original SETUP_GUIDE.md)

---

## Local AI Setup (Ollama)

Ollama provides local AI inference for intent classification and structured tasks.

### Requirements

- NVIDIA GPU with 12GB+ VRAM
- NVIDIA Container Toolkit installed

### Setup

```bash
# Start with Ollama
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d

# Wait for model download (first time only)
docker compose logs -f ollama-init

# Verify
curl http://localhost:11434/api/tags
```

See [ollama/README.md](ollama/README.md) for detailed setup.

---

## Clawdbot Setup (AI Reasoning)

Clawdbot adds AI chat and reasoning capabilities to your Second Brain. It handles general conversation, complex questions, and remembers context across sessions.

### What Clawdbot Does

- **General chat:** "hey, how are you?" → friendly response
- **Complex reasoning:** "help me think through this decision..." → thoughtful analysis
- **Session memory:** Remembers your conversation within a session
- **Fallback handler:** Catches messages that don't match specific intents (calendar, notes, etc.)

### Requirements

- Ollama running with Gemma 3 12B model
- ~3GB additional RAM for Clawdbot gateway

### Quick Setup

```bash
# Run the setup script
./scripts/setup-clawdbot.sh
```

This will:
1. Clone Clawdbot source from GitHub
2. Build the Docker image locally (~5-10 minutes)
3. Create configuration with security hardening
4. Generate authentication tokens
5. Create workspace files (AGENTS.md, MEMORY.md)
6. Start Clawdbot and verify it's working

### Manual Setup

If you prefer manual setup:

```bash
# 1. Clone Clawdbot source
git clone https://github.com/clawdbot/clawdbot.git ~/projects/clawdbot

# 2. Build Docker image
cd ~/projects/clawdbot
docker build -t clawdbot:local .

# 3. Create directories
mkdir -p data/clawdbot/{config,state,workspace/second-brain}

# 4. Copy config file (see docs/CLAWDBOT_SECURITY_HARDENING.md)
# 5. Add tokens to .env
# 6. Start with docker compose
docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml up -d
```

### Verify Clawdbot is Working

```bash
# Check container status
docker ps | grep clawdbot

# Check logs
docker logs -f clawdbot-gateway

# Test the API
TOKEN=$(grep CLAWDBOT_GATEWAY_TOKEN .env | cut -d= -f2)
docker exec clawdbot-gateway curl -sS http://localhost:18789/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "x-clawdbot-agent-id: second-brain" \
  -d '{"model":"clawdbot","messages":[{"role":"user","content":"Hello!"}]}'
```

Expected response:
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "Hello! How can I help you today?"
    }
  }]
}
```

### n8n Integration

Clawdbot integrates with n8n via HTTP Request node:

| Setting | Value |
|---------|-------|
| Method | `POST` |
| URL | `http://clawdbot-gateway:18789/v1/chat/completions` |
| Auth Header | `Authorization: Bearer <CLAWDBOT_GATEWAY_TOKEN>` |
| Agent Header | `x-clawdbot-agent-id: second-brain` |

**Request body:**
```json
{
  "model": "clawdbot",
  "messages": [{"role": "user", "content": "={{ $json.message }}"}],
  "user": "={{ $json.sender_id || 'default-user' }}"
}
```

**Response extraction (Code node):**
```javascript
const response = $input.first().json;
const content = response.choices?.[0]?.message?.content || "Sorry, I couldn't process that.";
return [{ json: { reply: content } }];
```

### Customizing the System Prompt

Edit the workspace files:

```bash
# System prompt / personality
nano data/clawdbot/workspace/second-brain/AGENTS.md

# Persistent memory
nano data/clawdbot/workspace/second-brain/MEMORY.md
```

### Security Notes

Clawdbot is configured with security hardening:

- **Sandbox disabled:** Docker-in-Docker not supported
- **Dangerous tools blocked:** exec, write, browser, web_search, web_fetch
- **HTTP API only:** No external messaging channels
- **Token authentication:** Required for all API calls
- **Internal network only:** Not exposed to host

See [docs/CLAWDBOT_SECURITY_HARDENING.md](docs/CLAWDBOT_SECURITY_HARDENING.md) for full details.

### Troubleshooting Clawdbot

**Container won't start:**
```bash
docker logs clawdbot-gateway
```

**"Model context window too small":**
- Ensure `contextWindow` is at least 16000 in clawdbot.json

**"No API key found for provider ollama":**
- Add `"apiKey": "ollama-local"` to the Ollama provider config

**"Unhandled API in mapOptionsForApi":**
- Add `"api": "openai-completions"` to the Ollama provider config
- Ensure `baseUrl` ends with `/v1`

**Out of memory:**
- Don't set memory limits in docker-compose
- Clawdbot needs ~2GB+ RAM

---

## Migrating Existing Data

(See full instructions in the original SETUP_GUIDE.md)

---

## Verification

### Check All Services

```bash
docker compose ps
```

All services should show "running" status.

### Test Individual Services

**n8n:**
```bash
curl -s http://localhost:5678/healthz
# Should return "OK"
```

**Nextcloud:**
```bash
curl -s http://localhost:8088/status.php | jq .installed
# Should return "true"
```

**Obsidian API:**
```bash
curl -s http://localhost:8765/health
# Should return {"status":"healthy",...}
```

**SimpleX Bridge:**
```bash
docker compose logs simplex-bridge | tail -5
# Should show successful message forwarding or "waiting for messages"
```

**Ollama:**
```bash
curl -s http://localhost:11434/api/tags
# Should return JSON with model list
```

**Clawdbot:**
```bash
docker exec clawdbot-gateway curl -s http://localhost:18789/__clawdbot__/canvas/ | head -5
# Should return HTML with "Clawdbot"
```

### Test End-to-End

Send a message via SimpleX Chat:
```
add meeting at 3pm tomorrow
```

Check:
1. Bridge logs show the message received: `docker compose logs -f simplex-bridge`
2. n8n workflow executes (check Executions tab)
3. Calendar event appears in Nextcloud
4. You receive a confirmation response in SimpleX

Send a general chat message:
```
hey, what's up?
```

Check:
1. Message routes to Clawdbot
2. You receive a friendly response

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs for the specific container
docker compose logs n8n
docker compose logs nextcloud
docker compose logs simplex-bridge
docker compose logs simplex-chat-cli
docker compose logs clawdbot-gateway

# Rebuild if needed
docker compose down
docker compose build --no-cache
docker compose up -d
```

### SimpleX Shows "No Profile Found" Error

This is expected on first run. Follow the [Connecting SimpleX Chat](#connecting-simplex-chat) section to create the profile interactively.

### Clawdbot Configuration Errors

Common config issues:

| Error | Fix |
|-------|-----|
| `cpus` as string | Use number: `1.0` not `"1.0"` |
| Invalid `bind` | Use enum: `"lan"` not `"0.0.0.0"` |
| Context window too small | Set `contextWindow` to 32000 |
| No API key for Ollama | Add `"apiKey": "ollama-local"` |
| Unhandled API | Add `"api": "openai-completions"` |
| baseUrl missing /v1 | Use `http://ollama:11434/v1` |

### n8n Can't Connect to Nextcloud

1. Verify NEXTCLOUD_PASSWORD in `.env` is correct
2. Restart n8n: `docker compose restart n8n`
3. Check Nextcloud is accessible: `curl http://localhost:8088`

### Ollama Not Responding

```bash
# Check Ollama logs
docker compose logs -f ollama

# Check GPU is accessible
nvidia-smi

# Check model is loaded
curl http://localhost:11434/api/tags

# Test inference
curl http://localhost:11434/api/generate -d '{"model":"gemma3:12b","prompt":"Hi"}'
```

### Permission Errors

```bash
# Fix ownership of data directories
sudo chown -R $USER:$USER data/
```

---

## Useful Commands

### Daily Operations

```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f n8n
docker compose logs -f simplex-bridge
docker compose logs -f clawdbot-gateway
docker compose logs -f ollama

# Restart all services
docker compose restart

# Restart specific service
docker compose restart n8n

# Stop all services
docker compose down

# Start all services (with local AI + Clawdbot)
docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml up -d
```

### Clawdbot Management

```bash
# Check status
docker exec clawdbot-gateway node dist/index.js status

# View logs
docker logs -f clawdbot-gateway

# Restart
docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml restart clawdbot-gateway

# Rebuild after source update
cd ~/projects/clawdbot && git pull && docker build -t clawdbot:local .
docker compose -f docker-compose.yml -f docker-compose.ollama.yml -f docker-compose.clawdbot.yml up -d clawdbot-gateway
```

### Backup & Restore

```bash
# Create backup
./scripts/backup.sh

# List backups
ls -la backups/

# Restore from backup
./scripts/restore.sh backups/second-brain-backup-YYYYMMDD-HHMMSS.tar.gz
```

### Updates

```bash
# Pull latest code
git pull

# Rebuild containers
docker compose build

# Restart with new images
docker compose up -d
```

---

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| n8n | http://localhost:5678 | Automation workflows |
| Nextcloud | http://localhost:8088 | Calendar (CalDAV) |
| Obsidian API | http://localhost:8765 | Notes management |
| SimpleX | ws://localhost:5225 | Chat interface (internal) |
| Ollama | http://localhost:11434 | Local AI inference |
| Clawdbot | http://localhost:18789 | AI reasoning (internal) |

---

## Security Notes

- **Keep `.env` private** - never commit to git
- **Use strong passwords** for Nextcloud admin
- **Firewall** - only expose ports you need externally
- **Backups** - run `./scripts/backup.sh` regularly
- **Updates** - keep Docker and images updated
- **Local AI** - Ollama API has no authentication (internal use only)
- **Clawdbot** - token authentication required, dangerous tools blocked
- **SimpleX Bot Address** - treat this like a password; anyone with it can connect to your bot

---

## Getting Help

- Check [Troubleshooting](#troubleshooting) section
- Review logs: `docker compose logs -f`
- Local AI docs: [ollama/README.md](ollama/README.md)
- Clawdbot docs: [docs/CLAWDBOT_SECURITY_HARDENING.md](docs/CLAWDBOT_SECURITY_HARDENING.md)
- Open an issue on GitHub

---

## License

MIT License - See LICENSE file for details.
