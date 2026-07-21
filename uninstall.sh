#!/usr/bin/env bash
# Uninstaller for r510-command-center.
#
# Removes the application files, launcher, and any TTY1 autostart block
# added by install.sh. Leaves system packages (python3, tmux, htop, ...)
# untouched, and preserves the user's config.toml unless told otherwise.
set -euo pipefail

APP_NAME="r510-command-center"
INSTALL_ROOT="${HOME}/.local/share/${APP_NAME}"
BIN_DIR="${HOME}/.local/bin"
LAUNCHER="${BIN_DIR}/command-center"
CONFIG_DIR="${HOME}/.config/${APP_NAME}"

log() { printf '\033[1;36m[uninstall]\033[0m %s\n' "$1"; }

if [[ -d "${INSTALL_ROOT}" ]]; then
  log "Removing ${INSTALL_ROOT}..."
  rm -rf "${INSTALL_ROOT}"
else
  log "No installed application files found at ${INSTALL_ROOT}."
fi

if [[ -f "${LAUNCHER}" ]]; then
  log "Removing launcher ${LAUNCHER}..."
  rm -f "${LAUNCHER}"
fi

for rc in "${HOME}/.bashrc" "${HOME}/.bash_profile" "${HOME}/.zshrc"; do
  [[ -f "${rc}" ]] || continue

  if grep -qsF "BEGIN r510-command-center TTY1 autostart" "${rc}"; then
    log "Removing TTY1 autostart block from ${rc}..."
    sed -i.bak '/# BEGIN r510-command-center TTY1 autostart/,/# END r510-command-center TTY1 autostart/d' "${rc}"
    log "Backup saved as ${rc}.bak"
  fi

  if grep -qsF "# added by r510-command-center installer" "${rc}"; then
    log "Removing PATH addition from ${rc}..."
    sed -i.bak '/# added by r510-command-center installer/,+1d' "${rc}"
  fi
done

echo
read -r -p "Remove configuration directory ${CONFIG_DIR} as well? [y/N] " remove_config
if [[ "${remove_config}" =~ ^[Yy]$ ]]; then
  rm -rf "${CONFIG_DIR}"
  log "Removed ${CONFIG_DIR}."
else
  log "Preserving configuration at ${CONFIG_DIR}."
fi

log "Uninstall complete. Python and system packages (tmux, htop, etc.) were left untouched."
