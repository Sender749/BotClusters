# Multi-Bot-Deployer — Dockerfile with Docker-in-Docker support
FROM python:3.11-slim

# Install system deps + Docker CLI (so worker.py can `docker build/run` bot images)
RUN apt-get update && apt-get install -y \
    git \
    supervisor \
    curl \
    build-essential \
    ca-certificates \
    gnupg \
    lsb-release \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
       https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Create required supervisor log directory
RUN mkdir -p /var/log/supervisor /etc/supervisor/conf.d

WORKDIR /app

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# run.py is the real orchestrator (starts gunicorn + supervisord + worker + ping_server)
CMD ["python3", "run.py"]
