import ctypes
import subprocess
from contextlib import contextmanager
from ctypes import wintypes

import comtypes
from pycaw.pycaw import AudioUtilities

VOLUME_STEP = 0.02


@contextmanager
def _com():
    comtypes.CoInitialize()
    try:
        yield
    finally:
        comtypes.CoUninitialize()


def _run(command):
    subprocess.run(command, check=True)


def _speakers():
    return AudioUtilities.GetSpeakers().EndpointVolume


def _clamp(value):
    return min(1.0, max(0.0, value))


def _apply(current, delta):
    return _clamp(current + delta)


def _change_volume(delta):
    with _com():
        volume = _speakers()
        level = _apply(volume.GetMasterVolumeLevelScalar(), delta)
        volume.SetMasterVolumeLevelScalar(level, None)


def get_volume():
    with _com():
        return round(_speakers().GetMasterVolumeLevelScalar() * 100)


def get_mute():
    with _com():
        return bool(_speakers().GetMute())


def set_volume(percent):
    with _com():
        _speakers().SetMasterVolumeLevelScalar(_clamp(percent / 100), None)


def reduce_volume_by_2():
    _change_volume(-VOLUME_STEP)


def reduce_volume_by_10():
    _change_volume(-5 * VOLUME_STEP)


def increase_volume_by_2():
    _change_volume(VOLUME_STEP)


def increase_volume_by_10():
    _change_volume(5 * VOLUME_STEP)


def mute_sound():
    with _com():
        volume = _speakers()
        volume.SetMute(not volume.GetMute(), None)


def sleep_mode_pc():
    _run(
        [
            "powershell",
            "-Command",
            "Add-Type -AssemblyName System.Windows.Forms; "
            "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)",
        ]
    )


def shutdown_pc():
    _run(["shutdown", "/s", "/t", "10"])


def restart_pc():
    _run(["shutdown", "/r", "/t", "10"])


def logoff_pc():
    _run(["shutdown", "/l"])


def lock_pc():
    _run(["rundll32.exe", "user32.dll,LockWorkStation"])


_INPUT_KEYBOARD = 1
_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004

KEYS = {
    "enter": 0x0D,
    "esc": 0x1B,
    "backspace": 0x08,
    "tab": 0x09,
    "space": 0x20,
    "delete": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
}
KEYS.update({f"f{i}": 0x6F + i for i in range(1, 13)})
EXTENDED = {"delete", "insert", "home", "end", "pageup", "pagedown", "up", "down", "left", "right"}
MODIFIERS = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B}


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


_user32 = ctypes.windll.user32
_user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
_user32.SendInput.restype = wintypes.UINT


def _key_input(vk=0, scan=0, flags=0):
    item = _INPUT()
    item.type = _INPUT_KEYBOARD
    item.u.ki.wVk = vk
    item.u.ki.wScan = scan
    item.u.ki.dwFlags = flags
    item.u.ki.time = 0
    item.u.ki.dwExtraInfo = None
    return item


def _send(inputs):
    array = (_INPUT * len(inputs))(*inputs)
    _user32.SendInput(len(inputs), array, ctypes.sizeof(_INPUT))


def _resolve_key(name):
    name = name.lower()
    if name in KEYS:
        return KEYS[name], name in EXTENDED
    if len(name) == 1 and name.isalnum():
        return ord(name.upper()), False
    return None


def type_text(text):
    inputs = []
    for char in text:
        code = ord(char)
        if code > 0xFFFF:
            code -= 0x10000
            units = [0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)]
        else:
            units = [code]
        for unit in units:
            inputs.append(_key_input(scan=unit, flags=_KEYEVENTF_UNICODE))
            inputs.append(_key_input(scan=unit, flags=_KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP))
    if inputs:
        _send(inputs)


def press_key(name):
    resolved = _resolve_key(name)
    if resolved is None:
        raise ValueError(f"unknown key: {name}")
    vk, extended = resolved
    flags = _KEYEVENTF_EXTENDEDKEY if extended else 0
    _send([_key_input(vk=vk, flags=flags), _key_input(vk=vk, flags=flags | _KEYEVENTF_KEYUP)])


def press_hotkey(combo):
    parts = [part.strip() for part in combo.split("+") if part.strip()]
    if len(parts) < 2:
        raise ValueError(f"invalid combo: {combo}")
    *mods, key = parts
    modifier_vks = []
    for mod in mods:
        if mod.lower() not in MODIFIERS:
            raise ValueError(f"unknown modifier: {mod}")
        modifier_vks.append(MODIFIERS[mod.lower()])
    resolved = _resolve_key(key)
    if resolved is None:
        raise ValueError(f"unknown key: {key}")
    vk, extended = resolved
    key_flags = _KEYEVENTF_EXTENDEDKEY if extended else 0
    inputs = [_key_input(vk=v, flags=0) for v in modifier_vks]
    inputs.append(_key_input(vk=vk, flags=key_flags))
    inputs.append(_key_input(vk=vk, flags=key_flags | _KEYEVENTF_KEYUP))
    inputs.extend(_key_input(vk=v, flags=_KEYEVENTF_KEYUP) for v in reversed(modifier_vks))
    _send(inputs)
