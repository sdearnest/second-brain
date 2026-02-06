FROM docker.n8n.io/n8nio/n8n:latest

USER root

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-distutils \
    build-essential \
    libffi-dev \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python

RUN pip3 install --no-cache-dir --break-system-packages \
    requests \
    python-dateutil \
    pytz

ENV NPM_CONFIG_PREFIX=/home/node/.npm-global
ENV PATH=$PATH:/home/node/.npm-global/bin

RUN mkdir -p /home/node/.npm-global && \
    chown -R node:node /home/node

USER node

RUN npm install -g \
    n8n-nodes-simplexity@latest

ENV N8N_CUSTOM_EXTENSIONS=/home/node/.npm-global/lib/node_modules
ENV NODE_PATH=/home/node/.npm-global/lib/node_modules
ENV N8N_COMMUNITY_PACKAGES_ENABLED=true
ENV TZ=Europe/London

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget -q --spider http://localhost:5678/healthz || exit 1

EXPOSE 5678
