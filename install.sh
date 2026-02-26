#!/bin/bash
set -e

usage() {
    echo "Usage: $0 [--apt-packages \"pkg1 pkg2...\"] [--pip-packages \"pkg1 pkg2...\"]"
    exit 1
}

APT_PACKAGES="nano"
PIP_PACKAGES="croniter python-dateutil apscheduler"

echo "[INFO] Starting install.sh script"

while [[ $# -gt 0 ]]; do
    case $1 in
        --apt-packages)
            APT_PACKAGES="$2"
            echo "[INFO] Overriding APT packages to install: $APT_PACKAGES"
            shift 2
            ;;
        --pip-packages)
            PIP_PACKAGES="$2"
            echo "[INFO] Overriding PIP packages to install: $PIP_PACKAGES"
            shift 2
            ;;
        *)
            usage
            ;;
    esac
done

if [ ! -z "$APT_PACKAGES" ]; then
    echo "[INFO] Updating APT repositories"
    apt-get update -y || echo "[WARN] apt-get update failed, continuing..."
    echo "[INFO] Installing APT packages: $APT_PACKAGES"
    echo "$APT_PACKAGES" | xargs apt-get install -y || echo "[WARN] apt-get install failed, continuing..."
    echo "[INFO] APT packages installed (with possible warnings)"
fi

if [ ! -z "$PIP_PACKAGES" ]; then
    echo "[INFO] Checking for pip3"
    if ! command -v pip3 &> /dev/null; then
        echo "[INFO] pip3 not found, installing python3-pip"
        apt-get install -y python3-pip
    fi
    echo "[INFO] Installing pip packages: $PIP_PACKAGES"
    echo "$PIP_PACKAGES" | xargs pip3 install --break-system-packages
    echo "[INFO] PIP packages installed successfully"
fi

echo "[INFO] install.sh script completed"
