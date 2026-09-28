# OpenWrt on the Zyxel WX3100-T0

This guide installs OpenWrt on a Zyxel WX3100-T0 (Wi-Fi 6 access point /
extender). OpenWrt goes into flash slot 0; the Zyxel firmware stays in slot 1,
so you can always switch back. You need a serial console for the first
installation only; later upgrades run from OpenWrt itself.

The images are built from the branch `zyxel-wx3100-t0` of
<https://github.com/ghahramani/openwrt> (OpenWrt `main` plus the EX3301-T0
changes it shares the SoC with, plus the WX3100-T0 support).

## What works

- 2x Gigabit Ethernet (`lan1`, `lan2`), bridged as LAN by default.
- Wi-Fi 6, 2.4 GHz and 5 GHz (MediaTek MT7915).
- LEDs (power, link, Wi-Fi, WPS) and the reset and WPS buttons.
- Settings are kept across reboots and upgrades.
- `sysupgrade` from OpenWrt (LuCI or shell).
- The image is OpenWrt's standard package set plus the LuCI web interface.

## 1. What you need

- A USB-to-serial adapter set to **3.3 V**. Never use 5 V: it damages the SoC.
- A PC with an Ethernet port, a TFTP server and a terminal program
  (`minicom` is recommended; `screen` often misses the short bootloader
  prompt).
- The files from <https://openwrt.style.dev/wx3100-t0/>:
  - `openwrt-econet-en751627-zyxel_wx3100-t0-squashfs-tclinux.trx`
    (installation from the bootloader)
  - `openwrt-econet-en751627-zyxel_wx3100-t0-squashfs-sysupgrade.bin`
    (upgrades from OpenWrt)

  Check them against `sha256sums`.

## 2. Serial console

Connect **three wires only**: adapter GND to router GND, adapter TX to router
RX, adapter RX to router TX. Leave VCC unconnected; the device runs from its
own power supply. Settings: 115200 baud, 8N1, no hardware flow control.

```sh
minicom -D /dev/ttyUSB0 -b 115200
```

In minicom, turn hardware flow control off: `Ctrl+A`, `O`, *Serial port
setup*, `F`, then *Exit*.

## 3. Prepare the PC

Give the PC's Ethernet port the address `192.168.1.2/24` (no gateway) and
connect it to one of the two Ethernet ports. Save the installation image under
the name the bootloader expects, `RAS.bin`, and serve it over TFTP, for
example with dnsmasq:

```sh
mkdir -p ~/tftp
cp openwrt-econet-en751627-zyxel_wx3100-t0-squashfs-tclinux.trx ~/tftp/RAS.bin
sudo dnsmasq -d -p 0 --enable-tftp --tftp-root="$HOME/tftp" --listen-address=192.168.1.2
```

## 4. Stop the Zyxel bootloader

Switch the device on with minicom open and **tap the lowercase `b` key
repeatedly** until the bootloader prompt appears (`x`, which the prompt also
offers, often does not stop the boot):

```
Press 'x' or 'b' key in 1 secs to enter or skip bootloader upgrade.
...
zloader>
```

If it boots on, switch it off and try again.

## 5. Install OpenWrt into slot 0

At the bootloader prompt:

```
ATEN
ATUR RAS.bin,0
```

`ATEN` enables the flash commands (answer: `OK`). `ATUR RAS.bin,0` downloads
`RAS.bin` from `192.168.1.2` and writes it to **slot 0**. Always type the `,0`:
it keeps the Zyxel firmware in slot 1. Wait for `OK`, then start OpenWrt:

```
ATGO
```

## 6. First login

- Web interface: <http://192.168.1.1>, user `root`, no password. Set one under
  **System -> Administration**.
- SSH: `ssh root@192.168.1.1`.
- Put the PC back to DHCP when you are done.

## 7. Check that everything works

1. **Boot log** (serial console): the bad-block tables are found
   (`en75_bmt: BBT & BMT found`) and the shell prompt is `root@OpenWrt`.
2. **Ports**: the device answers `ping 192.168.1.1` on both Ethernet ports,
   and the link LED follows the link.
3. **Wi-Fi**: enable both radios under **Network -> Wireless**, connect a
   phone to each.
4. **Buttons**: a short press of reset reboots the device.
5. **Settings survive a reboot**:
   ```sh
   touch /etc/persistence-test && sync && reboot
   ```
   After the reboot, `ls /etc/persistence-test` still finds the file.
6. **Upgrade**: run the upgrade of section 9 with the same image; the device
   comes back with your settings.

## 8. Access point or router

### Access point (default)

Both Ethernet ports and Wi-Fi are bridged into the LAN. To use the device as
an access point behind your main router, give it a free address in your
network and turn off its DHCP server before you connect it there (the example
assumes the main router is `192.168.1.1`; use a free address of your network):

```sh
uci set dhcp.lan.ignore='1'
uci set network.lan.ipaddr='192.168.1.2/24'
uci set network.lan.gateway='192.168.1.1'
uci add_list network.lan.dns='192.168.1.1'
uci commit
reload_config
```

Then connect a port to the main router; the web interface is at the new
address.

### Router (WAN on `lan1`)

```sh
uci del_list network.@device[0].ports='lan1'
uci set network.wan=interface
uci set network.wan.device='lan1'
uci set network.wan.proto='dhcp'
uci set network.lan.ipaddr='192.168.2.1/24'
uci set dhcp.lan.ignore='0'
uci commit
reload_config
```

Connect the main router to `lan1` and the PC to `lan2`; the web interface is
at <http://192.168.2.1>.

## 9. Upgrades

In LuCI: **System -> Backup / Flash Firmware -> Flash new firmware image**,
choose the new `...-squashfs-sysupgrade.bin`, keep the settings. From the
shell:

```sh
scp -O openwrt-econet-en751627-zyxel_wx3100-t0-squashfs-sysupgrade.bin root@192.168.1.1:/tmp/
ssh root@192.168.1.1 sysupgrade /tmp/openwrt-econet-en751627-zyxel_wx3100-t0-squashfs-sysupgrade.bin
```

Add `-n` to `sysupgrade` to start with default settings instead.

## 10. Back to the Zyxel firmware

The Zyxel firmware stays untouched in slot 1. To boot it:

```sh
en75_chboot factory
reboot
```

`en75_chboot` alone shows the current slot; `en75_chboot openwrt` switches
back to OpenWrt. If OpenWrt does not start at all, stop the bootloader
(section 4) and install again (section 5).

## 11. Build it yourself

```sh
git clone -b zyxel-wx3100-t0 https://github.com/ghahramani/openwrt.git && cd openwrt
./scripts/feeds update -a && ./scripts/feeds install -a
cat > .config <<'EOF'
CONFIG_TARGET_econet=y
CONFIG_TARGET_econet_en751627=y
CONFIG_TARGET_econet_en751627_DEVICE_zyxel_wx3100-t0=y
CONFIG_PACKAGE_luci=y
EOF
make defconfig
make -j$(nproc) download
make -j$(nproc)
```

The images are in `bin/targets/econet/en751627/`.
