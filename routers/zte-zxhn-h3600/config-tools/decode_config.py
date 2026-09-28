"""Decode H3600 V9 backups locally; validates CRCs and XML before writing.

Format/key reference: https://lacerta.es/zteh3600p/ztetool.py
Requires the openssl command. Does not contact or modify the router.
"""
import hashlib
import io
import os
from pathlib import Path
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zlib


def chunks(stream):
    while True:
        header = stream.read(12)
        if len(header) != 12:
            raise ValueError('Incomplete chunk header')
        plain_size, stored_size, more = struct.unpack('>III', header)
        data = stream.read(stored_size)
        if len(data) != stored_size:
            raise ValueError('Incomplete download: truncated chunk')
        yield plain_size, data
        if not more:
            break


def decode(data):
    outer = io.BytesIO(data)
    header = outer.read(60)
    if len(header) != 60 or struct.unpack('>II', header[:8]) != (0x01020304, 4):
        raise ValueError('Not the expected H3600 encrypted backup format')
    key = hashlib.sha256(b'H3600V9Key02660008').hexdigest()
    iv = hashlib.sha256(b'H3600V9Iv02660008').hexdigest()[:32]
    decrypted = bytearray()
    for size, ciphertext in chunks(outer):
        result = subprocess.run(['openssl', 'enc', '-d', '-aes-256-cbc', '-nopad',
                                 '-K', key, '-iv', iv], input=ciphertext,
                                capture_output=True, check=True)
        decrypted.extend(result.stdout[:size])
    if outer.tell() != len(data):
        raise ValueError('Unexpected trailing bytes in backup')
    inner = io.BytesIO(decrypted)
    header = inner.read(60)
    magic, kind, expected_size, _, _, expected_crc, header_crc = struct.unpack('>7I', header[:28])
    if (magic, kind) != (0x01020304, 0):
        raise ValueError('Decryption key did not produce the expected inner header')
    if zlib.crc32(header[:24]) != header_crc:
        raise ValueError('Inner header CRC mismatch')
    xml = bytearray()
    crc = 0
    for size, compressed in chunks(inner):
        crc = zlib.crc32(compressed, crc)
        block = zlib.decompress(compressed)
        if len(block) != size:
            raise ValueError('Chunk size mismatch')
        xml.extend(block)
    if len(xml) != expected_size or crc != expected_crc:
        raise ValueError('Payload size or CRC mismatch')
    ET.fromstring(xml)
    return bytes(xml)


if __name__ == '__main__':
    source, target = map(Path, sys.argv[1:])
    data = source.read_bytes()
    xml = decode(data)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(xml)
    print(f'Decoded {len(data)} bytes to {len(xml)} bytes; header CRC, payload CRC, sizes and XML verified.')
