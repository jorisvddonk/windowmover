import glob
import json
import os
import shutil
import subprocess

WMCTRL = shutil.which("wmctrl") or os.path.expanduser("~/.local/bin/wmctrl")
GDBUS = shutil.which("gdbus") or "/usr/bin/gdbus"

MANUFACTURERS = {
    "AUS": "ASUS",
    "MSI": "MSI",
    "SNY": "Sony",
    "DEL": "Dell",
    "SAM": "Samsung",
    "GSM": "LG",
    "HWP": "HP",
    "ACR": "Acer",
}


def edid_model(name):
    for path in glob.glob(f"/sys/class/drm/card*-{name}/edid"):
        try:
            data = open(path, "rb").read()
        except OSError:
            continue
        if len(data) < 128:
            continue
        raw = data[8:10]
        man = "".join(
            chr(((raw[0] >> 2) & 0x1F) + 64)
            + chr((((raw[0] & 3) << 3) | (raw[1] >> 5)) + 64)
            + chr((raw[1] & 0x1F) + 64)
        )
        model = ""
        for off in range(54, 126, 18):
            if data[off:off + 3] == b"\x00\x00\x00" and data[off + 3] == 0xFC:
                model = data[off + 5:off + 18].decode("ascii", "ignore").strip("\x00 \n")
        return (MANUFACTURERS.get(man, man) + " " + model).strip()
    return ""


def get_monitors():
    try:
        data = json.loads(subprocess.check_output(["kscreen-doctor", "-j"], text=True))
    except Exception:
        return []
    monitors = []
    for out in data.get("outputs", []):
        if not out.get("enabled") or not out.get("connected"):
            continue
        name = out.get("name", "")
        mode = None
        for candidate in out.get("modes", []):
            if candidate.get("id") == out.get("currentModeId"):
                mode = candidate
                break
        width = mode["size"]["width"] if mode else 0
        height = mode["size"]["height"] if mode else 0
        model = edid_model(name)
        label = name
        if model:
            label += f" - {model}"
        if width and height:
            label += f" ({width}x{height})"
        monitors.append(
            {
                "name": name,
                "label": label,
                "model": model,
                "width": width,
                "height": height,
                "priority": out.get("priority") or 99,
            }
        )
    monitors.sort(key=lambda item: item["priority"])
    return monitors


def get_windows(exclude_titles=("Window Mover",)):
    try:
        output = subprocess.check_output([WMCTRL, "-lxG"], text=True)
    except Exception:
        return []
    windows = []
    for line in output.splitlines():
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        wid, desktop, x, y, width, height, window_class, host, title = parts
        title = title.strip()
        if title in exclude_titles:
            continue
        if not title:
            title = window_class
        windows.append(
            {
                "id": wid,
                "class": window_class.split(".")[-1],
                "class_full": window_class,
                "title": title,
                "x": int(x),
                "y": int(y),
                "width": int(width),
                "height": int(height),
            }
        )
    return windows


def kwin_run(script, plugin_name="windowmover_action"):
    path = f"/tmp/{plugin_name}.js"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(script)
    subprocess.run(
        [
            GDBUS,
            "call",
            "--session",
            "--dest",
            "org.kde.KWin",
            "--object-path",
            "/Scripting",
            "--method",
            "org.kde.kwin.Scripting.unloadScript",
            plugin_name,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            GDBUS,
            "call",
            "--session",
            "--dest",
            "org.kde.KWin",
            "--object-path",
            "/Scripting",
            "--method",
            "org.kde.kwin.Scripting.loadScript",
            path,
            plugin_name,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            GDBUS,
            "call",
            "--session",
            "--dest",
            "org.kde.KWin",
            "--object-path",
            "/Scripting",
            "--method",
            "org.kde.kwin.Scripting.start",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def move_script(output_name, caption, window_class, fullscreen=False, maximize=False):
    return f"""
var OUT = {json.dumps(output_name)};
var CAP = {json.dumps(caption)};
var CLS = {json.dumps(window_class)};
var FULL = {str(fullscreen).lower()};
var MAX = {str(maximize).lower()};
function outByName(n) {{
    var screens = workspace.screens;
    for (var i = 0; i < screens.length; i++) {{
        if (screens[i].name === n) return screens[i];
    }}
    return null;
}}
function findWindow() {{
    var wins = workspace.stackingOrder;
    if (!wins) {{ try {{ wins = workspace.windowList(); }} catch (e) {{}} }}
    var byCaption = null;
    var byClass = null;
    for (var i = 0; i < wins.length; i++) {{
        var w = wins[i];
        var cap = (w.caption || "").trim();
        var cls = w.resourceClass || "";
        if (cap === CAP) {{
            if (!CLS || cls.indexOf(CLS) >= 0) return w;
            if (!byCaption) byCaption = w;
        }}
        if (CLS && cls.indexOf(CLS) >= 0 && !byClass) byClass = w;
    }}
    return byCaption || byClass;
}}
var target = findWindow();
var screen = outByName(OUT);
if (target && screen) {{
    workspace.sendClientToScreen(target, screen);
    if (FULL) {{ try {{ target.fullScreen = true; }} catch (e) {{}} }}
    if (MAX) {{ try {{ target.setMaximize(true, true); }} catch (e) {{}} }}
    try {{ workspace.activeWindow = target; }} catch (e) {{}}
}}
"""


def self_script(caption="Window Mover"):
    return f"""
var CAP = {json.dumps(caption)};
var wins = workspace.stackingOrder;
if (!wins) {{ try {{ wins = workspace.windowList(); }} catch (e) {{}} }}
var target = null;
for (var i = 0; i < wins.length; i++) {{
    var w = wins[i];
    var cap = (w.caption || "").trim();
    var cls = w.resourceClass || "";
    if (cap === CAP || cls.indexOf("windowmover") >= 0) {{ target = w; break; }}
}}
if (target) {{
    var pos = workspace.cursorPos;
    var screens = workspace.screens;
    var screen = null;
    for (var i = 0; i < screens.length; i++) {{
        var g = screens[i].geometry;
        if (pos.x >= g.x && pos.x < g.x + g.width && pos.y >= g.y && pos.y < g.y + g.height) {{
            screen = screens[i];
            break;
        }}
    }}
    if (!screen) screen = workspace.activeScreen;
    if (screen) workspace.sendClientToScreen(target, screen);
    try {{ workspace.activeWindow = target; }} catch (e) {{}}
}}
"""


def move_window(window, monitor, fullscreen=False, maximize=False):
    kwin_run(move_script(monitor["name"], window["title"], window["class"], fullscreen, maximize))


def find_window(windows, class_part=None, title_part=None):
    if class_part:
        for window in windows:
            if class_part.lower() in window["class_full"].lower():
                return window
    if title_part:
        for window in windows:
            if title_part.lower() in window["title"].lower():
                return window
    return None


def find_monitor(monitors, name):
    for monitor in monitors:
        if monitor["name"].lower() == name.lower():
            return monitor
    for monitor in monitors:
        if name.lower() in monitor["label"].lower():
            return monitor
    return None
