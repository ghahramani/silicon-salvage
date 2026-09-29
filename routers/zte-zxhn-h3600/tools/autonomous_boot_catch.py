#!/usr/bin/env python3
import os, termios, select, time, sys

DEV = os.environ.get("SERIAL_DEV", "/dev/ttyUSB0")
LOG_PATH = os.environ.get("SERIAL_LOG", "serial_boot.log")

LOG = open(LOG_PATH, 'ab', buffering=0)

def emit(c):
    LOG.write(c)
    sys.stdout.buffer.write(c)
    sys.stdout.buffer.flush()

fd = os.open(DEV, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
a = termios.tcgetattr(fd)
a[0] = 0; a[1] = 0; a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL; a[3] = 0
a[4] = a[5] = termios.B115200
termios.tcsetattr(fd, termios.TCSANOW, a)
termios.tcflush(fd, termios.TCIOFLUSH)

def w(b):
    if isinstance(b, str): b = b.encode()
    try:
        os.write(fd, b)
    except BlockingIOError:
        pass

print("[*] Autonomous boot monitor started. Waiting for router power cycle...", flush=True)
print("[*] All output logged to latest/artifacts/serial_live2.log", flush=True)

buf = b''
activated = False
shell_ready = False
start_time = time.time()
timeout = 3600  # 1 hour
last_enter = 0
boot_started = False

while time.time() - start_time < timeout:
    r, _, _ = select.select([fd], [], [], 0.1)
    now = time.time()
    if r:
        try:
            c = os.read(fd, 8192)
        except BlockingIOError:
            c = b''
        if c:
            emit(c)
            buf += c
            boot_started = True
            if len(buf) > 16384:
                buf = buf[-8192:]
            
            low = buf.lower()
            if b'done loading kernel modules from /etc/modules.d' in low and not activated:
                print("\n[+] All kernel modules loaded successfully! Activating console...", flush=True)
                time.sleep(1.0)
                w(b'\r\n')
                activated = True
                last_enter = now

            if activated and (b'root@' in buf or b'root@openwrt' in low or b'# ' in buf):
                print("\n[+] Shell prompt detected!", flush=True)
                time.sleep(0.5)
                w(b'\r\nuptime; df -h; cat /proc/mtd\r\n')
                shell_ready = True
                break

    if activated and not shell_ready and (now - last_enter > 2.0):
        w(b'\r\n')
        last_enter = now

if shell_ready:
    print("\n[+] Router successfully booted and shell is ready!", flush=True)
    # Drain remaining command output for 3 seconds
    end = time.time() + 3.0
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.2)
        if r:
            try:
                c = os.read(fd, 8192)
                if c: emit(c)
            except BlockingIOError:
                pass
    os.close(fd)
    LOG.close()
    sys.exit(0)
else:
    print("\n[-] Timeout or failed to reach shell prompt.", flush=True)
    os.close(fd)
    LOG.close()
    sys.exit(1)
