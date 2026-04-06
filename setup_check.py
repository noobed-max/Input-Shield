#!/usr/bin/env python3
"""
KB2Controller — Setup & Dependency Checker (InputShield Edition)
Run this ONCE before kb2controller.py to verify your environment.
"""
import sys
import subprocess
import platform
import ctypes
import os
from pathlib import Path

OS = platform.system()
if OS != "Windows":
    sys.exit("KB2Controller is Windows-only.")

print("KB2Controller Setup — Windows (InputShield Edition)")
print("─" * 55)

# ── Admin check ────────────────────────────────────────────────────────────────
try:
    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
except Exception:
    is_admin = False

if is_admin:
    print("  ✓  Running as Administrator")
else:
    print("  ✗  NOT running as Administrator")
    print("     Right-click this script → 'Run as administrator'")
    input("\nPress Enter to continue anyway (driver checks may fail)…")

print()

# ── Python packages ────────────────────────────────────────────────────────────
print("Checking Python packages…")

def pip_install(*pkgs):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", *pkgs])

def check_pkg(pkg, import_name=None):
    import_name = import_name or pkg
    try:
        __import__(import_name)
        print(f"  ✓  {pkg}")
        return True
    except ImportError:
        print(f"  ✗  {pkg} — installing…")
        try:
            pip_install(pkg)
            print(f"  ✓  {pkg} (installed)")
            return True
        except Exception as e:
            print(f"  ✗  {pkg} — FAILED: {e}")
            return False

check_pkg("keyboard")
check_pkg("vgamepad")

print()

# ── ViGEmBus driver ────────────────────────────────────────────────────────────
print("Checking ViGEmBus driver (vgamepad)…")
try:
    import vgamepad as vg
    g = vg.VX360Gamepad()
    del g
    print("  ✓  ViGEmBus driver found")
except Exception as e:
    print(f"  ✗  ViGEmBus not found: {e}")
    print()
    print("  Download and install from:")
    print("  https://github.com/nefarius/ViGEmBus/releases/latest")
    print("  (Then rerun this script)")
    sys.exit(1)

print()

# ── InputShield / Interception DLL ───────────────────────────────────────
print("Checking InputShield driver & DLL…")

SCRIPT_DIR = Path(__file__).parent
DLL_SEARCH = [
    (SCRIPT_DIR / "inputshield.dll",                            "inputshield.dll"),
    (Path("C:/Windows/System32/inputshield.dll"),               "inputshield.dll"),
    (Path("C:/Program Files/InputShield/inputshield.dll"),      "inputshield.dll"),
    # fallback to original name
    (SCRIPT_DIR / "interception.dll",                           "interception.dll"),
    (Path("C:/Windows/System32/interception.dll"),              "interception.dll"),
    (Path("C:/Program Files/Interception/interception.dll"),    "interception.dll"),
]

dll_found = None
dll_name  = None
for p, name in DLL_SEARCH:
    if p.exists():
        dll_found = p
        dll_name  = name
        break

if dll_found:
    print(f"  ✓  {dll_name} found at: {dll_found}")
else:
    # Try loading by name (might be in PATH)
    for name in ("inputshield.dll", "interception.dll"):
        try:
            ctypes.WinDLL(name)
            print(f"  ✓  {name} found via PATH")
            dll_found = "PATH"
            dll_name  = name
            break
        except OSError:
            pass

if not dll_found:
    print("  ✗  inputshield.dll NOT found (interception.dll also not found)")
    print()
    print("  ┌─ How to install InputShield ──────────────────────────────────────┐")
    print("  │  1. python tools/patch_driver.py path/to/interception.sys     │")
    print("  │  2. copy inputshield.sys to %SystemRoot%\\System32\\drivers\\  │")
    print("  │  3. tools\\install-inputshield.cmd /install  (as Admin)        │")
    print("  │  4. REBOOT your PC                                             │")
    print("  │  5. Build inputshield.dll  (library/buildit-x64.cmd with WDK)  │")
    print("  │     and copy it next to this script                            │")
    print("  └─────────────────────────────────────────────────────────────────┘")
    print()
    input("Press Enter once you've completed these steps and re-run this script…")
    sys.exit(1)

# Try actually creating an InputShield/Interception context
print()
print(f"Testing {dll_name} context…")
try:
    dll = ctypes.WinDLL(str(dll_found)) if dll_found != "PATH" else ctypes.WinDLL(dll_name)
    # auto-detect prefix
    create_fn = destroy_fn = None
    for pfx in ("ishield_", "interception_"):
        try:
            create_fn  = getattr(dll, f"{pfx}create_context")
            destroy_fn = getattr(dll, f"{pfx}destroy_context")
            break
        except AttributeError:
            pass
    if create_fn is None:
        raise RuntimeError("Neither ishield_create_context nor interception_create_context found in DLL")
    create_fn.restype = ctypes.c_void_p
    ctx = create_fn()
    if ctx:
        destroy_fn.argtypes = [ctypes.c_void_p]
        destroy_fn(ctx)
        print(f"  ✓  {dll_name} context created successfully")
    else:
        raise RuntimeError(f"{create_fn.__name__}() returned NULL")
except Exception as e:
    print(f"  ✗  Driver context FAILED: {e}")
    print()
    print("  Possible causes:")
    print("    • The InputShield kernel driver is not installed")
    print("      (run patch_driver.py → install-inputshield.cmd /install)")
    print("    • You need to reboot after installing the driver")
    print("    • Script is not running as Administrator")
    sys.exit(1)

print()

# ── Enumerate devices ──────────────────────────────────────────────────────────
print("Enumerating connected devices…")
try:
    dll2 = ctypes.WinDLL(str(dll_found)) if dll_found != "PATH" else ctypes.WinDLL(dll_name)
    
    # auto-detect prefix
    pfx = "ishield_" if hasattr(dll2, "ishield_create_context") else "interception_"
    
    create_fn = getattr(dll2, f"{pfx}create_context")
    hw_fn     = getattr(dll2, f"{pfx}get_hardware_id")
    iskb_fn   = getattr(dll2, f"{pfx}is_keyboard")
    dest_fn   = getattr(dll2, f"{pfx}destroy_context")

    create_fn.restype  = ctypes.c_void_p
    hw_fn.restype      = ctypes.c_uint
    hw_fn.argtypes     = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
    iskb_fn.restype    = ctypes.c_int
    iskb_fn.argtypes   = [ctypes.c_int]
    dest_fn.argtypes   = [ctypes.c_void_p]

    ctx2 = create_fn()
    devices_found = 0
    for d in range(1, 21):
        buf = ctypes.create_unicode_buffer(512)
        n   = hw_fn(ctx2, d, buf, ctypes.sizeof(buf))
        if n > 0:
            kind = "keyboard" if iskb_fn(d) else "mouse"
            print(f"  [{kind[0].upper()}] device {d:02d}: {buf.value[:60]}")
            devices_found += 1
    dest_fn(ctx2)

    if devices_found == 0:
        print("  (no devices enumerated — this is normal if no filter is set yet)")
    else:
        print(f"\n  {devices_found} device(s) found")
except Exception as e:
    print(f"  (enumeration error: {e} — this is non-fatal)")

print()
print("─" * 55)
print("✓  All checks passed!")
print()
print("  Next steps:")
print("    1. Open kb2controller.py as Administrator")
print("    2. Click '⟳ Refresh' to list your devices")
print("    3. Check the devices you want to hide from Windows")
print("    4. Press START")
print()
print("  In any game:")
print("    • Your physical keyboard/mouse will be INVISIBLE to the game")
print("    • The game only sees the virtual Xbox 360 controller")
print("    • Anti-cheat will not detect Interception or InputShield by name")
print()
print("  F12 = emergency stop (always works, even if keyboard is blocked)")
print()