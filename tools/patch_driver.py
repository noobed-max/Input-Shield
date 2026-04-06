#!/usr/bin/env python3
r"""
patch_driver.py  –  Binary-patch interception.sys → inputshield.sys
====================================================================
Run this on Windows (Python 3.x) with the driver .sys file beside this
script.  It produces inputshield.sys with all device-name references
rewritten.

Usage (run as Administrator):
    python patch_driver.py [path\to\keyboard.sys]
    python patch_driver.py [path\to\interception.sys]

The source file can have ANY name (e.g. keyboard.sys if it was renamed
by the system).  The output is always 'inputshield.sys' in the same
directory as the source.

If no argument is given it looks for interception.sys in the same folder.

IMPORTANT: You still need to sign the patched driver (or enable test-signing
on the target machine with: bcdedit /set testsigning on).
"""

import sys
import os
import shutil

def patch(data: bytes, old: bytes, new: bytes) -> tuple[bytes, int]:
    """Replace all occurrences of old with new (must be same length)."""
    assert len(new) == len(old), "Patch lengths must match"
    count = 0
    result = bytearray(data)
    i = 0
    while True:
        idx = result.find(old, i)
        if idx == -1:
            break
        result[idx:idx+len(old)] = new
        count += 1
        i = idx + len(new)
    return bytes(result), count


def main():
    if len(sys.argv) > 1:
        src = sys.argv[1]
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        src = os.path.join(here, "interception.sys")

    if not os.path.exists(src):
        print(f"[!] Cannot find driver: {src}")
        sys.exit(1)

    # Always output as inputshield.sys in the same directory as the source
    src_dir = os.path.dirname(os.path.abspath(src))
    dst = os.path.join(src_dir, "inputshield.sys")

    if os.path.abspath(src) == os.path.abspath(dst):
        print("[!] Source is already named inputshield.sys — nothing to copy.")
        print("    Will patch in-place.")
    else:
        shutil.copy2(src, dst)
        print(f"[*] Copied {os.path.basename(src)} → {os.path.basename(dst)}")

    with open(dst, "rb") as f:
        data = f.read()

    total = 0

    # ---- ANSI patches ----
    # "interception" (12 bytes)  →  "inputshield\x00" (12 bytes, null-padded)
    data, n = patch(data, b"interception", b"inputshield\x00")
    total += n
    print(f"  ANSI 'interception'      → 'inputshield\\0'  : {n} replacements")

    # ---- UTF-16LE patches ----
    # L"interception" → L"inputshield\x00"
    old_u = "interception".encode("utf-16-le")   # 24 bytes
    new_u = ("inputshield\x00").encode("utf-16-le")  # 24 bytes
    data, n = patch(data, old_u, new_u)
    total += n
    print(f"  UTF16 'interception'     → 'inputshield\\0'  : {n} replacements")

    # Device symbolic-link path  \DosDevices\interception  (ANSI)
    data, n = patch(data, b"\\DosDevices\\interception",
                          b"\\DosDevices\\inputshield\x00")
    total += n
    print(f"  ANSI '\\DosDevices\\interception' patched      : {n}")

    # Device object path  \Device\Interception  (ANSI, mixed case)
    data, n = patch(data, b"\\Device\\Interception",
                          b"\\Device\\InputShield\x00")
    total += n
    print(f"  ANSI '\\Device\\Interception'    patched        : {n}")

    # UTF-16 device object path
    old_u2 = "\\Device\\Interception".encode("utf-16-le")
    new_u2 = "\\Device\\InputShield\x00".encode("utf-16-le")
    if len(new_u2) == len(old_u2):
        data, n = patch(data, old_u2, new_u2)
        total += n
        print(f"  UTF16 '\\Device\\Interception'   patched       : {n}")

    with open(dst, "wb") as f:
        f.write(data)

    print(f"\n[+] Patched driver written to: {dst}")
    print(f"    Total replacements: {total}")
    print()
    print("Next steps on Windows (run as Administrator):")
    print(f"  sc create inputshield binPath= \"%SystemRoot%\\System32\\drivers\\inputshield.sys\" type= kernel start= auto")
    print(f"  copy /Y {os.path.basename(dst)} %SystemRoot%\\System32\\drivers\\inputshield.sys")
    print( "  sc start inputshield")


if __name__ == "__main__":
    main()
