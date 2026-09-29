import os
import socket
import sys
import time

HOST = os.environ.get("ROUTER_IP", "192.168.1.1")
USER = os.environ.get("ROUTER_USER", "admin")
PWD = os.environ.get("ROUTER_PASS", "")


def scrub(d):
    out = bytearray()
    i = 0
    while i < len(d):
        if d[i] == 255 and i + 2 < len(d):
            i += 3
        else:
            out.append(d[i])
            i += 1
    return bytes(out)


class T:
    def __init__(self, host=HOST, user=USER, password=PWD):
        if not password:
            raise ValueError("Password required: set ROUTER_PASS environment variable or pass password argument")
        self.host = host
        self.user = user
        self.password = password
        self.s = socket.create_connection((self.host, 23), timeout=8)
        self.s.settimeout(2)

    def rd(self, t=2.0):
        self.s.settimeout(t)
        b = b""
        try:
            while True:
                c = self.s.recv(4096)
                if not c:
                    break
                b += c
        except Exception:
            pass
        return scrub(b)

    def login(self):
        self.rd(1.5)
        self.s.sendall(self.user.encode() + b"\r\n")
        time.sleep(0.7)
        self.rd(1)
        self.s.sendall(self.password.encode() + b"\r\n")
        time.sleep(1.5)
        b = self.rd(2)
        return b"# " in b or b"ash" in b

    def cmd(self, c, t=4.0):
        self.s.sendall(c.encode() + b"\r\n")
        time.sleep(0.3)
        return self.rd(t).decode(errors="ignore")

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


if __name__ == "__main__":
    t = T()
    print("login status:", t.login())
    print(t.cmd("uname -a; uptime"))
    t.close()
