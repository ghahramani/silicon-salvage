#!/usr/bin/env python3
"""send_rwmem.py: Push a compiled binary over serial console via base64 chunking.

Useful when the target router has a serial shell but no network connectivity.
"""
import argparse
import base64
import sys
import time
import serial


def main():
    parser = argparse.ArgumentParser(description="Upload binary over serial console via base64")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port (default: /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--file", default="rwmem", help="Binary file to upload (default: rwmem)")
    parser.add_argument("--dest", default="/tmp/rwmem", help="Destination path on router (default: /tmp/rwmem)")
    args = parser.parse_args()

    with open(args.file, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")

    print(f"Opening serial port {args.port} at {args.baud} baud...")
    s = serial.Serial(args.port, args.baud, timeout=1.0)
    s.write(b"\x03\n")
    time.sleep(0.5)

    remote_b64 = args.dest + ".b64"
    s.write(f"rm -f {remote_b64} {args.dest}\n".encode())
    time.sleep(0.3)
    s.read(4096)

    chunk_size = 64
    total_chunks = (len(data) + chunk_size - 1) // chunk_size
    print(f"Uploading {len(data)} base64 chars in {total_chunks} chunks...")

    for i in range(0, len(data), chunk_size):
        chunk = data[i : i + chunk_size]
        s.write(f'echo -n "{chunk}" >> {remote_b64}\n'.encode())
        s.read_until(b"\n")
        if (i // chunk_size) % 10 == 0:
            print(f"Progress: {i // chunk_size}/{total_chunks} chunks", flush=True)

    print("Decoding base64 and setting executable permissions...")
    s.write(f"base64 -d {remote_b64} > {args.dest}\n".encode())
    time.sleep(0.5)
    s.write(f"chmod +x {args.dest}\n".encode())
    time.sleep(0.5)
    s.write(f"ls -l {args.dest}\n".encode())
    time.sleep(0.5)
    print(s.read(4096).decode("utf-8", errors="ignore"))
    s.close()
    print("Upload complete.")


if __name__ == "__main__":
    main()
