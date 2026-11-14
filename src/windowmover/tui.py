import curses
import sys

from . import core

HELP = "Tab focus Enter move/toggle F move+full M maximize C center T tile P screen O out-off R refresh Q quit"


class MoverTui:
    def __init__(self, screen):
        self.screen = screen
        self.focus = 0
        self.windows = []
        self.monitors = []
        self.outputs = []
        self.window_index = 0
        self.monitor_index = 0
        self.output_index = 0
        self.message = "Select a window and a monitor."
        self.running = True
        self.setup()
        self.reload()

    def setup(self):
        curses.curs_set(0)
        self.screen.keypad(True)
        if curses.has_colors():
            curses.start_color()
            try:
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_CYAN, -1)
                curses.init_pair(2, curses.COLOR_YELLOW, -1)
                curses.init_pair(3, curses.COLOR_GREEN, -1)
            except curses.error:
                pass

    def color(self, pair, attr=0):
        if curses.has_colors():
            return curses.color_pair(pair) | attr
        return attr

    def reload(self):
        selected_window = self.windows[self.window_index]["title"] if self.windows else None
        selected_monitor = self.monitors[self.monitor_index]["name"] if self.monitors else None
        selected_output = self.outputs[self.output_index]["name"] if self.outputs else None

        self.windows = core.get_windows(exclude_titles=("Window Mover", "windowmover"))
        self.monitors = core.get_monitors()
        self.outputs = core.get_outputs()

        self.window_index = 0
        self.monitor_index = 0
        self.output_index = 0
        for index, window in enumerate(self.windows):
            if selected_window and window["title"] == selected_window:
                self.window_index = index
                break
            if "steam_app_2605790" in window["class_full"]:
                self.window_index = index
        for index, monitor in enumerate(self.monitors):
            if selected_monitor and monitor["name"] == selected_monitor:
                self.monitor_index = index
                break
            if monitor["name"] == "DP-4":
                self.monitor_index = index
        for index, out in enumerate(self.outputs):
            if selected_output and out["name"] == selected_output:
                self.output_index = index
                break

    def clamp(self):
        if self.windows:
            self.window_index = max(0, min(self.window_index, len(self.windows) - 1))
        if self.monitors:
            self.monitor_index = max(0, min(self.monitor_index, len(self.monitors) - 1))
        if self.outputs:
            self.output_index = max(0, min(self.output_index, len(self.outputs) - 1))

    def addstr(self, y, x, text, attr=0):
        height, width = self.screen.getmaxyx()
        if y < 0 or y >= height or x < 0 or x >= width:
            return
        try:
            self.screen.addstr(y, x, text[: max(0, width - x - 1)], attr)
        except curses.error:
            pass

    def draw_list(self, y, x, height, width, title, items, index, focused):
        header_attr = self.color(1, curses.A_BOLD)
        if focused:
            header_attr |= curses.A_REVERSE
        self.addstr(y, x, title.ljust(width), header_attr)
        if not items:
            self.addstr(y + 1, x, "(none)", curses.A_DIM)
            return
        visible = max(1, height - 1)
        start = 0
        if index >= visible:
            start = index - visible + 1
        for offset, item in enumerate(items[start:start + visible]):
            position = start + offset
            attr = curses.A_REVERSE if position == index else 0
            prefix = "> " if position == index else "  "
            self.addstr(y + 1 + offset, x, prefix + item, attr)

    def draw(self):
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        if height < 6 or width < 30:
            self.addstr(0, 0, "Terminal too small", curses.A_BOLD)
            self.screen.refresh()
            return

        header = " Window Mover "
        self.addstr(0, 0, header.ljust(width), self.color(1, curses.A_BOLD))
        self.addstr(0, max(0, width - len(HELP) - 1), " " + HELP, curses.A_DIM)

        split1 = max(20, int(width * 0.46))
        split2 = max(split1 + 15, int(width * 0.76))
        list_height = height - 4

        window_items = [window["title"] for window in self.windows]
        monitor_items = [monitor["label"] for monitor in self.monitors]
        output_items = [
            f'{out["name"]} [{"on" if out["enabled"] else "off"}] x{out["scale"]}'
            for out in self.outputs
        ]

        self.draw_list(1, 0, list_height, split1 - 1, "Windows", window_items, self.window_index, self.focus == 0)
        for row in range(1, height - 2):
            self.addstr(row, split1 - 1, "|", curses.A_DIM)
        self.draw_list(1, split1, list_height, split2 - split1 - 1, "Monitors", monitor_items, self.monitor_index, self.focus == 1)
        for row in range(1, height - 2):
            self.addstr(row, split2 - 1, "|", curses.A_DIM)
        self.draw_list(1, split2, list_height, width - split2, "Outputs", output_items, self.output_index, self.focus == 2)

        self.addstr(height - 2, 0, self.message.ljust(width), self.color(3))
        self.screen.refresh()

    def selected(self):
        window = self.windows[self.window_index] if self.windows else None
        monitor = self.monitors[self.monitor_index] if self.monitors else None
        return window, monitor

    def action(self, fullscreen=False, maximize=False):
        window, monitor = self.selected()
        if not window or not monitor:
            self.message = "Nothing selected."
            return
        core.move_window(window, monitor, fullscreen, maximize)
        mode = " + fullscreen" if fullscreen else " + maximize" if maximize else ""
        self.message = f'Moved "{window["title"]}" to {monitor["name"]}{mode}.'
        self.reload()

    def op_tile(self, area):
        window, monitor = self.selected()
        if not window or not monitor:
            self.message = "Nothing selected."
            return
        if area == "center":
            core.center_window(window, monitor)
            self.message = f'Centered "{window["title"]}" on {monitor["name"]}.'
        else:
            core.tile_window(window, monitor, area)
            self.message = f'Tiled "{window["title"]}" {area} on {monitor["name"]}.'
        self.reload()

    def op_state(self, action):
        if not self.windows:
            self.message = "No windows."
            return
        window = self.windows[self.window_index]
        core.window_state(window, action)
        self.message = f'Applied {action} to "{window["title"]}".'
        self.reload()

    def op_output(self, enable):
        if not self.outputs:
            self.message = "No outputs."
            return
        output = self.outputs[self.output_index]
        if enable is None:
            enable = not output["enabled"]
        core.set_output_enabled(output, enable)
        state = "on" if enable else "off"
        self.message = f"Turned {state} {output['name']}."
        self.reload()

    def handle_key(self, key):
        if key in (ord("q"), ord("Q")):
            self.running = False
        elif key in (ord("r"), ord("R")):
            self.reload()
            self.message = "Refreshed."
        elif key in (9, ord("\t")):
            self.focus = (self.focus + 1) % 3
        elif key in (ord("\n"), curses.KEY_ENTER, 10, 13):
            if self.focus == 2:
                self.op_output(None)
            else:
                self.action()
        elif key in (ord("f"), ord("F")):
            self.action(fullscreen=True)
        elif key in (ord("m"), ord("M")):
            self.action(maximize=True)
        elif key in (ord("c"), ord("C")):
            self.op_tile("center")
        elif key == ord("t"):
            self.op_tile("left")
        elif key == ord("T"):
            self.op_tile("right")
        elif key in (ord("n"), ord("N")):
            self.op_state("minimize")
        elif key in (ord("v"), ord("V")):
            self.op_state("fullscreen-toggle")
        elif key in (ord("o"), ord("O")):
            if self.focus == 2:
                self.op_output(None)
            elif self.monitors:
                monitor = self.monitors[self.monitor_index]
                out = core.find_output(self.outputs, monitor["name"])
                if out:
                    self.output_index = self.outputs.index(out)
                    self.op_output(False)
                else:
                    self.message = "Output not found."
            else:
                self.message = "No monitors found."
        elif key in (ord("p"), ord("P")):
            if self.monitors:
                monitor = self.monitors[self.monitor_index]
                core.set_primary(monitor)
                self.message = f'Set default screen to {monitor["name"]}.'
                self.reload()
            else:
                self.message = "No monitors found."
        elif key in (curses.KEY_UP, ord("k"), ord("K")):
            if self.focus == 0:
                self.window_index -= 1
            elif self.focus == 1:
                self.monitor_index -= 1
            else:
                self.output_index -= 1
            self.clamp()
        elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
            if self.focus == 0:
                self.window_index += 1
            elif self.focus == 1:
                self.monitor_index += 1
            else:
                self.output_index += 1
            self.clamp()
        elif key in (curses.KEY_LEFT, ord("h"), ord("H")):
            self.focus = (self.focus - 1) % 3
        elif key in (curses.KEY_RIGHT, ord("l"), ord("L")):
            self.focus = (self.focus + 1) % 3
        elif ord("1") <= key <= ord("9"):
            index = key - ord("1")
            if index < len(self.monitors):
                self.monitor_index = index
                self.focus = 1
                self.clamp()
        elif key == curses.KEY_RESIZE:
            pass

    def run(self):
        while self.running:
            self.draw()
            key = self.screen.getch()
            self.handle_key(key)


def run(screen):
    MoverTui(screen).run()


def main(argv=None):
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("windowmover tui requires an interactive terminal.", file=sys.stderr)
        return 1
    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        return 130
    return 0
