import ctypes
import hashlib
import hmac
import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlparse

import mss
from PIL import Image

import config
import functional

MAX_INIT_DATA_AGE = 7 * 24 * 3600

POWER_ACTIONS = {
    "shutdown": functional.shutdown_pc,
    "restart": functional.restart_pc,
    "sleep": functional.sleep_mode_pc,
    "logoff": functional.logoff_pc,
    "lock": functional.lock_pc,
}

ALLOWED_HOTKEYS = {
    "win+d",
    "alt+tab",
    "ctrl+w",
    "alt+f4",
    "ctrl+a",
    "ctrl+c",
    "ctrl+v",
}

public_url = None
_server = None


def _set_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()


def _sign(init_data):
    pairs = dict(parse_qsl(init_data, strict_parsing=True))
    received = pairs.pop("hash", None)
    if not received:
        return None
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", config.TOKEN.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, received):
        return None
    return pairs


def validate_init_data(init_data):
    if not init_data:
        return None
    try:
        pairs = _sign(init_data)
    except ValueError:
        return None
    if pairs is None:
        return None
    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        return None
    if (datetime.now(UTC).timestamp() - auth_date) > MAX_INIT_DATA_AGE:
        return None
    try:
        user = json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError:
        return None
    if user.get("id") != config.ALLOWED_USER_ID:
        return None
    return user


def _monitor():
    with mss.mss() as sct:
        return dict(sct.monitors[0])


def _map(u, v, monitor):
    x = int(monitor["left"] + u * monitor["width"])
    y = int(monitor["top"] + v * monitor["height"])
    return x, y


def grab_jpeg(max_width=1280, quality=70):
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[0])
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        if 0 < max_width < shot.size.width:
            height = round(shot.size.height * max_width / shot.size.width)
            image = image.resize((max_width, height), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, "JPEG", quality=quality)
        return buffer.getvalue()


def click_at(u, v):
    x, y = _map(u, v, _monitor())
    ctypes.windll.user32.SetCursorPos(x, y)
    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
    return x, y


def _state():
    return {"volume": functional.get_volume(), "mute": functional.get_mute()}


PAGE = Path(__file__).with_name("page.html").read_text(encoding="utf-8")


class _Handler(BaseHTTPRequestHandler):
    def _reply(self, code, body, content_type="text/plain; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json_reply(self, payload, code=200):
        self._reply(code, json.dumps(payload), "application/json; charset=utf-8")

    def _authorized(self):
        return validate_init_data(self.headers.get("X-Telegram-Init-Data", "")) is not None

    def _path(self):
        return self.path.split("?", 1)[0]

    def _query(self):
        return parse_qs(urlparse(self.path).query)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return None

    def do_GET(self):
        path = self._path()
        if path == "/":
            self._reply(200, PAGE, "text/html; charset=utf-8")
            return
        if not self._authorized():
            self._reply(403, "forbidden")
            return
        if path == "/screen":
            query = self._query()
            try:
                width = int(query.get("w", ["1280"])[0])
                quality = int(query.get("q", ["70"])[0])
                self._reply(200, grab_jpeg(width, quality), "image/jpeg")
            except Exception as error:
                self._reply(500, f"error: {error}")
        elif path == "/state":
            try:
                self._json_reply(_state())
            except Exception as error:
                self._json_reply({"error": str(error)}, 500)
        else:
            self._reply(404, "not found")

    def do_POST(self):
        if not self._authorized():
            self._reply(403, "forbidden")
            return
        path = self._path()
        payload = self._body()
        if payload is None:
            self._reply(400, "bad json")
            return
        try:
            if path == "/click":
                x, y = click_at(float(payload["u"]), float(payload["v"]))
                self._json_reply({"clicked": [x, y]})
            elif path == "/volume":
                functional.set_volume(int(payload["percent"]))
                self._json_reply(_state())
            elif path == "/mute":
                functional.mute_sound()
                self._json_reply(_state())
            elif path == "/power":
                action = payload["action"]
                if action not in POWER_ACTIONS:
                    self._json_reply({"error": "unknown action"}, 400)
                    return
                POWER_ACTIONS[action]()
                self._json_reply({"action": action})
            elif path == "/type":
                functional.type_text(str(payload["text"])[:2000])
                self._json_reply({"typed": True})
            elif path == "/key":
                key = str(payload["key"]).lower()
                if key not in functional.KEYS:
                    self._json_reply({"error": "unknown key"}, 400)
                    return
                functional.press_key(key)
                self._json_reply({"key": key})
            elif path == "/hotkey":
                combo = str(payload["combo"]).lower()
                if combo not in ALLOWED_HOTKEYS:
                    self._json_reply({"error": "unknown combo"}, 400)
                    return
                functional.press_hotkey(combo)
                self._json_reply({"combo": combo})
            else:
                self._reply(404, "not found")
        except Exception as error:
            self._json_reply({"error": str(error)}, 500)

    def log_message(self, *args):
        pass


def start(port, authtoken):
    global public_url, _server
    if public_url:
        return public_url
    _set_dpi_awareness()
    _server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=_server.serve_forever, daemon=True).start()
    from pyngrok import ngrok

    if authtoken:
        ngrok.set_auth_token(authtoken)
    tunnel = ngrok.connect(port, "http")
    public_url = tunnel.public_url
    return public_url
