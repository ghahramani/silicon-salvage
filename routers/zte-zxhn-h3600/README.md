# OpenWrt on the ZTE ZXHN H3600 (H1600): installation guide

This guide installs OpenWrt on a ZTE ZXHN H3600 that still runs the stock ZTE
firmware. It needs a serial console once. After that, upgrades go through the
web interface. The stock firmware is kept in the second flash slot.

Downloads: <https://openwrt.style.dev/h3600/>

| File | Used for |
|------|----------|
| `openwrt-sanechips-generic-zte_zxhn-h3600-initramfs.uImage` | first boot over TFTP (runs from RAM, writes nothing) |
| `openwrt-sanechips-generic-zte_zxhn-h3600-squashfs-sysupgrade.bin` | the installation itself, and later upgrades |
| `sha256sums` | checksums of both files |

## What works

- 4x Gigabit LAN and Gigabit WAN, one network interface per port (`lan1`-`lan4`, `wan`)
- MT7915 Wi-Fi 6, 2.4 GHz and 5 GHz, with the factory calibration and MAC addresses
- 128 MiB SPI-NAND with bad-block handling, JFFS2 overlay, `sysupgrade` with kept settings
- USB host (USB 3.0), all LEDs, buttons (reset, WPS, Wi-Fi, LED on/off)
- Power LED as status LED, as in the stock firmware: red while booting (blinking
  in failsafe mode and during an upgrade), green once OpenWrt is up
- Hardware flow offloading for IPv4 NAT: 940 Mbit/s with the CPU idle (off by default)
- Hardware LAN switching between LAN ports: ~940 Mbit/s instead of ~600 through the CPU (off by default)
- The standard OpenWrt package set plus LuCI, nothing else, with OpenWrt's
  standard package feed settings; everything else (kernel modules, USB storage,
  VPNs, adblock, docker, ...) is in the H3600 package feed (section 11)

Not supported: the two FXS phone ports.

## 1. What you need

- A USB-to-serial adapter with **3.3 V** logic (FT232, CP2102, CH340). Not 5 V.
- An Ethernet cable and a PC (Linux here; any OS with a TFTP server works).
- The two image files above, checked against `sha256sums`.
- The cspboot **boot mode password** (asked for in step 4): `Boot4128s!`.

## 2. Serial console

Open the case. The 4-pin header **X1A22** carries the console:

| Pin | Signal | Connect to adapter |
|-----|--------|--------------------|
| 1 | VCC 3.3 V | leave unconnected |
| 2 | TX (router out) | RX |
| 3 | RX (router in) | TX |
| 4 | GND | GND |

Settings: 115200 baud, 8N1, no flow control. For example:

```sh
picocom -b 115200 /dev/ttyUSB0
```

## 3. Prepare the PC

Connect the PC to **LAN 1** of the router and leave the **WAN** port unplugged
until step 8 (OpenWrt starts with LAN `192.168.1.1/24`, and a WAN lease from a
`192.168.1.x` network would collide with it). Give the PC interface the
address `192.168.1.2/24` (no gateway). If the PC is also connected to a network
that uses `192.168.1.0/24` (many home routers do), disconnect it from that
network for the installation, otherwise replies go out the wrong interface.
Serve the initramfs image over TFTP, for example with dnsmasq:

```sh
mkdir -p ~/tftp
cp openwrt-sanechips-generic-zte_zxhn-h3600-initramfs.uImage ~/tftp/
sudo dnsmasq -d -p 0 --enable-tftp --tftp-root="$HOME/tftp" --listen-address=192.168.1.2
```

## 4. Stop the boot at the U-Boot prompt

Power the router on with the serial console open. When cspboot prints

```
*** Press 1 means entering boot mode***
```

press **1 once**. Do not repeat it or hold the key: every extra `1` becomes
part of the password and the prompt then fails. At

```
*** Please input bootmode password: ***
```

type the boot mode password and press Enter. You get a U-Boot prompt. If you
missed the moment, power-cycle and try again.

## 5. Boot OpenWrt from RAM

At the U-Boot prompt:

```
setenv ipaddr 192.168.1.1
setenv serverip 192.168.1.2
tftp 0x43000000 openwrt-sanechips-generic-zte_zxhn-h3600-initramfs.uImage
bootm 0x43000000
```

OpenWrt boots from RAM; nothing is written to flash yet. After about a minute
it answers on `192.168.1.1` (SSH as `root`, no password yet).

## 6. Back up the stock flash (recommended)

The `tag` partition holds the MAC addresses and the `wifi` partition the Wi-Fi
calibration. OpenWrt reads them but never writes them. Keep a copy of every
partition anyway:

```sh
ssh root@192.168.1.1 cat /proc/mtd
mkdir h3600-backup && cd h3600-backup
for n in $(ssh root@192.168.1.1 "sed -n 's/^mtd\([0-9]*\):.*/\1/p' /proc/mtd"); do
    ssh root@192.168.1.1 "cat /dev/mtd$n" > mtd$n.bin
done
ssh root@192.168.1.1 cat /proc/mtd > partitions.txt
```

## 7. Install

```sh
scp -O openwrt-sanechips-generic-zte_zxhn-h3600-squashfs-sysupgrade.bin root@192.168.1.1:/tmp/
ssh root@192.168.1.1 sysupgrade -n /tmp/openwrt-sanechips-generic-zte_zxhn-h3600-squashfs-sysupgrade.bin
```

The router writes OpenWrt to flash slot 0 and reboots (2-3 minutes). The stock
firmware stays in slot 1. Put the PC interface back to DHCP.

## 8. First login

- Web interface: <http://192.168.1.1>, user `root`, no password. Set one
  under **System -> Administration**.
- If the network on the WAN side also uses `192.168.1.0/24`, change the LAN
  address first (**Network -> Interfaces -> LAN**, e.g. `192.168.2.1`), then
  connect the WAN cable. From the shell, keep the prefix length, because the
  address and prefix are stored together:

  ```sh
  uci set network.lan.ipaddr='192.168.2.1/24'
  uci commit network && /etc/init.d/network reload
  ```
- Wi-Fi is off until you configure it under **Network -> Wireless**.
- To install packages, switch to the H3600 package feed first (section 11).

## 9. Optional speed features

Both are on the page **Network -> Firewall**, section **Routing/NAT Offloading**.

- **Flow offloading type: Hardware flow offloading.** Established IPv4
  connections between WAN and LAN are forwarded by the SoC's packet processor
  (940 Mbit/s down, 930 up, CPU about 5%). IPv6, PPPoE and VLAN traffic stay in
  software.
- **Hardware LAN switching.** Traffic between LAN ports of the same bridge is
  switched by the Ethernet switch (~940 Mbit/s) instead of the CPU (~600).
  The router itself and Wi-Fi clients are still reached through the CPU, and a
  device that moves between cable and Wi-Fi is reachable again within about a
  second. Traffic switched in hardware does not pass bridge firewall rules or
  packet captures on the router.

From the command line:

```sh
uci set firewall.@defaults[0].flow_offloading=1
uci set firewall.@defaults[0].flow_offloading_hw=1
uci commit firewall && /etc/init.d/firewall restart
uci set hw_switching.settings.enabled=1
uci commit hw_switching && /etc/init.d/hw_switching reload
```

## 10. Use as a Wi-Fi access point behind another router

Connect a LAN port of the H3600 to a LAN port of the main router. Then, with
the main router handing out addresses (example: main router `192.168.1.1`):

```sh
# LAN address inside the main network, no DHCP or RA from the H3600
uci set network.lan.ipaddr='192.168.1.2/24'
uci set network.lan.gateway='192.168.1.1'
uci add_list network.lan.dns='192.168.1.1'
uci set dhcp.lan.ignore='1'
uci set dhcp.lan.dhcpv6='disabled'
uci set dhcp.lan.ra='disabled'
uci commit
# Wi-Fi on both bands, bridged to the LAN
uci set wireless.radio0.disabled='0'
uci set wireless.radio1.disabled='0'
uci set wireless.default_radio0.ssid='MyNet'; uci set wireless.default_radio0.encryption='sae-mixed'; uci set wireless.default_radio0.key='<password>'; uci set wireless.default_radio0.disabled='0'
uci set wireless.default_radio1.ssid='MyNet'; uci set wireless.default_radio1.encryption='sae-mixed'; uci set wireless.default_radio1.key='<password>'; uci set wireless.default_radio1.disabled='0'
uci commit wireless
# optional: switch the wired LAN ports in hardware
uci set hw_switching.settings.enabled=1; uci commit hw_switching
reboot
```

Afterwards the H3600 is reached at `192.168.1.2`. Clients on its Wi-Fi and LAN
ports get their addresses from the main router. The WAN port stays unused (to
use it as a fifth LAN port, add `wan` to `br-lan` under **Network -> Interfaces
-> Devices**).

## 11. Package feed

The image keeps OpenWrt's standard feed settings, which point to
`downloads.openwrt.org`. OpenWrt's servers do not carry packages for this
device yet (no kernel modules at all), so use the H3600 feed on
`https://openwrt.style.dev/h3600`, which carries the same packages as
OpenWrt's own feeds, built from the same sources as the image: all kernel
modules and the base, luci, packages, routing, telephony and video feeds
(packages that OpenWrt's build servers cannot build either are missing there
too). Its indexes are signed with the build key that the image already trusts
(`/etc/apk/keys/public-key.pem`, also published as
<https://openwrt.style.dev/h3600/public-key.pem>).

In LuCI: **System -> Software -> Configure apk...**

- In `distfeeds.list`, put `#` in front of every line.
- In `customfeeds.list`, add:

  ```
  https://openwrt.style.dev/h3600/targets/sanechips/generic/packages/packages.adb
  https://openwrt.style.dev/h3600/packages/arm_cortex-a9/base/packages.adb
  https://openwrt.style.dev/h3600/packages/arm_cortex-a9/luci/packages.adb
  https://openwrt.style.dev/h3600/packages/arm_cortex-a9/packages/packages.adb
  https://openwrt.style.dev/h3600/packages/arm_cortex-a9/routing/packages.adb
  https://openwrt.style.dev/h3600/packages/arm_cortex-a9/telephony/packages.adb
  https://openwrt.style.dev/h3600/packages/arm_cortex-a9/video/packages.adb
  ```

- Save, then **Update lists**.

From the shell, the same:

```sh
sed -i 's/^https/# https/' /etc/apk/repositories.d/distfeeds.list
for f in targets/sanechips/generic/packages packages/arm_cortex-a9/base \
         packages/arm_cortex-a9/luci packages/arm_cortex-a9/packages \
         packages/arm_cortex-a9/routing packages/arm_cortex-a9/telephony \
         packages/arm_cortex-a9/video; do
    echo "https://openwrt.style.dev/h3600/$f/packages.adb"
done >> /etc/apk/repositories.d/customfeeds.list
apk update
```

`customfeeds.list` is kept across upgrades; `distfeeds.list` is rewritten by
every upgrade, so comment its lines out again after one.

Kernel modules only fit the kernel they were built with. After a firmware
upgrade, install modules from the feed that belongs to that firmware.

The router has about 15 MB free for extra packages. Small ones (VPN, adblock,
statistics, ...) fit; big ones (docker, clamav, crowdsec, openlist) need a USB
drive as extra storage. USB storage support is not in the image; install it
with:

```sh
apk update
apk add kmod-usb-storage block-mount kmod-fs-ext4 e2fsprogs
```

and follow the OpenWrt "extroot" guide
(<https://openwrt.org/docs/guide-user/additional-software/extroot_configuration>)
to move the package storage onto the drive.

## 12. Upgrades

**System -> Backup / Flash Firmware -> Flash image**, choose the new
`...-squashfs-sysupgrade.bin`, keep settings. From the shell:
`sysupgrade /tmp/<file>-squashfs-sysupgrade.bin`.

## 13. Recovery

- **OpenWrt does not start / you want the stock firmware back:** cspboot boots
  slot 0 only while its checksums are valid. Otherwise it boots the stock
  firmware in slot 1. Note that stock then copies itself into slot 0: to go
  back to OpenWrt, repeat steps 4-7.
- **No console output, no network:** check the serial wiring (TX/RX crossed,
  3.3 V), then power-cycle and watch for the cspboot banner.
- **Settings broken:** hold the reset button for 5 s or longer while the
  router runs; the power LED starts blinking red, and on release the OpenWrt
  settings are reset (a short press reboots). Or, on the serial console, press `f` and Enter when OpenWrt
  offers failsafe mode during boot, then run `firstboot -y && reboot`.

## 14. Build it yourself

The target is `sanechips/generic`, profile `zte_zxhn-h3600`. Everything needed
is published next to the images (<https://openwrt.style.dev/h3600/source/>):

| File | Content |
|------|---------|
| `h3600-openwrt.patch` | all H3600 changes as one patch, for `git am` on OpenWrt `main` at `101929399c` (2026-09-27) |
| `luci-app-firewall-hardware-LAN-switching.patch` | the LuCI checkbox for hardware LAN switching (feeds/luci) |
| `feeds.conf` | the exact feed revisions of the published build |
| `h3600-image.config` | configuration seed of the firmware images |
| `h3600-feed.config` | configuration seed of the complete package feed |
| `official-arm_cortex-a9-packages.txt` | the packages OpenWrt publishes for arm_cortex-a9 (the feed must contain all of them) |
| `checkfeed.py`, `mkfeedconfig.py` | check the built feed against that list; regenerate the feed configuration from it |

You need a Linux PC with OpenWrt's build prerequisites
(<https://openwrt.org/docs/guide-developer/toolchain/install-buildsystem>).
The firmware needs about 25 GB of disk; the complete package feed about 60 GB
more and several hours on a fast machine.

### Sources

The H3600 changes are the branch `zte-zxhn-h3600` of
<https://github.com/ghahramani/openwrt> (OpenWrt `main` plus the H3600
commits). The build files come from <https://openwrt.style.dev/h3600/source/>.

```sh
git clone -b zte-zxhn-h3600 https://github.com/ghahramani/openwrt.git h3600-openwrt
cd h3600-openwrt
./scripts/feeds update -a
./scripts/feeds install -a
curl -fO https://openwrt.style.dev/h3600/source/luci-app-firewall-hardware-LAN-switching.patch
git -C feeds/luci apply luci-app-firewall-hardware-LAN-switching.patch
```

The LuCI patch adds the "Hardware LAN switching" checkbox; it is the only
change to the feeds. To get the exact feed revisions of the published build,
run `curl -fo feeds.conf https://openwrt.style.dev/h3600/source/feeds.conf`
before `./scripts/feeds update -a`. Instead of the branch you can also apply
`h3600-openwrt.patch` with `git am` to OpenWrt `main` at `101929399c`.

LuCI packages take their version from the git history of the luci feed.
The published build, like OpenWrt's build servers, uses a shallow clone
(`git clone --depth 1`), so every LuCI package carries the version of the
feed's head commit; a full clone gives the same code older-looking versions.

### Kernel and firmware

```sh
curl -fo .config https://openwrt.style.dev/h3600/source/h3600-image.config
make defconfig
make -j$(nproc) download
make -j$(nproc)
```

`make` builds the toolchain, the kernel (`target/linux/sanechips`, patches in
`patches-6.18/`, configuration in `config-6.18`), the packages of the image and
the images in `bin/targets/sanechips/generic/`:
`...-initramfs.uImage` (step 5) and `...-squashfs-sysupgrade.bin` (step 7).

To rebuild only the kernel after changing it: `make -j$(nproc) target/linux/compile`,
then `make -j$(nproc) target/install` for new images. `make kernel_menuconfig`
edits the kernel configuration. Kernel modules only load into a kernel with
the same configuration, so build the images and the package feed from the
same tree without changing the kernel configuration in between.

### Complete package feed

The feed contains the same packages as OpenWrt's own `arm_cortex-a9` feeds.
`h3600-feed.config` selects every package (`CONFIG_ALL=y`) and then excludes,
by name, the ones OpenWrt does not publish because they fail on its build
servers too (the published list of OpenWrt's packages is
`official-arm_cortex-a9-packages.txt`). It also removes each package's build
directory after packaging it (`CONFIG_AUTOREMOVE=y`). A few unpublished
packages are still pulled in as dependencies of published ones (`ffmpeg` by
`go2rtc`, for example) and fail as they do for OpenWrt, so the build ignores
errors, and `checkfeed.py` checks afterwards that every package OpenWrt
publishes was built:

```sh
curl -fO https://openwrt.style.dev/h3600/source/official-arm_cortex-a9-packages.txt
curl -fO https://openwrt.style.dev/h3600/source/checkfeed.py
curl -fo .config https://openwrt.style.dev/h3600/source/h3600-feed.config
make defconfig
make -j$(nproc) download
make -j$(nproc) IGNORE_ERRORS=1 package/compile
make package/index
python3 checkfeed.py . official-arm_cortex-a9-packages.txt
```

Build the firmware first and the feed afterwards in the same tree, and run
only `package/compile` with the feed configuration, never a plain `make`:
like OpenWrt's own package builds, the packages are compiled against the
firmware's kernel. A full `make` would rebuild the kernel with options that
some packages request (e.g. `GPIO_CDEV` for libgpiod), and the kernel modules
of the feed would then no longer load on the firmware. Likewise, do not build
the firmware with the feed configuration: with every package selected, two
libraries (`libexpat`, `libpcre2`) are pulled into the image by option
defaults of `tvheadend` and `libstrophe`.

The packages end up in `bin/targets/sanechips/generic/packages/` (kernel
modules and target packages) and `bin/packages/arm_cortex-a9/<feed>/`. The
indexes (`packages.adb`) are signed with the build key in `private-key.pem`,
created on the first build; the images you build trust this key
(`/etc/apk/keys/public-key.pem`). To serve your own feed, publish the two
directories with the same layout as <https://openwrt.style.dev/h3600/> and
use your address in the lines of section 11.
