#!/usr/bin/env python3
"""RAM-only boot using the existing vendor shell and a bounded serial state machine."""
import argparse, fcntl, importlib.util, os, re, select, termios, time, socket, subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("image");p.add_argument("--wait",action="store_true");p.add_argument("--from-openwrt",action="store_true");p.add_argument("--from-uboot", action="store_true");a=p.parse_args()
assert re.fullmatch(r"[A-Za-z0-9_.-]+",a.image)
root=Path(__file__).resolve().parents[2]
assert (root/"h3600/tftp_root"/a.image).is_file()
pw=(root/"h3600/backup/uboot-password.txt").read_text().strip().encode()
fd=os.open("/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BG03G1LJ-if00-port0",os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
t=termios.tcgetattr(fd);t[0]=0;t[1]=0;t[2]=termios.CS8|termios.CREAD|termios.CLOCAL;t[3]=0;t[4]=t[5]=termios.B115200
termios.tcsetattr(fd,termios.TCSANOW,t)
log=(root/"latest/artifacts/serial_live2.log").open("ab",buffering=0)
def wr(s):
 b=s if isinstance(s,bytes) else s.encode()
 end=time.monotonic()+3
 while b:
  if time.monotonic()>end: raise TimeoutError("serial write")
  if select.select([],[fd],[],0.1)[1]:
   try: n=os.write(fd,b);b=b[n:]
   except BlockingIOError: pass
def wait(pattern,timeout,quiet=False):
 buf=b"";end=time.monotonic()+timeout
 while time.monotonic()<end:
  if select.select([fd],[],[],0.1)[0]:
   c=os.read(fd,8192)
   if not c: raise RuntimeError("serial disconnected")
   buf+=c
   if not quiet:
    c2=c.replace(pw,b"[REDACTED]");log.write(c2);print(c2.decode(errors="replace"),end="",flush=True)
   if re.search(pattern,buf,re.I): return buf
 raise TimeoutError("waiting for "+repr(pattern))
def ub(c,timeout=10):
 wr(c+"\r");return wait(rb"=> ?",timeout)

def _get_host_ip():
 return "192.168.55.14"  # confirmed wired interface (enp129s0) IP

# ---- Boot entry path ----
if a.from_openwrt:
 wr("reboot\r")

if a.from_uboot:
 print("Capturing U-Boot => prompt...", flush=True)
 wr(b"\x03\r")
 wait(rb"=> ?", 10)
 print("U-Boot prompt captured", flush=True)
else:
 if a.wait:
  print("READY: waiting for physical router power cycle", flush=True)
 elif not a.from_openwrt:
  # telnet reboot path
  src=root/"h3600/backup/vendor_telnet.py"
  spec=importlib.util.spec_from_file_location("vendor",src);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
  tn=v.T()
  assert tn.login(), "vendor shell login failed"
  print("Vendor shell authenticated; requesting reboot for RAM boot", flush=True)
  tn.cmd("reboot",2);tn.close()
 # Wait for boot mode prompt – 240 s when power-cycled manually
 print("Waiting for boot mode gate...", flush=True)
 wait(rb"Press 1 means entering boot mode", 240 if (a.wait or a.from_openwrt) else 60)
 wr(b"1")
 print("Sent '1', waiting for password prompt...", flush=True)
 wait(rb"(?:password|\*\*\*)", 10)
 time.sleep(0.3)
 wr(pw+b"\r")
 print("Sent password, waiting for U-Boot prompt...", flush=True)
 wait(rb"=> ?",15,quiet=True)
 print("U-Boot prompt authenticated", flush=True)

# ---- Network setup ----
host_ip = _get_host_ip()
print(f"Host TFTP server IP: {host_ip}", flush=True)
ub("setenv ipaddr 192.168.55.1")
ub(f"setenv serverip {host_ip}")
print("Warming up ethernet link...", flush=True)
ub(f"ping {host_ip}", 15)

# ---- TFTP transfer ----
print(f"Starting TFTP transfer of {a.image}...", flush=True)
b=ub("tftp 0x43000000 "+a.image, 180)
assert b"ransferred" in b, "TFTP failed"
print("TFTP transfer complete. Booting from RAM...", flush=True)

# ---- Boot ----
wr("bootm 0x43000000\r")
wait(rb"Please press Enter to activate this console", 120)
time.sleep(2);wr(b"\r")
wait(rb"(?:root@|BusyBox|# )", 20)
print("RAM boot reached OpenWrt console", flush=True)
os.close(fd);log.close()
