#!/usr/bin/env python3
"""
KB2Controller — InputShield Edition (Windows 11)
─────────────────────────────────────────────────
Uses the InputShield kernel-mode filter driver to intercept keyboard & mouse
BEFORE Windows (and games using Raw Input / DirectInput) ever see them.

Prerequisites:
  1. pip install keyboard vgamepad
  2. Install InputShield driver (patch_driver.py + install-inputshield.cmd, reboot required)
  3. Place inputshield.dll next to this script (or in System32)
  4. Run this script as Administrator
"""

import sys, time, math, json, ctypes, threading, tkinter as tk, re
from tkinter import ttk, messagebox, filedialog, simpledialog
from pathlib import Path
from typing import Dict, Set, Tuple, Any, List, Optional

try:
    import keyboard
    import vgamepad as vg
except ImportError as exc:
    sys.exit(f"Missing dependency: {exc}\nRun: pip install keyboard vgamepad")

CONFIG_PATH = Path.home() / ".kb2controller_inputshield.json"


# ══════════════════════════════════════════════════════════════════════════════
# Interception Driver — ctypes wrapper
# ══════════════════════════════════════════════════════════════════════════════
INTERCEPTION_MAX_DEVICE = 20
MOUSE_LEFT_DOWN   = 0x001;  MOUSE_LEFT_UP   = 0x002
MOUSE_RIGHT_DOWN  = 0x004;  MOUSE_RIGHT_UP  = 0x008
MOUSE_MID_DOWN    = 0x010;  MOUSE_MID_UP    = 0x020
MOUSE_BTN4_DOWN   = 0x040;  MOUSE_BTN4_UP   = 0x080
MOUSE_BTN5_DOWN   = 0x100;  MOUSE_BTN5_UP   = 0x200
MOUSE_MOVE_RELATIVE = 0x000
MOUSE_MOVE_ABSOLUTE = 0x001
KEY_UP = 0x01
KEY_E0 = 0x02
FILTER_NONE      = 0x0000
FILTER_KEY_ALL   = 0xFFFF
FILTER_MOUSE_ALL = 0xFFFF


class _KeyStroke(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("state", ctypes.c_ushort),
                ("information", ctypes.c_uint)]

class _MouseStroke(ctypes.Structure):
    _fields_ = [("state", ctypes.c_ushort), ("flags", ctypes.c_ushort),
                ("rolling", ctypes.c_short), ("x", ctypes.c_int),
                ("y", ctypes.c_int), ("information", ctypes.c_uint)]

class _Stroke(ctypes.Union):
    _fields_ = [("key", _KeyStroke), ("mouse", _MouseStroke)]

_PredicateFn = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int)

_SC_TABLE: Dict[str, Tuple[int, bool]] = {
    'escape':(1,False),'esc':(1,False),
    '1':(2,False),'2':(3,False),'3':(4,False),'4':(5,False),'5':(6,False),
    '6':(7,False),'7':(8,False),'8':(9,False),'9':(10,False),'0':(11,False),
    '-':(12,False),'=':(13,False),'backspace':(14,False),'tab':(15,False),
    'q':(16,False),'w':(17,False),'e':(18,False),'r':(19,False),'t':(20,False),
    'y':(21,False),'u':(22,False),'i':(23,False),'o':(24,False),'p':(25,False),
    '[':(26,False),']':(27,False),'enter':(28,False),
    'ctrl':(29,False),'left ctrl':(29,False),'control':(29,False),
    'a':(30,False),'s':(31,False),'d':(32,False),'f':(33,False),'g':(34,False),
    'h':(35,False),'j':(36,False),'k':(37,False),'l':(38,False),
    ';':(39,False),"'":(40,False),'`':(41,False),
    'shift':(42,False),'left shift':(42,False),'\\':(43,False),
    'z':(44,False),'x':(45,False),'c':(46,False),'v':(47,False),'b':(48,False),
    'n':(49,False),'m':(50,False),',':(51,False),'.':(52,False),'/':(53,False),
    'right shift':(54,False),
    'alt':(56,False),'left alt':(56,False),'menu':(56,False),
    'space':(57,False),'caps lock':(58,False),'caps':(58,False),
    'f1':(59,False),'f2':(60,False),'f3':(61,False),'f4':(62,False),
    'f5':(63,False),'f6':(64,False),'f7':(65,False),'f8':(66,False),
    'f9':(67,False),'f10':(68,False),'num lock':(69,False),
    'scroll lock':(70,False),'f11':(87,False),'f12':(88,False),
    'up':(72,True),'down':(80,True),'left':(75,True),'right':(77,True),
    'insert':(82,True),'delete':(83,True),'del':(83,True),
    'home':(71,True),'end':(79,True),
    'page up':(73,True),'page down':(81,True),
    'right ctrl':(29,True),'right alt':(56,True),
    'windows':(91,True),'left windows':(91,True),'right windows':(92,True),
    'apps':(93,True),
}

def _name_to_sc(name: str) -> Optional[Tuple[int, bool]]:
    n = name.strip().lower()
    if n in _SC_TABLE:
        return _SC_TABLE[n]
    try:
        scodes = keyboard.key_to_scan_codes(n)
        if scodes:
            sc = scodes[0]
            return (sc & 0x7F, True) if sc > 0x7F else (sc, False)
    except Exception:
        pass
    return None


class InterceptionAPI:
    """Thin ctypes wrapper around inputshield.dll (renamed Interception fork)."""
    _DLL_PATHS = [
        Path(__file__).parent / "inputshield.dll",          # next to this script
        Path("C:/Windows/System32/inputshield.dll"),
        Path("C:/Program Files/InputShield/inputshield.dll"),
        # fallback: original dll name still works if you haven't renamed yet
        Path(__file__).parent / "interception.dll",
        Path("C:/Windows/System32/interception.dll"),
    ]

    def __init__(self):
        dll = None
        self._dll_name = None
        for p in self._DLL_PATHS:
            if p.exists():
                dll = ctypes.WinDLL(str(p))
                self._dll_name = p.name
                break
        if dll is None:
            for name in ("inputshield.dll", "interception.dll"):
                try:
                    dll = ctypes.WinDLL(name)
                    self._dll_name = name
                    break
                except OSError:
                    pass
        if dll is None:
            raise FileNotFoundError(
                "inputshield.dll not found.\n\nSteps:\n"
                "  1. Run tools/patch_driver.py to produce inputshield.sys\n"
                "  2. Run tools/install-inputshield.cmd /install as Administrator and REBOOT\n"
                "  3. Build inputshield.dll (library/buildit-x64.cmd) and copy it here"
            )
        self._dll = dll
        # Detect which export prefix this DLL uses
        self._pfx = self._detect_prefix()
        self._init_signatures()
        self.ctx = getattr(dll, f"{self._pfx}create_context")()
        if not self.ctx:
            raise RuntimeError(
                f"{self._pfx}create_context() returned NULL.\n"
                "Make sure the driver is installed and you're running as Administrator."
            )
        self._kbd_pred   = _PredicateFn(lambda d: getattr(self._dll, f"{self._pfx}is_keyboard")(d))
        self._mouse_pred = _PredicateFn(lambda d: getattr(self._dll, f"{self._pfx}is_mouse")(d))

    def _detect_prefix(self) -> str:
        """Auto-detect whether the DLL exports ishield_* or interception_* symbols."""
        for prefix in ("ishield_", "interception_"):
            try:
                getattr(self._dll, f"{prefix}create_context")
                return prefix
            except AttributeError:
                pass
        raise RuntimeError(
            f"{self._dll_name} does not export ishield_create_context or "
            "interception_create_context.  Is this the right DLL?"
        )

    def _fn(self, name):
        """Return dll.<prefix><name> e.g. dll.ishield_send"""
        return getattr(self._dll, f"{self._pfx}{name}")

    def _init_signatures(self):
        p = self._pfx
        d = self._dll
        getattr(d, f"{p}create_context").restype     = ctypes.c_void_p
        getattr(d, f"{p}create_context").argtypes    = []
        getattr(d, f"{p}destroy_context").restype    = None
        getattr(d, f"{p}destroy_context").argtypes   = [ctypes.c_void_p]
        getattr(d, f"{p}set_filter").restype         = None
        getattr(d, f"{p}set_filter").argtypes        = [ctypes.c_void_p, _PredicateFn, ctypes.c_ushort]
        getattr(d, f"{p}wait").restype               = ctypes.c_int
        getattr(d, f"{p}wait").argtypes              = [ctypes.c_void_p]
        getattr(d, f"{p}wait_with_timeout").restype  = ctypes.c_int
        getattr(d, f"{p}wait_with_timeout").argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        getattr(d, f"{p}receive").restype            = ctypes.c_int
        getattr(d, f"{p}receive").argtypes           = [ctypes.c_void_p, ctypes.c_int,
                                                        ctypes.c_void_p, ctypes.c_uint]
        getattr(d, f"{p}send").restype               = ctypes.c_int
        getattr(d, f"{p}send").argtypes              = [ctypes.c_void_p, ctypes.c_int,
                                                        ctypes.c_void_p, ctypes.c_uint]
        getattr(d, f"{p}get_hardware_id").restype    = ctypes.c_uint
        getattr(d, f"{p}get_hardware_id").argtypes   = [ctypes.c_void_p, ctypes.c_int,
                                                        ctypes.c_void_p, ctypes.c_uint]
        for fn in ("is_keyboard", "is_mouse", "is_invalid"):
            getattr(d, f"{p}{fn}").restype  = ctypes.c_int
            getattr(d, f"{p}{fn}").argtypes = [ctypes.c_int]

    def set_keyboard_filter(self, flt: int):
        self._fn("set_filter")(self.ctx, self._kbd_pred, ctypes.c_ushort(flt))

    def set_mouse_filter(self, flt: int):
        self._fn("set_filter")(self.ctx, self._mouse_pred, ctypes.c_ushort(flt))

    def wait(self, timeout_ms: int = 100) -> int:
        return self._fn("wait_with_timeout")(self.ctx, timeout_ms)

    def receive(self, device: int) -> Optional[_Stroke]:
        s = _Stroke()
        return s if self._fn("receive")(self.ctx, device, ctypes.byref(s), 1) > 0 else None

    def send(self, device: int, stroke: _Stroke):
        self._fn("send")(self.ctx, device, ctypes.byref(stroke), 1)

    def get_hardware_id(self, device: int) -> str:
        buf = ctypes.create_unicode_buffer(512)
        n = self._fn("get_hardware_id")(self.ctx, device, buf, ctypes.sizeof(buf))
        return buf.value if n > 0 else ""

    def is_keyboard(self, d: int) -> bool: return bool(self._fn("is_keyboard")(d))
    def is_mouse(self, d: int)    -> bool: return bool(self._fn("is_mouse")(d))
    def is_invalid(self, d: int)  -> bool: return bool(self._fn("is_invalid")(d))

    def enumerate_devices(self) -> List[Tuple[int, str, str]]:
        out = []
        for d in range(1, INTERCEPTION_MAX_DEVICE + 1):
            hw = self.get_hardware_id(d)
            if hw:
                out.append((d, "keyboard" if self.is_keyboard(d) else "mouse", hw))
        return out

    def destroy(self):
        if self.ctx:
            self._fn("destroy_context")(self.ctx)
            self.ctx = None


# ══════════════════════════════════════════════════════════════════════════════
# Controller State
# ══════════════════════════════════════════════════════════════════════════════
class ControllerState:
    def __init__(self):
        self._lock = threading.Lock()
        self.left_x = self.left_y = self.right_x = self.right_y = 0.0
        self.left_trigger = self.right_trigger = 0.0
        self.buttons: Set[str] = set()

    def set_axis(self, name: str, val: float):
        with self._lock:
            setattr(self, name, max(-1.0, min(1.0, float(val))))

    def get_axes(self):
        with self._lock:
            return (self.left_x, self.left_y, self.right_x, self.right_y,
                    self.left_trigger, self.right_trigger)

    def press(self, btn: str):
        with self._lock: self.buttons.add(btn)

    def release(self, btn: str):
        with self._lock: self.buttons.discard(btn)

    def snapshot_buttons(self):
        with self._lock: return frozenset(self.buttons)


# ══════════════════════════════════════════════════════════════════════════════
# Mouse → Right-Stick accumulator  (circular clamp)
# ══════════════════════════════════════════════════════════════════════════════
class MouseAccumulator:
    def __init__(self, state: ControllerState, sensitivity: float = 0.004):
        self._state = state
        self.sensitivity = sensitivity
        self._x = self._y = 0.0
        self._lock = threading.Lock()

    def on_move(self, dx: int, dy: int):
        with self._lock:
            self._x += dx * self.sensitivity
            self._y += dy * self.sensitivity
            mag = math.hypot(self._x, self._y)
            if mag > 1.0:
                self._x /= mag
                self._y /= mag
            self._state.set_axis("right_x", self._x)
            self._state.set_axis("right_y", self._y)

    def center(self):
        with self._lock:
            self._x = self._y = 0.0
            self._state.set_axis("right_x", 0.0)
            self._state.set_axis("right_y", 0.0)

    def get_pos(self):
        with self._lock: return self._x, self._y


# ══════════════════════════════════════════════════════════════════════════════
# Interception Capture Thread
# ══════════════════════════════════════════════════════════════════════════════
class InterceptionCapture:
    _MOUSE_BTN_EVENTS = [
        (MOUSE_LEFT_DOWN,  "left",   True),  (MOUSE_LEFT_UP,   "left",   False),
        (MOUSE_RIGHT_DOWN, "right",  True),  (MOUSE_RIGHT_UP,  "right",  False),
        (MOUSE_MID_DOWN,   "middle", True),  (MOUSE_MID_UP,    "middle", False),
        (MOUSE_BTN4_DOWN,  "x1",    True),   (MOUSE_BTN4_UP,   "x1",    False),
        (MOUSE_BTN5_DOWN,  "x2",    True),   (MOUSE_BTN5_UP,   "x2",    False),
    ]
    _F12_SC = 88

    def __init__(self, api, state, acc, mappings, blocked_devices, stop_cb):
        self._api      = api
        self._state    = state
        self._acc      = acc
        self._mappings = mappings
        self._blocked  = blocked_devices
        self._stop_cb  = stop_cb
        self._running  = False
        self._thread: Optional[threading.Thread] = None
        self._ls_held: Set[str] = set()
        self._sc_lookup: Dict[Tuple[int, bool], List[str]] = {}
        self._mb_lookup: Dict[str, List[str]] = {}
        self._rebuild_lookups()

    def _rebuild_lookups(self):
        self._sc_lookup.clear()
        self._mb_lookup.clear()
        for btn, mapping in self._mappings.items():
            typ, val = mapping[0], mapping[1]
            if typ == "key":
                sc_info = _name_to_sc(val.lower())
                if sc_info:
                    self._sc_lookup.setdefault(sc_info, []).append(btn)
            elif typ == "mouse_button":
                self._mb_lookup.setdefault(val.lower(), []).append(btn)

    def _dispatch(self, btn: str, pressed: bool):
        s = self._state
        if btn == "CENTER_RS":
            if pressed: self._acc.center()
            return
        if btn in ("LT", "RT"):
            s.set_axis("left_trigger" if btn == "LT" else "right_trigger",
                       1.0 if pressed else 0.0)
            return
        _LS = {"LS_UP": (0,-1), "LS_DOWN": (0,1), "LS_LEFT": (-1,0), "LS_RIGHT": (1,0)}
        if btn in _LS:
            if pressed: self._ls_held.add(btn)
            else:       self._ls_held.discard(btn)
            x = sum(_LS[b][0] for b in self._ls_held)
            y = sum(_LS[b][1] for b in self._ls_held)
            mag = math.hypot(x, y)
            if mag > 1.0: x /= mag; y /= mag
            s.set_axis("left_x", float(x)); s.set_axis("left_y", float(y))
            return
        if pressed: s.press(btn)
        else:       s.release(btn)

    def start(self):
        self._api.set_keyboard_filter(FILTER_KEY_ALL)
        self._api.set_mouse_filter(FILTER_MOUSE_ALL)
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True, name="IC-capture")
        self._thread.start()

    def stop(self):
        self._running = False
        self._api.set_keyboard_filter(FILTER_NONE)
        self._api.set_mouse_filter(FILTER_NONE)

    def _loop(self):
        while self._running:
            device = self._api.wait(timeout_ms=100)
            if not self._running: break
            if self._api.is_invalid(device): continue
            stroke = self._api.receive(device)
            if stroke is None: continue
            blocked = device in self._blocked
            if self._api.is_keyboard(device):
                ks      = stroke.key
                is_e0   = bool(ks.state & KEY_E0)
                is_down = not bool(ks.state & KEY_UP)
                if ks.code == self._F12_SC:
                    if not blocked: self._api.send(device, stroke)
                    if self._stop_cb: self._stop_cb()
                    continue
                for btn in self._sc_lookup.get((ks.code, is_e0), []):
                    self._dispatch(btn, is_down)
                if not blocked: self._api.send(device, stroke)
            elif self._api.is_mouse(device):
                ms = stroke.mouse
                if not (ms.flags & MOUSE_MOVE_ABSOLUTE):
                    if ms.x != 0 or ms.y != 0:
                        self._acc.on_move(ms.x, ms.y)
                for flag, btn_name, pressed in self._MOUSE_BTN_EVENTS:
                    if ms.state & flag:
                        for btn in self._mb_lookup.get(btn_name, []):
                            self._dispatch(btn, pressed)
                if not blocked: self._api.send(device, stroke)


# ══════════════════════════════════════════════════════════════════════════════
# vgamepad Output
# ══════════════════════════════════════════════════════════════════════════════
class WindowsController:
    def __init__(self, state: ControllerState):
        self._state = state
        self._gp    = vg.VX360Gamepad()
        self._prev  = frozenset()
        self._btn_map = {
            "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
            "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
            "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
            "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            "LB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
            "RB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
            "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
            "BACK": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
            "LS": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
            "RS": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
            "DPAD_UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
            "DPAD_DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
            "DPAD_LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
            "DPAD_RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
        }

    def update(self):
        s = self._state
        lx, ly, rx, ry, lt, rt = s.get_axes()
        self._gp.left_joystick_float(x_value_float=lx,  y_value_float=-ly)
        self._gp.right_joystick_float(x_value_float=rx, y_value_float=-ry)
        self._gp.left_trigger_float(value_float=lt)
        self._gp.right_trigger_float(value_float=rt)
        btns = s.snapshot_buttons()
        for b in btns - self._prev:
            if b in self._btn_map: self._gp.press_button(button=self._btn_map[b])
        for b in self._prev - btns:
            if b in self._btn_map: self._gp.release_button(button=self._btn_map[b])
        self._prev = btns
        self._gp.update()

    def close(self): pass


class OutputLoop:
    def __init__(self, ctrl: WindowsController, hz: int = 250):
        self._ctrl    = ctrl
        self._hz      = hz
        self._running = False

    def start(self):
        self._running = True
        threading.Thread(target=self._run, daemon=True, name="output-loop").start()

    def _run(self):
        interval = 1.0 / self._hz
        while self._running:
            t0 = time.perf_counter()
            self._ctrl.update()
            sleep = interval - (time.perf_counter() - t0)
            if sleep > 0: time.sleep(sleep)

    def stop(self): self._running = False


# ══════════════════════════════════════════════════════════════════════════════
# USB VID → Manufacturer
# ══════════════════════════════════════════════════════════════════════════════
_USB_VENDORS: Dict[str, str] = {
    "046d": "Logitech",      "045e": "Microsoft",    "1532": "Razer",
    "1b1c": "Corsair",       "1038": "SteelSeries",  "1e7d": "ROCCAT",
    "0951": "HyperX",        "2516": "Cooler Master","3367": "Endgame Gear",
    "0458": "Genius",        "054c": "Sony",         "04b4": "Cypress",
    "04d9": "Holtek",        "04f2": "Chicony",      "0461": "Primax",
    "093a": "Pixart",        "0c45": "Sonix",        "1d57": "Xenta",
    "258a": "Sinowealth",    "25a7": "Areson",       "0e8f": "GreenAsia",
    "24ae": "Sharkoon",      "2dc8": "8BitDo",       "057e": "Nintendo",
    "045f": "Microsoft Xbox","0955": "NVIDIA",       "0bda": "Realtek",
    "05ac": "Apple",         "03f0": "HP",           "413c": "Dell",
    "17ef": "Lenovo",        "04ca": "Lite-On",      "0557": "ATEN",
    "1a2c": "China Resource","0518": "EzKEY",        "0416": "Winbond",
    "1c4f": "SiGma Micro",   "04fc": "Sunplus",      "062a": "Creative",
    "1a81": "Holtek Gaming", "0738": "Mad Catz",     "0079": "DragonRise",
    "2563": "ShenZhen",      "0483": "STMicro",      "2f68": "SteelSeries Alt",
}

def _manufacturer_from_hwid(hw_id: str) -> str:
    m = re.search(r'VID_([0-9A-Fa-f]{4})', hw_id)
    if not m:
        return ""
    return _USB_VENDORS.get(m.group(1).lower(), "")


# ══════════════════════════════════════════════════════════════════════════════
# Config
# ══════════════════════════════════════════════════════════════════════════════
DEFAULT_MAPPINGS: Dict[str, list] = {
    "A":          ["key",          "space"],
    "B":          ["key",          "e"],
    "X":          ["key",          "r"],
    "Y":          ["key",          "f"],
    "LB":         ["key",          "q"],
    "RB":         ["key",          "shift"],
    "LT":         ["mouse_button", "right"],
    "RT":         ["mouse_button", "left"],
    "START":      ["key",          "esc"],
    "BACK":       ["key",          "tab"],
    "LS":         ["key",          "ctrl"],
    "RS":         ["mouse_button", "middle"],
    "DPAD_UP":    ["key",          "up"],
    "DPAD_DOWN":  ["key",          "down"],
    "DPAD_LEFT":  ["key",          "left"],
    "DPAD_RIGHT": ["key",          "right"],
    "LS_UP":      ["key",          "w"],
    "LS_DOWN":    ["key",          "s"],
    "LS_LEFT":    ["key",          "a"],
    "LS_RIGHT":   ["key",          "d"],
    "CENTER_RS":  ["key",          "alt"],
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "mouse_sensitivity":  0.004,
    "output_hz":          250,
    "blocked_devices":    [],
    "mappings":           DEFAULT_MAPPINGS,
    # {"Cat Name": {"device_ids": [1, 3], "enabled": true}}
    "device_categories":  {},
}

def load_config(path: Path = CONFIG_PATH) -> Dict[str, Any]:
    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
            cfg = dict(DEFAULT_CONFIG)
            cfg.update({k: v for k, v in data.items() if k != "mappings"})
            cfg["mappings"] = {**DEFAULT_MAPPINGS, **data.get("mappings", {})}
            cfg.setdefault("device_categories", {})
            return cfg
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg: Dict[str, Any], path: Path = CONFIG_PATH):
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)

def _collect_all_blocked(cfg: Dict[str, Any]) -> Set[int]:
    """Union of individually blocked devices + all enabled-category devices."""
    blocked: Set[int] = set(cfg.get("blocked_devices", []))
    for cat_data in cfg.get("device_categories", {}).values():
        if cat_data.get("enabled", False):
            blocked.update(cat_data.get("device_ids", []))
    return blocked


# ══════════════════════════════════════════════════════════════════════════════
# Theme / Fonts
# ══════════════════════════════════════════════════════════════════════════════
DARK_BG  = "#0d0f14"
PANEL_BG = "#13161e"
CARD_BG  = "#1a1e2a"
ACCENT   = "#00e5ff"
ACCENT2  = "#7c3aed"
TEXT     = "#e2e8f0"
TEXT_DIM = "#94a3b8"
SUCCESS  = "#22c55e"
WARNING  = "#f59e0b"
DANGER   = "#ef4444"
BORDER   = "#2a2f3e"
CAT_HDR  = "#1e2235"

F_TITLE  = ("Segoe UI", 20, "bold")
F_CARD   = ("Segoe UI", 11, "bold")
F_BTN    = ("Segoe UI", 10, "bold")
F_BTN_SM = ("Segoe UI",  9)
F_LABEL  = ("Segoe UI", 10)
F_DIM    = ("Segoe UI",  9)
F_BIND   = ("Segoe UI", 10, "bold")
F_DEV    = ("Segoe UI", 10, "bold")
F_DEV_HW = ("Segoe UI",  8)
F_MONO   = ("Courier New", 11)
F_STATUS = ("Segoe UI", 12, "bold")
F_AXIS   = ("Courier New", 12)
F_GRP    = ("Segoe UI",  9, "bold")


# ══════════════════════════════════════════════════════════════════════════════
# Scrollable Frame
# ══════════════════════════════════════════════════════════════════════════════
class ScrollFrame(tk.Frame):
    def __init__(self, parent, bg=CARD_BG, **kw):
        super().__init__(parent, bg=bg, **kw)
        vsb = tk.Scrollbar(self, orient="vertical",
                           bg=DARK_BG, troughcolor=PANEL_BG, activebackground=ACCENT)
        vsb.pack(side="right", fill="y")
        self._canvas = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0,
                                  yscrollcommand=vsb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        vsb.config(command=self._canvas.yview)
        self.inner = tk.Frame(self._canvas, bg=bg)
        self._win  = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(
            self._win, width=e.width))
        for w in (self._canvas, self.inner):
            w.bind("<MouseWheel>", self._scroll)

    def _scroll(self, e):
        self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def bind_scroll(self, widget):
        widget.bind("<MouseWheel>", self._scroll)


# ══════════════════════════════════════════════════════════════════════════════
# Application
# ══════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KB2Controller — InputShield Edition")
        self.configure(bg=DARK_BG)
        self.minsize(1320, 780)

        self.cfg   = load_config()
        self.state = ControllerState()
        self.acc   = MouseAccumulator(self.state, self.cfg["mouse_sensitivity"])

        self._api:      Optional[InterceptionAPI]     = None
        self._capture:  Optional[InterceptionCapture] = None
        self._ctrl_hw:  Optional[WindowsController]   = None
        self._out_loop: Optional[OutputLoop]          = None
        self._active    = False

        self._dev_list: List[Tuple[int, str, str]] = []
        self._dev_vars: Dict[int, tk.BooleanVar]   = {}
        self._cat_vars: Dict[str, tk.BooleanVar]   = {}   # prevent GC of category BooleanVars
        self._bind_btns: Dict[str, tk.Button]      = {}

        self._try_load_api()
        self._build_ui()
        self._refresh_devices()
        self._ui_tick()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── driver ────────────────────────────────────────────────────────────────
    def _try_load_api(self):
        try:
            self._api = InterceptionAPI()
            self._api_error = None
        except Exception as exc:
            self._api = None
            self._api_error = str(exc)

    def _autosave(self):
        try: save_config(self.cfg)
        except Exception: pass

    # ══════════════════════════════════════════════════════════════════════════
    # UI skeleton
    # ══════════════════════════════════════════════════════════════════════════
    def _build_ui(self):
        # title bar
        top = tk.Frame(self, bg=DARK_BG, pady=12, padx=20)
        top.pack(fill="x")
        tk.Label(top, text="KB2Controller", bg=DARK_BG,
                 fg=ACCENT, font=F_TITLE).pack(side="left")
        self._status_lbl = tk.Label(top, text="● STOPPED",
                                     bg=DARK_BG, fg=DANGER, font=F_STATUS)
        self._status_lbl.pack(side="right", padx=8)
        drv_ok   = self._api is not None
        drv_text = (f"✓ InputShield driver loaded ({self._api._dll_name})" if drv_ok
                    else f"✗ Driver not found — {self._api_error or 'unknown'}")
        tk.Label(top, text=drv_text, bg=DARK_BG,
                 fg=SUCCESS if drv_ok else DANGER, font=F_DIM).pack(side="right", padx=20)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # three-column body
        body = tk.Frame(self, bg=DARK_BG)
        body.pack(fill="both", expand=True, padx=14, pady=10)

        left = tk.Frame(body, bg=DARK_BG)
        left.pack(side="left", fill="both", expand=True)
        tk.Frame(body, bg=BORDER, width=1).pack(side="left", fill="y", padx=8)
        center = tk.Frame(body, bg=DARK_BG, width=420)
        center.pack(side="left", fill="y")
        center.pack_propagate(False)
        tk.Frame(body, bg=BORDER, width=1).pack(side="left", fill="y", padx=8)
        right = tk.Frame(body, bg=DARK_BG, width=305)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self._build_bindings_panel(left)
        self._build_devices_panel(center)
        self._build_settings_panel(right)

        # bottom bar
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        bot = tk.Frame(self, bg=DARK_BG, pady=12, padx=20)
        bot.pack(fill="x")

        self._toggle_btn = tk.Button(
            bot, text="▶   START", command=self._toggle,
            bg=ACCENT2, fg="white", relief="flat", padx=30, pady=11,
            font=("Segoe UI", 13, "bold"), cursor="hand2",
            state="normal" if self._api else "disabled"
        )
        self._toggle_btn.pack(side="left")

        for txt, cmd in [("  💾  Save", self._save),
                          ("  📤  Export Config", self._export_config),
                          ("  📥  Import Config", self._import_config)]:
            tk.Button(bot, text=txt, command=cmd, bg=CARD_BG, fg=TEXT,
                      relief="flat", padx=16, pady=11,
                      font=F_BTN, cursor="hand2").pack(side="left", padx=6)

        tk.Label(bot, text="F12 = Emergency stop",
                 bg=DARK_BG, fg=TEXT_DIM, font=F_DIM).pack(side="right")

    # ══════════════════════════════════════════════════════════════════════════
    # Key Bindings Panel
    # ══════════════════════════════════════════════════════════════════════════
    def _build_bindings_panel(self, parent):
        hdr = tk.Frame(parent, bg=DARK_BG)
        hdr.pack(fill="x", pady=(0, 8))
        tk.Label(hdr, text="KEY  BINDINGS", bg=DARK_BG,
                 fg=ACCENT, font=F_CARD).pack(side="left")
        tk.Label(hdr, text="(stop before rebinding)",
                 bg=DARK_BG, fg=TEXT_DIM, font=F_DIM).pack(side="left", padx=10)

        sf = ScrollFrame(parent, bg=DARK_BG)
        sf.pack(fill="both", expand=True)
        card = sf.inner

        groups = [
            ("Face Buttons",  ["A", "B", "X", "Y"]),
            ("Shoulders",     ["LB", "RB", "LT", "RT"]),
            ("Menu / Sticks", ["START", "BACK", "LS", "RS"]),
            ("D-Pad",         ["DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT"]),
            ("Left Stick",    ["LS_UP", "LS_DOWN", "LS_LEFT", "LS_RIGHT"]),
            ("Misc",          ["CENTER_RS"]),
        ]

        for group_name, keys in groups:
            grp = tk.Frame(card, bg=CARD_BG,
                            highlightbackground=BORDER, highlightthickness=1)
            grp.pack(fill="x", pady=5, padx=2)
            tk.Label(grp, text=group_name.upper(), bg=CARD_BG,
                     fg=TEXT_DIM, font=F_GRP, padx=10, pady=6).pack(anchor="w")
            row = tk.Frame(grp, bg=CARD_BG)
            row.pack(fill="x", padx=10, pady=(0, 10))
            for k in keys:
                _typ, val = self.cfg["mappings"].get(k, ["key", "?"])
                b = tk.Button(
                    row, text=f"{k}\n[{val}]",
                    bg=PANEL_BG, fg=TEXT, relief="flat",
                    width=9, height=2,
                    font=F_BIND, cursor="hand2",
                    command=lambda key=k: self._rebind(key)
                )
                b.pack(side="left", padx=4)
                self._bind_btns[k] = b
                sf.bind_scroll(b)

    # ══════════════════════════════════════════════════════════════════════════
    # Device Blocker Panel
    # ══════════════════════════════════════════════════════════════════════════
    def _build_devices_panel(self, parent):
        hdr = tk.Frame(parent, bg=DARK_BG)
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(hdr, text="DEVICE  BLOCKER", bg=DARK_BG,
                 fg=ACCENT, font=F_CARD).pack(side="left")

        # toolbar
        tb = tk.Frame(parent, bg=DARK_BG)
        tb.pack(fill="x", pady=(0, 6))
        for txt, cmd in [("⟳  Refresh", self._refresh_devices),
                          ("＋  New Category", self._create_category)]:
            tk.Button(tb, text=txt, command=cmd,
                      bg=CARD_BG, fg=TEXT, relief="flat",
                      padx=12, pady=6, font=F_BTN_SM,
                      cursor="hand2").pack(side="left", padx=3)

        tk.Label(parent,
                 text="☑ = hidden from Windows & games   ☐ = passes through as normal",
                 bg=DARK_BG, fg=TEXT_DIM, font=F_DIM).pack(anchor="w", pady=(0, 6))

        self._dev_scroll = ScrollFrame(parent, bg=DARK_BG)
        self._dev_scroll.pack(fill="both", expand=True)
        self._dev_area = self._dev_scroll.inner

    # ── populate device area ──────────────────────────────────────────────────
    def _refresh_devices(self):
        for w in self._dev_area.winfo_children():
            w.destroy()
        self._dev_vars.clear()
        self._cat_vars.clear()

        if not self._api:
            tk.Label(self._dev_area,
                     text="Driver not loaded — check installation.",
                     bg=DARK_BG, fg=DANGER, font=F_DIM).pack(anchor="w", pady=8)
            return

        try:
            self._dev_list = self._api.enumerate_devices()
        except Exception:
            self._dev_list = []

        if not self._dev_list:
            tk.Label(self._dev_area,
                     text="No devices found.\nPlug in devices and hit Refresh.",
                     bg=DARK_BG, fg=TEXT_DIM, font=F_DIM,
                     justify="left").pack(anchor="w", pady=8)
            return

        individually_blocked = set(self.cfg.get("blocked_devices", []))
        categories = self.cfg.get("device_categories", {})
        categorised: Set[int] = set()
        for cd in categories.values():
            categorised.update(cd.get("device_ids", []))

        # Uncategorised section
        uncategorised = [d for d in self._dev_list if d[0] not in categorised]
        if uncategorised:
            self._render_plain_section("Uncategorised", uncategorised,
                                        individually_blocked)

        # Category sections
        for cat_name, cat_data in list(categories.items()):
            cat_ids  = set(cat_data.get("device_ids", []))
            cat_devs = [d for d in self._dev_list if d[0] in cat_ids]
            self._render_category_section(cat_name, cat_devs,
                                           cat_data.get("enabled", False))

    def _render_plain_section(self, title, devices, individually_blocked):
        sec = tk.Frame(self._dev_area, bg=CARD_BG,
                       highlightbackground=BORDER, highlightthickness=1)
        sec.pack(fill="x", pady=4, padx=2)
        tk.Label(sec, text=title.upper(), bg=CARD_BG,
                 fg=TEXT_DIM, font=F_GRP, padx=10, pady=6).pack(anchor="w")
        for dev_id, kind, hw_id in devices:
            self._render_device_row(sec, dev_id, kind, hw_id,
                                     individually_blocked, cat_name=None,
                                     bg=CARD_BG)

    def _render_category_section(self, cat_name, devices, enabled):
        outer = tk.Frame(self._dev_area, bg=CAT_HDR,
                         highlightbackground=ACCENT2, highlightthickness=1)
        outer.pack(fill="x", pady=5, padx=2)

        # header
        hdr = tk.Frame(outer, bg=CAT_HDR)
        hdr.pack(fill="x")

        cat_var = tk.BooleanVar(value=enabled)
        self._cat_vars[cat_name] = cat_var 

        def on_toggle(cv=cat_var, cn=cat_name):
            self.cfg["device_categories"][cn]["enabled"] = cv.get()
            self._autosave()

        tk.Checkbutton(hdr, variable=cat_var, command=on_toggle,
                    bg=CAT_HDR, fg=TEXT, selectcolor=ACCENT2,
                    activebackground=CAT_HDR, cursor="hand2").pack(side="left", padx=(10, 0), pady=8)

        tk.Label(hdr, text=f"📁  {cat_name}", bg=CAT_HDR,
                 fg=ACCENT, font=("Segoe UI", 11, "bold")).pack(side="left", padx=4)

        n = len(devices)
        tk.Label(hdr, text=f"({n} device{'s' if n != 1 else ''})",
                 bg=CAT_HDR, fg=TEXT_DIM, font=F_DIM).pack(side="left", padx=4)

        # rename / delete
        btns = tk.Frame(hdr, bg=CAT_HDR)
        btns.pack(side="right", padx=10, pady=6)
        tk.Button(btns, text="✏ Rename",
                  command=lambda cn=cat_name: self._rename_category(cn),
                  bg=PANEL_BG, fg=TEXT_DIM, relief="flat",
                  padx=10, pady=4, font=F_BTN_SM,
                  cursor="hand2").pack(side="left", padx=2)
        tk.Button(btns, text="✕ Delete",
                  command=lambda cn=cat_name: self._delete_category(cn),
                  bg=PANEL_BG, fg=DANGER, relief="flat",
                  padx=10, pady=4, font=F_BTN_SM,
                  cursor="hand2").pack(side="left", padx=2)

        tk.Frame(outer, bg=BORDER, height=1).pack(fill="x")

        if devices:
            for dev_id, kind, hw_id in devices:
                self._render_device_row(outer, dev_id, kind, hw_id,
                                         set(), cat_name=cat_name,
                                         bg=CAT_HDR, inside_cat=True)
        else:
            tk.Label(outer, text="  (no devices assigned — use 'Assign to category')",
                     bg=CAT_HDR, fg=TEXT_DIM, font=F_DIM,
                     pady=6).pack(anchor="w", padx=10)

    def _render_device_row(self, parent, dev_id, kind, hw_id,
                            individually_blocked, cat_name, bg, inside_cat=False):
        mfr  = _manufacturer_from_hwid(hw_id) or "Unknown Manufacturer"
        icon = "⌨" if kind == "keyboard" else "🖱"

        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", padx=12, pady=4)

        # checkbox (only for uncategorised)
        if not inside_cat:
            var = tk.BooleanVar(value=(dev_id in individually_blocked))
            self._dev_vars[dev_id] = var

            def on_dev(dv=var, did=dev_id):
                bl = set(self.cfg.get("blocked_devices", []))
                if dv.get(): bl.add(did)
                else:        bl.discard(did)
                self.cfg["blocked_devices"] = list(bl)
                self._autosave()

            tk.Checkbutton(row, variable=var, command=on_dev,
                    bg=bg, fg=TEXT, selectcolor=ACCENT2,
                    activebackground=bg, cursor="hand2").pack(side="left")

        # device info
        info = tk.Frame(row, bg=bg)
        info.pack(side="left", fill="x", expand=True, padx=(4, 0))
        tk.Label(info, text=f"{icon}  {mfr}", bg=bg,
                 fg=TEXT, font=F_DEV, anchor="w").pack(anchor="w")
        tk.Label(info, text=f"   {hw_id[:52]}", bg=bg,
                 fg=TEXT_DIM, font=F_DEV_HW, anchor="w").pack(anchor="w")

        # assign / remove button
        bf = tk.Frame(row, bg=bg)
        bf.pack(side="right")
        if inside_cat:
            tk.Button(bf, text="Remove",
                      command=lambda did=dev_id, cn=cat_name: self._remove_from_category(did, cn),
                      bg=PANEL_BG, fg=WARNING, relief="flat",
                      padx=10, pady=4, font=F_BTN_SM,
                      cursor="hand2").pack()
        else:
            if self.cfg.get("device_categories"):
                tk.Button(bf, text="Assign →",
                          command=lambda did=dev_id, dk=kind, dh=hw_id: self._assign_to_category(did, dk, dh),
                          bg=PANEL_BG, fg=ACCENT, relief="flat",
                          padx=10, pady=4, font=F_BTN_SM,
                          cursor="hand2").pack()

    # ── category management ───────────────────────────────────────────────────
    def _create_category(self):
        name = simpledialog.askstring("New Category", "Category name:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        cats = self.cfg.setdefault("device_categories", {})
        if name in cats:
            messagebox.showerror("Duplicate", f'Category "{name}" already exists.')
            return
        cats[name] = {"device_ids": [], "enabled": False}
        self._autosave()
        self._refresh_devices()

    def _rename_category(self, old: str):
        new = simpledialog.askstring("Rename", "New name:", parent=self, initialvalue=old)
        if not new or not new.strip():
            return
        new = new.strip()
        cats = self.cfg.get("device_categories", {})
        if new in cats and new != old:
            messagebox.showerror("Duplicate", f'Category "{new}" already exists.')
            return
        cats[new] = cats.pop(old)
        self._autosave()
        self._refresh_devices()

    def _delete_category(self, cat_name: str):
        if not messagebox.askyesno("Delete Category",
                                    f'Delete "{cat_name}"?\nDevices return to Uncategorised.'):
            return
        self.cfg.get("device_categories", {}).pop(cat_name, None)
        self._autosave()
        self._refresh_devices()

    def _assign_to_category(self, dev_id: int, kind: str, hw_id: str):
        cats = list(self.cfg.get("device_categories", {}).keys())
        if not cats:
            messagebox.showinfo("No Categories",
                                "Create a category first with '＋ New Category'.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Assign to Category")
        dlg.configure(bg=DARK_BG)
        dlg.geometry("340x280")
        dlg.grab_set()
        dlg.resizable(False, False)

        mfr  = _manufacturer_from_hwid(hw_id) or "Unknown"
        icon = "⌨" if kind == "keyboard" else "🖱"
        tk.Label(dlg, text="Assign Device to Category",
                 bg=DARK_BG, fg=ACCENT, font=("Segoe UI", 13, "bold")).pack(pady=(16, 4))
        tk.Label(dlg, text=f"{icon}  {mfr}", bg=DARK_BG,
                 fg=TEXT, font=F_LABEL).pack()
        tk.Label(dlg, text=hw_id[:46], bg=DARK_BG,
                 fg=TEXT_DIM, font=("Segoe UI", 8)).pack()
        tk.Label(dlg, text="Select category:", bg=DARK_BG,
                 fg=TEXT_DIM, font=F_DIM).pack(pady=(10, 4))

        sel = tk.StringVar(value=cats[0])
        for c in cats:
            tk.Radiobutton(dlg, text=c, variable=sel, value=c,
                           bg=DARK_BG, fg=TEXT, selectcolor=DARK_BG,
                           activebackground=DARK_BG, font=F_LABEL,
                           cursor="hand2").pack(anchor="w", padx=50)

        def confirm():
            cat_data = self.cfg["device_categories"][sel.get()]
            if dev_id not in cat_data["device_ids"]:
                cat_data["device_ids"].append(dev_id)
            bl = set(self.cfg.get("blocked_devices", []))
            bl.discard(dev_id)
            self.cfg["blocked_devices"] = list(bl)
            self._autosave()
            dlg.destroy()
            self._refresh_devices()

        tk.Button(dlg, text="Assign", command=confirm,
                  bg=ACCENT2, fg="white", relief="flat",
                  padx=20, pady=8, font=F_BTN,
                  cursor="hand2").pack(pady=12)

    def _remove_from_category(self, dev_id: int, cat_name: str):
        cd = self.cfg.get("device_categories", {}).get(cat_name)
        if cd and dev_id in cd["device_ids"]:
            cd["device_ids"].remove(dev_id)
            self._autosave()
            self._refresh_devices()

    # ══════════════════════════════════════════════════════════════════════════
    # Settings Panel
    # ══════════════════════════════════════════════════════════════════════════
    def _build_settings_panel(self, parent):
        tk.Label(parent, text="MOUSE → STICK", bg=DARK_BG,
                 fg=ACCENT, font=F_CARD).pack(anchor="w", pady=(0, 8))

        # sensitivity
        sens_card = tk.Frame(parent, bg=CARD_BG,
                              highlightbackground=BORDER, highlightthickness=1)
        sens_card.pack(fill="x", pady=4)
        si = tk.Frame(sens_card, bg=CARD_BG, padx=12, pady=10)
        si.pack(fill="x")

        self._sens_var = tk.DoubleVar(value=self.cfg["mouse_sensitivity"])

        def on_sens(_=None):
            v = round(self._sens_var.get(), 4)
            self.acc.sensitivity = v
            self.cfg["mouse_sensitivity"] = v
            self._sens_lbl.config(text=f"{v:.4f}")
            self._autosave()

        tk.Label(si, text="Sensitivity (displacement per pixel)",
                 bg=CARD_BG, fg=TEXT_DIM, font=F_DIM).pack(anchor="w")
        sr = tk.Frame(si, bg=CARD_BG)
        sr.pack(fill="x", pady=6)
        self._sens_lbl = tk.Label(sr, text=f"{self.cfg['mouse_sensitivity']:.4f}",
                                   bg=CARD_BG, fg=ACCENT, font=F_MONO, width=8)
        self._sens_lbl.pack(side="right")
        ttk.Scale(sr, from_=0.0005, to=0.03, variable=self._sens_var,
                  command=on_sens).pack(side="left", fill="x", expand=True)
        tk.Label(si,
                 text="Mouse stops → stick holds.\nAlt (CENTER_RS) snaps to centre.",
                 bg=CARD_BG, fg=TEXT_DIM, font=F_DIM,
                 justify="left").pack(anchor="w", pady=(4, 0))

        # live RS position
        rs_card = tk.Frame(parent, bg=CARD_BG,
                            highlightbackground=BORDER, highlightthickness=1)
        rs_card.pack(fill="x", pady=8)
        ri = tk.Frame(rs_card, bg=CARD_BG, padx=12, pady=10)
        ri.pack(fill="x")
        tk.Label(ri, text="RIGHT STICK LIVE", bg=CARD_BG,
                 fg=ACCENT, font=F_GRP).pack(anchor="w")
        self._rs_lbl = tk.Label(ri, text="X: +0.000   Y: +0.000",
                                 bg=CARD_BG, fg=ACCENT, font=F_AXIS)
        self._rs_lbl.pack(pady=6)
        tk.Button(ri, text="Re-center RS", command=self.acc.center,
                  bg=PANEL_BG, fg=TEXT, relief="flat",
                  padx=14, pady=6, font=F_BTN_SM,
                  cursor="hand2").pack()

        # output hz
        hz_card = tk.Frame(parent, bg=CARD_BG,
                            highlightbackground=BORDER, highlightthickness=1)
        hz_card.pack(fill="x", pady=4)
        hi = tk.Frame(hz_card, bg=CARD_BG, padx=12, pady=10)
        hi.pack(fill="x")

        self._hz_var = tk.IntVar(value=self.cfg.get("output_hz", 250))

        def on_hz(_=None):
            v = int(self._hz_var.get())
            self.cfg["output_hz"] = v
            self._hz_lbl.config(text=f"{v} Hz")
            self._autosave()

        tk.Label(hi, text="Output polling rate", bg=CARD_BG,
                 fg=TEXT_DIM, font=F_DIM).pack(anchor="w")
        hr = tk.Frame(hi, bg=CARD_BG)
        hr.pack(fill="x", pady=6)
        self._hz_lbl = tk.Label(hr, text=f"{self._hz_var.get()} Hz",
                                 bg=CARD_BG, fg=ACCENT, font=F_MONO, width=8)
        self._hz_lbl.pack(side="right")
        ttk.Scale(hr, from_=60, to=1000, variable=self._hz_var,
                  command=on_hz).pack(side="left", fill="x", expand=True)

    # ══════════════════════════════════════════════════════════════════════════
    # Start / Stop
    # ══════════════════════════════════════════════════════════════════════════
    def _toggle(self):
        if self._active: self._stop()
        else:            self._start()

    def _start(self):
        if not self._api:
            messagebox.showerror("Driver Error", "InputShield driver not available.")
            return
        blocked = _collect_all_blocked(self.cfg)
        if not blocked:
            if not messagebox.askyesno(
                "No devices blocked",
                "No devices are blocked.\nGames will still receive raw input.\n\nContinue anyway?"
            ):
                return
        try:
            self.acc       = MouseAccumulator(self.state, self.cfg["mouse_sensitivity"])
            self._ctrl_hw  = WindowsController(self.state)
            self._out_loop = OutputLoop(self._ctrl_hw, self.cfg["output_hz"])
            self._out_loop.start()
            self._capture  = InterceptionCapture(
                self._api, self.state, self.acc,
                self.cfg["mappings"], blocked, self._stop_from_thread
            )
            self._capture.start()
            self._active = True
            self._toggle_btn.config(text="■   STOP", bg=DANGER)
            self._status_lbl.config(text="● RUNNING", fg=SUCCESS)
            for b in self._bind_btns.values(): b.config(state="disabled")
        except Exception as exc:
            messagebox.showerror("Start Error", f"Failed to start:\n{exc}")

    def _stop(self):
        if self._capture:  self._capture.stop();  self._capture = None
        if self._out_loop: self._out_loop.stop();  self._out_loop = None
        if self._ctrl_hw:  self._ctrl_hw.close();  self._ctrl_hw = None
        self._active = False
        self._toggle_btn.config(text="▶   START", bg=ACCENT2)
        self._status_lbl.config(text="● STOPPED", fg=DANGER)
        for b in self._bind_btns.values(): b.config(state="normal")

    def _stop_from_thread(self):
        self.after(0, self._stop)

    # ══════════════════════════════════════════════════════════════════════════
    # Rebind dialog
    # ══════════════════════════════════════════════════════════════════════════
    def _rebind(self, button_key: str):
        if self._active:
            messagebox.showinfo("Stop First", "Stop the controller before rebinding.")
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Rebind: {button_key}")
        dlg.configure(bg=DARK_BG)
        dlg.geometry("420x250")
        dlg.grab_set()
        dlg.resizable(False, False)

        tk.Label(dlg, text=f"Rebind  {button_key}",
                 bg=DARK_BG, fg=ACCENT,
                 font=("Segoe UI", 14, "bold")).pack(pady=20)
        result_var = tk.StringVar(value="Press any key or click a mouse button…")
        tk.Label(dlg, textvariable=result_var,
                 bg=DARK_BG, fg=TEXT, font=F_LABEL).pack(pady=8)

        captured: Dict[str, Any] = {"type": None, "val": None}
        confirm_btn = tk.Button(dlg, text="Confirm",
                                 bg=ACCENT2, fg="white", relief="flat",
                                 padx=22, pady=9, font=F_BTN, cursor="hand2")

        def kbd_capture(e):
            if e.event_type == "down":
                captured["type"] = "key"
                captured["val"]  = str(e.name).lower()
                dlg.after(0, lambda: result_var.set(f"Key: {captured['val']}"))

        hook_id = keyboard.hook(kbd_capture)

        def on_mouse(e):
            if e.widget == confirm_btn: return
            bmap = {1:"left", 2:"middle", 3:"right", 4:"x1", 5:"x2", 8:"x1", 9:"x2"}
            n = bmap.get(e.num, str(e.num))
            captured["type"] = "mouse_button"
            captured["val"]  = n
            result_var.set(f"Mouse button: {n}")

        dlg.bind("<ButtonPress>", on_mouse)

        def confirm():
            keyboard.unhook(hook_id)
            if captured["type"]:
                self.cfg["mappings"][button_key] = [captured["type"], captured["val"]]
                self._bind_btns[button_key].config(
                    text=f"{button_key}\n[{captured['val']}]")
                self._autosave()
            dlg.destroy()

        def on_close():
            keyboard.unhook(hook_id)
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", on_close)
        confirm_btn.config(command=confirm)
        confirm_btn.pack(pady=10)

    # ══════════════════════════════════════════════════════════════════════════
    # Config: save / export / import
    # ══════════════════════════════════════════════════════════════════════════
    def _save(self):
        save_config(self.cfg)
        messagebox.showinfo("Saved", f"Config saved to:\n{CONFIG_PATH}")

    def _export_config(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="Export Config",
            defaultextension=".json",
            filetypes=[("JSON config", "*.json"), ("All files", "*.*")],
            initialfile="kb2controller_config.json",
        )
        if not path:
            return
        try:
            save_config(self.cfg, Path(path))
            messagebox.showinfo("Exported", f"Config exported to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc))

    def _import_config(self):
        path = filedialog.askopenfilename(
            parent=self, title="Import Config",
            filetypes=[("JSON config", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            new_cfg = load_config(Path(path))
            self.cfg = new_cfg
            # sync live objects
            self.acc.sensitivity = self.cfg["mouse_sensitivity"]
            self._sens_var.set(self.cfg["mouse_sensitivity"])
            self._hz_var.set(self.cfg.get("output_hz", 250))
            self._sens_lbl.config(text=f"{self.cfg['mouse_sensitivity']:.4f}")
            self._hz_lbl.config(text=f"{self.cfg.get('output_hz', 250)} Hz")
            # rebuild binding buttons
            for k, btn in self._bind_btns.items():
                _typ, val = self.cfg["mappings"].get(k, ["key", "?"])
                btn.config(text=f"{k}\n[{val}]")
            self._refresh_devices()
            self._autosave()
            messagebox.showinfo("Imported", f"Config imported from:\n{path}")
        except Exception as exc:
            messagebox.showerror("Import Error", str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    # UI tick + close
    # ══════════════════════════════════════════════════════════════════════════
    def _ui_tick(self):
        try:
            rx, ry = self.acc.get_pos()
            self._rs_lbl.config(text=f"X: {rx:+.3f}   Y: {ry:+.3f}")
        except Exception:
            pass
        self.after(30, self._ui_tick)

    def _on_close(self):
        self._stop()
        self._autosave()
        if self._api: self._api.destroy()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()