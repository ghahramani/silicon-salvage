#!/usr/bin/env python3
"""reboot_and_flash.py: Catch the Zyxel zloader bootloader prompt and automate flashing slot 0 via TFTP."""
import argparse
import sys
import time
import serial


def main():
    parser = argparse.ArgumentParser(description="Automate zloader interception and TFTP flashing")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port (default: /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--image", default="RAS.bin", help="Image name on TFTP server (default: RAS.bin)")
    parser.add_argument("--server", default="192.168.1.2", help="TFTP server IP (default: 192.168.1.2)")
    args = parser.parse_args()

    print(f"Connecting to serial port {args.port} at {args.baud} baud...")
    s = serial.Serial(args.port, args.baud, timeout=0.1)

    print("Listening for bootloader prompt. Power-cycle the router now...")
    caught = False
    start_time = time.time()

    while time.time() - start_time < 60:
        # Spam 'b' to interrupt zloader
        s.write(b"b")
        line = s.readline().decode("utf-8", errors="ignore")
        if line:
            sys.stdout.write(line)
            sys.stdout.flush()
        if "zloader>" in line or "ZLOADER" in line:
            caught = True
            break
        time.sleep(0.05)

    if not caught:
        print("\nTimed out waiting for zloader prompt.")
        s.close()
        sys.exit(1)

    print("\n[+] Bootloader halted at zloader prompt!")
    time.sleep(0.5)

    # Enable write commands
    print("[+] Sending ATEN...")
    s.write(b"ATEN\r\n")
    time.sleep(0.5)

    # Download and flash image to slot 0
    cmd = f"ATUR {args.image},0\r\n"
    print(f"[+] Sending flash command: {cmd.strip()} (TFTP from {args.server})...")
    s.write(cmd.encode())

    # Monitor flash progress
    while True:
        line = s.readline().decode("utf-8", errors="ignore")
        if line:
            sys.stdout.write(line)
            sys.stdout.flush()
        if "OK" in line or "boot" in line.lower():
            print("\n[+] Flashing succeeded. Booting into OpenWrt...")
            break
        time.sleep(0.1)

    s.close()


if __name__ == "__main__":
    main()
