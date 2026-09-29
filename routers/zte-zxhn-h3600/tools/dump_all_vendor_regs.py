#!/usr/bin/env python3
"""dump_all_vendor_regs.py: Extract switch forwarding and port filter registers from stock firmware."""
import sys
from vendor_telnet import T

t = T()
if not t.login():
    print("[-] Login failed")
    sys.exit(1)

print("[+] Logged into stock firmware.")

regs = [
    # Port filter registers 0x921c0060..0x921c0074
    0x921c0060, 0x921c0064, 0x921c0068, 0x921c006c, 0x921c0070, 0x921c0074,
    # Port isolate / forwarding matrix 0x923883c0..0x923883dc
    0x923883c0, 0x923883c4, 0x923883c8, 0x923883cc, 0x923883d0, 0x923883d4, 0x923883d8, 0x923883dc,
    # Forwarding configs
    0x921d4000, 0x921d4004,
    0x921d4040, 0x921d4044,
    0x921d4080, 0x921d4084,
    0x921d40c0, 0x921d40c4,
    0x921d4100, 0x921d4104,
    0x921d4140, 0x921d4144,
    0x921d4180, 0x921d4184,
    0x921d41c0, 0x921d41c4,
    # Switch enable & port enables
    0x921cc000,
    0x921d428c, 0x921d4290, 0x921d4294, 0x921d4298, 0x921d429c, 0x921d42a0, 0x921d42a4,
    # MAC block ports 0-4
    0x92200000, 0x92240000, 0x92280000, 0x922c0000, 0x92300000,
]

cmd_str = "for r in " + " ".join(f"0x{r:08x}" for r in regs) + "; do /tmp/rwmem $r; done"
print("=== DUMPING REGISTERS ===")
out = t.cmd(cmd_str, t=4.0)
print(out)

print("\n=== ROUTING AND INTERFACES ===")
print(t.cmd("ip route show; echo ---; ip -6 route show", t=2.0))

print("\n=== VENDOR MODULE PARAMS / PROC ENTRIES ===")
print(t.cmd("ls -la /proc/driver/ /proc/net/ /proc/sys/net/ 2>/dev/null; ls -la /proc/vlan /proc/l2 2>/dev/null", t=2.0))

t.close()
