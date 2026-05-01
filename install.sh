#!/usr/bin/env bash
set -euo pipefail

# --------------------------------------------------------------------------
# install.sh — Install the Inference Server as a systemd service
# --------------------------------------------------------------------------

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="inference-server"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
RUN_USER="${SUDO_USER:-$(whoami)}"
RUN_GROUP="$(id -gn "$RUN_USER")"
PYTHON="${APP_DIR}/.venv/bin/python"

# --- Must run as root -------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    echo "Please run with sudo:  sudo ./install.sh"
    exit 1
fi

# --- Create venv & install deps if needed -----------------------------------
if [[ ! -x "$PYTHON" ]]; then
    echo ">>> Creating virtual environment & installing dependencies …"
    sudo -u "$RUN_USER" bash -c "cd '$APP_DIR' && python3 -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install ."
fi

# --- Write systemd unit -----------------------------------------------------
echo ">>> Installing systemd service → ${SERVICE_FILE}"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Inference Server — Multi-Camera Detection Pipeline
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${APP_DIR}
ExecStart=${PYTHON} ${APP_DIR}/main.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=${APP_DIR}/recordings ${APP_DIR}/engines
ProtectHome=false

[Install]
WantedBy=multi-user.target
EOF

# --- Enable & start ---------------------------------------------------------
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl start "${SERVICE_NAME}.service"

echo ">>> Done. Service status:"
systemctl --no-pager status "${SERVICE_NAME}.service" || true
echo ""
echo "Useful commands:"
echo "  journalctl -u ${SERVICE_NAME} -f      # follow logs"
echo "  sudo systemctl restart ${SERVICE_NAME} # restart"
echo "  sudo systemctl stop ${SERVICE_NAME}    # stop"
