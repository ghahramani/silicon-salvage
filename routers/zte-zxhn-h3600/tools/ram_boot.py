#!/usr/bin/env python3
"""RAM-only boot using serial state machine and TFTP load."""
import argparse
import fcntl
import os
import re
import select
import termios
import time
from pathlib import Path
from vendor_telnet import T

p = argparse.ArgumentParser(description="Load and boot an image directly into RAM via U-Boot TFTP")
p.add_argument("image", help="U-Boot image file name")
p.add_argument("--password", default=os.environ.get("BOOT_PASSWORD", ""), help="Bootloader password")
p.add_argument("--port", default=os.environ.get("SERIAL_DEV", "/dev/ttyUSB0"), help="Serial port")
p.add_argument("--log", default="serial_live.log", help="Log file path")
p.add_argument("--wait", action="store_true", help="Wait for power cycle")
p.add_argument("--from-openwrt", action="store_true", help="Reboot from existing OpenWrt")
p.add_argument("--from-uboot", action="store_true", help="Assume already at U-Boot prompt")
a = p.parse_args()

assert re.fullmatch(r"[A-Za-z0-9_.-]+", a.image)
pw = a.password.encode() if a.password else b""

fd = os.open(a.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
t = termios.tcgetattr(fd)
t[0] = 0
t[1] = 0
t[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
t[3] = 0
t[4] = t[5] = termios.B115200
termios.tcsetattr(fd, termios.TCSANOW, t)
log = open(a.log, "ab", buffering=0)


def wr(s):
    b = s if isinstance(s, bytes) else s.encode()
    end = time.monotonic() + 3
    while b:
        if time.monotonic() > end:
            raise TimeoutError("serial write")
        if select.select([], [fd], [], 0.1)[1]:
            try:
                n = os.write(fd, b)
                b = b[n:]
            except BlockingIOError:
                pass


def wait(pattern, timeout, quiet=False):
    buf = b""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if select.select([fd], [], [], 0.1)[0]:
            c = os.read(fd, 8192)
            if not c:
                raise RuntimeError("serial disconnected")
            buf += c
            if not quiet:
                c2 = c.replace(pw, b"[REDACTED]") if pw else c
                log.write(c2)
                print(c2.decode(errors="replace"), end="", flush=True)
            if re.search(pattern, buf, re.I):
                return buf
    raise TimeoutError("waiting for " + repr(pattern))


def ub(c, timeout=10):
    wr(c + "\r")
    return wait(rb"=> ?", timeout)


def _get_host_ip():
    return os.environ.get("TFTP_HOST_IP", "192.168.55.14")


# ---- Boot entry path ----
if a.from_openwrt:
    wr("reboot\r")

if a.from_uboot:
    print("Capturing U-Boot => prompt...", flush=True)
    wr(b"\x03\r")
    wait(rb"=> ?", 10)
    print("U-Boot prompt captured", flush=True)
else:
    if a.wait:
        print("READY: waiting for physical router power cycle", flush=True)
    elif not a.from_openwrt:
        tn = T()
        assert tn.login(), "vendor shell login failed"
        print("Vendor shell authenticated; requesting reboot for RAM boot", flush=True)
        tn.cmd("reboot", 2)
        tn.close()
    print("Waiting for boot mode gate...", flush=True)
    wait(rb"Press 1 means entering boot mode", 240 if (a.wait or a.from_openwrt) else 60)
    wr(b"1")
    print("Sent '1', waiting for password prompt...", flush=True)
    wait(rb"(?:password|\*\*\*)", 10)
    time.sleep(0.3)
    wr(pw + b"\r")
    print("Sent password, waiting for U-Boot prompt...", flush=True)
    wait(rb"=> ?", 15, quiet=True)
    print("U-Boot prompt authenticated", flush=True)

# ---- Network setup ----
host_ip = _get_host_ip()
print(f"Host TFTP server IP: {host_ip}", flush=True)
ub("setenv ipaddr 192.168.55.1")
ub(f"setenv serverip {host_ip}")
print("Warming up ethernet link...", flush=True)
ub(f"ping {host_ip}", 15)

# ---- TFTP transfer ----
print(f"Starting TFTP transfer of {a.image}...", flush=True)
b = ub("tftp 0x43000000 " + a.image, 180)
assert b"ransferred" in b, "TFTP failed"
print("TFTP transfer complete. Booting from RAM...", flush=True)

# ---- Boot ----
wr("bootm 0x43000000\r")
wait(rb"Please press Enter to activate this console", 120)
time.sleep(2)
wr(b"\r")
wait(rb"(?:root@|BusyBox|# )", 20)
print("RAM boot reached OpenWrt console", flush=True)
os.close(fd)
log.close()
