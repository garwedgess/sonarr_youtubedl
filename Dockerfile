FROM python:3.9-slim-buster
LABEL maintainer="Martin Jones <whatdaybob@outlook.com>"

# Update and install ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg gosu && \
    rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt requirements.txt
RUN pip3 install --no-compile --no-cache-dir -r requirements.txt

# create abc user so root isn't used
RUN \
# create some files / folders
	mkdir -p /config /app /sonarr_root /logs && \
	touch /var/lock/sonarr_youtube.lock


# add volumes
VOLUME /config
VOLUME /sonarr_root
VOLUME /logs

# add local files
COPY app/ /app

# update file permissions
RUN \
    chmod a+x \
    /app/sonarr_youtubedl.py \
    /app/utils.py \
    /app/config.yml.template

# ENV setup
ENV CONFIGPATH /config/config.yml

# Copy entrypoint script
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Use entrypoint script
ENTRYPOINT ["entrypoint.sh"]

CMD [ "python", "-u", "/app/sonarr_youtubedl.py" ]
