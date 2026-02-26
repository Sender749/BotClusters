# Multi-Bot-Deployer — Dockerfile with Docker bot support
FROM python:3.11-slim

# Install system deps + Docker CLI (needed by worker.py to build/run Dockerfile-based bots)
RUN apt-get update && apt-get install -y \
    git \
    supervisor \
    curl \
    build-essential \
    ca-certificates \
    gnupg \
    lsb-release \
    ffmpeg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
       | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
       https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Create required directories for supervisord
RUN mkdir -p /var/log/supervisor /etc/supervisor/conf.d

WORKDIR /app

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# cluster.py is the real orchestrator:
# it starts update.py, gunicorn (web UI), supervisord, worker.py, and ping_server.py
CMD ["python3", "cluster.py"]
