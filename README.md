# R510 Command Center

A full-screen, animated ASCII command center for a local AI server -- built
to run directly on `tty1` of a headless Ubuntu Server box, no desktop
environment required. Think NASA mission control meets a Starlink ground
station, rendered entirely in `curses`.

It's designed as the visual home screen for a machine running **Ollama**,
**OpenCode**, and **tmux** over SSH or on the physical console.

## Preview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       R510 ORBITAL AI COMMAND CENTER                         │
│                     NODE ONLINE · UPLINK ESTABLISHED                         │
├──────────────────────────────────────────────────────────────────────────────┤
│     .:oOo:.          ·◆····                             .--------.          │
│  .oOOOOOOOo.    ··········✦·               / AI  CORE \                     │
│ oOOO@@@OOOOOo···· ·◆·····          +------------+                          │
│ oOO@@@@@OOOoo*                       \  * ** *  /                          │
│ oOOOO@@OOOOOo                          '--------'                          │
│  `oOOOOOOo'          *      ·                                              │
│    `:oOo:'                                                                  │
├────────────────────────────── SYSTEM TELEMETRY ──────────────────────────────┤
│ CPU  [████████░░░░░░░░]  RAM  [██████░░░░░░░░░░]                            │
│ SWAP [██░░░░░░░░░░░░░░]  DISK [████░░░░░░░░░░░░]                            │
│ TEMP  42C                LOAD  0.42 0.31 0.20                               │
│                                                                              │
│ OLLAMA   ONLINE          MODEL     gemma3:12b                               │
│ OPENCODE READY           TMUX      ATTACHED                                 │
│ HOST r510-node1          IP 192.168.0.169                                   │
│ UPTIME 3h 22m  PROCS 214  USERS matty    NET rx 12.4K/s tx 3.1K/s           │
├──────────────────────────────────────────────────────────────────────────────┤
│ [O]OpenCode [S]Shell [L]Logs [M]Models [R]Restart [T]Top [N]Net [H]Help [Q]Exit│
└──────────────────────────────────────────────────────────────────────────────┘
```

The real thing animates: data packets travel along the uplink arc between
Earth and the AI core, stars twinkle, a satellite drifts across the top of
the scene, and a faint scanline sweeps the display. Hostname, IP, model,
and every telemetry value shown above are examples -- your own values are
read live from the system.

## Features

- Animated orbital scene: ASCII Earth, an AI core/satellite station,
  traveling data packets, twinkling stars, a drifting satellite, and a
  subtle scanline sweep -- all rendered with plain `curses`, no external
  graphics libraries.
- Live system telemetry: hostname, IPv4, uptime, CPU (overall and
  per-core), RAM, swap, root disk usage, load averages, process count,
  logged-in users, temperature (when sensors are available), and network
  throughput.
- Ollama integration: state (`ONLINE` / `BUSY` / `IDLE` / `OFFLINE` /
  `ERROR`) determined from both `systemctl` and the Ollama HTTP API,
  installed model list, and the currently loaded model.
- OpenCode integration: auto-detects the OpenCode executable and manages
  a dedicated `tmux` session for it.
- Keyboard-driven hotkeys for a shell, logs, model list, service restart,
  `htop`, network info, and a help screen.
- Reduced-motion and ASCII-only modes for accessibility, low-bandwidth
  SSH links, or terminals without Unicode support.
- Resizes gracefully, degrades gracefully when a terminal is too small,
  and never crashes when Ollama, tmux, htop, or sensors are unavailable.
- Optional TTY1 autostart that only ever triggers on the physical
  console, never over SSH.

## Requirements

- Linux (developed for Ubuntu Server 24.04; any systemd-based distro works)
- Python 3.11+
- [`psutil`](https://pypi.org/project/psutil/) (the only mandatory
  third-party dependency)
- `tmux`, `htop`, and `curl` are optional but recommended (`install.sh`
  installs them via `apt` when available)

## Installation

```bash
git clone https://github.com/Mattjhagen/r510-command-center.git
cd r510-command-center
./install.sh
```

`install.sh`:

1. Verifies you're on Ubuntu/Debian-compatible Linux with Python 3.
2. Installs `python3-venv`, `python3-pip`, `tmux`, `curl`, and `htop` via
   `apt` (skipped if `apt` isn't available).
3. Creates an isolated virtual environment at
   `~/.local/share/r510-command-center/venv`.
4. Installs the project and `psutil` into that virtualenv.
5. Creates a `command-center` launcher at `~/.local/bin/command-center`
   and makes sure `~/.local/bin` is on your `PATH`.
6. Writes a default `~/.config/r510-command-center/config.toml` if one
   doesn't already exist (existing configs are never overwritten).
7. Optionally offers to enable TTY1 autostart (see below).

It's safe to run more than once -- re-running reuses the existing
virtualenv and never overwrites your config.

## Manual launch

Once installed:

```bash
command-center
```

Or, to run directly from a checked-out repo without installing anything
(useful for development):

```bash
./command-center
```

## TTY1 autostart

If you opted in during install, a small guarded block is appended to
`~/.bashrc`:

```bash
# BEGIN r510-command-center TTY1 autostart
if [[ $- == *i* ]] \
  && [[ "$(tty)" == "/dev/tty1" ]] \
  && [[ -z "${SSH_CONNECTION:-}" ]] \
  && [[ -n "${TERM:-}" ]] \
  && command -v command-center >/dev/null 2>&1 \
  && [[ -z "${R510_DASHBOARD_RUNNING:-}" ]]; then
  export R510_DASHBOARD_RUNNING=1
  command-center
fi
# END r510-command-center TTY1 autostart
```

It only launches the dashboard when **all** of these hold:

- the shell is interactive,
- the controlling terminal is exactly `/dev/tty1` (the physical console),
- there is no active SSH connection,
- `TERM` is set, and
- `command-center` is on `PATH`.

The `R510_DASHBOARD_RUNNING` guard prevents it from ever re-launching
itself in a loop. When you quit the dashboard (`Q`), you're dropped back
to a normal shell prompt on tty1 -- it does not re-launch automatically.

**Enable manually:** run `./install.sh` again and answer `y` to the
autostart prompt, or paste the block above into `~/.bashrc` yourself.

**Disable:** remove the block between the `BEGIN`/`END` markers in
`~/.bashrc`, or run `./uninstall.sh`, which removes it for you.

### SSH behavior

Because the guard checks `SSH_CONNECTION` and requires the terminal to be
exactly `/dev/tty1`, the dashboard **never** autostarts on an SSH session
-- SSH logins always land on a normal shell prompt. You can still launch
it manually over SSH by running `command-center` yourself.

## OpenCode integration

Pressing `O` creates or attaches a `tmux` session (default name
`opencode`, configurable) running your OpenCode executable, equivalent
to:

```bash
tmux new-session -A -s opencode <opencode-executable>
```

The executable is located in this order:

1. `opencode_path` in `config.toml`, if set.
2. `opencode` on `PATH`.
3. `~/.opencode/bin/opencode`.
4. `~/.local/bin/opencode`.

If OpenCode or `tmux` isn't found, you'll see a message explaining what's
missing instead of a crash. Detaching from the session (`Ctrl-b d`) or
exiting OpenCode returns you straight to the dashboard.

## Ollama integration

Ollama's status is checked using **two** independent signals so the
dashboard can tell "stopped" apart from "running but unhealthy":

- `systemctl is-active ollama`
- The Ollama HTTP API on `http://<ollama_host>:<ollama_port>` (`/api/tags`
  for installed models, `/api/ps` for what's currently loaded)

| State     | Meaning                                                              |
|-----------|-----------------------------------------------------------------------|
| `OFFLINE` | The `ollama` service is confirmed not running.                       |
| `ERROR`   | The service is active, but the HTTP API can't be reached.            |
| `BUSY`    | The API is reachable and a model is currently loaded.                |
| `IDLE`    | The API is reachable, nothing is loaded, and no models are installed.|
| `ONLINE`  | The API is reachable, nothing is loaded, but models are installed.   |

All HTTP calls use a short timeout (well under a second) so an
unreachable or hung daemon never freezes the dashboard's render loop.

- `M` lists installed models (and marks the currently loaded one).
- `L` shows recent logs via `journalctl -u ollama`, with scrolling.
- `R` restarts the service via `sudo systemctl restart ollama`, after an
  explicit `y/N` confirmation. This uses your normal `sudo`
  authentication -- the installer never touches `sudoers`, and Ollama is
  never exposed beyond `localhost` by this tool.

## Configuration

Fully optional. Create `~/.config/r510-command-center/config.toml` (the
installer does this for you with sensible defaults):

```toml
title = "R510 ORBITAL AI COMMAND CENTER"

ollama_host = "127.0.0.1"
ollama_port = 11434

# Leave blank to auto-detect: PATH, then ~/.opencode/bin, then ~/.local/bin
opencode_path = ""

tmux_session = "opencode"

refresh_interval = 1.0
animation_speed = 1.0

color_mode = true
reduced_motion = false
ascii_only = false

default_screen = "dashboard"
autostart_tty1 = false
```

| Key                | Default                          | Description                                              |
|--------------------|-----------------------------------|-----------------------------------------------------------|
| `title`            | `R510 ORBITAL AI COMMAND CENTER` | Dashboard title shown in the header.                      |
| `ollama_host`      | `127.0.0.1`                      | Host for the Ollama HTTP API.                              |
| `ollama_port`      | `11434`                          | Port for the Ollama HTTP API.                               |
| `opencode_path`    | *(auto-detect)*                  | Explicit path to the OpenCode executable.                  |
| `tmux_session`     | `opencode`                       | tmux session name used for OpenCode.                        |
| `refresh_interval` | `1.0`                            | Reserved for telemetry refresh pacing.                     |
| `animation_speed`  | `1.0`                            | Reserved for animation pacing.                              |
| `color_mode`       | `true`                           | Start with color enabled (toggle at runtime with `C`).      |
| `reduced_motion`   | `false`                          | Start in reduced-motion mode (fewer moving parts).          |
| `ascii_only`       | `false`                          | Start in ASCII-only mode (no Unicode box-drawing/symbols).  |
| `default_screen`   | `dashboard`                      | Reserved for a future multi-screen default.                 |
| `autostart_tty1`   | `false`                          | Informational; the actual hook is installed by `install.sh`.|

Missing, empty, or malformed config files always fall back to defaults --
the dashboard never fails to start because of a bad config.

## Keyboard controls

| Key      | Action                                                        |
|----------|----------------------------------------------------------------|
| `O`      | Open or attach the OpenCode tmux session                     |
| `S`      | Open an interactive Bash shell                                |
| `L`      | View recent Ollama logs (`journalctl -u ollama`, scrollable)  |
| `M`      | View installed Ollama models                                  |
| `R`      | Restart the Ollama service (confirmation required)            |
| `T`      | Open `htop`                                                    |
| `N`      | View network information                                       |
| `P`      | Pause / resume the orbital animation                           |
| `C`      | Toggle color mode                                              |
| `A`      | Toggle ASCII-only mode                                         |
| `H`, `?` | Open the help screen                                           |
| `Q`      | Exit the dashboard                                             |
| `ESC`    | Return from a secondary screen                                 |

## Troubleshooting

- **"terminal too small"** -- resize your terminal to at least 64 columns
  by 20 rows. The dashboard shows a static message instead of drawing a
  broken layout.
- **Animation looks garbled / wrong characters** -- press `A` to switch
  to ASCII-only mode, or set `ascii_only = true` in `config.toml`. Some
  serial consoles and minimal TTY fonts don't have the Unicode
  box-drawing or symbol glyphs used by default.
- **`OLLAMA ERROR`** -- the `ollama` service is active but not answering
  its HTTP API. Check `journalctl -u ollama` (press `L`) or run
  `systemctl status ollama` yourself.
- **`OPENCODE MISSING`** -- OpenCode wasn't found via `PATH`,
  `~/.opencode/bin`, or `~/.local/bin`. Install it, or set
  `opencode_path` explicitly in `config.toml`.
- **`command-center: command not found`** -- open a new shell (or `source
  ~/.bashrc`) so the `PATH` update from `install.sh` takes effect.
- **No temperature shown** -- not every system exposes sensors `psutil`
  can read (this is common in VMs and some servers); the dashboard shows
  `N/A` instead of guessing.
- **Restart requires a password every time** -- that's your normal `sudo`
  policy; this tool never modifies `sudoers` or caches credentials.

## Uninstallation

```bash
./uninstall.sh
```

Removes the installed virtualenv, the `command-center` launcher, and any
TTY1 autostart block added by `install.sh`. You'll be asked separately
whether to remove your `config.toml`. System packages (Python, tmux,
htop, ...) are never touched.

## Development and testing

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

python3 -m compileall command_center tests
pytest
```

The test suite covers telemetry formatting and progress-bar math, Ollama
API parsing and state-machine logic (including "API unreachable" and
"systemctl unavailable" paths), OpenCode executable detection, safe
`tmux`/subprocess command construction, and configuration defaults --
plus a non-interactive smoke test that initializes every major component
(config, telemetry, Ollama status, animation rendering) without ever
calling into `curses`.

Project layout:

```
r510-command-center/
├── command_center/       # application package
│   ├── app.py             # curses main loop, layout, key handling
│   ├── animation.py       # orbital scene generator (pure functions)
│   ├── telemetry.py       # system stats + formatting
│   ├── ollama.py          # systemctl + HTTP API status detection
│   ├── screens.py         # help/logs/models/network secondary screens
│   ├── actions.py         # opencode/shell/htop/restart actions
│   ├── config.py          # config.toml loading, OpenCode detection
│   └── rendering.py       # curses-safe drawing primitives
├── assets/                # reference ASCII art (not loaded at runtime)
├── tests/                 # pytest suite
├── command-center         # dev-convenience launcher (no install needed)
├── install.sh / uninstall.sh
├── pyproject.toml / requirements*.txt
└── README.md
```

## License

MIT -- see [LICENSE](LICENSE).
