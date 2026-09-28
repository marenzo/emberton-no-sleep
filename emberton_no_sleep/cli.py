"""Backup, build, update and verify. Nothing connects at import time."""
import argparse
import asyncio
import json
import os
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from . import firmware as fw
from .protocol import connect


def say(message):
    print(message, flush=True)


def new_directory(path):
    path.mkdir(parents=True, mode=0o700, exist_ok=False)
    return path


def write_json(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')


async def application(link):
    result = bytearray()
    for offset in range(0, fw.SIZE, 4096):
        result.extend(await link.read(fw.BASE+offset, min(4096, fw.SIZE-offset)))
        if offset % 0x20000 == 0:
            say(f'Application read: {len(result)}/{fw.SIZE} bytes')
    return bytes(result)


async def layout(link):
    info = await link.one(0x1C00, b'\0')
    fw.require(info == struct.pack('<BBBII', 0, 0, 0, fw.STAGE, 0x353000), 'Unexpected staging partition')
    boot = await link.read(0x08000000, 0x13000)
    fw.require(fw.sha(boot) == fw.BOOT_SHA, 'Unsupported bootloader/partition-table SHA256')
    return boot


async def power(link):
    identity = await link.identity()
    fw.require(identity['battery'] >= 30, 'At least 30% battery required')
    fw.require((await link.word(0x14239A20)) & 255 == 1, 'USB power must be attached')
    return identity


async def transfer(link, package):
    """One sequential update, without a user-input delay during the FOTA session."""
    fw.require(len(package) == 0x3000 and fw.sha(package) in fw.PACKAGE_SHA.values(), 'Unrecognized update package')
    result = await link.query(0x1C08, b'\1\0', 0x15, (0x5B, 0x5D))
    fw.require(result == {0x5B: b'\0', 0x5D: b'\0\1\0'}, 'Invalid FOTA start response')
    table = [await link.word(a) for a in range(0x14201FD8, 0x14201FF4, 4)]
    fw.require(table == [1, fw.STAGE, 0x354000, 0x101, 0, 0, 0], 'Unexpected flash write permissions')
    fw.require(await link.one(0x1C0A, b'', 0x15) == b'\0', 'Transaction rejected')
    await link.setstate(0x201)
    await link.setstate(0x210)
    say('Erasing 12 KB of staging storage')
    result = await link.query(0x0404, struct.pack('<BII', 0, len(package), fw.STAGE),
                              kinds=(0x5B, 0x5D), timeout=30)
    fw.require(result == {0x5B: b'\0', 0x5D: struct.pack('<BBII', 0, 0, len(package), fw.STAGE)}, 'Invalid erase completion')
    fw.require(await link.read(0x08000000+fw.STAGE, len(package)) == b'\xff'*len(package), 'Staging erase verification failed')
    for offset in range(0, len(package), 256):
        page, address = package[offset:offset+256], fw.STAGE+offset
        payload = struct.pack('<BBBI', 0, 1, fw.checksum(page), address) + page
        response = await link.one(0x0402, payload, 0x15)
        fw.require(response == struct.pack('<BBBI', 0, 0, 1, address), 'Page program not acknowledged')
    fw.require(await link.read(0x08000000+fw.STAGE, len(package)) == package, 'Staged package readback differs')
    say('Staged package readback verified; requesting device integrity check')
    result = await link.query(0x1C01, b'\1\0\0', 0x15, (0x5B, 0x5D), timeout=30)
    fw.require(result == {0x5B: b'\0', 0x5D: b'\0\1\0\0'}, 'Device integrity check failed')
    await link.setstate(0x211)
    await power(link)
    fw.require(await link.state() == 0x211, 'Update state changed before commit')
    link.record(commit_requested=True)
    say('Integrity passed. Committing; keep USB connected.')
    response = await link.one(0x1C02, b'\0', 0x15)
    fw.require(response == b'\0', 'Commit not acknowledged')
    link.record(commit_acknowledged=True)
    say('Commit acknowledged. Waiting for reboot.')
    await asyncio.sleep(5)


async def verify(device, expected, out, log):
    async with connect(device, log) as link:
        identity = await link.identity()
        for address in fw.SECTORS:
            data = await link.read(address, 4096)
            fw.require(data == expected[address-fw.BASE:address-fw.BASE+4096], 'Installed target sector mismatch')
        say('Both target sectors match. Verifying entire application.')
        data = await application(link)
        fw.require(data == expected, 'Full installed application differs')
        (out/'verified-application.bin').write_bytes(data)
        samples = []
        for _ in range(3):
            samples.append({'usb': (await link.word(0x14239A20)) & 255,
                            'counter': await link.word(0x1423A248),
                            'enabled': (await link.word(0x1423A24C)) & 255})
            await asyncio.sleep(2)
        write_json(out/'verification.json', {'identity': identity, 'application_sha256': fw.sha(data),
                                            'state': hex(await link.state()), 'timer_samples': samples})
        say(f'Full application verified: {fw.sha(data)}')
        say(f'Timer samples (state dependent): {samples}')


async def run(args):
    if args.command in ('install', 'restore'):
        fw.require(args.yes, 'Explicit --yes acknowledgment required')
        print('EXPERIMENTAL FIRMWARE UPDATE: permanent device damage is possible.\n'
              'Recovery and charging/thermal safety are not qualified. The public CLI\n'
              'has not been live-flashed; firmware 9.1.7 lacks later vendor security fixes.\n'
              'Read SAFETY.md and NOTICE.md. --yes authorizes staging, commit and reboot.\n',
              file=sys.stderr, flush=True)
    if args.command == 'scan':
        from bleak import BleakScanner
        for device in await BleakScanner.discover(timeout=10):
            if 'emberton' in (device.name or '').lower():
                say(f'{device.address}  {device.name}')
        return
    if args.command in ('build', 'install', 'restore', 'verify'):
        stock = args.stock.read_bytes()
        modified = fw.patched(stock)  # full hash and displaced instruction checks
    if args.command == 'build':
        out = new_directory(args.out)
        artifacts = {'patched-application.bin': modified, 'patched.fota.bin': fw.package(modified),
                     'stock.fota.bin': fw.package(stock)}
        for name, data in artifacts.items():
            (out/name).write_bytes(data)
        write_json(out/'manifest.json', {name: {'bytes': len(data), 'sha256': fw.sha(data)} for name, data in artifacts.items()})
        say(f'Built locally in {out}; do not publish the generated firmware files.')
        return
    if args.command == 'backup':
        out = new_directory(args.out)
    else:
        out = new_directory(args.work/'runs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ'))
    with (out/'operations.jsonl').open('x') as log:
        if args.command == 'verify':
            await verify(args.device, modified if args.expect == 'patched' else stock, out, log)
            return
        async with connect(args.device, log) as link:
            identity = await link.identity()
            boot = await layout(link)
            if args.command == 'backup':
                (out/'boot-and-tables.bin').write_bytes(boot)
                first = await application(link)
                fw.require(fw.sha(first) == fw.STOCK_SHA, 'Backup is not the supported stock application')
                (out/'application.bin').write_bytes(first)
                say('Reading application again to verify backup')
                second = await application(link)
                fw.require(first == second, 'Independent application reads differ')
                write_json(out/'backup.json', {'identity': identity, 'device': args.device,
                                               'application_sha256': fw.sha(first), 'boot_sha256': fw.sha(boot),
                                               'two_application_reads_matched': True, 'full_device_backup': False})
                say(f'Verified backup saved in {out}')
                return
            await power(link)
            state = await link.state()
            fw.require(state in (0xFFFF, 0x101), f'Existing/unfinished update state {state:#x}; inspect before retrying')
            current = await application(link)
            expected_current, target = (stock, modified) if args.command == 'install' else (modified, stock)
            fw.require(current == expected_current, 'Current firmware is not the expected source; no writes sent')
            await power(link)
            update = fw.package(target)
            (out/'before-application.bin').write_bytes(current)
            (out/'target.fota.bin').write_bytes(update)
            write_json(out/'preflight.json', {'identity': identity, 'before_sha256': fw.sha(current),
                                             'target_sha256': fw.sha(target), 'package_sha256': fw.sha(update)})
            link.allow_update = True
            await transfer(link, update)
        # Never retry the write/commit sequence automatically if reconnection fails.
        await verify(args.device, target, out, log)


def parser():
    p = argparse.ArgumentParser(description='Experimental Emberton III 9.1.7 / hardware 01.04.00 USB idle patch')
    commands = p.add_subparsers(dest='command', required=True)
    commands.add_parser('scan', help='List advertising Embertons; no settings writes')
    backup = commands.add_parser('backup', help='Read application twice and boot/tables once')
    backup.add_argument('--device', required=True)
    backup.add_argument('--out', type=Path, default=Path('work/backup'))
    build = commands.add_parser('build', help='Offline: build patch and stock restoration packages')
    build.add_argument('--stock', required=True, type=Path)
    build.add_argument('--out', type=Path, default=Path('work/build'))
    for action in ('install', 'restore', 'verify'):
        cmd = commands.add_parser(action)
        cmd.add_argument('--device', required=True, help='Exact ID from scan; macOS UUID or platform address')
        cmd.add_argument('--stock', required=True, type=Path)
        cmd.add_argument('--work', type=Path, default=Path('work'))
        if action != 'verify':
            cmd.add_argument('--yes', action='store_true', required=True,
                             help='Acknowledge SAFETY.md risks and authorize staging, commit and reboot; not a legal waiver')
        else:
            cmd.add_argument('--expect', choices=('patched', 'stock'), default='patched')
    return p


def main():
    args = parser().parse_args()
    os.umask(0o077)
    try:
        asyncio.run(run(args))
    except (Exception, KeyboardInterrupt) as error:
        raise SystemExit(f'Stopped: {error or type(error).__name__}. No automatic retry. Keep backups and inspect the operation log.') from error


if __name__ == '__main__':
    main()
