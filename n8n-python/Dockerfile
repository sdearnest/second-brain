# n8n with Python support and pre-installed community nodes
# 
# This Dockerfile extends the official n8n image with:
# - Python 3 and pip for code nodes
# - Pre-installed n8n-nodes-simplexity for SimpleX Chat integration
#
# Build: docker build -t n8n-python:latest ./n8n-python
# 
FROM docker.n8n.io/n8nio/n8n:latest

# Switch to root for installations
USER root

# Install Python and common dependencies
#RUN apk add --no-cache \
#    python3 \
#    py3-pip \
#    python3-dev \
#    gcc \
#    musl-dev \
#    libffi-dev

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ca-certificates \
    netcat-openbsd \
    curl \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Create symlinks for python commands
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Install common Python packages for n8n code nodes
RUN pip3 install --no-cache-dir --break-system-packages \
    requests \
    python-dateutil \
    pytz

# ==============================================================================
# PRE-INSTALL COMMUNITY NODES
# ==============================================================================
# Community nodes are installed globally so they persist across container restarts
# and are available immediately without manual installation via the UI.
#
# The n8n-nodes-simplexity package provides:
#   - SimplexityTrigger: Receive messages from SimpleX Chat
#   - Simplexity: Send messages to SimpleX Chat contacts
#
# To add more community nodes, add them to the npm install command below.
# ==============================================================================

# Set npm global directory and install community nodes
ENV NPM_CONFIG_PREFIX=/home/node/.npm-global
ENV PATH=$PATH:/home/node/.npm-global/bin

# Create the npm global directory with correct permissions
RUN mkdir -p /home/node/.npm-global && \
    chown -R node:node /home/node/.npm-global

# Switch to node user for npm installations
USER node

# Install community nodes globally
# Add additional community nodes here as needed (space-separated)
RUN npm install -g \
    n8n-nodes-simplexity@latest

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Environment variables for n8n to find the community nodes
ENV N8N_CUSTOM_EXTENSIONS=/home/node/.npm-global/lib/node_modules
ENV NODE_PATH=/home/node/.npm-global/lib/node_modules

# Ensure community packages are enabled
ENV N8N_COMMUNITY_PACKAGES_ENABLED=true

# Default timezone
ENV TZ=Europe/London

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget -q --spider http://localhost:5678/healthz || exit 1

# Expose default n8n port
EXPOSE 5678

# Default command (inherited from base image)
# CMD ["n8n", "start"]
