#!/usr/bin/env python3
"""vendor_serial_login.py: Automate serial login into stock ZTE firmware console."""
import argparse
import os
import select
import sys
import termios
import time


def main():
    parser = argparse.ArgumentParser(description="Automate serial login on stock firmware")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port (default: /dev/ttyUSB0)")
    parser.add_argument("--user", default="admin", help="Username (default: admin)")
    parser.add_argument("--pass", dest="password", required=True, help="Console password (required)")
    args = parser.parse_args()

    fd = os.open(args.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    t = termios.tcgetattr(fd)
    t[0] = 0
    t[1] = 0
    t[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    t[3] = 0
    t[4] = t[5] = termios.B115200
    termios.tcsetattr(fd, termios.TCSANOW, t)

    def send_and_read(data, wait=1.0):
        os.write(fd, data)
        time.sleep(wait)
        buf = b""
        while select.select([fd], [], [], 0.2)[0]:
            c = os.read(fd, 4096)
            if not c:
                break
            buf += c
        return buf.decode(errors="replace")

    print(f"Connecting to {args.port}...")
    print(send_and_read(b"\r\n", 0.5))

    print(f"Sending username '{args.user}'...")
    out = send_and_read(f"{args.user}\r\n".encode(), 0.8)
    print(out)

    print("Sending password...")
    out = send_and_read(f"{args.password}\r\n".encode(), 1.5)
    print(out)

    print("Testing shell responsiveness with 'uptime'...")
    out = send_and_read(b"uptime\r\n", 0.5)
    print(out)

    os.close(fd)


if __name__ == "__main__":
    main()
