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
        self.resize(780, 500)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self.window_list = QListWidget()
        self.monitor_list = QListWidget()
        self.status = QLabel("Select a window and a monitor.")

        left = QVBoxLayout()
        left.addWidget(QLabel("Windows"))
        left.addWidget(self.window_list)

        right = QVBoxLayout()
        right.addWidget(QLabel("Monitors"))
        right.addWidget(self.monitor_list)

        lists = QHBoxLayout()
        lists.addLayout(left, 3)
        lists.addLayout(right, 2)

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

        layout = QVBoxLayout(self)
        layout.addLayout(lists)
        layout.addLayout(buttons)
        layout.addWidget(self.status)

        self.monitor_list.itemDoubleClicked.connect(lambda _: self.apply(False, False))
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
