import hashlib, io, os, struct, subprocess, sys, zlib
from pathlib import Path
import xml.etree.ElementTree as ET

CHUNK_SIZE = 65536

def encode(xml_data: bytes) -> bytes:
    raw_chunks = [xml_data[i:i+CHUNK_SIZE] for i in range(0, len(xml_data), CHUNK_SIZE)]
    comp_chunks = [zlib.compress(c, 9) for c in raw_chunks]

    rolling_crc = 0
    for comp in comp_chunks:
        rolling_crc = zlib.crc32(comp, rolling_crc)

    inner_chunks = bytearray()
    curr_offset = 60
    for i, (raw_c, comp_c) in enumerate(zip(raw_chunks, comp_chunks)):
        next_offset = curr_offset + 12 + len(comp_c)
        more = next_offset if i < len(raw_chunks) - 1 else 0
        hdr = struct.pack('>III', len(raw_c), len(comp_c), more)
        inner_chunks.extend(hdr)
        inner_chunks.extend(comp_c)
        last_offset = curr_offset
        curr_offset = next_offset

    # Inner header (60 bytes)
    h_pre = struct.pack('>6I', 0x01020304, 0, len(xml_data), last_offset, CHUNK_SIZE, rolling_crc)
    h_crc = zlib.crc32(h_pre)
    inner_header = h_pre + struct.pack('>I', h_crc) + bytes(60 - 28)

    inner_data = inner_header + inner_chunks
    pad_len = (16 - (len(inner_data) % 16)) % 16
    padded_inner = inner_data + bytes(pad_len)

    key = hashlib.sha256(b"H3600V9Key02660008").hexdigest()
    iv = hashlib.sha256(b"H3600V9Iv02660008").hexdigest()[:32]

    res = subprocess.run([
        "openssl", "enc", "-aes-256-cbc", "-nopad",
        "-K", key, "-iv", iv
    ], input=padded_inner, capture_output=True, check=True)
    ciphertext = res.stdout

    outer_header = struct.pack(">II", 0x01020304, 4) + bytes(52)
    outer_chunk = struct.pack(">III", len(inner_data), len(ciphertext), 0) + ciphertext
    return outer_header + outer_chunk

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input.xml> <output.bin>")
        sys.exit(1)
    source = Path(sys.argv[1])
    target = Path(sys.argv[2])
    xml_data = source.read_bytes()
    ET.fromstring(xml_data)
    encoded = encode(xml_data)
    target.write_bytes(encoded)
    print(f"Encoded {len(xml_data)} bytes XML -> {len(encoded)} bytes config: {target}")
