import argparse
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch
from emberton_no_sleep.cli import run

spec = importlib.util.spec_from_file_location('check_release', Path(__file__).resolve().parents[1]/'tools/check_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_binary_and_capture_rejected(self):
        for content in (b'\xff\0', b'\0', b'a' * 1024, b'x' * (128*1024+1)):
            with self.assertRaises(ValueError):
                release.inspect_blob('source.py', content)

    def test_identifiers_and_paths_rejected(self):
        # Construct synthetic identifiers without putting literal identifiers in the repository.
        mac = ':'.join(['ab'] * 6)
        uuid = '-'.join(['1'*8, '2'*4, '3'*4, '4'*4, '5'*12])
        local = '/' + 'Users' + '/' + 'example/file'
        key = '-----BEGIN ' + 'PRIVATE KEY-----'
        for text in (mac, uuid, local, key):
            with self.assertRaises(ValueError):
                release.inspect_blob('source.py', text.encode())

    def test_known_protocol_constants_allowed(self):
        for uuid in release.PROTOCOL_UUIDS:
            release.inspect_blob('protocol.py', uuid.encode())

    def test_unlisted_path_and_symlink_rejected(self):
        for entries in ([('100644', 'dummy', 'private/dump.bin')], [('120000', 'dummy', 'README.md')]):
            with self.assertRaises(ValueError):
                release.check_entries(entries, {'README.md'}, set())


class WarningTests(unittest.IsolatedAsyncioTestCase):
    async def test_warning_before_any_device_connection(self):
        args = argparse.Namespace(command='install', yes=True, stock=Path('missing-stock-file'))
        with patch('emberton_no_sleep.cli.connect') as connection, \
             patch.object(Path, 'read_bytes', side_effect=FileNotFoundError), \
             contextlib.redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaises(FileNotFoundError):
                await run(args)
            connection.assert_not_called()
        self.assertIn('EXPERIMENTAL', stderr.getvalue())
        self.assertIn('security fixes', stderr.getvalue())

    async def test_missing_acknowledgment_stops_before_device(self):
        args = argparse.Namespace(command='restore', yes=False)
        with patch('emberton_no_sleep.cli.connect') as connection:
            with self.assertRaises(ValueError):
                await run(args)
            connection.assert_not_called()
