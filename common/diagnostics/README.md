# Low-Level Hardware Diagnostics

This directory contains standalone diagnostic utilities used to inspect hardware, dump registers, and verify peripheral interfaces independently of high-level OS drivers.

### 1. `rwmem.c`
Direct physical address reader and writer via `/dev/mem` and `mmap`.
* **Read**: `./rwmem <hex_address>`
* **Write**: `./rwmem <hex_address> <hex_value>`

Compile with any target cross-compiler:
```sh
# For ARM Cortex-A9 (ZTE H3600):
arm-openwrt-linux-gcc -O2 rwmem.c -o rwmem

# For MIPS interAptiv (EcoNet EN751627 / Zyxel EX3301 / WX3100):
mips-openwrt-linux-gcc -O2 rwmem.c -o rwmem
```

### 2. `send_rwmem.py`
Uploads a binary over a raw serial console session using base64 chunking when no network transfer or USB drive is available.

```sh
python3 send_rwmem.py --port /dev/ttyUSB0 --baud 115200 --file rwmem --dest /tmp/rwmem
```

### 3. `spitest.c`
SPI controller register and SPI-NAND feature interrogation tool. Verifies `READID`, page read (cache read), and feature status flags directly against the SPI controller registers.

### 4. `tcp_dump.c`
Streams raw partitions or flash block devices directly to a remote TCP listener on your workstation.

Workstation listener:
```sh
nc -l -p 9999 > stock_nand.bin
```

Target router:
```sh
./tcp_dump /dev/mtd0 192.168.1.2 9999
```
