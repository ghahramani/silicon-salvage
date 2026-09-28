
import hashlib
import re
import struct
import sys
import zlib

from argparse import ArgumentParser, ArgumentTypeError, FileType
from io import BytesIO

try:
	from Crypto.Cipher import AES
except:
	print('Missing library "pycryptodome".', file=sys.stderr)
	print('Please install using "pip install pycryptodome" before running this tool.', file=sys.stderr)
	exit(1)

######################################
# BEGINS BUGGY SHA256 IMPLEMENTATION #
######################################

# 32-bit right rotation
def rotr32(a, c):
	return ((a >> c) | (a << (32 - c))) & 0xFFFFFFFF

ROUND_CONSTANTS = [
	0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
	0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
	0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
	0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
	0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
	0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
	0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
	0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
]

def _sha256_raw_digest(message):
	"""Processes an already padded SHA-256 message"""

	# Initialize hash value
	digest = [
		0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
		0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
	]

	# Process message in 64 byte chunks
	for chunk in range(0, len(message), 64):
		chunk = message[chunk : chunk + 64]

		# Unpack chunk into 32-bit words in big endian
		w = list(struct.unpack('>' + 'I' * 16, chunk))

		# Extend chunk into the remaining 48 words of the message schedule array
		for i in range(16, 64):
			s0 = rotr32(w[-15], 7) ^ rotr32(w[-15], 18) ^ (w[-15] >> 3)
			s1 = rotr32(w[-2], 17) ^ rotr32(w[-2], 19) ^ (w[-2] >> 10)
			w.append((w[-16] + s0 + w[-7] + s1) & 0xFFFFFFFF)

		# Initialize working variables to current hash value
		a, b, c, d, e, f, g, h = digest

		# Main compression loop
		for r_w, r_k in zip(w, ROUND_CONSTANTS):
			S1 = rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25)
			ch = (e & f) ^ ((e ^ 0xFFFFFFFF) & g)
			temp1 = (h + S1 + ch + r_k + r_w)
			S0 = rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22)
			maj = (a & b) ^ (a & c) ^ (b & c)
			temp2 = (S0 + maj)

			h = g
			g = f
			f = e
			e = (d + temp1) & 0xFFFFFFFF
			d = c
			c = b
			b = a
			a = (temp1 + temp2) & 0xFFFFFFFF

		# Add the result to the current digest
		digest = [(x + y) & 0xFFFFFFFF for x, y in zip(digest, (a, b, c, d, e, f, g, h))]

	# Pack the words in big-endian, and return as the digest
	return struct.pack('>' + 'I' * 8, *digest)

def buggy_sha256(message):
	"""
	This function implements the buggy SHA-256 function available at
	https://github.com/ilvn/SHA256/blob/d8d69dbfeeb68f31e74f8e24971332e996eed76b/mark2/sha256.c,
	in that specific commit.

	This function is what the ZTE Z3600P router is using in the libsha256.so library, for
	derivating the configuration encryption key and IV.
	"""

	# Process depending on the length of last chunk 64-byte chunk in the message
	last_chunk_len = len(message) % 64

	# If 0 to 55, all is ok, so process as regular SHA2
	if last_chunk_len <= 55:
		return hashlib.sha256(message).digest()

	# Pack message length in bits
	packed_len = struct.pack('>Q', 8 * len(message))

	# If 56 bytes:
	#  - No extra padding block is added, despite being necessary.
	#  - The total message length overwrites the 0x80 end-of-message marker.
	if last_chunk_len == 56:
		return _sha256_raw_digest(message + packed_len)

	# If 57-63:
	#  - End of message bit present
	#  - Zeros added as padding within current block as expected
	#  - Padding in padding block, instead of being zeros, uses bytes from last block due to memory
	#    not being cleared.
	message += b'\x80' + b'\x00' * (64 - last_chunk_len - 1)
	message += message[-64 : -8] + packed_len
	return _sha256_raw_digest(message)

####################################
# ENDS BUGGY SHA256 IMPLEMENTATION #
####################################

F680_HEADER = b'\x04\x03\x02\x01\x00\x00\x00\x00\x00\x00\x00\x04F680'

def chunk_reader(fin):
	has_next = True

	while has_next:
		header = fin.read(12)
		if len(header) != 12:
			raise IOError('Failed to read encrypted chunk header')

		unpacked_size, packed_size, has_next = struct.unpack('>III', header)
		chunk = fin.read(packed_size)
		if len(chunk) != packed_size:
			raise IOError('Failed to read encrypted chunk contents')

		yield chunk

def parse_serial(serial):
	serial = serial.upper()
	if not re.match(r'^ZTE[A-Z0-9]{8,32}$', serial):
		raise ArgumentTypeError('Invalid serial')
	return serial

def parse_mac(mac):
	mac = re.sub(r'[ :-]', '', mac).lower()
	if not re.match(r'^[0-9a-f]{12}$', mac):
		raise ArgumentTypeError('Invalid MAC address')
	return ':'.join([mac[0:2], mac[2:4], mac[4:6], mac[6:8], mac[8:10], mac[10:12]])

def parse_password(pwd):
	if len(pwd) != 32:
		raise ArgumentTypeError('Invalid password - must be 32 characters in length')
	return pwd

parser = ArgumentParser(
	description='ZTE configuration encoder/decoder',
)
parser.add_argument('-e', '--encode', help='Convert from XML to binary.', action='store_true')
parser.add_argument('-d', '--decode', help='Convert from binary to XML.', action='store_true')

parser.add_argument('-r', '--router', help="Router model", choices=('h3600p', 'f680', 'h3600'), required=True)
parser.add_argument('-s', '--serial', help="Device's serial number", type=parse_serial)
parser.add_argument('-m', '--mac', help="Device's MAC address", type=parse_mac)
parser.add_argument('-p', '--password', help="Device's encryption passphrase", type=parse_password)

parser.add_argument('input', help='Input file. Defaults to stdin.', nargs='?', type=FileType('rb'), default=sys.stdin.buffer)
parser.add_argument('output', help='Output file. Defaults to stdout.', nargs='?', type=FileType('wb'), default=sys.stdout.buffer)

parser.add_argument('--decrypt-only', help='Only decrypt, but do not decompress.', action='store_true')
parser.add_argument('--compress-only', help='Only compress, but do not encrypt.', action='store_true')

args = parser.parse_args()

if not (args.encode ^ args.decode):
	print('Must either encode or decode.', file=sys.stderr)
	exit(1)

if args.decode:
	if args.router == 'h3600p':
		if not args.password or not args.mac or not args.serial:
			print('Missing serial, MAC or password required for decryption', file=sys.stderr)
			exit(1)

		key = args.password + args.serial + 'Mcd5c46e'
		key = buggy_sha256(key.encode('ascii'))

		iv = 'G21b667b' + args.mac + args.password
		iv = buggy_sha256(iv.encode('ascii'))[:16]

		aes_mode = AES.MODE_CBC

		print('Generated keys:', file=sys.stderr)
		print(f'  - AES key: {key.hex()}', file=sys.stderr)
		print(f'  - AES IV:  {iv.hex()}', file=sys.stderr)
	elif args.router == 'f680':
		if not args.mac or not args.serial:
			print('Missing GPON serial or MAC required for decryption', file=sys.stderr)
			exit(1)

		if len(args.serial) != 12 or args.serial[:4] != 'ZTEG':
			print('Must specify GPON serial, not router serial', file=sys.stderr)
			exit(1)

		# Generated in pdtGetAesUserEncry.isra.0 in cspd
		mac_reverse = args.mac.split(':')
		mac_reverse.reverse()
		mac_reverse = ''.join(mac_reverse)
		key = args.serial[4:] + mac_reverse
		key = hashlib.md5(key.encode('ascii')).hexdigest().encode('ascii')[:16]

		aes_mode = AES.MODE_ECB

		print('Generated keys:', file=sys.stderr)
		print(f'  - AES key: {key.hex()}', file=sys.stderr)

		header = args.input.read(len(F680_HEADER))
		if header != F680_HEADER:
			print('Missing model header')
			exit(1)
	elif args.router == 'h3600':
		# They fucked up their algorithm and ended up with hardcoded keys lol
		key = 'H3600V9Key02660008'
		key = buggy_sha256(key.encode('ascii'))

		iv = 'H3600V9Iv02660008'
		iv = buggy_sha256(iv.encode('ascii'))[:16]

		aes_mode = AES.MODE_CBC

		print('Generated keys:', file=sys.stderr)
		print(f'  - AES key: {key.hex()}', file=sys.stderr)
		print(f'  - AES IV:  {iv.hex()}', file=sys.stderr)

	print('Decryption starts', file=sys.stderr)

	header = args.input.read(0x3C)
	if len(header) != 0x3C:
		print('Could not read encrypted file header', file=sys.stderr)
		exit(1)

	magic, fmt = struct.unpack('>II', header[0:8])
	if magic != 0x01020304 or fmt != 4:
		print('Wrong encrypted file header', file=sys.stderr)
		exit(1)

	compressed_config = args.output if args.decrypt_only else BytesIO()
	try:
		for chunk in chunk_reader(args.input):
			print(f' - Chunk: {len(chunk)} bytes', file=sys.stderr)
			if aes_mode == AES.MODE_ECB:
				chunk = AES.new(key, aes_mode).decrypt(chunk)
			else:
				chunk = AES.new(key, aes_mode, iv=iv).decrypt(chunk)
			compressed_config.write(chunk)
	except Exception as e:
		print(f'Error while decrypting file: {e}', file=sys.stderr)
		exit(1)

	if not args.decrypt_only:
		compressed_config.seek(0)

		print('Decompression starts', file=sys.stderr)

		header = compressed_config.read(0x3C)
		if len(header) != 0x3C:
			print('Could not read compressed file header', file=sys.stderr)
			exit(1)

		magic, fmt, dec_size, _, _, correct_crc, header_crc = struct.unpack('>IIIIIII', header[0:28])
		if magic != 0x01020304 or fmt != 0:
			print('Wrong compressed file header. Are the AES keys correct?', file=sys.stderr)
			exit(1)

		if zlib.crc32(header[0:24]) != header_crc:
			print('Bad compressed file header CRC. Are the AES keys correct?', file=sys.stderr)
			exit(1)

		total_size = 0
		calculated_crc = 0
		try:
			for chunk in chunk_reader(compressed_config):
				print(f' - Chunk: {len(chunk)} bytes', file=sys.stderr)
				calculated_crc = zlib.crc32(chunk, calculated_crc)
				chunk = zlib.decompress(chunk)
				total_size += len(chunk)
				args.output.write(chunk)
		except Exception as e:
			print(f'Error while decompressing file: {e}', file=sys.stderr)
			exit(1)

		print(f'Expected length: {dec_size}, processed length: {total_size}', file=sys.stderr)
		if total_size != dec_size:
			print('Decompression failed - size does not match', file=sys.stderr)
			exit(1)

		print(f'Expected CRC: {correct_crc:08x}, calculated CRC: {calculated_crc:08x}', file=sys.stderr)
		if correct_crc != calculated_crc:
			print('Decompression failed - bad CRC', file=sys.stderr)
			exit(1)
else:
	print('Compression starts', file=sys.stderr)

	plain = args.input.read()
	compressed = zlib.compress(plain, level=9)
	print(f'Compressed from {len(plain)} to {len(compressed)} bytes', file=sys.stderr)

	calculated_crc = zlib.crc32(compressed)
	print(f'Data CRC: {calculated_crc:08x}', file=sys.stderr)

	# Create compression header. We will not bother creating chunks as the device can handle
	# any size, and it has plenty of RAM to store a measly 200KB from the config file.
	header = struct.pack('>IIIIII',
		0x01020304,		# Magic (checked)
		0,				# Version (checked)
		len(plain),		# Uncompressed length (ignored)
		len(compressed),# Compressed length (ignored)
		len(plain),		# Required memory per chunk (used for malloc)
		calculated_crc	# Data CRC (checked)
	)

	header_crc = zlib.crc32(header)
	print(f'Header CRC: {header_crc:08x}', file=sys.stderr)
	header += struct.pack('>I', header_crc) + b'\x00' * (0x3C - 28)

	# Build one single chunk with its header
	chunk = struct.pack('>III', len(plain), len(compressed), 0) + compressed

	# Result is the header plus compressed data
	# The router will gladly accept compressed but unencrypted dumps, so why bother encrypting lol
	result = header + chunk

	if args.router == 'f680':
		args.output.write(F680_HEADER)

	args.output.write(result)

print('Operation succeeded', file=sys.stderr)
