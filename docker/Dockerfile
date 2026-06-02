# KrakTAK runtime image.
#
# Build from the repo root:
#   docker build -f docker/Dockerfile -t kraktak:local .
FROM python:3.12-slim

LABEL org.opencontainers.image.title="KrakTAK" \
      org.opencontainers.image.description="KrakenSDR to TAK Bridge" \
      org.opencontainers.image.source="https://github.com/snstac/kraktak"

ARG DEBIAN_FRONTEND=noninteractive

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir . \
    && python3 -m kraktak --version > /dev/null

RUN useradd --create-home --home-dir /home/kraktak --shell /bin/bash kraktak
USER kraktak

# Configure via environment variables (see kraktak-example.conf) or mount a
# config at /etc/kraktak/kraktak.conf and override the command.
ENTRYPOINT ["kraktak"]
