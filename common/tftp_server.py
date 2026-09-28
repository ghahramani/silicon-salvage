import socket, struct, os, sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 6969
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', PORT))
print(f"TFTP Server listening on 0.0.0.0:{PORT}...", flush=True)

while True:
    data, addr = sock.recvfrom(1024)
    if len(data) < 2:
        continue
    opcode = struct.unpack('!H', data[:2])[0]
    if opcode == 2:  # WRQ
        raw_name = data[2:].split(bytes([0]))[0]
        filename = os.path.basename(raw_name.decode(errors='ignore'))
        print(f"Incoming file '{filename}' from {addr[0]}:{addr[1]}", flush=True)
        with open(filename, 'wb') as f:
            tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            tx.settimeout(5.0)
            tx.sendto(struct.pack('!HH', 4, 0), addr)
            expected = 1
            while True:
                try:
                    pkt, c_addr = tx.recvfrom(1024)
                except socket.timeout:
                    print(f"Timeout waiting for data on {filename}", flush=True)
                    break
                p_op, blk = struct.unpack('!HH', pkt[:4])
                if p_op == 3:  # DATA
                    if blk == expected:
                        chunk = pkt[4:]
                        f.write(chunk)
                        tx.sendto(struct.pack('!HH', 4, blk), c_addr)
                        expected = (expected + 1) % 65536
                        if len(chunk) < 512:
                            print(f"Saved {filename} ({f.tell()} bytes)", flush=True)
                            break
                    else:
                        tx.sendto(struct.pack('!HH', 4, (expected - 1) % 65536), c_addr)
            tx.close()
