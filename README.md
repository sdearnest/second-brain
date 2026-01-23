# Second Brain

A privacy-focused personal AI assistant that manages calendar, notes, and tasks through natural language via SimpleX Chat. All processing occurs on self-hosted infrastructure without cloud dependencies.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/second-brain.git
cd second-brain

# Run setup
./scripts/setup.sh

# Edit .env with your settings
nano .env

# Start services
docker compose up -d
```

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │            SECOND BRAIN                 │
                         │                                         │
SimpleX Chat ──────────► │  n8n Hub                                │
  (Mobile/Desktop)       │    ├── Calendar Agent ──► Nextcloud     │
                         │    ├── Notes Agent ────► Obsidian API   │
                         │    ├── Search Agent ───► Obsidian API   │
                         │    └── Delete Agent ───► Obsidian API   │
                         │                                         │
                         └─────────────────────────────────────────┘
                                    All Local / Self-Hosted
```

## Components

| Service | Port | Purpose |
|---------|------|---------|
| n8n | 5678 | Automation hub, workflow orchestration |
| Nextcloud | 8088 | Calendar (CalDAV) |
| Obsidian API | 8765 | Notes management (5 databases) |
| SimpleX Chat | 5225 | Encrypted messaging interface |
| SimpleX Bridge | - | Connects SimpleX ↔ n8n |

## Features

### Calendar Management

| Command | Example |
|---------|---------|
| Query today | "what's on my calendar today?" |
| Query tomorrow | "tell me my schedule tomorrow" |
| Query specific date | "what's on the 9th Jan?" |
| Query this week | "what's on this week?" |
| Add event | "add meeting at 3pm tomorrow" |
| Add multiple | "add lunch at 1pm and meeting at 3pm" |
| Delete event | "cancel my 3pm meeting tomorrow" |

### Notes Management (Obsidian)

| Database | Purpose | Example |
|----------|---------|---------|
| People | Contact info | "add to Nikki she has good eye for photography" |
| Projects | Multi-step goals | "new project: Second Brain mobile app" |
| Ideas | Insights | "idea: AI-powered email sorter" |
| Admin | Tasks/todos | "task: renew passport by March" |
| Inbox Log | Audit trail | (automatic) |

### Delete with Confirmation

```
User: "delete photography"
System: "🔍 Found 3 matches:
         1. 👤 "Nikki" in people
         2. 💡 "photography NFT project" in ideas
         Reply with number (1-3) to delete, or 'cancel'."
User: "2"
System: "✅ Deleted: photography NFT project from ideas"
```

## Directory Structure

```
second-brain/
├── docker-compose.yml      # All services
├── .env.example            # Template (committed)
├── .env                    # Secrets (gitignored)
├── README.md
│
├── n8n-python/             # Custom n8n image with Python
│   └── Dockerfile
│
├── simplex/                # SimpleX Chat CLI
│   ├── Dockerfile
│   └── start-simplex.sh
│
├── obsidian-api/           # Notes API (FastAPI)
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
│
├── scripts/
│   ├── bridge.py           # SimpleX ↔ n8n connector
│   ├── setup.sh            # First-time setup
│   ├── backup.sh           # Backup script
│   └── restore.sh          # Restore script
│
└── data/                   # All persistent data (gitignored)
    ├── n8n/
    ├── nextcloud/
    ├── nextcloud-db/
    ├── vault/
    ├── simplex/
    └── simplex-bridge/
```

## Configuration

All configuration is in `.env`. Key settings:

```bash
# n8n
N8N_BASIC_AUTH_PASSWORD=your-secure-password

# Nextcloud
NEXTCLOUD_DB_PASSWORD=your-db-password
NEXTCLOUD_PASSWORD=your-app-password  # For CalDAV access

# Timezone
TZ=Europe/London
```

## Backup & Restore

```bash
# Create backup
./scripts/backup.sh

# Restore from backup
./scripts/restore.sh backups/second-brain-backup-20260122.tar.gz

# Automated backups (add to crontab)
0 2 * * * /path/to/second-brain/scripts/backup.sh --cron
```

## Remote Access

### With Tailscale (Recommended)

1. Install Tailscale on server and devices
2. Access services via Tailscale IP:
   - n8n: `http://100.x.x.x:5678`
   - Nextcloud: `http://100.x.x.x:8088`

### With Cloudflare Tunnel (For webhooks)

For external webhook access without opening ports:

```bash
# Install cloudflared
# Configure tunnel to expose n8n webhooks
cloudflared tunnel --url http://localhost:5678
```

## API Reference (Obsidian)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/db/people` | GET/POST | List/create people |
| `/db/projects` | GET/POST | List/create projects |
| `/db/ideas` | GET/POST | List/create ideas |
| `/db/admin` | GET/POST | List/create tasks |
| `/search?query=...` | POST | Search all databases |
| `/pending_delete` | GET/POST/DELETE | Delete confirmation flow |
| `/fix?category=...` | POST | Fix misclassified entries |

## Troubleshooting

### Services won't start

```bash
# Check logs
docker compose logs -f

# Check specific service
docker compose logs -f n8n
```

### SimpleX not connecting

```bash
# Check bridge logs
docker compose logs -f simplex-bridge

# Check SimpleX CLI
docker compose logs -f simplex-chat-cli
```

### Permission errors

```bash
# Fix permissions (run as root)
sudo chown -R 1000:1000 data/n8n
sudo chown -R 33:33 data/nextcloud
sudo chown -R 1001:1001 data/simplex
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - See LICENSE file for details.
