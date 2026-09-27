import hashlib
import hmac
import json
from datetime import UTC, datetime
from urllib.parse import urlencode

import config
import functional
import remote


def check_volume_math():
    assert abs(functional._apply(0.3, 0.1) - 0.4) < 1e-9
    assert functional._apply(0.95, 0.1) == 1.0
    assert functional._apply(0.03, -0.1) == 0.0
    assert functional._clamp(1.5) == 1.0
    assert functional._clamp(-0.2) == 0.0
    assert functional._clamp(0.42) == 0.42


def make_init_data(user_id, tamper=False):
    pairs = {
        "auth_date": str(int(datetime.now(UTC).timestamp())),
        "user": json.dumps({"id": user_id}),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", config.TOKEN.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if tamper:
        digest = "0" * len(digest)
    return urlencode({**pairs, "hash": digest})


def check_init_data():
    assert remote.validate_init_data(make_init_data(config.ALLOWED_USER_ID)) is not None
    assert remote.validate_init_data(make_init_data(config.ALLOWED_USER_ID, tamper=True)) is None
    assert remote.validate_init_data(make_init_data(999999)) is None
    assert remote.validate_init_data("") is None


def check_map():
    monitor = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    assert remote._map(0, 0, monitor) == (0, 0)
    assert remote._map(0.5, 0.5, monitor) == (960, 540)
    assert remote._map(1, 1, monitor) == (1920, 1080)
    second = {"left": -1920, "top": 0, "width": 1920, "height": 1080}
    assert remote._map(0.5, 0.5, second) == (-960, 540)


def check_keyboard():
    assert functional._resolve_key("enter") == (0x0D, False)
    assert functional._resolve_key("up") == (0x26, True)
    assert functional._resolve_key("f5") == (0x74, False)
    assert functional._resolve_key("d") == (ord("D"), False)
    assert functional._resolve_key("??") is None
    for bad in ("foo+d", "d"):
        try:
            functional.press_hotkey(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {bad}")


if __name__ == "__main__":
    check_volume_math()
    check_init_data()
    check_map()
    check_keyboard()
    print("core OK")
