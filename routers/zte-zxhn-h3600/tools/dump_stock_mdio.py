#!/usr/bin/env python3
"""dump_stock_mdio.py: Dump MDIO PHY registers from stock ZTE firmware."""
import sys
from vendor_telnet import T

t = T()
if not t.login():
    print("[-] Login failed")
    sys.exit(1)

print("[+] Reading MDIO 8 and MDIO 9 on stock firmware...")

mdio_script = """cat << 'EOF' > /tmp/read_mdio.sh
#!/bin/sh
# read_mdio <phy_addr> <reg>
phy=$1
reg=$2
cmd=$(( 0x5800 | (phy << 5) | reg ))
/tmp/rwmem 0x9a101014 $cmd >/dev/null
usleep 1000
val=$(/tmp/rwmem 0x9a101008 | awk '{print $2}')
echo "PHY $phy reg $reg = 0x$val"
EOF
chmod +x /tmp/read_mdio.sh
"""
t.cmd(mdio_script)

regs = [0, 1, 2, 3, 16, 17, 18, 19, 20, 21, 22, 23, 27, 29]
print("\n--- PHY 8 (WAN Copper) ---")
cmd8 = "for r in " + " ".join(str(r) for r in regs) + "; do /tmp/read_mdio.sh 8 $r; done"
print(t.cmd(cmd8, t=4.0))

print("\n--- PHY 9 (WAN SerDes) ---")
cmd9 = "for r in " + " ".join(str(r) for r in regs) + "; do /tmp/read_mdio.sh 9 $r; done"
print(t.cmd(cmd9, t=4.0))

t.close()
