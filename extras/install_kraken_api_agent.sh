#!/bin/bash
#
# Install the kraken_api_agent on a KrakenSDR (Raspberry Pi image) to give
# KrakTAK a rich REST control backend (port 8181) for retune/gain/VFO/coords.
#
# Run this ON the KrakenSDR device, not on the KrakTAK host:
#   ssh krakenrf@<KRAKEN_IP>
#   bash install_kraken_api_agent.sh
#
# KrakTAK works without this (it falls back to the settings.json upload path),
# but the agent is more robust and avoids toggling remote-control mode.
set -e

REPO="https://github.com/ghostop14/kraken_api_agent.git"
DEST="${HOME}/kraken_api_agent"

echo "[kraktak] Installing kraken_api_agent prerequisites..."
sudo apt-get update -qq
sudo apt-get install -y python3-tzlocal git

if [ ! -d "${DEST}" ]; then
    echo "[kraktak] Cloning ${REPO} -> ${DEST}"
    git clone "${REPO}" "${DEST}"
else
    echo "[kraktak] Updating existing checkout in ${DEST}"
    git -C "${DEST}" pull --ff-only || true
fi

if [ -d "${DEST}/systemctl_service" ]; then
    echo "[kraktak] Installing systemd service (krakensdragent)..."
    cd "${DEST}/systemctl_service"
    sudo ./install_service.sh
    echo "[kraktak] Done. Check status with: sudo systemctl status krakensdragent"
else
    echo "[kraktak] Service installer not found; start manually:"
    echo "  cd ${DEST} && sudo ./kraken_api_agent.py"
fi

echo "[kraktak] The agent listens on :8181. Set KrakTAK CONTROL_BACKEND=api_agent"
echo "[kraktak] (or leave it on 'auto') and point KRAKEN_HOST at this device."
