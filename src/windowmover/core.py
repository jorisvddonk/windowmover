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


def get_outputs():
    try:
        data = json.loads(subprocess.check_output(["kscreen-doctor", "-j"], text=True))
    except Exception:
        return []
    outputs = []
    for out in data.get("outputs", []):
        if not out.get("connected"):
            continue
        outputs.append(
            {
                "name": out.get("name", ""),
                "enabled": bool(out.get("enabled")),
                "connected": bool(out.get("connected")),
                "scale": out.get("scale", 1.0),
                "priority": out.get("priority") or 99,
            }
        )
    outputs.sort(key=lambda item: item["priority"])
    return outputs


def find_output(outputs, name):
    for out in outputs:
        if out["name"].lower() == name.lower():
            return out
    for out in outputs:
        if name.lower() in out["name"].lower():
            return out
    return None


def set_output_enabled(output, enabled):
    action = "enable" if enabled else "disable"
    subprocess.run(
        ["kscreen-doctor", f"output.{output['name']}.{action}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def set_output_scale(output, scale):
    subprocess.run(
        ["kscreen-doctor", f"output.{output['name']}.scale.{scale}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _xrandr_offsets():
    offsets = {}
    try:
        output = subprocess.check_output(["xrandr", "--query"], text=True)
    except Exception:
        return offsets
    import re

    for line in output.splitlines():
        match = re.match(r"^(\S+)\s+connected.*?(\d+)x(\d+)\+(\d+)\+(\d+)", line)
        if match:
            name, _, _, x, y = match.groups()
            offsets[name] = (int(x), int(y))
    return offsets


def get_monitors():
    try:
        data = json.loads(subprocess.check_output(["kscreen-doctor", "-j"], text=True))
    except Exception:
        return []
    offsets = _xrandr_offsets()
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
        x, y = offsets.get(name, (0, 0))
        monitors.append(
            {
                "name": name,
                "label": label,
                "model": model,
                "width": width,
                "height": height,
                "x": x,
                "y": y,
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


def _gdbus(*args):
    try:
        return subprocess.run(
            [GDBUS, "call", "--session", "--dest", "org.kde.KWin", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None


def kwin_run(script, plugin_name="windowmover_action"):
    path = f"/tmp/{plugin_name}.js"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(script)
    _gdbus(
        "--object-path",
        "/Scripting",
        "--method",
        "org.kde.kwin.Scripting.unloadScript",
        plugin_name,
    )
    result = _gdbus(
        "--object-path",
        "/Scripting",
        "--method",
        "org.kde.kwin.Scripting.loadScript",
        path,
        plugin_name,
    )
    script_id = None
    if result is not None:
        import re

        match = re.search(r"\((\d+),?\)", result.stdout or "")
        if match:
            script_id = match.group(1)
    if script_id is not None:
        _gdbus(
            "--object-path",
            f"/Scripting/Script{script_id}",
            "--method",
            "org.kde.kwin.Script.run",
        )
        _gdbus(
            "--object-path",
            "/Scripting",
            "--method",
            "org.kde.kwin.Scripting.unloadScript",
            plugin_name,
        )
        return
    _gdbus(
        "--object-path",
        "/Scripting",
        "--method",
        "org.kde.kwin.Scripting.start",
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
    try {{ target.fullScreen = false; }} catch (e) {{}}
    try {{ target.setMaximize(false, false); }} catch (e) {{}}
    workspace.sendClientToScreen(target, screen);
    if (FULL) {{
        try {{ target.frameGeometry = screen.geometry; }} catch (e) {{}}
        try {{ target.fullScreen = true; }} catch (e) {{}}
    }}
    if (MAX && !FULL) {{ try {{ target.setMaximize(true, true); }} catch (e) {{}} }}
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


def set_primary(monitor):
    subprocess.run(
        ["kscreen-doctor", f"output.{monitor['name']}.primary"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    subprocess.run(
        ["xrandr", "--output", monitor["name"], "--primary"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _wmctrl(*args):
    try:
        subprocess.run(
            [WMCTRL, *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return True
    except FileNotFoundError:
        return False


def place_window(window, x=None, y=None, width=None, height=None):
    wid = window["id"]
    gx = window["x"] if x is None else x
    gy = window["y"] if y is None else y
    gw = window["width"] if width is None else width
    gh = window["height"] if height is None else height
    _wmctrl("-i", "-r", wid, "-e", f"0,{gx},{gy},{gw},{gh}")


def center_window(window, monitor):
    w = min(window["width"], monitor["width"])
    h = min(window["height"], monitor["height"])
    x = monitor["x"] + (monitor["width"] - w) // 2
    y = monitor["y"] + (monitor["height"] - h) // 2
    place_window(window, x, y, w, h)


TILE_AREAS = {
    "left": (0.0, 0.0, 0.5, 1.0),
    "right": (0.5, 0.0, 0.5, 1.0),
    "top": (0.0, 0.0, 1.0, 0.5),
    "bottom": (0.0, 0.5, 1.0, 0.5),
    "topleft": (0.0, 0.0, 0.5, 0.5),
    "topright": (0.5, 0.0, 0.5, 0.5),
    "bottomleft": (0.0, 0.5, 0.5, 0.5),
    "bottomright": (0.5, 0.5, 0.5, 0.5),
    "center": (0.25, 0.25, 0.5, 0.5),
    "full": (0.0, 0.0, 1.0, 1.0),
}


def tile_window(window, monitor, area):
    spec = TILE_AREAS.get(area)
    if not spec:
        return False
    fx, fy, fw, fh = spec
    x = monitor["x"] + int(monitor["width"] * fx)
    y = monitor["y"] + int(monitor["height"] * fy)
    w = int(monitor["width"] * fw)
    h = int(monitor["height"] * fh)
    _wmctrl("-i", "-r", window["id"], "-b", "remove,fullscreen, maximized_vert, maximized_horz")
    place_window(window, x, y, w, h)
    return True


def window_state(window, action):
    wid = window["id"]
    if action == "minimize":
        _wmctrl("-i", "-r", wid, "-b", "add,hidden")
    elif action == "unminimize":
        _wmctrl("-i", "-r", wid, "-b", "remove,hidden")
        _wmctrl("-i", "-a", wid)
    elif action == "maximize":
        _wmctrl("-i", "-r", wid, "-b", "add,maximized_vert,maximized_horz")
    elif action == "unmaximize":
        _wmctrl("-i", "-r", wid, "-b", "remove,maximized_vert,maximized_horz")
    elif action == "fullscreen-on":
        _wmctrl("-i", "-r", wid, "-b", "add,fullscreen")
    elif action == "fullscreen-off":
        _wmctrl("-i", "-r", wid, "-b", "remove,fullscreen")
    elif action == "fullscreen-toggle":
        _wmctrl("-i", "-r", wid, "-b", "toggle,fullscreen")
    elif action == "above-on":
        _wmctrl("-i", "-r", wid, "-b", "add,above")
    elif action == "above-off":
        _wmctrl("-i", "-r", wid, "-b", "remove,above")
    elif action == "below-on":
        _wmctrl("-i", "-r", wid, "-b", "add,below")
    elif action == "below-off":
        _wmctrl("-i", "-r", wid, "-b", "remove,below")
    elif action == "sticky-on":
        _wmctrl("-i", "-r", wid, "-b", "add,sticky")
    elif action == "sticky-off":
        _wmctrl("-i", "-r", wid, "-b", "remove,sticky")
    elif action == "shade-on":
        _wmctrl("-i", "-r", wid, "-b", "add,shaded")
    elif action == "shade-off":
        _wmctrl("-i", "-r", wid, "-b", "remove,shaded")
    elif action == "raise":
        _wmctrl("-i", "-a", wid)
    elif action == "close":
        _wmctrl("-i", "-c", wid)
    else:
        return False
    return True


def window_opacity(window, percent):
    try:
        pct = max(0, min(100, int(percent)))
    except (TypeError, ValueError):
        return False
    if pct >= 100:
        subprocess.run(
            ["xprop", "-id", window["id"], "-remove", "_NET_WM_WINDOW_OPACITY"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return True
    value = int(0xFFFFFFFF * pct / 100)
    subprocess.run(
        [
            "xprop", "-id", window["id"], "-f", "_NET_WM_WINDOW_OPACITY",
            "32c", "-set", "_NET_WM_WINDOW_OPACITY", str(value),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return True


def set_output_mode(output, mode):
    subprocess.run(
        ["kscreen-doctor", f"output.{output['name']}.mode.{mode}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def set_output_position(output, x, y):
    subprocess.run(
        ["kscreen-doctor", f"output.{output['name']}.position.{x},{y}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def set_output_rotation(output, rotation):
    subprocess.run(
        ["kscreen-doctor", f"output.{output['name']}.rotation.{rotation}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def layout_dir():
    path = os.path.join(os.path.expanduser("~"), ".config", "windowmover", "layouts")
    os.makedirs(path, exist_ok=True)
    return path


def layout_save(name):
    monitors = get_monitors()
    entries = []
    for window in get_windows():
        entries.append(
            {
                "class": window["class_full"],
                "title": window["title"],
                "x": window["x"],
                "y": window["y"],
                "width": window["width"],
                "height": window["height"],
                "monitors": [m["name"] for m in monitors],
            }
        )
    path = os.path.join(layout_dir(), f"{name}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, indent=2)
    return path


def layout_load(name):
    path = os.path.join(layout_dir(), f"{name}.json")
    try:
        with open(path, encoding="utf-8") as handle:
            entries = json.load(handle)
    except (OSError, ValueError):
        return None
    monitors = {m["name"]: m for m in get_monitors()}
    windows = get_windows()
    applied = 0
    for entry in entries:
        window = find_window(windows, entry.get("class"), None)
        if not window and entry.get("title"):
            window = find_window(windows, None, entry.get("title"))
        if not window:
            continue
        target = None
        for mname in entry.get("monitors", []):
            if mname in monitors:
                target = monitors[mname]
                break
        if target is None:
            place_window(window, entry["x"], entry["y"], entry["width"], entry["height"])
        else:
            move_window(window, target)
            place_window(window, entry["x"], entry["y"], entry["width"], entry["height"])
        applied += 1
    return applied


def layout_list():
    try:
        return sorted(
            f[:-5] for f in os.listdir(layout_dir()) if f.endswith(".json")
        )
    except OSError:
        return []
