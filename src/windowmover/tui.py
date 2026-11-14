import curses
import sys

from . import core

HELP = "Tab focus  Enter move  F move+fullscreen  M maximize  R refresh  Q quit"


class MoverTui:
    def __init__(self, screen):
        self.screen = screen
        self.focus = 0
        self.windows = []
        self.monitors = []
        self.window_index = 0
        self.monitor_index = 0
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

        self.windows = core.get_windows(exclude_titles=("Window Mover", "windowmover"))
        self.monitors = core.get_monitors()

        self.window_index = 0
        self.monitor_index = 0
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

    def clamp(self):
        if self.windows:
            self.window_index = max(0, min(self.window_index, len(self.windows) - 1))
        if self.monitors:
            self.monitor_index = max(0, min(self.monitor_index, len(self.monitors) - 1))

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

        split = max(20, int(width * 0.58))
        list_height = height - 4

        window_items = [window["title"] for window in self.windows]
        monitor_items = [monitor["label"] for monitor in self.monitors]

        self.draw_list(1, 0, list_height, split - 1, "Windows", window_items, self.window_index, self.focus == 0)
        for row in range(1, height - 2):
            self.addstr(row, split - 1, "|", curses.A_DIM)
        self.draw_list(1, split, list_height, width - split, "Monitors", monitor_items, self.monitor_index, self.focus == 1)

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

    def handle_key(self, key):
        if key in (ord("q"), ord("Q")):
            self.running = False
        elif key in (ord("r"), ord("R")):
            self.reload()
            self.message = "Refreshed."
        elif key in (9, ord("\t")):
            self.focus = 1 - self.focus
        elif key in (ord("\n"), curses.KEY_ENTER, 10, 13):
            self.action()
        elif key in (ord("f"), ord("F")):
            self.action(fullscreen=True)
        elif key in (ord("m"), ord("M")):
            self.action(maximize=True)
        elif key in (curses.KEY_UP, ord("k"), ord("K")):
            if self.focus == 0:
                self.window_index -= 1
            else:
                self.monitor_index -= 1
            self.clamp()
        elif key in (curses.KEY_DOWN, ord("j"), ord("J")):
            if self.focus == 0:
                self.window_index += 1
            else:
                self.monitor_index += 1
            self.clamp()
        elif key in (curses.KEY_LEFT, ord("h"), ord("H")):
            self.focus = 0
        elif key in (curses.KEY_RIGHT, ord("l"), ord("L")):
            self.focus = 1
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
