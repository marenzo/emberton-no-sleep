"""Bounded Airoha RACE BLE transport; no third-party flasher imported."""
import asyncio
import json
import struct
import time
from contextlib import asynccontextmanager
from .firmware import BASE, SIZE, STAGE, require

TX = '43484152-2dab-3241-6972-6f6861424c45'
RX = '43484152-2dab-3141-6972-6f6861424c45'
WORDS = {0x14239A20, 0x1423A248, 0x1423A24C, *range(0x14201FD8, 0x14201FF4, 4)}


class Frames:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        require(len(self.buffer) <= 16384, 'Receive buffer exceeds bound')
        result = []
        while len(self.buffer) >= 4:
            size = int.from_bytes(self.buffer[2:4], 'little') + 4
            require(self.buffer[0] in (5, 0x15) and 7 <= size <= 8192, 'Invalid RACE frame')
            if len(self.buffer) < size:
                break
            result.append(bytes(self.buffer[:size]))
            del self.buffer[:size]
        return result


class Link:
    def __init__(self, client, log):
        self.client, self.log = client, log
        self.frames, self.queue = Frames(), asyncio.Queue()
        self.allow_update = False

    def record(self, **event):
        self.log.write(json.dumps({'time': time.time(), **event}) + '\n')
        self.log.flush()

    def receive(self, _, data):
        try:
            for frame in self.frames.feed(data):
                self.queue.put_nowait(frame)
        except ValueError as error:
            self.queue.put_nowait(error)

    async def query(self, cmd, payload=b'', head=5, kinds=(0x5B,), timeout=15):
        if cmd not in (0x0403, 0x1680, 0x1C00, 0x1C04):
            require(self.allow_update, 'Writes disabled until preflight passes')
            require(cmd in (0x1C08, 0x1C0A, 0x1C06, 0x0404, 0x0402, 0x1C01, 0x1C02), 'Unsupported write command')
        if cmd == 0x0404:
            require(payload == struct.pack('<BII', 0, 0x3000, STAGE), 'Erase outside staging package')
        if cmd == 0x0402:
            require(len(payload) == 263 and payload[:2] == b'\0\1', 'Invalid program request')
            address = int.from_bytes(payload[3:7], 'little')
            require(address % 256 == 0 and STAGE <= address < STAGE+0x3000, 'Program outside staging package')
        if cmd == 0x1C06:
            require(payload in (b'\x01\x02', b'\x10\x02', b'\x11\x02'), 'Unsupported update state')
        frame = struct.pack('<BBHH', head, 0x5A, len(payload)+2, cmd) + payload
        self.record(command=hex(cmd), bytes=len(frame))
        limit = self.client.services.get_characteristic(TX).max_write_without_response_size
        require(limit >= 20, 'Invalid BLE write size')
        for offset in range(0, len(frame), limit):
            await self.client.write_gatt_char(TX, frame[offset:offset+limit], response=False)
            if len(frame) > limit:
                await asyncio.sleep(.02)
        responses = {}
        deadline = time.monotonic() + timeout
        while not all(kind in responses for kind in kinds):
            reply = await asyncio.wait_for(self.queue.get(), max(.01, deadline-time.monotonic()))
            if isinstance(reply, Exception):
                raise reply
            require(int.from_bytes(reply[4:6], 'little') == cmd, f'Unexpected reply: {reply.hex()}')
            require(reply[1] in kinds and reply[1] not in responses, 'Unexpected/duplicate response type')
            require(reply[6] == 0, f'Command {cmd:04x} rejected: {reply.hex()}')
            responses[reply[1]] = reply[6:]
            self.record(response=hex(cmd), kind=hex(reply[1]), status=reply[6])
        return responses

    async def one(self, cmd, payload=b'', head=5):
        return (await self.query(cmd, payload, head))[0x5B]

    async def read(self, address, size):
        ranges = ((0x08000000, 0x08013000), (BASE, BASE+SIZE),
                  (0x08000000+STAGE, 0x08000000+STAGE+0x3000))
        require(size > 0 and address % 256 == size % 256 == 0, 'Unaligned flash read')
        require(any(lo <= address and address+size <= hi for lo, hi in ranges), 'Read outside supported regions')
        result = bytearray()
        for page in range(address, address+size, 256):
            data = await self.one(0x0403, struct.pack('<BBI', 0, 1, page))
            require(len(data) == 264 and data[1] == 0 and int.from_bytes(data[4:8], 'little') == page, 'Invalid flash read response')
            result.extend(data[8:])
        return bytes(result)

    async def word(self, address):
        require(address in WORDS, 'Unsupported RAM read')
        data = await self.one(0x1680, struct.pack('<HI', 0, address))
        require(len(data) == 11 and data[1:3] == b'\0\0' and int.from_bytes(data[3:7], 'little') == address, 'Invalid RAM response')
        return int.from_bytes(data[7:], 'little')

    async def state(self):
        data = await self.one(0x1C04)
        require(len(data) == 3, 'Invalid state response')
        return int.from_bytes(data[1:], 'little')

    async def setstate(self, state):
        data = await self.one(0x1C06, struct.pack('<H', state), 0x15)
        require(data == struct.pack('<BH', 0, state) and await self.state() == state, 'State readback mismatch')

    async def characteristics(self, short):
        uuid = f'0000{short}-0000-1000-8000-00805f9b34fb'
        chars = [c for s in self.client.services for c in s.characteristics if c.uuid == uuid]
        require(bool(chars), f'Missing characteristic {short}')
        return [bytes(await self.client.read_gatt_char(c)) for c in chars]

    async def identity(self):
        fields = {}
        for name, short, expected in [('model', '2a24', 'EMBERTON III'),
                                      ('firmware', '2a26', '9.1.7'), ('hardware', '2a27', '01.04.00')]:
            values = [x.decode().strip('\0') for x in await self.characteristics(short)]
            require(all(value == expected for value in values), f'Unsupported {name}: {values}')
            fields[name] = expected
        fields['battery'] = min(int.from_bytes(x, 'little') for x in await self.characteristics('2a19'))
        return fields


@asynccontextmanager
async def connect(device_id, log):
    from bleak import BleakClient, BleakScanner
    device = await BleakScanner.find_device_by_address(device_id, timeout=25)
    require(device is not None and 'emberton' in (device.name or '').lower(), 'Selected Emberton not advertising')
    async with BleakClient(device, timeout=20) as client:
        link = Link(client, log)
        await client.start_notify(RX, link.receive)
        await link.identity()
        yield link
