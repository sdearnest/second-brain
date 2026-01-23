FROM node:20-bullseye

# Install python3 + pip + utilities
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ca-certificates \
    netcat-openbsd \
    curl \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Install n8n globally
RUN npm install -g n8n

# Install SimpleX community node
RUN npm install -g n8n-nodes-simplexity

# Ensure n8n data dir exists and is owned by node
RUN mkdir -p /home/node/.n8n \
 && chown -R node:node /home/node/.n8n

USER node
WORKDIR /home/node

EXPOSE 5678
CMD ["n8n"]
