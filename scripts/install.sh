#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "Bitte als normaler Benutzer mit sudo-Rechten ausführen, nicht direkt als root."
  exit 1
fi

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_USER="$(id -un)"

if [[ "${APP_DIR}" =~ [[:space:]] ]]; then
  echo "Der Projektpfad darf für die systemd-Installation keine Leerzeichen enthalten: ${APP_DIR}"
  exit 1
fi

sudo apt-get update
sudo apt-get install -y python3-venv
python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

sudo usermod -aG dialout "${APP_USER}"

if [[ ! -f /etc/default/dmx-controller ]]; then
  sudo install -m 0644 "${APP_DIR}/.env.example" /etc/default/dmx-controller
fi

sed -e "s|__USER__|${APP_USER}|g" -e "s|__APP_DIR__|${APP_DIR}|g" \
  "${APP_DIR}/deploy/dmx-controller.service" | sudo tee /etc/systemd/system/dmx-controller.service >/dev/null

sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/dmx-controller.service
sudo systemctl enable dmx-controller.service

echo
echo "Installation abgeschlossen."
echo "1. UART wie in README.md beschrieben aktivieren und Raspberry Pi neu starten."
echo "2. Danach: sudo systemctl start dmx-controller"
echo "3. Status:  sudo systemctl status dmx-controller"
