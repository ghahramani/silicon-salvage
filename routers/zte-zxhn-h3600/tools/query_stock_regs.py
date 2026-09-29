#!/usr/bin/env python3
"""query_stock_regs.py: Interactively query hardware memory and network state on stock firmware."""
from vendor_telnet import T

t = T()
if not t.login():
    print("[-] Login failed")
    exit(1)

print("[+] Logged into stock firmware.")

cmds = [
    "ifconfig -a",
    "brctl show",
    "cat /proc/net/dev",
    "hexdump -s 0x921c0060 -n 32 -e '8/4 \"%08x \" \"\\n\"' /dev/mem",
    "hexdump -s 0x923883c0 -n 48 -e '8/4 \"%08x \" \"\\n\"' /dev/mem",
    "hexdump -s 0x921d4000 -n 64 -e '8/4 \"%08x \" \"\\n\"' /dev/mem",
    "hexdump -s 0x921d4040 -n 64 -e '8/4 \"%08x \" \"\\n\"' /dev/mem",
    "hexdump -s 0x921d4080 -n 64 -e '8/4 \"%08x \" \"\\n\"' /dev/mem",
    "hexdump -s 0x921d40c0 -n 64 -e '8/4 \"%08x \" \"\\n\"' /dev/mem",
    "hexdump -s 0x921d4100 -n 64 -e '8/4 \"%08x \" \"\\n\"' /dev/mem",
    "hexdump -s 0x921d41c0 -n 32 -e '8/4 \"%08x \" \"\\n\"' /dev/mem",
    "hexdump -s 0x921d4280 -n 48 -e '8/4 \"%08x \" \"\\n\"' /dev/mem",
]

for cmd in cmds:
    print(f"\n=== CMD: {cmd} ===")
    out = t.cmd(cmd, t=2.0)
    print(out.strip())

t.close()
