#!/usr/bin/env bash
# Installer for r510-command-center.
#
# - Verifies Ubuntu/Debian-compatible Linux and Python 3
# - Installs tmux, curl, htop, python3-venv/pip via apt (when available)
# - Creates an isolated virtualenv under ~/.local/share/r510-command-center
# - Installs a `command-center` launcher into ~/.local/bin
# - Creates a default config if one does not already exist
# - Optionally wires up TTY1 autostart (physical console only, never SSH)
#
# Safe to run more than once.
set -euo pipefail

APP_NAME="r510-command-center"
INSTALL_ROOT="${HOME}/.local/share/${APP_NAME}"
VENV_DIR="${INSTALL_ROOT}/venv"
BIN_DIR="${HOME}/.local/bin"
LAUNCHER="${BIN_DIR}/command-center"
CONFIG_DIR="${HOME}/.config/${APP_NAME}"
CONFIG_FILE="${CONFIG_DIR}/config.toml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { printf '\033[1;36m[install]\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[install]\033[0m %s\n' "$1"; }
err()  { printf '\033[1;31m[install]\033[0m %s\n' "$1" >&2; }

if [[ "$(id -u)" -eq 0 ]]; then
  err "Do not run this installer as root. Run it as the user who will use the dashboard."
  exit 1
fi

log "Checking platform..."
if [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  log "Detected: ${PRETTY_NAME:-unknown}"
  case "${ID:-}${ID_LIKE:-}" in
    *ubuntu*|*debian*) ;;
    *) warn "This installer targets Ubuntu/Debian. Continuing anyway on '${ID:-unknown}'." ;;
  esac
else
  warn "Could not detect distribution (missing /etc/os-release). Continuing anyway."
fi

if ! command -v python3 >/dev/null 2>&1; then
  err "python3 is required but was not found. Install Python 3.11+ and re-run."
  exit 1
fi
log "Found python3 $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"

if command -v apt-get >/dev/null 2>&1; then
  log "Installing system packages via apt (may prompt for your sudo password)..."
  sudo apt-get update -y
  sudo apt-get install -y python3-venv python3-pip tmux curl htop
else
  warn "apt-get not found; skipping system package installation."
  warn "Make sure python3-venv, tmux, curl, and htop are installed manually."
fi

log "Creating virtual environment at ${VENV_DIR}..."
mkdir -p "${INSTALL_ROOT}"
if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
else
  log "Virtual environment already exists, reusing it."
fi

log "Installing r510-command-center and its dependencies..."
"${VENV_DIR}/bin/pip" install --upgrade pip >/dev/null
"${VENV_DIR}/bin/pip" install "${SCRIPT_DIR}"

log "Creating launcher at ${LAUNCHER}..."
mkdir -p "${BIN_DIR}"
cat > "${LAUNCHER}" <<LAUNCHER_EOF
#!/usr/bin/env bash
exec "${VENV_DIR}/bin/python3" -m command_center.app "\$@"
LAUNCHER_EOF
chmod +x "${LAUNCHER}"

if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
  warn "${BIN_DIR} is not currently on your PATH."
  SHELL_RC="${HOME}/.bashrc"
  if [[ -n "${ZSH_VERSION:-}" || "${SHELL:-}" == *zsh* ]]; then
    SHELL_RC="${HOME}/.zshrc"
  fi
  PATH_MARKER="# added by r510-command-center installer"
  if ! grep -qsF "${PATH_MARKER}" "${SHELL_RC}" 2>/dev/null; then
    {
      echo ""
      echo "${PATH_MARKER}"
      echo 'export PATH="$HOME/.local/bin:$PATH"'
    } >> "${SHELL_RC}"
    log "Added ${BIN_DIR} to PATH in ${SHELL_RC}. Run: source ${SHELL_RC} (or open a new shell)."
  fi
fi

if [[ ! -f "${CONFIG_FILE}" ]]; then
  log "Creating default configuration at ${CONFIG_FILE}..."
  mkdir -p "${CONFIG_DIR}"
  "${VENV_DIR}/bin/python3" - <<'PYEOF'
from command_center.config import ensure_config_dir, default_config_toml, CONFIG_PATH
ensure_config_dir()
CONFIG_PATH.write_text(default_config_toml())
PYEOF
else
  log "Existing configuration found at ${CONFIG_FILE}, leaving it untouched."
fi

echo
read -r -p "Enable automatic dashboard launch on TTY1 (physical console only, never over SSH)? [y/N] " enable_autostart
if [[ "${enable_autostart}" =~ ^[Yy]$ ]]; then
  BASH_PROFILE="${HOME}/.bashrc"
  BEGIN_MARKER="# BEGIN r510-command-center TTY1 autostart"
  END_MARKER="# END r510-command-center TTY1 autostart"
  if grep -qsF "${BEGIN_MARKER}" "${BASH_PROFILE}" 2>/dev/null; then
    log "TTY1 autostart is already configured in ${BASH_PROFILE}."
  else
    cat >> "${BASH_PROFILE}" <<AUTOSTART_EOF

${BEGIN_MARKER}
if [[ \$- == *i* ]] \\
  && [[ "\$(tty)" == "/dev/tty1" ]] \\
  && [[ -z "\${SSH_CONNECTION:-}" ]] \\
  && [[ -n "\${TERM:-}" ]] \\
  && command -v command-center >/dev/null 2>&1 \\
  && [[ -z "\${R510_DASHBOARD_RUNNING:-}" ]]; then
  export R510_DASHBOARD_RUNNING=1
  command-center
fi
${END_MARKER}
AUTOSTART_EOF
    log "TTY1 autostart added to ${BASH_PROFILE}."
  fi
else
  log "Skipping TTY1 autostart configuration (see README to enable it later)."
fi

echo
log "Installation complete."
log "Run the dashboard with: command-center"
log "If the command is not found, run: export PATH=\"\$HOME/.local/bin:\$PATH\""
