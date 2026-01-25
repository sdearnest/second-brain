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
7. [Local AI Setup (Optional)](#local-ai-setup-optional)
8. [Migrating Existing Data](#migrating-existing-data)
9. [Verification](#verification)
10. [Troubleshooting](#troubleshooting)
11. [Useful Commands](#useful-commands)

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

4. **Send a test message:**
   ```
   what's on my calendar today?
   ```

### Step 8: Verify Bridge is Working

```bash
docker compose logs -f simplex-bridge
```

You should see messages being forwarded to n8n:
```
[OK] Posted: contactId=1 itemId=43 from="YourName" text='what's on my calendar today?' | Response: {"success":true}
```

---

## Configuring n8n Simplexity Integration

The Second Brain uses a hybrid approach for SimpleX communication:
- **Input:** The Python bridge forwards incoming messages to n8n via webhook
- **Output:** The **n8n-nodes-simplexity** community package sends responses back to SimpleX

### Step 1: Install the Simplexity Community Node

> **Note:** If you deployed using the setup script with the latest Docker image, the `n8n-nodes-simplexity` package is **already pre-installed**. You can verify this by going to Settings → Community nodes. If it's listed, skip to Step 2. If you're upgrading an existing installation or the node isn't showing, follow these steps.

1. **Open n8n** at `http://localhost:5678`

2. **Go to Settings** (gear icon in the left sidebar)

3. **Click "Community nodes"**

4. **Check if `n8n-nodes-simplexity` is already listed**
   - If yes, skip to Step 2
   - If no, continue below

5. **Click "Install a community node"**

6. **Enter:** `n8n-nodes-simplexity`

7. **Click "Install"**

8. **Wait for installation** - n8n may restart automatically

After installation, you'll have two new nodes available:
- **SimplexityTrigger** - Can receive incoming messages (alternative to bridge)
- **Simplexity** - Sends messages back to SimpleX contacts ← **This is what we use**

### Step 2: Create Simplexity API Credentials

The Simplexity node needs credentials to connect to your SimpleX Chat CLI.

1. **In n8n, go to** Settings → Credentials

2. **Click "Add credential"**

3. **Search for** "SimplexityApi" and select it

4. **Configure the credentials:**

   | Field | Value | Description |
   |-------|-------|-------------|
   | **Credential Name** | `simplex` | A friendly name for this credential |
   | **Host** | `simplex-chat-cli` | The Docker container name (internal network) |
   | **Port** | `5225` | The SimpleX WebSocket API port |
   | **Bot Address** | `https://smp6.simplex.im/a#...` | Your full bot address from the previous section |

   > **Finding your Bot Address:** If you didn't save it earlier, retrieve it with:
   > ```bash
   > docker exec -it simplex-chat-cli simplex-chat -d /home/simplex/.simplex/simplex
   > ```
   > 
   > You'll see:
   > ```
   > SimpleX Chat v6.4.7.1
   > db: /home/simplex/.simplex/simplex_chat.db, /home/simplex/.simplex/simplex_agent.db
   > ...
   > Current user: second-brain
   > 1 contacts connected (use /cs for the list)
   > Your address is active! To show: /sa
   > ```
   > 
   > Then type `/sa` to show the address:
   > ```
   > /sa
   > Your chat address:
   > https://smp6.simplex.im/a#Am1D1vZgHiCZbKg-aLj8WguJBGgvOAHbj5JSqzUytWM
   > ```
   > 
   > Copy the full URL, then type `/quit` to exit.

5. **Click "Save"**

### Step 3: Configure the Simplexity Action Node in the Main Workflow

The **Simplexity** action node sends responses back to SimpleX contacts. You'll find these at the end of each response branch in your workflow.

1. **Open your workflow** (e.g., `SimpleX_SecondBrain_Router`)

2. **Find the Simplexity action nodes** (they appear at the end of response branches like `Pass_Delete_Reply`, `Pass_Confirm_Reply`, etc.)

3. **Configure each Simplexity node with these settings:**

   | Field | Value |
   |-------|-------|
   | **Credential** | Select `simplex` (the credential you created above) |
   | **Contact ID** | `{{ $('Webhook_SimpleX_In').first().json.body.contactId }}` |
   | **Message** | `{{ $json.reply \|\| $json.message }}` |

   **Explanation:**
   - **Contact ID:** References the `contactId` from the incoming webhook payload (sent by the bridge). This ensures the response goes to the correct person.
   - **Message:** Uses the `reply` field if available, otherwise falls back to `message`. This handles different response formats from various workflow branches.

4. **Save the workflow**

### Step 4: Configure the Simplexity Action Node in the Calendar Workflow

The **Calendar_input_output** workflow (or similar calendar sub-workflow) also has a Simplexity node that needs configuration.

1. **Open the Calendar workflow** in n8n

2. **Find the Simplexity action node** (usually at the end, for sending confirmations)

3. **Configure it with these settings:**

   | Field | Value |
   |-------|-------|
   | **Credential** | Select `simplex` |
   | **Contact ID** | `{{ $json.contactId \|\| $('Classify_Request').item.json.contactId }}` |
   | **Message** | `{{ $json.reply \|\| $json.message \|\| "✅ Event added: " + $('Classify_Request').item.json.request }}` |

   **Explanation:**
   - **Contact ID:** Pulls from either the current item or falls back to the `Classify_Request` node. This handles cases where the calendar workflow is called as a sub-workflow and the contactId is passed through differently.
   - **Message:** Provides a chain of fallbacks:
     1. Uses `reply` if explicitly set
     2. Falls back to `message` if available
     3. Constructs a default confirmation using the original request text

4. **Save the workflow**

### Step 5: Verify the Integration

1. **Ensure both the bridge and workflows are running:**
   ```bash
   docker compose logs -f simplex-bridge
   ```

2. **Activate your workflows** (toggle the "Active" switch for both the main router and calendar workflows)

3. **Send test messages** from your phone via SimpleX:
   ```
   what's on my calendar today?
   ```
   ```
   add meeting at 3pm tomorrow
   ```

4. **Check the workflow executions** in n8n (Executions tab) to see the data flowing through

5. **You should receive responses** back in SimpleX Chat for both queries and event creation

### Architecture Overview

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────┐
│  SimpleX App    │     │  simplex-chat-cli   │     │    n8n      │
│  (Your Phone)   │◄───►│  (WebSocket :5225)  │◄───►│  Workflows  │
└─────────────────┘     └─────────────────────┘     └─────────────┘
                                  ▲                        │
                    ┌─────────────┘                        │
                    │ INPUT: Bridge polls                  │
                    │ and forwards to webhook              │
                    ▼                                      │
              ┌───────────────┐                           │
              │ simplex-bridge│                           │
              │ (Python)      │───► Webhook_SimpleX_In    │
              └───────────────┘                           │
                                                          │
                    OUTPUT: Simplexity node ◄─────────────┘
                    sends directly to SimpleX CLI
```

---

## Importing Workflows

### If You Have Existing Workflow JSON Files

1. **Open n8n:** http://localhost:5678

2. **Import each workflow:**
   - Click "Add workflow" (or the + button)
   - Click "Import from file"
   - Select your `.json` file
   - Click "Save"

3. **Recreate credentials:**
   
   Credentials are NOT included in workflow exports. You need to recreate:
   
   - **SimplexityApi** (see [Configuring n8n Simplexity Integration](#configuring-n8n-simplexity-integration))
   - **OpenAI API Key:**
     - Settings → Credentials → Add credential
     - Select "OpenAI API"
     - Paste your API key
   
   - **Other APIs** as needed

4. **Update credential references:**
   - Open each workflow
   - Find nodes with missing credentials (shown with ⚠️)
   - Select the correct credential from dropdown

5. **Activate workflows:**
   - Toggle the "Active" switch for each workflow

### If Starting Fresh

Import the example workflows from `n8n/workflows/` directory, then customize for your needs.

---

## Local AI Setup (Optional)

For running AI models locally instead of using cloud APIs, see the separate documentation in `ollama/README.md`.

Quick start:

```bash
# Start with local AI enabled
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d

# Pull a model
docker exec ollama ollama pull gemma3:12b
```

---

## Migrating Existing Data

If you're moving from another machine with existing Second Brain data:

### Option A: Using Backup/Restore Scripts

**On your old machine:**

```bash
cd ~/second-brain
./scripts/backup.sh
# Creates: backups/second-brain-backup-YYYYMMDD-HHMMSS.tar.gz
```

**Transfer to new machine:**

```bash
scp ~/second-brain/backups/second-brain-backup-*.tar.gz user@newmachine:~/second-brain/backups/
```

**On new machine:**

```bash
cd ~/second-brain
./scripts/restore.sh backups/second-brain-backup-YYYYMMDD-HHMMSS.tar.gz
```

### Option B: Manual Copy

**Transfer specific data directories:**

```bash
# From old machine to new machine
scp -r old-machine:~/second-brain/data/vault/* ~/second-brain/data/vault/
scp -r old-machine:~/second-brain/data/n8n/* ~/second-brain/data/n8n/
scp -r old-machine:~/second-brain/data/simplex/* ~/second-brain/data/simplex/
```

**Restart services after copying:**

```bash
docker compose restart
```

---

## Verification

### Check All Services Are Running

```bash
docker compose ps
```

**Expected output:**

```
NAME                STATUS              PORTS
n8n                 Up (healthy)        0.0.0.0:5678->5678/tcp
nextcloud           Up                  0.0.0.0:8088->80/tcp
nextcloud-cron      Up
nextcloud-db        Up (healthy)
obsidian-api        Up (healthy)        0.0.0.0:8765->8000/tcp
simplex-bridge      Up
simplex-chat-cli    Up                  0.0.0.0:5225->5225/tcp
```

### Test Each Service

**n8n:**
```bash
curl -s http://localhost:5678/healthz
# Should return: {"status":"ok"}
```

**Obsidian API:**
```bash
curl -s http://localhost:8765/health
# Should return: {"status":"healthy",...}
```

**Nextcloud:**
```bash
curl -s http://localhost:8088/status.php
# Should return JSON with "installed":true
```

**SimpleX Bridge:**
```bash
docker compose logs simplex-bridge | tail -5
# Should show successful message forwarding or "waiting for messages"
```

**Ollama (if enabled):**
```bash
curl -s http://localhost:11434/api/tags
# Should return JSON with model list
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

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs for the specific container
docker compose logs n8n
docker compose logs nextcloud
docker compose logs simplex-bridge
docker compose logs simplex-chat-cli

# Rebuild if needed
docker compose down
docker compose build --no-cache
docker compose up -d
```

### SimpleX Shows "No Profile Found" Error

This is expected on first run. Follow the [Connecting SimpleX Chat](#connecting-simplex-chat) section to create the profile interactively.

**Quick fix:**

```bash
# 1. Stop the container
docker compose stop simplex-chat-cli

# 2. Create profile interactively
docker compose run -it --rm simplex-chat-cli \
  simplex-chat -d /home/simplex/.simplex/simplex

# 3. Enter display name: second-brain
# 4. Type /auto_accept on
# 5. Type /address then /sa and SAVE THE URL
# 6. Type /quit to exit

# 7. Start all services
docker compose up -d
```

### SimpleX Profile Lost After Restart

If your SimpleX profile disappears after container restart, check that:

1. **Volume mount exists:** `data/simplex/` directory exists on host
2. **Files are present:** `ls -la data/simplex/` shows `.db` files
3. **Permissions are correct:** `sudo chown -R $USER:$USER data/simplex/`

### Simplexity Node Shows "Could not connect"

1. **Verify SimpleX CLI is running:**
   ```bash
   docker compose logs simplex-chat-cli
   ```

2. **Check the credential configuration:**
   - Host should be `simplex-chat-cli` (container name, not localhost)
   - Port should be `5225`
   - Bot Address should be the full `https://smp6.simplex.im/...` URL

3. **Test connectivity from n8n container:**
   ```bash
   docker exec -it n8n sh -c "wget -q -O- http://simplex-chat-cli:5225 || echo 'Connection test complete'"
   ```

### Simplexity Trigger Not Receiving Messages

1. **Check that the workflow is active** (toggle must be ON)

2. **Verify SimpleX CLI is receiving messages:**
   ```bash
   docker compose logs -f simplex-chat-cli
   ```

3. **Check n8n executions** for errors

4. **Ensure auto-accept is enabled** in SimpleX:
   ```bash
   docker exec -it simplex-chat-cli simplex-chat -d /home/simplex/.simplex/simplex
   # Type: /auto_accept on
   # Type: /quit
   ```

### SimpleX Bridge Not Forwarding Messages

The bridge forwards incoming messages from SimpleX to n8n via webhook.

1. **Check bridge logs:**
   ```bash
   docker compose logs -f simplex-bridge
   ```

2. **Verify the bridge can reach SimpleX CLI:**
   - Look for connection errors in the logs
   - Ensure `simplex-chat-cli` container is running

3. **Verify the bridge can reach n8n webhook:**
   ```bash
   # Test webhook manually
   curl -X POST http://localhost:5678/webhook/simplex-in \
     -H "Content-Type: application/json" \
     -d '{"text": "test", "contactId": 1, "displayName": "Test"}'
   ```

4. **Check webhook URL in bridge environment:**
   - Should be `http://n8n:5678/webhook/simplex-in` (internal Docker network)
   - Workflow must be **active** for production webhook to work

5. **Common issues:**
   - Bridge shows "connection refused" → SimpleX CLI not running or wrong host
   - Bridge shows "404" → Workflow not active or wrong webhook path
   - No output at all → Check `SIMPLEX_WS_URL` environment variable

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

### Ollama Out of Memory

If you see CUDA out of memory errors:

```bash
# Use a smaller quantization
docker exec ollama ollama pull gemma3:12b-q4_K_M

# Update .env
nano .env
# Change OLLAMA_MODEL to the smaller model

# Restart
docker compose -f docker-compose.yml -f docker-compose.ollama.yml restart ollama
```

### Permission Errors

```bash
# Fix ownership of data directories
sudo chown -R $USER:$USER data/
```

### Database Issues

```bash
# Reset Nextcloud database (WARNING: deletes all data)
docker compose down
sudo rm -rf data/nextcloud-db/*
docker compose up -d
```

### Out of Disk Space

```bash
# Check disk usage
df -h

# Clean up Docker
docker system prune -a
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
docker compose logs -f simplex-chat-cli
docker compose logs -f ollama

# Restart all services
docker compose restart

# Restart specific service
docker compose restart n8n

# Stop all services
docker compose down

# Start all services (without local AI)
docker compose up -d

# Start all services (with local AI)
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d
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

### Accessing Containers

```bash
# Shell into n8n
docker exec -it n8n /bin/bash

# Shell into Nextcloud
docker exec -it nextcloud /bin/bash

# SimpleX CLI (if profile already exists)
docker exec -it simplex-chat-cli simplex-chat -d /home/simplex/.simplex/simplex

# Ollama CLI
docker exec -it ollama ollama list
```

### SimpleX Management

```bash
# Get your bot address again
docker exec -it simplex-chat-cli simplex-chat -d /home/simplex/.simplex/simplex
# Then type: /sa
# Then type: /quit

# Check auto-accept status
docker exec -it simplex-chat-cli simplex-chat -d /home/simplex/.simplex/simplex
# Then type: /auto_accept
# Then type: /quit

# Reset SimpleX profile (start fresh)
docker compose stop simplex-chat-cli
sudo rm -rf data/simplex/*
# Then follow "Connecting SimpleX Chat" section again
```

### Ollama Management

```bash
# List models
docker exec ollama ollama list

# Pull a new model
docker exec ollama ollama pull mistral:7b

# Remove a model
docker exec ollama ollama rm gemma3:12b

# Check GPU usage
nvidia-smi
```

---

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| n8n | http://localhost:5678 | Automation workflows |
| Nextcloud | http://localhost:8088 | Calendar (CalDAV) |
| Obsidian API | http://localhost:8765 | Notes management |
| SimpleX | ws://localhost:5225 | Chat interface (internal) |
| Ollama | http://localhost:11434 | Local AI (optional) |

---

## Security Notes

- **Keep `.env` private** - never commit to git
- **Use strong passwords** for Nextcloud admin
- **Firewall** - only expose ports you need externally
- **Backups** - run `./scripts/backup.sh` regularly
- **Updates** - keep Docker and images updated
- **Local AI** - Ollama API has no authentication (internal use only)
- **SimpleX Bot Address** - treat this like a password; anyone with it can connect to your bot

---

## Getting Help

- Check [Troubleshooting](#troubleshooting) section
- Review logs: `docker compose logs -f`
- Local AI docs: [ollama/README.md](ollama/README.md)
- Open an issue on GitHub

---

## License

MIT License - See LICENSE file for details.
