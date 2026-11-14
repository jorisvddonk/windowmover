import argparse
import os
import shutil
import sys
from pathlib import Path

from . import core

HELP = """usage: windowmover [command] [options]

Commands:
  list                     List monitors and windows
  move --to MONITOR        Move a window to a monitor
  tui                      Open the terminal UI
  gui                      Open the graphical UI

Legacy options:
  --list
  --to MONITOR --class CLASS | --title TITLE [--fullscreen] [--maximize]

Examples:
  windowmover list
  windowmover move --to DP-4 --class steam_app_2605790 --fullscreen
  windowmover tui
  windowmover gui
"""


def has_display():
    return bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


def gui_script():
    executable = shutil.which("windowmover-gui")
    if executable:
        return executable
    candidate = Path(__file__).resolve().parent.parent.parent / "scripts" / "windowmover-gui"
    if candidate.exists():
        return str(candidate)
    return None


def run_gui(argv):
    script = gui_script()
    if script:
        os.execv(script, [script] + list(argv))
    try:
        from .gui import main as gui_main
    except Exception as exc:
        print(f"GUI unavailable: {exc}", file=sys.stderr)
        return 1
    return gui_main(argv)


def cmd_list():
    for monitor in core.get_monitors():
        print(f"MONITOR {monitor['name']:<10} {monitor['label']}")
    for window in core.get_windows():
        print(f"WINDOW  {window['id']:<10} {window['class_full']:<40} {window['title']}")
    return 0


def move_parser():
    parser = argparse.ArgumentParser(prog="windowmover move")
    parser.add_argument("--to", required=True, metavar="MONITOR")
    parser.add_argument("--class", dest="window_class", metavar="CLASS")
    parser.add_argument("--title", metavar="TITLE")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--maximize", action="store_true")
    return parser


def cmd_move(args):
    monitors = core.get_monitors()
    monitor = core.find_monitor(monitors, args.to)
    if not monitor:
        print(f"Unknown monitor: {args.to}", file=sys.stderr)
        return 1
    window = core.find_window(core.get_windows(), args.window_class, args.title)
    if not window:
        print("No matching window found.", file=sys.stderr)
        return 1
    core.move_window(window, monitor, args.fullscreen, args.maximize)
    print(f'Moved "{window["title"]}" to {monitor["name"]}.')
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv:
        command = argv[0]
        if command in ("list", "ls"):
            return cmd_list()
        if command == "move":
            return cmd_move(move_parser().parse_args(argv[1:]))
        if command == "tui":
            from .tui import main as tui_main
            return tui_main(argv[1:])
        if command == "gui":
            return run_gui(argv[1:])
        if command in ("-h", "--help", "help"):
            print(HELP)
            return 0
        if not command.startswith("-"):
            print(f"Unknown command: {command}", file=sys.stderr)
            print(HELP, file=sys.stderr)
            return 2

    legacy = argparse.ArgumentParser(prog="windowmover", add_help=False)
    legacy.add_argument("-h", "--help", action="store_true")
    legacy.add_argument("--list", action="store_true")
    legacy.add_argument("--to", metavar="MONITOR")
    legacy.add_argument("--class", dest="window_class")
    legacy.add_argument("--title")
    legacy.add_argument("--fullscreen", action="store_true")
    legacy.add_argument("--maximize", action="store_true")
    legacy.add_argument("--tui", action="store_true")
    legacy.add_argument("--gui", action="store_true")
    args = legacy.parse_args(argv)

    if args.help:
        print(HELP)
        return 0
    if args.list:
        return cmd_list()
    if args.tui:
        from .tui import main as tui_main
        return tui_main([])
    if args.to:
        return cmd_move(args)
    if args.gui:
        return run_gui([])
    if has_display():
        return run_gui([])
    from .tui import main as tui_main
    return tui_main([])
