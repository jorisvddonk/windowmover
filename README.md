# Window Mover

Move windows between monitors on KDE Plasma without dragging, walking to another
screen, or remembering keyboard shortcuts.

It ships with three frontends:

- **GUI** — pick a window and a monitor, then move, maximize, or fullscreen it.
- **TUI** — the same thing in the terminal with arrow keys.
- **CLI** — scriptable commands for panels, shortcuts, or automation.

Window Mover uses KWin's own scripting API (`sendClientToScreen`) through D-Bus,
so moves work on both X11 and Wayland sessions. Window discovery uses `wmctrl`,
which sees X11 and XWayland windows (most games).

## Requirements

- KDE Plasma 6 (X11 or Wayland)
- `kscreen-doctor` (Plasma)
- `wmctrl` (for listing X11/XWayland windows)
- `gdbus` (GLib)
- `uv` for running the PEP 723 scripts
- Python 3.10+
- `PySide6` for the GUI (installed automatically by `uv` on first run)

On Fedora Kinoite, `wmctrl` can be installed to `~/.local/bin` if it is not in
the base image.

## Install

```sh
git clone https://github.com/jorisvddonk/windowmover.git ~/projects/windowmover
cd ~/projects/windowmover
./install.sh
```

`install.sh` symlinks the launchers into `~/.local/bin` and copies the desktop
entries into `~/.local/share/applications`.

You can also run everything straight from the checkout:

```sh
./scripts/windowmover list
./scripts/windowmover tui
./scripts/windowmover-gui
```

### PEP 723

Every executable in `scripts/` is a standalone
[PEP 723](https://peps.python.org/pep-0723/) script. `uv` reads the inline
metadata and creates an isolated environment on demand:

```sh
uv run --script scripts/windowmover list
uv run --script scripts/windowmover-gui
```

The first GUI run downloads PySide6 into the uv cache and can take a minute or
two. Later runs start quickly.

## Usage

### GUI

```sh
windowmover-gui
```

The window opens on the monitor under the mouse cursor. Select a window and a
monitor, then choose **Move**, **Move + Fullscreen**, **Maximize**, or
**Set default screen** (makes that monitor the primary screen, so new games
open there).

### TUI

```sh
windowmover tui
```

| Key | Action |
| --- | --- |
| `Tab` / `h` / `l` | Switch pane |
| `j` / `k` / arrows | Select |
| `Enter` | Move selected window to selected monitor |
| `f` | Move + fullscreen |
| `m` | Move + maximize |
| `c` | Center window on monitor |
| `t` / `T` | Tile window left / right half |
| `n` | Minimize window |
| `v` | Toggle window fullscreen |
| `p` | Set selected monitor as default screen |
| `o` / `Enter` on Outputs | Toggle selected output on/off |
| `r` | Refresh |
| `q` | Quit |

### CLI

```sh
windowmover list
windowmover move --to DP-4 --class steam_app_2605790 --fullscreen
windowmover move --to DP-3 --title "Deep Rock"
windowmover move --to DP-4 --title "Firefox" --tile left
windowmover move --to DP-4 --title "Firefox" --center
windowmover move --to DP-4 --title "Firefox" --geometry 1600x900 --pos 300,200
windowmover primary DP-4
windowmover output list
windowmover output off HDMI-A-3
windowmover output on HDMI-A-3
windowmover output scale HDMI-A-3 1.15
windowmover output mode DP-4 3440x1440@144
windowmover output pos DP-3 0,0
windowmover output rotate DP-3 left
windowmover win minimize --title "Firefox"
windowmover win full-toggle --class steam_app_2321470
windowmover win opacity 90 --title "Discord"
windowmover layout save gaming
windowmover layout load gaming
```

The GUI has the same powers: an Outputs column (double-click toggles),
plus Center / Tile Left / Tile Right / Minimize / Fullscreen toggle /
Raise / Close window buttons.

Legacy flags are accepted too:

```sh
windowmover --list
windowmover --to DP-4 --class steam_app_2605790 --fullscreen
```

### Desktop launchers

`desktop/` contains:

- `windowmover.desktop` — the GUI
- `move-game-asus.desktop`
- `move-game-msi.desktop`
- `move-game-tv.desktop`

Pin one of the **Move Game to …** launchers to a panel for one-click moves.

## How it works

1. `wmctrl -lxG` lists X11/XWayland windows and their classes.
2. `kscreen-doctor -j` lists enabled monitors; EDID data gives the model name.
3. A temporary KWin script is generated and loaded over D-Bus. It calls
   `workspace.sendClientToScreen(window, output)` and optionally toggles
   fullscreen or maximize.

Because the move happens inside KWin, it also works when the target window is
fullscreen on another monitor.

## Limitations

- Native Wayland windows are not listed by `wmctrl`; use the window class/title
  path if you already know it, or move them with KWin's own window menu.
- The GUI installs PySide6 via `uv` on first launch.
- Monitor names (`DP-3`, `DP-4`, `HDMI-A-3`) are specific to the current setup;
  use `windowmover list` to see yours.

## Development

```sh
uv run --script scripts/windowmover --help
uv run --script scripts/windowmover list
uv run --script scripts/windowmover-tui
```

The Python package lives in `src/windowmover/` and has no dependencies for the
CLI/TUI. The GUI is an optional extra (`pip install .[gui]`).

## License

MIT. See `LICENSE`.
