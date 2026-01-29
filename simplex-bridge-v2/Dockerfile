FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directories
RUN mkdir -p /app/scripts/state /app/logs

# Copy bridge script
COPY bridge_v2.py /app/scripts/bridge.py

# Make executable
RUN chmod +x /app/scripts/bridge.py

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=5)"

# Run bridge
CMD ["python3", "-u", "/app/scripts/bridge.py"]
