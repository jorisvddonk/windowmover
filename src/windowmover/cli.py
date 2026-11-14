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
  primary MONITOR          Set MONITOR as the default (primary) screen
  output list              List all outputs (including disabled)
  output on OUTPUT         Turn an output on
  output off OUTPUT        Turn an output off
  output scale OUTPUT S    Set an output's scale (e.g. 1.15)
  output mode OUTPUT M     Set an output's mode (e.g. 3440x1440@144)
  output pos OUTPUT X Y   Position an output in the layout
  output rotate OUTPUT R  Rotate (none, left, right, inverted)
  win ACTION [--class C | --title T]
                          Window ops: minimize unminimize maximize unmaximize
                          full-on full-off full-toggle above-on above-off
                          below-on below-off sticky-on sticky-off
                          shade-on shade-off raise close opacity PCT
  layout save NAME         Save window layout
  layout load NAME         Restore window layout
  layout list              List saved layouts
  tui                      Open the terminal UI
  gui                      Open the graphical UI

Legacy flags:
  --list
  --to MONITOR --class CLASS | --title TITLE [--fullscreen] [--maximize]

Examples:
  windowmover list
  windowmover move --to DP-4 --class steam_app_2605790 --fullscreen
  windowmover primary DP-4
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
    parser.add_argument("--geometry", metavar="WxH", help="Resize to WIDTHxHEIGHT")
    parser.add_argument("--pos", metavar="X,Y", help="Move to X,Y position")
    parser.add_argument("--tile", metavar="AREA",
                        help="Tile: left right top bottom topleft topright "
                             "bottomleft bottomright center full")
    parser.add_argument("--center", action="store_true", help="Center on monitor")
    return parser


def cmd_primary(args):
    monitors = core.get_monitors()
    monitor = core.find_monitor(monitors, args.monitor)
    if not monitor:
        print(f"Unknown monitor: {args.monitor}", file=sys.stderr)
        return 1
    core.set_primary(monitor)
    print(f'Set default screen to {monitor["name"]}.')
    return 0


def primary_parser():
    parser = argparse.ArgumentParser(prog="windowmover primary")
    parser.add_argument("monitor", metavar="MONITOR")
    return parser


def output_parser():
    parser = argparse.ArgumentParser(prog="windowmover output")
    parser.add_argument("action", choices=["list", "on", "off", "enable", "disable",
                                           "scale", "mode", "pos", "rotate"])
    parser.add_argument("output", nargs="?", metavar="OUTPUT")
    parser.add_argument("value", nargs="?", metavar="VALUE")
    parser.add_argument("value2", nargs="?", metavar="VALUE2")
    return parser


def cmd_output(args):
    if args.action == "list":
        for out in core.get_outputs():
            state = "enabled" if out["enabled"] else "disabled"
            print(f"OUTPUT  {out['name']:<10} {state:<8} scale {out['scale']}")
        return 0
    if not args.output:
        print("Specify an output name.", file=sys.stderr)
        return 2
    output = core.find_output(core.get_outputs(), args.output)
    if not output:
        print(f"Unknown output: {args.output}", file=sys.stderr)
        return 1
    if args.action in ("on", "enable"):
        core.set_output_enabled(output, True)
        print(f"Turned on {output['name']}.")
        return 0
    if args.action in ("off", "disable"):
        core.set_output_enabled(output, False)
        print(f"Turned off {output['name']}.")
        return 0
    if args.action == "scale":
        try:
            float(args.value)
        except (TypeError, ValueError):
            print("Specify a numeric scale, e.g. 1.15.", file=sys.stderr)
            return 2
        core.set_output_scale(output, args.value)
        print(f"Set {output['name']} scale to {args.value}.")
        return 0
    if args.action == "mode":
        if not args.value:
            print("Specify a mode, e.g. 3440x1440@144.", file=sys.stderr)
            return 2
        core.set_output_mode(output, args.value)
        print(f"Set {output['name']} mode to {args.value}.")
        return 0
    if args.action == "pos":
        try:
            x = int(args.value)
            y = int(args.value2)
        except (TypeError, ValueError):
            print("Specify position as X Y.", file=sys.stderr)
            return 2
        core.set_output_position(output, x, y)
        print(f"Positioned {output['name']} at {x},{y}.")
        return 0
    if args.action == "rotate":
        if args.value not in ("none", "left", "right", "inverted"):
            print("Rotation: none left right inverted.", file=sys.stderr)
            return 2
        core.set_output_rotation(output, args.value)
        print(f"Set {output['name']} rotation to {args.value}.")
        return 0
    return 2


def win_parser():
    parser = argparse.ArgumentParser(prog="windowmover win")
    parser.add_argument("action", help="minimize unminimize maximize unmaximize "
                        "full-on full-off full-toggle above-on above-off below-on "
                        "below-off sticky-on sticky-off shade-on shade-off raise "
                        "close opacity")
    parser.add_argument("--class", dest="window_class", metavar="CLASS")
    parser.add_argument("--title", metavar="TITLE")
    parser.add_argument("extra", nargs="?", metavar="VALUE", help="opacity percent")
    return parser


def cmd_win(args):
    window = core.find_window(core.get_windows(), args.window_class, args.title)
    if not window:
        print("No matching window found.", file=sys.stderr)
        return 1
    if args.action == "opacity":
        if not core.window_opacity(window, args.extra):
            print("Specify opacity 0-100.", file=sys.stderr)
            return 2
        print(f'Set "{window["title"]}" opacity to {args.extra}%.')
        return 0
    if not core.window_state(window, args.action.replace("_", "-")):
        print(f"Unknown action: {args.action}", file=sys.stderr)
        return 2
    print(f'Applied {args.action} to "{window["title"]}".')
    return 0


def layout_parser():
    parser = argparse.ArgumentParser(prog="windowmover layout")
    parser.add_argument("action", choices=["save", "load", "list"])
    parser.add_argument("name", nargs="?", metavar="NAME")
    return parser


def cmd_layout(args):
    if args.action == "list":
        for name in core.layout_list():
            print(f"LAYOUT  {name}")
        return 0
    if not args.name:
        print("Specify a layout name.", file=sys.stderr)
        return 2
    if args.action == "save":
        path = core.layout_save(args.name)
        print(f"Saved layout to {path}.")
        return 0
    applied = core.layout_load(args.name)
    if applied is None:
        print(f"Unknown layout: {args.name}", file=sys.stderr)
        return 1
    print(f"Restored {applied} window(s) from layout {args.name}.")
    return 0


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
    if args.tile:
        if not core.tile_window(window, monitor, args.tile.lower()):
            print(f"Unknown tile area: {args.tile}", file=sys.stderr)
            return 2
    elif args.center:
        core.center_window(window, monitor)
    else:
        width = height = x = y = None
        if args.geometry:
            try:
                width, height = (int(v) for v in args.geometry.lower().split("x"))
            except ValueError:
                print("Bad --geometry, use WIDTHxHEIGHT.", file=sys.stderr)
                return 2
        if args.pos:
            try:
                x, y = (int(v) for v in args.pos.split(","))
            except ValueError:
                print("Bad --pos, use X,Y.", file=sys.stderr)
                return 2
        if width is not None or x is not None:
            core.place_window(window, x, y, width, height)
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
        if command in ("primary", "default"):
            return cmd_primary(primary_parser().parse_args(argv[1:]))
        if command == "output":
            return cmd_output(output_parser().parse_args(argv[1:]))
        if command == "win":
            return cmd_win(win_parser().parse_args(argv[1:]))
        if command == "layout":
            return cmd_layout(layout_parser().parse_args(argv[1:]))
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
