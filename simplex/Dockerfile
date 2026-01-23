# SimpleX Chat CLI container
FROM ubuntu:24.04

# Set environment variables to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Update package list and install necessary dependencies
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    socat \
    telnet \
    && rm -rf /var/lib/apt/lists/*

# Create directory for simplex-chat
RUN mkdir -p /usr/local/bin

# Download and install simplex-chat CLI
# Check https://github.com/simplex-chat/simplex-chat/releases for latest version
RUN wget -O /usr/local/bin/simplex-chat \
    https://github.com/simplex-chat/simplex-chat/releases/download/v6.4.7/simplex-chat-ubuntu-24_04-x86_64 \
    && chmod +x /usr/local/bin/simplex-chat

# Create a non-root user for running simplex-chat
RUN useradd -m -s /bin/bash simplex

# Create the .simplex directory and set proper ownership
RUN mkdir -p /home/simplex/.simplex && chown -R simplex:simplex /home/simplex/.simplex

# Copy the startup script
COPY start-simplex.sh /usr/local/bin/start-simplex.sh
RUN chmod +x /usr/local/bin/start-simplex.sh

# Switch to non-root user
USER simplex

# Set working directory
WORKDIR /home/simplex

# Expose port 5225 for simplex-chat WebSocket API
EXPOSE 5225

# Start SimpleX with WebSocket API enabled
CMD ["/usr/local/bin/start-simplex.sh"]
