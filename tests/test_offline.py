import asyncio
import io
import struct
import unittest
from unittest.mock import AsyncMock, patch
from emberton_no_sleep import firmware as fw
from emberton_no_sleep.cli import transfer, parser
from emberton_no_sleep.protocol import Frames, Link


class FirmwareTests(unittest.TestCase):
    def test_known_branch_encodings(self):
        self.assertEqual(fw.branch(fw.SITE, fw.STUB).hex(), '83f18afd')
        self.assertEqual(fw.branch(fw.STUB+26, 0x081A754A, False).hex(), '7cf696ba')
        with self.assertRaises(ValueError):
            fw.branch(0, 1)

    def test_unknown_images_rejected(self):
        for data in (b'', b'\xff' * fw.SIZE, b'\0' * fw.SIZE):
            with self.assertRaises(ValueError):
                fw.patched(data)
            with self.assertRaises(ValueError):
                fw.package(data)

    def test_crc_known_vector(self):
        self.assertEqual(fw.checksum(b'123456789'), 0x45)

    def test_framing_fragmentation_and_coalescing(self):
        first = bytes.fromhex('155b03000a1c00')
        second = bytes.fromhex('155d0500081c000100')
        frames = Frames()
        self.assertEqual(frames.feed(first[:3]), [])
        self.assertEqual(frames.feed(first[3:] + second), [first, second])

    def test_malformed_frame_rejected(self):
        for data in (bytes.fromhex('005b0300'), bytes.fromhex('155b0200'), bytes.fromhex('155bffff')):
            with self.assertRaises(ValueError):
                Frames().feed(data)

    def test_install_requires_explicit_opt_in(self):
        with patch('sys.stderr', io.StringIO()), self.assertRaises(SystemExit):
            parser().parse_args(['install', '--device', 'test', '--stock', 'test.bin'])


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_readonly_link_rejects_update(self):
        link = Link(None, io.StringIO())
        with self.assertRaisesRegex(ValueError, 'Writes disabled'):
            await link.query(0x1C08, b'\1\0')

    async def test_staging_bounds_enforced_before_transport(self):
        link = Link(None, io.StringIO())
        link.allow_update = True
        for address in (fw.BASE, fw.STAGE-256, fw.STAGE+0x3000, fw.STAGE+1):
            with self.assertRaises(ValueError):
                await link.query(0x0402, struct.pack('<BBBI', 0, 1, 0, address) + bytes(256))
        with self.assertRaises(ValueError):
            await link.query(0x0404, struct.pack('<BII', 0, 0x4000, fw.STAGE))

    async def test_unmapped_ram_rejected(self):
        with self.assertRaises(ValueError):
            await Link(None, io.StringIO()).word(0xA0000000)


class SimulatedSpeaker:
    """Protocol-level fake; never connects to hardware or imports Bleak."""
    def __init__(self, fail=None):
        self.events = []
        self.memory = bytearray(b'\xff' * 0x3000)
        self.current_state = 0xFFFF
        self.fail = fail

    def record(self, **event):
        self.events.append(('log', event))

    async def identity(self):
        return {'battery': 70}

    async def word(self, address):
        if address == 0x14239A20:
            return 0 if self.fail == 'power' else 1
        return [1, fw.STAGE, 0x354000, 0x101, 0, 0, 0][(address-0x14201FD8)//4]

    async def query(self, cmd, payload=b'', head=5, kinds=(0x5B,), timeout=15):
        self.events.append(('query', cmd))
        if cmd == 0x1C08:
            return {0x5B: b'\0', 0x5D: b'\0\1\0'}
        if cmd == 0x0404:
            return {0x5B: b'\0', 0x5D: struct.pack('<BBII', 0, 0, 0x3000, fw.STAGE)}
        if cmd == 0x1C01:
            if self.fail == 'integrity':
                raise ValueError('Device integrity rejected')
            return {0x5B: b'\0', 0x5D: b'\0\1\0\0'}
        raise AssertionError(hex(cmd))

    async def one(self, cmd, payload=b'', head=5):
        self.events.append(('one', cmd))
        if cmd == 0x0402:
            address = int.from_bytes(payload[3:7], 'little')
            offset = address-fw.STAGE
            self.memory[offset:offset+256] = payload[7:]
            return struct.pack('<BBBI', 0, 0, 1, address+256 if self.fail == 'page_ack' else address)
        if cmd in (0x1C0A, 0x1C02):
            return b'\0'
        raise AssertionError(hex(cmd))

    async def read(self, address, size):
        if self.fail == 'readback' and any(self.memory):
            # Only corrupt the programmed readback, not erase verification.
            if self.memory != b'\xff' * len(self.memory):
                return bytes(size)
        return bytes(self.memory)

    async def setstate(self, state):
        self.current_state = state

    async def state(self):
        return self.current_state


class UpdateTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, failure=None):
        speaker = SimulatedSpeaker(failure)
        data = b'\xa5' * 0x3000
        # Synthetic data allowed only inside this test; production pins real package hashes.
        with patch.dict(fw.PACKAGE_SHA, {'test-only': fw.sha(data)}), \
             patch('emberton_no_sleep.cli.asyncio.sleep', new=AsyncMock()), \
             patch('emberton_no_sleep.cli.say'):
            if failure:
                with self.assertRaises(ValueError):
                    await transfer(speaker, data)
            else:
                await transfer(speaker, data)
        return speaker

    async def test_success_commits_after_integrity(self):
        speaker = await self.exercise()
        self.assertEqual(speaker.events.count(('one', 0x0402)), 48)
        self.assertEqual(speaker.events.count(('one', 0x1C02)), 1)
        self.assertLess(speaker.events.index(('query', 0x1C01)), speaker.events.index(('one', 0x1C02)))

    async def test_failed_integrity_never_commits(self):
        speaker = await self.exercise('integrity')
        self.assertNotIn(('one', 0x1C02), speaker.events)

    async def test_bad_readback_never_checks_or_commits(self):
        speaker = await self.exercise('readback')
        self.assertNotIn(('query', 0x1C01), speaker.events)
        self.assertNotIn(('one', 0x1C02), speaker.events)

    async def test_wrong_page_ack_blocks_commit(self):
        speaker = await self.exercise('page_ack')
        self.assertNotIn(('one', 0x1C02), speaker.events)
        self.assertEqual(speaker.events.count(('one', 0x0402)), 1)

    async def test_power_loss_blocks_commit(self):
        speaker = await self.exercise('power')
        self.assertNotIn(('one', 0x1C02), speaker.events)


if __name__ == '__main__':
    unittest.main()
