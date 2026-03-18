FROM python:3.12-slim
LABEL maintainer="Gareth Williams <garethwilliams21@gmail.com>"

ENV DEBIAN_FRONTEND=noninteractive \
    NODE_VERSION=22.12.0 \
    APP_HOME=/app

# Install system packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        git \
        build-essential \
        ca-certificates \
        ffmpeg \
        gosu \
        wget \
        unzip \
        xz-utils \
        libffi-dev \
        libssl-dev \
        jq \
        locales && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js - architecture aware for multi-platform builds
RUN ARCH=$(dpkg --print-architecture) && \
    case "$ARCH" in \
        amd64) NODE_ARCH="x64" ;; \
        arm64) NODE_ARCH="arm64" ;; \
        *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac && \
    curl -fsSL https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.xz \
    | tar -xJ -C /usr/local --strip-components=1 && \
    node -v && npm -v

# Install bgutil PO token provider
RUN git clone --depth 1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /root/bgutil-ytdlp-pot-provider && \
    cd /root/bgutil-ytdlp-pot-provider/server && \
    npm install && \
    npx tsc

# Install python requirements
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-compile --no-cache-dir -r /tmp/requirements.txt

# Create folders
RUN mkdir -p /config /app /sonarr_root /logs && \
    touch /var/lock/sonarr_youtube.lock

# Volumes
VOLUME /config
VOLUME /sonarr_root
VOLUME /logs

# Copy application
COPY app/ /app

# Fix permissions
RUN chmod +x \
    /app/sonarr_youtubedl.py \
    /app/utils.py

# Environment
ENV CONFIGPATH=/config/config.yml

# Entrypoint
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["entrypoint.sh"]
CMD ["python", "-u", "/app/sonarr_youtubedl.py"]