#!/usr/bin/env python3
"""Bounded serial console probe/command; log traffic and require a real completion line."""
import argparse, fcntl, os, re, select, termios, time, uuid
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("command", nargs="?")
p.add_argument("--file",type=Path)
p.add_argument("--timeout", type=float, default=8)
a=p.parse_args()
if a.file: a.command=a.file.read_text().strip().replace("\n","; ")
root=Path(__file__).resolve().parents[2]
fd=os.open("/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BG03G1LJ-if00-port0", os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
t=termios.tcgetattr(fd)
t[0]=0;t[1]=0;t[2]=termios.CS8|termios.CREAD|termios.CLOCAL;t[3]=0
t[4]=t[5]=termios.B115200
termios.tcsetattr(fd,termios.TCSANOW,t)
marker="CODEX_"+uuid.uuid4().hex
payload=(a.command+"; printf "+"'\\n"+marker+":%s\\n' "+'"$?"'+"\r") if a.command else "\r"
with (root/"latest/artifacts/serial_live2.log").open("ab",buffering=0) as log:
 log.write(("\n[codex console] "+str(a.command or "probe")+"\n").encode())
 os.write(fd,payload.encode())
 buf=b"";end=time.monotonic()+a.timeout
 while time.monotonic()<end:
  if select.select([fd],[],[],0.2)[0]:
   try: c=os.read(fd,8192)
   except BlockingIOError: continue
   if not c: break
   log.write(c);buf+=c
   print(c.decode(errors="replace"),end="",flush=True)
   if a.command and re.search(rb"(?:^|[\r\n])"+marker.encode()+rb":([0-9]+)[\r\n]",buf): break
os.close(fd)
if not buf: print("[no serial response]")
if a.command:
 m=re.search(rb"(?:^|[\r\n])"+marker.encode()+rb":([0-9]+)[\r\n]",buf)
 raise SystemExit(int(m[1]) if m else 124)
