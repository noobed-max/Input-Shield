# InputShield + KB2Controller Setup Guide

## What is this?

**InputShield** is a stealth-renamed fork of the Interception keyboard/mouse
kernel filter driver. It intercepts **every keystroke and mouse event at the
driver level**, before Windows and any game ever sees them.

**KB2Controller** uses InputShield to translate your keyboard + mouse into a
virtual Xbox 360 controller (via ViGEmBus), so games that detect raw input
or the original "interception" driver name will not flag it.

---

## Folder layout

```
InputShield/
├── kb2controller.py            ← Main GUI application (run as Administrator)
├── setup_check.py              ← Run this FIRST to verify all dependencies
├── library/
│   ├── inputshield.h / .c / .rc  ← Driver DLL source (compile with WDK)
│   ├── interception_compat.h      ← Shim for old code using interception_ names
│   └── buildit-x64.cmd            ← Build script (requires WDK 7.1)
├── tools/
│   ├── patch_driver.py            ← Patches interception.sys → inputshield.sys
│   └── install-inputshield.cmd   ← Registers the Windows service
└── samples/                    ← Example programs using the new API
```

---

## Step-by-step setup (Windows)

### Prerequisites

| Requirement | Download |
|---|---|
| Python 3.10+ | https://python.org |
| ViGEmBus driver | https://github.com/nefarius/ViGEmBus/releases/latest |
| Windows Driver Kit 7.1 (for building DLL) | https://www.microsoft.com/en-us/download/details.aspx?id=11800 |
| Original `interception.sys` | From any interception release zip |

---

### Step 1 — Install Python packages

```cmd
pip install keyboard vgamepad
```

---

### Step 2 — Install ViGEmBus

Download and run the ViGEmBus installer (link above), then **reboot**.

---

### Step 3 — Patch the kernel driver

You need the original Interception `.sys` driver file. It may be named
`interception.sys` (from a release zip) **or** `keyboard.sys` (if already
installed in `%SystemRoot%\System32\drivers\`).

```cmd
REM If you have the original release file:
python tools\patch_driver.py C:\path\to\interception.sys

REM If the driver is already installed as keyboard.sys:
copy %SystemRoot%\System32\drivers\keyboard.sys .\keyboard.sys
python tools\patch_driver.py .\keyboard.sys
```

> **Note:** If the driver is currently loaded by Windows you cannot patch it
> directly from `System32\drivers\`. Copy it to a local folder first (as
> shown above), then patch the copy.

The output is always `inputshield.sys` in the same directory as the source.
The tool rewrites:
- Every `interception` device string → `inputshield` (ANSI + UTF-16LE)  
- `\Device\Interception` → `\Device\InputShield`
- `\DosDevices\interception` → `\DosDevices\inputshield`

> **Driver signing:** The patched driver needs to be signed, or test-signing
> must be enabled on the machine:
> ```cmd
> bcdedit /set testsigning on
> ```
> Then reboot. Use this on a **test machine only**.

---

### Step 4 — Install the driver service

Run **as Administrator**:

```cmd
copy inputshield.sys %SystemRoot%\System32\drivers\
tools\install-inputshield.cmd /install
```

**Reboot** after installation.

To uninstall later:
```cmd
tools\install-inputshield.cmd /uninstall
```

---

### Step 5 — Build inputshield.dll

The user-mode DLL is what Python talks to. Build it with:

```cmd
set WDK=C:\WinDDK\7600.16385.1
cd library
buildit-x64.cmd
```

Output will be at:
```
library\objfre_win7_amd64\amd64\inputshield.dll
```

**Copy `inputshield.dll` to the same folder as `kb2controller.py`** (i.e.
the root `InputShield\` directory).

> **Shortcut (not recommended for anti-cheat evasion):** You can temporarily
> use the original `interception.dll` from any existing Interception
> installation. The code will automatically detect and load it as a fallback.
> However, this defeats the stealth purpose — always use `inputshield.dll`
> for production use.

---

### Step 6 — Verify your setup

```cmd
python setup_check.py
```

Expected output:
```
KB2Controller Setup — Windows (InputShield Edition)
───────────────────────────────────────────────────
  ✓  Running as Administrator
  ✓  keyboard
  ✓  vgamepad
  ✓  ViGEmBus driver found
  ✓  inputshield.dll found at: C:\...\InputShield\inputshield.dll
  ✓  inputshield.dll context created successfully
  [K] device 01: HID\VID_...  (your keyboard)
  [M] device 11: HID\VID_...  (your mouse)
  ✓  All checks passed!
```

---

### Step 7 — Run KB2Controller

```cmd
python kb2controller.py
```

> **Must be run as Administrator.** Right-click → "Run as administrator"

---

## Using KB2Controller

### First run  

1. Click **⟳ Refresh** to see your connected keyboards and mice
2. **Check the box** next to devices you want to hide from games
3. Remap controller buttons as needed (click any button to rebind)
4. Click **▶ START**

### Device Blocker

| Checkbox state | What happens |
|---|---|
| ☑ Checked | Device is hidden from Windows & games. Only the virtual Xbox controller is visible. |
| ☐ Unchecked | Device passes through normally — games see both the real device AND the virtual controller |

### Key bindings

| Button | Default key | Description |
|---|---|---|
| A | Space | Jump / action |
| B | E | Interact |
| X | R | Reload |
| Y | F | Special action |
| LT | Right mouse | Aim / zoom |
| RT | Left mouse | Fire |
| LS_UP/DOWN/LEFT/RIGHT | W/S/A/D | Movement → Left Stick |
| CENTER_RS | Alt | Snap right stick to center |
| F12 | — | **Emergency stop** (always works) |

### Mouse → Right Stick

Mouse movement is accumulated into the right stick. Adjust the **Sensitivity**
slider to control how fast the stick moves per pixel of mouse movement.

`Alt` key (mapped to `CENTER_RS`) snaps the right stick back to center.

---

## Stealth coverage

| Detection vector | Original | InputShield |
|---|---|---|
| DLL filename | `interception.dll` | `inputshield.dll` |
| Exported functions | `interception_*` | `ishield_*` |
| PE version-info | `"Interception API"` | `"InputShield API"` |
| Device path (user-mode) | `\\.\interception00` | `\\.\inputshield00` |
| Kernel device object | `\Device\Interception` | `\Device\InputShield` |
| Windows service name | `interception` | `inputshield` |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `inputshield.dll not found` | Build the DLL (Step 5) and copy it to the `InputShield\` folder |
| `context returned NULL` | Driver not installed, or no reboot after install, or not running as Admin |
| `No devices found` after Refresh | Driver loaded OK, but no filter is set yet — click START first, then Refresh |
| Game still sees keyboard/mouse | Make sure the device checkbox is **checked** before clicking START |
| F12 doesn't stop | The keyboard device is blocked — F12 bypass is built in; check for Python errors |
| Driver won't load (signature error) | Enable test-signing: `bcdedit /set testsigning on` then reboot |
