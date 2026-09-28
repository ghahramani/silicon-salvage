# ⚡ silicon-salvage

> **Rescuing high-performance ISP routers from landfills through hardware reverse engineering, bootloader unlocking, and mainline OpenWrt ports.**

Millions of capable Wi-Fi 6 routers are treated as disposable e-waste once broadband contracts expire. Shackled by locked bootloaders, restricted ISP management portals, and undocumented silicon architectures, these powerful devices often end up in recycling bins or selling for a mere **£15 to £20 on second-hand markets**. 

Yet, beneath the plastic enclosure sits high-spec dual-core silicon, 512 MB of RAM, and Wi-Fi 6 hardware functionally identical to **£100–£150+ commercial enterprise gateways**. The depreciation is purely software-imposed.

**`silicon-salvage`** is a complete open-source research and engineering toolkit dedicated to liberating abandoned Customer Premises Equipment (CPE) and reclaiming the true value of the silicon. It documents bootloader passwords, serial UART interfaces, flash memory layouts, and clean OpenWrt Linux 6.18 ports with line-rate hardware offloading.

---

### 📱 Supported Hardware Matrix

| Device | Vendor / ISP | Silicon Architecture | Wi-Fi | Status | Guide & Tools |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ZTE ZXHN H3600** (H1600) | Hyperoptic / ZTE | Sanechips ZX279128S (Dual Cortex-A9) | Wi-Fi 6 (MT7915D) | ✅ Upstream PR ready / 940 Mbps offload | [`routers/zte-zxhn-h3600`](routers/zte-zxhn-h3600) |
| **Zyxel EX3301-T0** | Various ISPs | EcoNet EN751627 (Dual MIPS interAptiv) | Wi-Fi 6 (MT7915D) | ✅ Full OpenWrt / JFFS2 persistence | [`routers/zyxel-ex3301-t0`](routers/zyxel-ex3301-t0) |
| **Zyxel WX3100-T0** | Various ISPs | EcoNet EN751627 (Dual MIPS interAptiv) | Wi-Fi 6 Mesh AP | ✅ Clean OpenWrt target | [`routers/zyxel-wx3100-t0`](routers/zyxel-wx3100-t0) |

---

### 🛠️ Repository Architecture

```text
silicon-salvage/
├── COPYING                        # GNU General Public License v2.0
├── common/                        # Common utilities across all routers
│   ├── tftp_server.py             # Standalone Python TFTP server
│   └── README.md
├── routers/
│   ├── zte-zxhn-h3600/            # ZTE ZXHN H3600 / H1600 (Sanechips ZX279128S)
│   │   ├── README.md              # Full teardown, UART pinout, bootloader password, flash guide
│   │   ├── root-recovery/         # acs.py, run.sh (local TR-069 ACS recovery)
│   │   ├── config-tools/          # decode_config.py, encode_config.py, ztetool.py
│   │   ├── tools/                 # ram_boot.py, autonomous_boot_catch.py, console.py
│   │   ├── patches/               # openwrt-zte-zxhn-h3600.patch
│   │   └── pinout/                # High-res UART header photos
│   ├── zyxel-ex3301-t0/           # Zyxel EX3301-T0 (EcoNet EN751627)
│   │   ├── README.md              # Hardware specs, U-Boot flash commands, install guide
│   │   └── patches/               # openwrt-zyxel-ex3301-t0.patch
│   └── zyxel-wx3100-t0/           # Zyxel WX3100-T0 (EcoNet EN751627)
│       ├── README.md              # Hardware specs, U-Boot flash commands, install guide
│       └── patches/               # openwrt-zyxel-wx3100-t0.patch
```

---

### 🔌 Hardware Requirements & Safety

All routers in this project communicate over serial UART using **3.3V TTL** logic. Connecting standard 5V adapters can permanently destroy the processor's GPIO pins.

To prevent ground loops between mains-powered routers and host development PCs, we recommend:
* **[Waveshare Industrial USB-to-TTL Serial Converter](https://www.amazon.co.uk/dp/B0CX55K4RG?&linkCode=ll2&tag=navid015-21&linkId=fb0958a59eb9c1688fec1959cdadcac8&ref_=as_li_ss_tl)**: Features integrated galvanic digital isolation, onboard TVS surge suppression, and hardware 3.3V/5V level switching.

---

### 🌐 Precompiled Binaries & Package Feeds

All compiled installation images, recovery kernels, and target packages are hosted at:
🔗 **`https://openwrt.style.dev/`**

---

### ⚖️ License

This project is licensed under the **GNU General Public License v2.0 (GPL-2.0-only)** to match OpenWrt and the Linux kernel. 

- All tools, scripts, and target drivers are copyright © 2026 Navid Ghahremani.
- Anyone redistributing or modifying this code must keep it free and open-source under the GPL-2.0, preserving full attribution.
- Device Tree (`.dts`) files are dual-licensed under `GPL-2.0-only OR MIT` per OpenWrt kernel guidelines.
