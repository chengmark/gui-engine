# gui-engine

Windows automation toolkit with a control-panel GUI, JSON script runner, input recorder, and optional background hooks (volume, download limiting, and more).

## Features

- **GUI control panel** — browse scripts, load/toggle/stop, live cursor RGB readout, PID override for download limiting
- **JSON automation scripts** — keyboard, mouse, delays, imports, and subprocess subroutines
- **Background scripts** — persistent hooks (e.g. toggle mute on a mouse button) toggled from the GUI **BG** column
- **Input recorder** — capture keyboard/mouse and save as JSON scripts
- **Download limiter** — per-process bandwidth cap via `limit_download.py` (requires admin)
- **Modular runner** — one handler file per command under `handlers/`

## Requirements

- **Windows** (mouse/volume/download features are Windows-specific)
- Python 3.9+
- Administrator privileges for some features (global hotkeys, WinDivert packet capture)

## Installation

```bash
pip install -r requirements.txt
```

### JSON scripts (local only on `main`)

Automation JSON files live on the separate **`scripts`** branch so they are not pushed with application code on **`main`**. The `scripts/` folder is listed in `.gitignore` on `main`.

After cloning or switching to `main`, pull scripts into your working tree (not staged, not committed):

```powershell
.\sync_scripts.ps1
```

To commit or push script changes, use the `scripts` branch. On `main`, enable the repo hooks once so `scripts/` cannot be committed or pushed by mistake:

```powershell
.\setup_hooks.ps1
```

### Windows exe releases

Pushing to **`main`** (or a version tag like `v1.0.0`) runs GitHub Actions, which builds `gui-engine.exe` and publishes **[Releases](https://github.com/chengmark/gui-engine/releases)** with `gui-engine-windows.zip`.

- Push to `main` → updates the **Latest** release  
- Push tag `v*` → creates a versioned release  

```powershell
git push origin main
# or: git tag v1.0.0 && git push origin v1.0.0
```

Rebuild locally anytime with `.\build_exe.ps1`.

## Quick start

### GUI (recommended)

```bash
python gui.py
```

1. Select a script from the list
2. Optionally set **PID** (for scripts that use `limit_download.py`)
3. Click **Load Script**
4. Press the script’s toggle key (default **Home**) or use **Toggle Script**
5. **Shift+Esc** unloads the active script; **Stop Script** also unloads

Scripts with a `"background"` field show a **BG** checkbox. Check to enable background hooks; uncheck to disable.

Toggle on/off shows a toast on the monitor (bottom-right).

### CLI runner

```bash
python run.py scripts/script.json
```

| Key | Action |
|-----|--------|
| Script toggle key (default `home`) | Start/stop automation loop |
| **Shift+Esc** | Unload script (stop automation) |
| **Ctrl+Esc** | Exit runner |

### Recorder

```bash
python record.py -o scripts/my_script.json
```

| Key | Action |
|-----|--------|
| **F9** | Start recording |
| **F10** | Stop and save |
| **Ctrl+Esc** | Exit without saving |

### Cursor helper

```bash
python coord_helper.py
```

Floating window with live cursor position and pixel color. **Ctrl+Esc** to close.

## Project layout

```
gui-engine/
├── gui.py              # Control panel entry point
├── gui/
│   ├── services.py     # Lazy loading of run / record / coord_helper
│   └── toast.py        # On-screen toggle notifications
├── run.py              # CLI entry point (re-exports runner)
├── runner/             # Script engine, state, subroutines, volume, triggers
├── handlers/           # One module per script command
├── scripts/            # JSON automation scripts
├── record.py           # Input recorder
├── limit_download.py   # Process download bandwidth limiter
└── coord_helper.py     # Cursor position / color overlay
```

The GUI does not hard-import `run.py`, `record.py`, or `coord_helper.py`. Those services load on first use; if a module is missing, the GUI still starts and prints an error when that feature is used.

## Script format

Scripts are JSON files in `scripts/`.

```json
{
    "description": "My script",
    "toggle": "home",
    "scripts": [],
    "initial": [],
    "loop": [],
    "background": []
}
```

| Field | Description |
|-------|-------------|
| `description` | Display name in the GUI |
| `toggle` | Global hotkey to start/stop the loop (default `home`) |
| `initial` | Steps run once each time automation is turned **on** |
| `loop` | Steps repeated while automation is **on** |
| `steps` | Alias for `loop` (legacy) |
| `scripts` | Subprocess subroutines started when the script loads |
| `background` | Steps that register persistent hooks (GUI **BG** column) |

Each step:

```json
{
    "command": "KeyPress",
    "args": ["1", 1]
}
```

### Subroutines

```json
"scripts": [
    {
        "file": "limit_download.py",
        "args": [12345, "5 KB"]
    }
]
```

`.py` files resolve from the project root; `.json` files resolve relative to the script’s folder.

## Commands

| Command | Args | Description |
|---------|------|-------------|
| `Delay` | `[ms]` | Wait (interruptible when automation stops) |
| `KeyPress` | `[key, times?]` | Press and release; `"1111"` presses `1` four times |
| `KeyDown` | `[key, times?]` | Hold key down |
| `KeyUp` | `[key, times?]` | Release key |
| `KeyHoldAndRelease` | `[key, seconds]` | Press, hold, release |
| `MouseClick` | `[button, times?]` | Click at current cursor (`left`, `right`, `middle`) |
| `MouseMove` | `[dx, dy?]` | Relative mouse move |
| `MouseMoveTo` | `[x, y]` | Absolute move |
| `ClickOn` | `[x, y, button?]` | Move to coordinates and click |
| `ImportScript` | `[filename]` | Run another script’s steps inline |
| `Script` | `[file, ...args]` | Start a subroutine process |
| `SetVolume` | `[trigger, level]` | On trigger, set master volume `0.0`–`1.0` |
| `ToggleMute` | `[trigger]` | On trigger, toggle mute; restore previous volume when off |

**Triggers** for volume commands: keyboard keys (`home`, `f9`, …) or mouse buttons (`MB4`, `MB5`, `Left`, `Right`, `Middle`).

### Example: background mute toggle

`scripts/mute.json`:

```json
{
    "description": "Toggle Mute",
    "background": [
        {
            "command": "ToggleMute",
            "args": ["MB5"]
        }
    ]
}
```

Enable via the **BG** checkbox in the GUI. **MB5** toggles mute; volume is restored when toggled off or when the background script is unloaded.

## Download limiting

```bash
python limit_download.py <pid> "5 MB"
```

When used as a subroutine, the GUI **PID** field overrides the first argument. Requires admin (WinDivert). Cycles limit / resume when toggled from the parent script.

## License

No license file is included yet. Add one if you plan to distribute this project.
