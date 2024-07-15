#!/bin/bash
set -e

ENV_PUID=${PUID:-911}
ENV_GUID=${GUID:-1000}

# Create a temporary group and user based on PUID and PGID
if ! getent group tempgroup > /dev/null; then
  groupadd -g ${ENV_GUID} tempgroup
fi

if ! id -u tempuser > /dev/null 2>&1; then
  useradd -u ${ENV_PUID} -g tempgroup -d /config -s /bin/false tempuser
fi

# Change ownership of directories to the host user
chown -R ${ENV_PUID}:${ENV_GUID} /config /app /sonarr_root /logs /var/lock/sonarr_youtube.lock

# Execute the CMD passed to the Docker container as the specified user
exec su -s /bin/bash tempuser -c "$*"
