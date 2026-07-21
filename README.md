# r510-command-center

Build a complete production-ready Linux TTY dashboard project named:

r510-command-center

The target system is an Ubuntu Server 24.04 Dell PowerEdge R510 running directly on TTY1 with no desktop environment.

The project should feel like a retro NASA mission-control terminal combined with modern Starlink-style space animations.

Do not only describe the solution. Actually create every project file, implement the application, test it, and prepare it for GitHub.

PROJECT GOAL

Create a full-screen animated ASCII command center that runs directly on Linux TTY1.

The dashboard should act as the visual home screen for a local AI server running:

- Ubuntu Server 24.04
- Ollama
- OpenCode
- tmux
- Local AI models
- SSH access

VISUAL DIRECTION

The interface should look cinematic, fun, futuristic, and space-themed.

Visual inspiration:

- Starlink orbital animations
- NASA mission control
- Retro computer terminals
- Satellite ground-station interfaces
- Sci-fi spacecraft telemetry

The interface must remain attractive in a normal Linux text console.

Use Unicode box-drawing characters where safely supported, but include an ASCII fallback mode.

MAIN ANIMATION

The upper portion of the screen should contain an animated orbital scene.

Include:

- An ASCII Earth positioned on the left
- An AI moon, orbital AI core, or satellite station positioned on the right
- Animated data packets traveling between Earth and the AI core
- Moving signal pulses
- Slowly twinkling stars
- Occasional moving satellite
- Orbital paths or connection arcs
- Small randomized space particles
- A subtle animated scanline or signal effect
- Status text such as UPLINK ESTABLISHED or PROCESSING

Animation must:

- Run smoothly without excessive flicker
- Use curses or equivalent terminal-safe rendering
- Adapt to terminal resizing
- Avoid excessive CPU usage
- Pause or simplify when the terminal is too small
- Provide a reduced-motion mode

TELEMETRY

The lower portion should display live server telemetry.

Show:

- Server hostname
- Local IPv4 address
- Uptime
- CPU usage
- Per-socket or overall CPU activity when practical
- RAM used and total
- Swap usage
- Root filesystem usage
- System load averages
- Process count
- Logged-in users
- Server temperature when available
- Network receive and transmit rates
- Ollama service status
- Ollama API status
- Currently loaded Ollama model
- Installed Ollama models
- OpenCode installation status
- OpenCode tmux session status
- Current date and time

Use clear progress bars for:

- CPU
- RAM
- Swap
- Disk

OLLAMA STATES

Display Ollama as one of:

- ONLINE
- BUSY
- IDLE
- OFFLINE
- ERROR

Determine status using both:

- systemctl
- Ollama HTTP API on localhost port 11434

Use sensible timeouts so a failed API call does not freeze the dashboard.

KEYBOARD CONTROLS

Implement these hotkeys:

O
Open or attach to a tmux session named opencode.

If the session does not exist, create it and launch OpenCode.

When OpenCode exits or the user detaches, return to the dashboard.

S
Open an interactive Bash shell.

When the shell exits, return to the dashboard.

L
Display recent Ollama service logs.

Use:

journalctl -u ollama

Provide scrolling and an easy key to return.

M
Display installed Ollama models.

R
Restart the Ollama systemd service.

Require confirmation before restarting.

T
Open htop when installed.

If htop is unavailable, show a helpful message.

N
Display network information.

H or ?
Open a help screen.

P
Pause and resume animation.

C
Toggle color mode.

A
Toggle ASCII-only mode.

Q
Exit the dashboard.

ESC
Return from secondary screens.

SECURITY

Do not run the main dashboard as root.

Only use sudo for actions that require it, such as restarting Ollama.

The restart command should work with normal sudo authentication.

Do not automatically modify sudoers.

Do not expose Ollama publicly.

Do not execute arbitrary input from telemetry values.

ARCHITECTURE

Use Python 3.

Prefer the Python standard library.

The only acceptable mandatory external dependency is psutil.

Use curses for the interface.

Organize the project cleanly, for example:

r510-command-center/
├── command_center/
│   ├── __init__.py
│   ├── app.py
│   ├── animation.py
│   ├── telemetry.py
│   ├── ollama.py
│   ├── screens.py
│   ├── actions.py
│   ├── config.py
│   └── rendering.py
├── assets/
│   └── optional ASCII art files
├── tests/
│   ├── test_telemetry.py
│   ├── test_ollama.py
│   └── test_config.py
├── command-center
├── install.sh
├── uninstall.sh
├── requirements.txt
├── pyproject.toml
├── README.md
├── LICENSE
└── .gitignore

The application entry command should be:

command-center

CONFIGURATION

Support a configuration file at:

~/.config/r510-command-center/config.toml

Allow configuration of:

- Dashboard title
- Ollama host
- Ollama port
- OpenCode executable path
- tmux session name
- Refresh interval
- Animation speed
- Color mode
- Reduced-motion mode
- ASCII-only mode
- Default screen
- Whether dashboard launches automatically on TTY1

Provide sensible defaults.

Do not require the configuration file to exist.

OPENCODE PATH

Detect OpenCode using these locations:

- command -v opencode
- ~/.opencode/bin/opencode
- ~/.local/bin/opencode

The OpenCode action should use the first valid executable found.

TMUX BEHAVIOR

The OpenCode action should create or attach using behavior equivalent to:

tmux new-session -A -s opencode <opencode executable>

Handle quoting safely.

INSTALLER

Create an install.sh script that:

- Verifies Ubuntu or compatible Linux
- Verifies Python 3
- Installs python3-venv, python3-pip, tmux, curl, and htop when apt is available
- Creates an isolated virtual environment under ~/.local/share/r510-command-center/venv
- Installs the project and psutil
- Creates a launcher at ~/.local/bin/command-center
- Ensures ~/.local/bin is available in PATH
- Creates the default config when absent
- Offers an optional TTY1 autostart configuration
- Does not overwrite existing user configuration without permission
- Is safe to run more than once

UNINSTALLER

Create uninstall.sh that:

- Removes installed application files
- Removes the launcher
- Removes optional autostart configuration created by install.sh
- Preserves the user config unless explicitly requested
- Does not remove Python or system packages

TTY1 AUTOSTART

Support launching the dashboard automatically on the physical server monitor.

Prefer a safe user-level approach when possible.

A valid approach is adding logic to the user’s Bash profile that only runs when:

- The shell is interactive
- The active terminal is /dev/tty1
- The user is not connected through SSH
- The dashboard executable exists
- The dashboard is not already running

The guard should resemble:

- tty equals /dev/tty1
- SSH_CONNECTION is empty
- TERM is valid
- command-center is available

Do not launch it for SSH sessions.

Do not create an infinite login loop.

When the dashboard exits, leave the user at a normal shell prompt.

Include clear README instructions for enabling and disabling TTY1 autostart manually.

ERROR HANDLING

The application must not crash when:

- Ollama is stopped
- Ollama is unreachable
- systemctl is unavailable
- temperature sensors are unavailable
- psutil cannot read a metric
- the terminal is resized
- the terminal is too small
- Unicode is unsupported
- OpenCode is missing
- tmux is missing
- htop is missing
- network interfaces change
- the system has no active IPv4 address

Show useful status messages instead.

TESTING

Create unit tests for:

- Telemetry formatting
- Progress bar calculations
- Ollama API parsing
- Ollama unavailable behavior
- OpenCode executable detection
- Configuration defaults
- Safe command construction

Run:

python3 -m compileall
pytest

Also run a non-interactive smoke test that initializes the major components without entering curses.

QUALITY REQUIREMENTS

- Use type hints
- Use dataclasses where useful
- Keep modules focused
- Avoid giant monolithic files
- Include docstrings for important public functions
- Avoid global mutable state
- Use subprocess safely without shell=True where possible
- Keep network requests asynchronous or short-timeout so rendering does not freeze
- Cache slower telemetry values
- Keep the main animation loop responsive
- Target approximately 5–10 frames per second
- Avoid heavy CPU consumption

README

The README must include:

- Screenshot-style ASCII preview
- Feature list
- Requirements
- Installation
- Manual launch
- TTY1 autostart setup
- SSH behavior
- OpenCode integration
- Ollama integration
- Configuration reference
- Keyboard controls
- Troubleshooting
- Uninstallation
- Development and testing instructions

DESIGN DETAILS

Use a layout similar to:

┌──────────────────────────────────────────────────────────────────────────────┐
│                       R510 ORBITAL AI COMMAND CENTER                        │
│                    NODE ONLINE · UPLINK ESTABLISHED                         │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│      ASCII EARTH                   animated uplink             AI CORE        │
│                                                                              │
│             packets, stars, satellites, signal pulses                        │
│                                                                              │
├────────────────────────────── SYSTEM TELEMETRY ───────────────────────────────┤
│ CPU   [████████░░░░░░░░░░]  RAM   [██████░░░░░░░░░░░░]                     │
│ DISK  [████░░░░░░░░░░░░░░]  TEMP  40°C                                     │
│                                                                              │
│ OLLAMA     ONLINE     MODEL       gemma4:12b                                 │
│ OPENCODE   READY      TMUX        ATTACHED                                   │
│ IP         192.168.0.169          UPTIME      3h 22m                         │
├──────────────────────────────────────────────────────────────────────────────┤
│ [O] OpenCode  [S] Shell  [L] Logs  [R] Restart  [H] Help  [Q] Exit          │
└──────────────────────────────────────────────────────────────────────────────┘

Do not hardcode the hostname, IP, model, or temperature shown in this example.

GIT PREPARATION

Initialize the project as a clean Git repository if it is not already one.

Create meaningful commits rather than one giant unstructured commit.

Recommended commits:

1. Initialize Python project and telemetry foundation
2. Add animated curses dashboard
3. Add Ollama and OpenCode integrations
4. Add installer and TTY1 autostart
5. Add tests and documentation

At the end:

- Show the final file tree
- Show test results
- Show installation commands
- Show the exact commands needed to push to GitHub
- Do not claim tests passed unless they were actually run
