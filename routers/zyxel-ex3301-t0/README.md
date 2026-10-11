# OpenWrt on the Zyxel EX3301-T0

This guide installs OpenWrt on a Zyxel EX3301-T0. OpenWrt goes into flash
slot 0; the Zyxel firmware stays in slot 1, so you can always switch back.
You need a serial console for the first installation only; later upgrades run
from OpenWrt itself.

The images are built from the branch `zyxel-ex3301-t0` of
<https://github.com/ghahramani/openwrt> (OpenWrt `main` plus the EX3301-T0
changes).

## What works

- 4x Gigabit LAN (`lan1`-`lan4`) and the Gigabit WAN port on the built-in
  switch, with the port LEDs.
- Wi-Fi 6, 2.4 GHz and 5 GHz (MediaTek MT7915).
- Front-panel LEDs (power, internet, WAN, LAN, 2.4 GHz, 5 GHz).
- Settings are kept across reboots and upgrades.
- `sysupgrade` from OpenWrt (LuCI or shell).
- The image is OpenWrt's standard package set plus the LuCI web interface.

Not supported yet: the VDSL modem.

## 1. What you need

- A USB-to-serial adapter set to **3.3 V**. Never use 5 V: it damages the SoC.
- A PC with an Ethernet port, a TFTP server and a terminal program
  (`minicom` is recommended; `screen` often misses the short bootloader
  prompt).
- The files from <https://openwrt.style.dev/ex3301-t0/>:
  - `openwrt-econet-en751627-zyxel_ex3301-t0-squashfs-tclinux.trx`
    (installation from the bootloader)
  - `openwrt-econet-en751627-zyxel_ex3301-t0-squashfs-sysupgrade.bin`
    (upgrades from OpenWrt)

  Check them against `sha256sums`.

## 2. Serial console

Connect **three wires only**: adapter GND to router GND, adapter TX to router
RX, adapter RX to router TX. Leave VCC unconnected; the router runs from its
own power supply. Settings: 115200 baud, 8N1, no hardware flow control.

```sh
minicom -D /dev/ttyUSB0 -b 115200
```

In minicom, turn hardware flow control off: `Ctrl+A`, `O`, *Serial port
setup*, `F`, then *Exit*.

## 3. Prepare the PC

Give the PC's Ethernet port the address `192.168.1.2/24` (no gateway) and
connect it to a LAN port of the router. Save the installation image under the
name the bootloader expects, `RAS.bin`, and serve it over TFTP, for example
with Docker:

```sh
mkdir -p ~/tftp
cp openwrt-econet-en751627-zyxel_ex3301-t0-squashfs-tclinux.trx ~/tftp/RAS.bin
docker run -d --rm --name tftp --network host -v ~/tftp:/var/tftpboot pghalliday/tftp
```

## 4. Stop the Zyxel bootloader

Switch the router on with minicom open and **tap the lowercase `b` key
repeatedly** until the bootloader prompt appears (`x`, which the prompt also
offers, often does not stop the boot):

```
Press 'x' or 'b' key in 1 secs to enter or skip bootloader upgrade.
...
zloader>
```

If the router boots on, switch it off and try again.

## 5. Install OpenWrt into slot 0

At the bootloader prompt:

```
ATEN
ATUR RAS.bin,0
```

`ATEN` enables the flash commands (answer: `OK`). `ATUR RAS.bin,0` downloads
`RAS.bin` from `192.168.1.2` and writes it to **slot 0**. Always type the `,0`:
it keeps the Zyxel firmware in slot 1. Once flashing finishes, the router
automatically prints `OK` and reboots into OpenWrt (no need to type `ATGO`).

## 6. First login

- Web interface: <http://192.168.1.1>, user `root`, no password. Set one under
  **System -> Administration**.
- SSH: `ssh root@192.168.1.1`.
- Put the PC back to DHCP when you are done.
- If the network on the WAN side also uses `192.168.1.0/24`, change the LAN
  address first (**Network -> Interfaces -> LAN**), then connect the WAN cable.

## 7. Check that everything works

1. **Boot log** (serial console): the bad-block tables are found
   (`en75_bmt: BBT & BMT found`) and the shell prompt is `root@OpenWrt`.
2. **Ports**: plug a cable into each LAN port in turn; the router answers
   `ping 192.168.1.1` on every port, and the port LED follows the link. A
   cable to your upstream router on WAN gets an address
   (**Network -> Interfaces -> WAN**).
3. **Wi-Fi**: enable both radios under **Network -> Wireless**, connect a
   phone to each.
4. **Settings survive a reboot**:
   ```sh
   touch /etc/persistence-test && sync && reboot
   ```
   After the reboot, `ls /etc/persistence-test` still finds the file.
5. **Upgrade**: run the upgrade of section 8 with the same image; the router
   comes back with your settings.

## 8. Upgrades

In LuCI: **System -> Backup / Flash Firmware -> Flash new firmware image**,
choose the new `...-squashfs-sysupgrade.bin`, keep the settings. From the
shell:

```sh
scp -O openwrt-econet-en751627-zyxel_ex3301-t0-squashfs-sysupgrade.bin root@192.168.1.1:/tmp/
ssh root@192.168.1.1 sysupgrade /tmp/openwrt-econet-en751627-zyxel_ex3301-t0-squashfs-sysupgrade.bin
```

Add `-n` to `sysupgrade` to start with default settings instead.

## 9. Back to the Zyxel firmware

The Zyxel firmware stays untouched in slot 1. To boot it:

```sh
en75_chboot factory
reboot
```

`en75_chboot` alone shows the current slot; `en75_chboot openwrt` switches
back to OpenWrt. If OpenWrt does not start at all, stop the bootloader
(section 4) and install again (section 5).

## 10. Build it yourself

```sh
git clone -b zyxel-ex3301-t0 https://github.com/ghahramani/openwrt.git && cd openwrt
./scripts/feeds update -a && ./scripts/feeds install -a
cat > .config <<'EOF'
CONFIG_TARGET_econet=y
CONFIG_TARGET_econet_en751627=y
CONFIG_TARGET_econet_en751627_DEVICE_zyxel_ex3301-t0=y
CONFIG_PACKAGE_luci=y
EOF
make defconfig
make -j$(nproc) download
make -j$(nproc)
```

The images are in `bin/targets/econet/en751627/`.
