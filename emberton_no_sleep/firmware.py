"""Reproduce the hardware-tested patch without distributing vendor firmware."""
import hashlib
import struct

BASE = 0x08133000
SIZE = 0x1F9000
SITE = 0x081A74E8
STUB = 0x0832B000
SECTORS = (0x0832B000, 0x081A7000)  # helper must be installed before hook
STAGE = 0x004A1000
STOCK_SHA = '72b7ba32aadf5c48f8ca9946da56f9383c0d4d9649142eb2e8b5559bc68f20ae'
PATCHED_SHA = '37ba02a3a249e5dc3928a686d43620413ea3c3668766b17793996d9aec43f47b'
BOOT_SHA = '7167ff65d3425bdc9716a75ae9ab3d2e20e690a012642a0c78938b1eba57f4cf'
PACKAGE_SHA = {
    STOCK_SHA: '12c2e7349d8c9a601ead56d7af4b7cbf7bbc6c01eb1f1ddc76c486fd7f568585',
    PATCHED_SHA: 'e946425aee74cc4579522da3a36d0b755a479daa9c02b373ab796e1f1d8b2291',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def branch(pc, target, link=True):
    delta = target - (pc + 4)
    require(delta % 2 == 0 and -(1 << 24) <= delta < (1 << 24), 'Invalid Thumb branch')
    sign, i1, i2 = (delta >> 24) & 1, (delta >> 23) & 1, (delta >> 22) & 1
    j1, j2 = (~(i1 ^ sign)) & 1, (~(i2 ^ sign)) & 1
    return struct.pack('<HH', 0xF000 | sign << 10 | (delta >> 12) & 0x3FF,
                       (0xD000 if link else 0x9000) | j1 << 13 | j2 << 11 | (delta >> 1) & 0x7FF)


def patched(stock):
    require(len(stock) == SIZE and sha(stock) == STOCK_SHA, 'Unsupported stock application SHA256')
    require(stock[SITE-BASE:SITE-BASE+4] == bytes.fromhex('31493248'), 'Hook bytes differ')
    require(stock[STUB-BASE:STUB-BASE+40] == b'\xff' * 40, 'Helper space is not erased')
    require(branch(0x081A7510, 0x081ABD24) == stock[0x081A7510-BASE:0x081A7514-BASE], 'Branch encoding mismatch')
    helper = bytes.fromhex('1cb5') + branch(STUB+2, 0x081ABD24)
    helper += bytes.fromhex('0028bde81c4002d1044904487047024900200860')
    helper += branch(STUB+26, 0x081A754A, link=False) + bytes.fromhex('00bf')
    helper += struct.pack('<II', 0x1423A248, 0x1423A1FA)
    require(len(helper) == 40, 'Invalid helper size')
    output = bytearray(stock)
    output[SITE-BASE:SITE-BASE+4] = branch(SITE, STUB)
    output[STUB-BASE:STUB-BASE+40] = helper
    require(sha(output) == PATCHED_SHA, 'Patched image does not match tested build')
    return bytes(output)


def package(app):
    digest = sha(app)
    require(len(app) == SIZE and digest in PACKAGE_SHA, 'Unsupported package input')
    def tlv(kind, value):
        return struct.pack('<HH', kind, len(value)) + value
    payload = b''.join(app[a-BASE:a-BASE+4096] for a in SECTORS)
    movers = b''.join(struct.pack('<III', 4096+i*4096, 4096, a-0x08000000)
                      for i, a in enumerate(SECTORS))
    hashes = b''.join(hashlib.sha256(payload[i:i+4096]).digest() for i in range(0, 8192, 4096))
    fields = tlv(0x11, struct.pack('<BBII', 0, 1, 4096, 8192))
    fields += tlv(0x12, struct.pack('<I', 2) + movers)
    fields += tlv(0x14, struct.pack('<I', 2) + hashes) + tlv(0x13, b'9.1.7\0')
    header = bytearray(b'\xff' * 4096)
    header[256:256+len(fields)] = fields
    output = header + payload
    output[:32] = hashlib.sha256(output[256:]).digest()
    require(sha(output) == PACKAGE_SHA[digest], 'Package differs from tested artifact')
    return bytes(output)


def checksum(data):
    crc = 0
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31 if crc & 0x80 else crc << 1) & 255
    return int(f'{crc:08b}'[::-1], 2)
