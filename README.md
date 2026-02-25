# PortPilot

**SSH Port Forward Manager** — A Windows desktop app to manage SSH port-forward tunnels using native OpenSSH (`ssh.exe`).

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-green.svg)](https://www.python.org/downloads/)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

---

## Download

**Pre-built executable** (no Python required):

- **[Releases](https://github.com/mgot6/PortPilot/releases)** — Download `PortPilot.exe` or `PortPilot-Setup-1.0.0.exe` (installer)

---

## Features

| Feature | Description |
|---------|-------------|
| **Host management** | Add, edit, delete SSH hosts (name, hostname, port, username, identity file, extra args, keepalive) |
| **Tunnel types** | Local (-L), Remote (-R), Dynamic SOCKS (-D) |
| **Tunnel control** | Start, stop, restart per tunnel; Start All / Stop All |
| **Background mode** | Optional per-run toggle to keep tunnels running after app close |
| **Live logs** | Per-tunnel log viewer with copy and open-in-editor |
| **System tray** | Minimize to tray, Start All, Stop All, Quit |
| **SQLite persistence** | All data stored in `%APPDATA%\PortPilot\` |

---

## Requirements

- **Windows 10/11**
- **OpenSSH for Windows** — Install via Settings → Apps → Optional features → OpenSSH Client

---

## Quick Start (from source)

```powershell
# Clone and enter project
git clone https://github.com/mgot6/PortPilot.git
cd PortPilot

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install and run
pip install -r requirements.txt
python main.py
```

---

## Building the Executable

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt pyinstaller Pillow

# Optional: generate icon if missing
python scripts/build_icon.py

# Build
pyinstaller portpilot.spec
```

Output: `dist/PortPilot.exe`

**Or use the build script:**

```powershell
.\build.ps1
```

---

## Installer (Inno Setup)

1. Install [Inno Setup](https://jrsoftware.org/isinfo.php)
2. Build the exe: `pyinstaller portpilot.spec`
3. Run: `iscc installer.iss`
4. Installer output: `dist/PortPilot-Setup-1.0.0.exe`

---

## Data Locations

| Item | Path |
|------|------|
| Database | `%APPDATA%\PortPilot\portpilot.db` |
| Logs | `%APPDATA%\PortPilot\logs\` |

---

## Project Structure

```
PortPilot/
├── main.py              # Entry point
├── requirements.txt
├── portpilot.spec       # PyInstaller spec
├── installer.iss        # Inno Setup script
├── build.ps1            # One-click build script
├── assets/
│   └── icon.ico        # App icon
├── scripts/
│   └── build_icon.py   # Icon generator (requires Pillow)
└── src/portpilot/
    ├── app.py          # Application setup
    ├── core/           # DB, models, SSH, process management
    └── ui/             # Main window, dialogs, widgets
```

---

## Creating a Release

1. Push your code to GitHub
2. Replace `mgot6` in this README with your GitHub username
3. Create and push a tag: `git tag v1.0.0 && git push origin v1.0.0`
4. The [Release workflow](.github/workflows/release.yml) will build the exe and attach it to the new release

---

## License

MIT — see [LICENSE](LICENSE).
