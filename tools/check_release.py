#!/usr/bin/env python3
"""Offline, source-only Git release check. Never reads ignored work/private data."""
import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_UUIDS = {
    '43484152-2dab-3241-6972-6f6861424c45',
    '43484152-2dab-3141-6972-6f6861424c45',
}


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def inspect_blob(name, data):
    if len(data) > 128 * 1024:
        raise ValueError(f'{name}: too large for this source-only release')
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError as error:
        raise ValueError(f'{name}: non-text artifact') from error
    if '\0' in text:
        raise ValueError(f'{name}: binary content')
    local_roots = ('/' + 'Users' + '/', '/' + 'home' + '/', '/' + 'private/tmp' + '/')
    if any(root in text for root in local_roots):
        raise ValueError(f'{name}: local user/workspace path')
    if re.search(r'(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])', text):
        raise ValueError(f'{name}: possible device MAC address')
    for value in re.findall(r'(?i)\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b', text):
        if value.lower() not in PROTOCOL_UUIDS:
            raise ValueError(f'{name}: UUID needs review (only protocol constants allowed)')
    if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?' + 'PRIVATE KEY-----', text):
        raise ValueError(f'{name}: private-key material')
    if re.search(r'(?i)[0-9a-f]{1024,}', text):
        raise ValueError(f'{name}: possible encoded firmware/capture')


def check_entries(entries, allowed, seen):
    count = 0
    for mode, oid, path in entries:
        if path not in allowed:
            raise ValueError(f'Unapproved tracked path: {path}')
        if mode not in ('100644', '100755'):
            raise ValueError(f'{path}: links/submodules are not release source files')
        if oid not in seen:
            inspect_blob(path, git('cat-file', 'blob', oid))
            seen.add(oid)
        count += 1
    return count


def tree_entries(ref):
    for entry in git('ls-tree', '-r', '-z', ref).split(b'\0'):
        if entry:
            metadata, path = entry.split(b'\t', 1)
            mode, kind, oid = metadata.decode().split()
            if kind != 'blob':
                raise ValueError('Submodules are not allowed')
            yield mode, oid, path.decode()


def index_entries():
    for entry in git('ls-files', '--stage', '-z').split(b'\0'):
        if entry:
            metadata, path = entry.split(b'\t', 1)
            mode, oid, stage = metadata.decode().split()
            if stage != '0':
                raise ValueError('Resolve index conflicts before release')
            yield mode, oid, path.decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', action='store_true', help='Check staged changes plus existing history')
    args = parser.parse_args()
    manifest = git('show', ':release-files.txt' if args.index else 'HEAD:release-files.txt').decode()
    allowed = {line.strip() for line in manifest.splitlines() if line.strip() and not line.startswith('#')}
    for name in allowed:
        if name.startswith(('/', 'private/', 'work/')) or '..' in Path(name).parts or Path(name).suffix in ('.bin', '.fota', '.jsonl'):
            raise ValueError(f'Invalid public source allowlist entry: {name}')
    seen = set()
    if args.index:
        count = check_entries(index_entries(), allowed, seen)
    else:
        if git('status', '--porcelain', '--untracked-files=normal'):
            raise ValueError('Commit or remove unignored changes before checking a release')
        count = check_entries(tree_entries('HEAD'), allowed, seen)
    commits = git('rev-list', '--all').decode().splitlines()
    for commit in commits:
        check_entries(tree_entries(commit), allowed, seen)
    print(f'PASS: {count} source files; {len(commits)} reachable commits; {len(seen)} distinct text blobs checked.')
    print('No firmware/private artifacts or recognized leak markers found. This is not a legal or security clearance.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f'RELEASE CHECK FAILED: {error}') from error
