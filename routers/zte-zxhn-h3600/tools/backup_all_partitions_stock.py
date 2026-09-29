#!/usr/bin/env python3
import socket, time, threading, os, hashlib, sys
from pathlib import Path

ROOT = Path("/mnt/programming-ssd/projects/exploring/openwrt/zyxel")
BACKUP_DIR = ROOT / "h3600/backup/stock_dump_clean"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
HOST_IP = "192.168.55.14"
ROUTER_IP = "192.168.55.1"
PORT = 12345

PARTITIONS = [
    ("mtd1", "bootloader.bin", 0x100000),      # 1 MiB
    ("mtd2", "tag.bin", 0x100000),             # 1 MiB
    ("mtd3", "wifi.bin", 0x100000),            # 1 MiB
    ("mtd4", "usercfg.bin", 0x200000),         # 2 MiB
    ("mtd5", "defcfg.bin", 0x200000),          # 2 MiB
    ("mtd6", "kernel1.bin", 0x360000),         # 3.375 MiB
    ("mtd7", "kernel2.bin", 0x360000),         # 3.375 MiB
    ("mtd8", "rootfs.bin", 0x1640000),         # 22.25 MiB
    ("mtd0", "whole_flash_128M.bin", 0x8000000)# 128 MiB
]

def dump_partition(dev_name, out_name, expected_size):
    target_path = BACKUP_DIR / out_name
    print(f"\n[+] Starting dump of /dev/{dev_name} ({out_name}, expected {expected_size} bytes)...", flush=True)

    received_data = bytearray()
    rec_error = []

    def receiver():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", PORT))
        server.listen(1)
        server.settimeout(120)
        try:
            conn, addr = server.accept()
            conn.settimeout(60)
            while True:
                chunk = conn.recv(65536)
                if not chunk: break
                received_data.extend(chunk)
            conn.close()
        except Exception as e:
            rec_error.append(str(e))
        finally:
            server.close()

    t = threading.Thread(target=receiver)
    t.start()
    time.sleep(0.3)

    # Trigger dump on router via telnet
    s = socket.create_connection((ROUTER_IP, 23), timeout=5)
    time.sleep(0.3); s.recv(1024)
    s.sendall(b"admin\r\n"); time.sleep(0.3); s.recv(1024)
    s.sendall(b"Haikui_V2\r\n"); time.sleep(0.5); s.recv(4096)

    timeout_sec = 300 if dev_name == "mtd0" else 45
    cmd = f"/tmp/tcp_dump /dev/{dev_name} {HOST_IP} {PORT}\r\n".encode()
    s.sendall(cmd)

    t.join(timeout=timeout_sec)
    time.sleep(0.5)
    router_out = s.recv(4096).decode(errors="replace")
    s.close()

    if rec_error:
        print(f"[-] Receiver error: {rec_error}", flush=True)

    with open(target_path, "wb") as f:
        f.write(received_data)

    actual_size = len(received_data)
    sha = hashlib.sha256(received_data).hexdigest()
    print(f"[+] /dev/{dev_name} dumped: {actual_size} bytes (sha256: {sha[:16]}...)", flush=True)
    if actual_size != expected_size:
        print(f"[-] WARNING: size mismatch! Expected {expected_size}, got {actual_size}", flush=True)
    return actual_size == expected_size

print("=" * 60)
print("=== H3600 STOCK FIRMWARE COMPREHENSIVE BACKUP PIPELINE ===")
print("=" * 60)

# Check /tmp/tcp_dump on router
s = socket.create_connection((ROUTER_IP, 23), timeout=5)
time.sleep(0.3); s.recv(1024)
s.sendall(b"admin\r\n"); time.sleep(0.3); s.recv(1024)
s.sendall(b"Haikui_V2\r\n"); time.sleep(0.5); s.recv(4096)
s.sendall(b"tftp -g -r tcp_dump -l /tmp/tcp_dump 192.168.55.14 && chmod +x /tmp/tcp_dump\r\n")
time.sleep(1.5); s.recv(4096); s.close()

results = {}
for dev, name, size in PARTITIONS:
    ok = dump_partition(dev, name, size)
    results[name] = ok
    time.sleep(1.0)

print("\n" + "=" * 60)
print("=== DUMP SUMMARY ===")
print("=" * 60)
for name, ok in results.items():
    status = "SUCCESS" if ok else "FAILED"
    p = BACKUP_DIR / name
    sz = p.stat().st_size if p.exists() else 0
    print(f"{name:25s} : {status} ({sz} bytes)")

all_ok = all(results.values())
if all_ok:
    print("\n[+] ALL PARTITIONS INCLUDING WHOLE FLASH SUCCESSFULLY BACKED UP!")
else:
    print("\n[-] SOME PARTITIONS FAILED!")
