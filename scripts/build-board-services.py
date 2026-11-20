#!/usr/bin/env python3
"""Device board bring-up services archive: the weak platform observers the storage/CPU
drivers import (boot_progress_poll, arm64_platform_sleep_hook). The kernel link refuses
even weak undefined externals, so package/PlatformStubs.c provides truthful no-op
definitions until the real board services exist. Linked via CONFIG_XNU_EXTRA_LD_ARCHIVES.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess

ROOT = Path(os.environ.get('UNIXNU_TREE') or Path(__file__).resolve().parents[1])
DEVICE = Path(os.environ['UNIXNU_DEVICE'])   # device repository (board package sources), set by the driver
OUT = ROOT / 'build/board-services'
OUT.mkdir(parents=True, exist_ok=True)


def main():
    recipe = ROOT / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/bsd/DEVELOPMENT/bsd_init.o.json'
    record = json.loads(recipe.read_text().strip().rstrip(','))
    source = DEVICE / 'package/PlatformStubs.c'
    destination = OUT / 'PlatformStubs.o'
    command, index, args = [], 0, record['arguments']
    while index < len(args):
        value = args[index]
        if value == record['file']:
            command.append(str(source))
        elif value == '-o':
            command += ['-o', str(destination)]
            index += 1
        elif value in ('-MF', '-MJ'):
            index += 1
        elif value in ('-MD', '-MP'):
            pass
        elif value == '-Xclang' and index + 1 < len(args) and args[index + 1].startswith('-W'):
            index += 1
        elif value.startswith('-W'):
            pass
        else:
            command.append(value)
        index += 1
    command += ['-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter']
    result = subprocess.run(command, cwd=record['directory'], capture_output=True, text=True)
    (OUT / 'compile.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit(result.stderr[-3500:])
    if struct.unpack_from('<4I', destination.read_bytes()) != (0xfeedfacf, 0x100000c, 0, 1):
        raise SystemExit('PlatformStubs.o must remain ordinary ARM64')
    archive = OUT / 'libBoardServices.a'
    archive.unlink(missing_ok=True)
    subprocess.run(['xcrun', 'ar', 'rcs', str(archive), str(destination)], check=True)
    (OUT / 'build-report.json').write_text(json.dumps(dict(
        archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        services=['boot_progress_poll (no-op)', 'arm64_platform_sleep_hook (NULL)'],
        hardware_tested=False), indent=2) + '\n')
    print(f'board-services: {archive} ({hashlib.sha256(archive.read_bytes()).hexdigest()})')


if __name__ == '__main__':
    main()
