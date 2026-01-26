# iOS CalDAV Integration Guide

This guide explains how to sync your Nextcloud calendar with your iPhone's native Calendar app using CalDAV over Tailscale.

## Overview

The integration uses:
- **Tailscale** - Secure private network (VPN mesh)
- **Caddy** - HTTPS reverse proxy with proper header handling
- **Nextcloud** - Self-hosted calendar (CalDAV server)

```
iPhone Calendar ──► Tailscale VPN ──► Caddy (HTTPS:443) ──► Nextcloud (HTTP:80)
```

## Why This Setup?

iOS requires HTTPS for CalDAV connections - plain HTTP is blocked at the OS level. Additionally, iOS CalDAV has strict requirements:

1. Valid SSL/TLS certificate
2. Proper HTTPS redirects (not HTTP)
3. Correct `.well-known/caldav` discovery

Tailscale provides the certificate, and Caddy handles the HTTPS termination and redirect rewriting.

---

## Prerequisites

- Tailscale installed on your server and iPhone
- Nextcloud running in Docker (part of Second Brain stack)
- Server accessible via Tailscale domain (e.g., `yourserver.tail12345.ts.net`)

---

## Server Setup

### 1. Generate Tailscale Certificates

```bash
cd /tmp && sudo tailscale cert YOUR_MACHINE.YOUR_TAILNET.ts.net
```

Certificates are saved to `/var/snap/tailscale/common/certs/` (snap install) or `/var/lib/tailscale/certs/` (package install).

### 2. Copy Certificates to Project

```bash
mkdir -p ~/projects/second-brain/data/caddy/certs

sudo cp /var/snap/tailscale/common/certs/YOUR_MACHINE.YOUR_TAILNET.ts.net.crt \
    ~/projects/second-brain/data/caddy/certs/

sudo cp /var/snap/tailscale/common/certs/YOUR_MACHINE.YOUR_TAILNET.ts.net.key \
    ~/projects/second-brain/data/caddy/certs/

sudo chown -R $USER:$USER ~/projects/second-brain/data/caddy/
```

### 3. Create Caddyfile

Create `caddy/Caddyfile` (replace `YOUR_MACHINE.YOUR_TAILNET.ts.net` with your Tailscale domain):

```caddyfile
YOUR_MACHINE.YOUR_TAILNET.ts.net {
    tls /certs/YOUR_MACHINE.YOUR_TAILNET.ts.net.crt /certs/YOUR_MACHINE.YOUR_TAILNET.ts.net.key

    log {
        output stdout
        format console
    }

    # Handle CalDAV/CardDAV well-known redirects (critical for iOS)
    redir /.well-known/caldav /remote.php/dav/ permanent
    redir /.well-known/carddav /remote.php/dav/ permanent

    reverse_proxy nextcloud:80 {
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-Port 443
    }
}
```

A template is provided at `caddy/Caddyfile.example`.

### 4. Configure Nextcloud Trusted Domains

Add your Tailscale domain to Nextcloud's trusted domains:

```bash
docker exec -u 33 nextcloud php occ config:system:set trusted_domains 4 \
    --value="YOUR_MACHINE.YOUR_TAILNET.ts.net"
```

### 5. Configure Nextcloud Reverse Proxy Settings

```bash
# Tell Nextcloud it's behind HTTPS proxy
docker exec -u 33 nextcloud php occ config:system:set overwriteprotocol --value="https"
docker exec -u 33 nextcloud php occ config:system:set overwritehost \
    --value="YOUR_MACHINE.YOUR_TAILNET.ts.net"
docker exec -u 33 nextcloud php occ config:system:set overwrite.cli.url \
    --value="https://YOUR_MACHINE.YOUR_TAILNET.ts.net/"

# Trust the Caddy proxy (get Caddy's IP after starting it)
docker exec -u 33 nextcloud php occ config:system:set trusted_proxies 0 --value="172.18.0.0/16"
```

### 6. Add Caddy to Docker Compose

Add this to your `docker-compose.yml`:

```yaml
  # ============================================
  # CADDY - HTTPS Reverse Proxy for iOS CalDAV
  # ============================================
  caddy:
    image: caddy:2-alpine
    container_name: caddy
    restart: unless-stopped
    ports:
      - "443:443"
    volumes:
      - ./caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - ./data/caddy/certs:/certs:ro
      - ./data/caddy/data:/data
      - ./data/caddy/config:/config
    networks:
      - second-brain-net
```

### 7. Start Caddy

```bash
docker compose up -d caddy
```

### 8. Verify Setup

Test in Safari on your iPhone:
```
https://YOUR_MACHINE.YOUR_TAILNET.ts.net
```

You should see the Nextcloud login page with no SSL warnings.

---

## iPhone Setup

### 1. Connect to Tailscale

Open the Tailscale app on your iPhone and ensure it's connected.

### 2. Create Nextcloud App Password

1. On your iPhone, open Safari
2. Go to `https://YOUR_MACHINE.YOUR_TAILNET.ts.net`
3. Log in to Nextcloud
4. Go to **Settings → Security → Devices & sessions**
5. Create a new app password (e.g., "iPhone CalDAV")
6. **Copy the password** - you'll need it for the next step

### 3. Add CalDAV Account

1. Open **Settings** on your iPhone
2. Go to **Calendar → Accounts → Add Account**
3. Select **Other → Add CalDAV Account**
4. Enter:
   - **Server:** `YOUR_MACHINE.YOUR_TAILNET.ts.net`
   - **Username:** Your Nextcloud username
   - **Password:** The app password from step 2
   - **Description:** Nextcloud (or whatever you prefer)
5. Tap **Next**

The account should verify and connect. Your Nextcloud calendars will appear in the iOS Calendar app.

---

## Troubleshooting

### "Cannot Connect Using SSL"

This usually means:
1. Tailscale isn't connected on your iPhone
2. The certificate isn't valid or properly configured
3. The `.well-known/caldav` redirect is returning HTTP instead of HTTPS

**Check Caddy logs:**
```bash
docker logs caddy --tail 50
```

Look for the `Location` header in `.well-known/caldav` responses - it must be `https://`.

### "Unable to verify account information"

This is an authentication issue:
1. Check for trailing spaces in username/password
2. Try creating a new app password
3. Reset bruteforce protection:
   ```bash
   docker exec -u 33 nextcloud php occ security:bruteforce:reset all
   ```

### "CalDAV account verification failed"

Check Nextcloud logs:
```bash
docker exec nextcloud cat /var/www/html/data/nextcloud.log | tail -20
```

Common causes:
- Username mismatch (check `tokenLoginName` vs `sessionLoginName` in logs)
- App password not working (create a new one)
- Bruteforce protection blocking your IP

### Requests not reaching Nextcloud

1. Check if Caddy is receiving requests:
   ```bash
   docker logs caddy --tail 20
   ```

2. Check if containers are on the same network:
   ```bash
   docker network inspect second-brain-net
   ```

3. Verify Caddy can reach Nextcloud:
   ```bash
   docker exec caddy wget -q -O- http://nextcloud:80/status.php
   ```

---

## Technical Notes

### Why Caddy Instead of Tailscale Serve?

Tailscale Serve (`tailscale serve --https`) works for browsers but iOS CalDAV has stricter TLS requirements that it doesn't fully support. Caddy provides:

- Full control over TLS configuration
- Header manipulation for proxy settings
- URL rewriting for `.well-known` redirects
- Better compatibility with iOS CalDAV client

### The .well-known Redirect Problem

Nextcloud's `.well-known/caldav` redirect is handled by Apache's mod_rewrite, which doesn't respect the `overwriteprotocol` PHP setting. This causes:

```
/.well-known/caldav → 301 Redirect → http://server/remote.php/dav/
```

iOS follows this HTTP redirect and then fails because it requires HTTPS. The solution is to handle the redirect in Caddy:

```caddyfile
redir /.well-known/caldav /remote.php/dav/ permanent
```

This returns an HTTPS redirect since Caddy knows it's serving HTTPS.

### Certificate Renewal

Tailscale certificates are valid for 90 days and auto-renew. To manually refresh:

```bash
sudo tailscale cert YOUR_MACHINE.YOUR_TAILNET.ts.net
# Copy new certs to data/caddy/certs/
docker restart caddy
```

---

## Files Added

```
second-brain/
├── caddy/
│   ├── Caddyfile              # Your config (gitignored)
│   └── Caddyfile.example      # Template for others
├── data/
│   └── caddy/                 # Certs and Caddy data (gitignored)
│       ├── certs/
│       ├── config/
│       └── data/
└── docker-compose.yml         # Updated with Caddy service
```

---

## Security Considerations

- Certificates are stored in `data/caddy/certs/` which is gitignored
- The Caddyfile contains your Tailscale domain - also gitignored
- CalDAV traffic is encrypted end-to-end via Tailscale + HTTPS
- App passwords can be revoked individually in Nextcloud
- Access requires both Tailscale VPN connection and Nextcloud credentials
