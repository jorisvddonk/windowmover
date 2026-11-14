import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import core


class MoverWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Window Mover")
        self.setWindowIcon(QIcon.fromTheme("preferences-system-windows"))
        self.resize(1000, 520)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self.window_list = QListWidget()
        self.monitor_list = QListWidget()
        self.output_list = QListWidget()
        self.status = QLabel("Select a window and a monitor.")

        left = QVBoxLayout()
        left.addWidget(QLabel("Windows"))
        left.addWidget(self.window_list)

        right = QVBoxLayout()
        right.addWidget(QLabel("Monitors"))
        right.addWidget(self.monitor_list)

        outputs = QVBoxLayout()
        outputs.addWidget(QLabel("Outputs"))
        outputs.addWidget(self.output_list)

        lists = QHBoxLayout()
        lists.addLayout(left, 3)
        lists.addLayout(right, 2)
        lists.addLayout(outputs, 2)

        move_button = QPushButton("Move")
        move_button.clicked.connect(lambda: self.apply(False, False))
        move_full_button = QPushButton("Move + Fullscreen")
        move_full_button.clicked.connect(lambda: self.apply(True, False))
        maximize_button = QPushButton("Maximize")
        maximize_button.clicked.connect(lambda: self.apply(False, True))
        default_button = QPushButton("Set default screen")
        default_button.clicked.connect(self.set_default)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addWidget(move_button)
        buttons.addWidget(move_full_button)
        buttons.addWidget(maximize_button)
        buttons.addWidget(default_button)
        buttons.addWidget(refresh_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)

        ops = QHBoxLayout()
        center_button = QPushButton("Center")
        center_button.clicked.connect(self.op_center)
        tile_left_button = QPushButton("Tile Left")
        tile_left_button.clicked.connect(lambda: self.op_tile("left"))
        tile_right_button = QPushButton("Tile Right")
        tile_right_button.clicked.connect(lambda: self.op_tile("right"))
        min_button = QPushButton("Minimize")
        min_button.clicked.connect(lambda: self.op_state("minimize"))
        full_button = QPushButton("Fullscreen toggle")
        full_button.clicked.connect(lambda: self.op_state("fullscreen-toggle"))
        raise_button = QPushButton("Raise")
        raise_button.clicked.connect(lambda: self.op_state("raise"))
        kill_button = QPushButton("Close window")
        kill_button.clicked.connect(lambda: self.op_state("close"))
        out_on_button = QPushButton("Output on")
        out_on_button.clicked.connect(lambda: self.op_output(True))
        out_off_button = QPushButton("Output off")
        out_off_button.clicked.connect(lambda: self.op_output(False))
        for widget in (center_button, tile_left_button, tile_right_button,
                       min_button, full_button, raise_button, kill_button,
                       out_on_button, out_off_button):
            ops.addWidget(widget)
        ops.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(lists)
        layout.addLayout(buttons)
        layout.addLayout(ops)
        layout.addWidget(self.status)

        self.monitor_list.itemDoubleClicked.connect(lambda _: self.apply(False, False))
        self.output_list.itemDoubleClicked.connect(lambda _: self.op_output(None))
        self.refresh()
        QTimer.singleShot(600, lambda: core.kwin_run(core.self_script(), "windowmover_self"))

    def refresh(self):
        selected_window = self.window_list.currentItem()
        selected_monitor = self.monitor_list.currentItem()
        selected_window_title = selected_window.text() if selected_window else ""
        selected_monitor_name = (
            selected_monitor.data(Qt.UserRole)["name"] if selected_monitor else ""
        )

        self.window_list.clear()
        self.monitor_list.clear()

        for window in core.get_windows():
            item = QListWidgetItem(window["title"])
            item.setData(Qt.UserRole, window)
            item.setToolTip(f'{window["class_full"]}  [{window["id"]}]')
            self.window_list.addItem(item)
            if window["title"] == selected_window_title:
                self.window_list.setCurrentItem(item)
            if "steam_app_2605790" in window["class_full"] and not selected_window_title:
                self.window_list.setCurrentItem(item)

        for monitor in core.get_monitors():
            item = QListWidgetItem(monitor["label"])
            item.setData(Qt.UserRole, monitor)
            self.monitor_list.addItem(item)
            if monitor["name"] == selected_monitor_name:
                self.monitor_list.setCurrentItem(item)
            if monitor["name"] == "DP-4" and not selected_monitor_name:
                self.monitor_list.setCurrentItem(item)

        self.output_list.clear()
        for out in core.get_outputs():
            state = "on" if out["enabled"] else "off"
            item = QListWidgetItem(f'{out["name"]} [{state}] x{out["scale"]}')
            item.setData(Qt.UserRole, out)
            self.output_list.addItem(item)

        if not self.window_list.currentItem() and self.window_list.count():
            self.window_list.setCurrentRow(0)
        if not self.monitor_list.currentItem() and self.monitor_list.count():
            self.monitor_list.setCurrentRow(0)

    def set_default(self):
        monitor_item = self.monitor_list.currentItem()
        if not monitor_item:
            self.status.setText("Select a monitor.")
            return
        monitor = monitor_item.data(Qt.UserRole)
        core.set_primary(monitor)
        self.status.setText(f'Set default screen to {monitor["name"]}.')
        self.refresh()

    def op_center(self):
        window, monitor = self.selected_pair()
        if not window or not monitor:
            self.status.setText("Select a window and a monitor.")
            return
        core.center_window(window, monitor)
        self.status.setText(f'Centered "{window["title"]}" on {monitor["name"]}.')
        QTimer.singleShot(1200, self.refresh)

    def op_tile(self, area):
        window, monitor = self.selected_pair()
        if not window or not monitor:
            self.status.setText("Select a window and a monitor.")
            return
        core.tile_window(window, monitor, area)
        self.status.setText(f'Tiled "{window["title"]}" {area} on {monitor["name"]}.')
        QTimer.singleShot(1200, self.refresh)

    def op_state(self, action):
        window_item = self.window_list.currentItem()
        if not window_item:
            self.status.setText("Select a window.")
            return
        window = window_item.data(Qt.UserRole)
        core.window_state(window, action)
        self.status.setText(f'Applied {action} to "{window["title"]}".')
        QTimer.singleShot(1200, self.refresh)

    def op_output(self, enable):
        output_item = self.output_list.currentItem()
        if not output_item:
            self.status.setText("Select an output.")
            return
        output = output_item.data(Qt.UserRole)
        if enable is None:
            enable = not output["enabled"]
        core.set_output_enabled(output, enable)
        state = "on" if enable else "off"
        self.status.setText(f"Turned {state} {output['name']}.")
        QTimer.singleShot(1200, self.refresh)

    def selected_pair(self):
        window_item = self.window_list.currentItem()
        monitor_item = self.monitor_list.currentItem()
        window = window_item.data(Qt.UserRole) if window_item else None
        monitor = monitor_item.data(Qt.UserRole) if monitor_item else None
        return window, monitor

    def apply(self, fullscreen, maximize):
        window_item = self.window_list.currentItem()
        monitor_item = self.monitor_list.currentItem()
        if not window_item or not monitor_item:
            self.status.setText("Select a window and a monitor.")
            return
        window = window_item.data(Qt.UserRole)
        monitor = monitor_item.data(Qt.UserRole)
        core.move_window(window, monitor, fullscreen, maximize)
        self.status.setText(f'Moved "{window["title"]}" to {monitor["name"]}.')
        QTimer.singleShot(1200, self.refresh)


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    app = QApplication(argv)
    app.setApplicationName("windowmover")
    app.setDesktopFileName("windowmover")
    window = MoverWindow()
    window.show()
    return app.exec()
