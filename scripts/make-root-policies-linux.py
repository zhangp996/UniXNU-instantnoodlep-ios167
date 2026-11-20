#!/usr/bin/env python3
"""Linux host adaptation of the official scripts/make-root-policies.py.

The official recipe builds its host verifier with `xcrun clang -dynamiclib`
(macOS). On this Linux build host the same kit C (kits/VerifiedRoot/src/verified_root.c
+ tests/openssl_provider.c) is compiled as an ELF shared object against the system
OpenSSL 3, then the OFFICIAL kit tools manifest.py (sign) and verify_image.py (real
RSA + every-block C verification) run unchanged. Owner keys are made once in
TREE/build/verified-root-host/keys (0600, never committed); all windows share them.

    make-root-policies-linux.py --tree TREE --output POLICIES \
        --window NAME=IMAGE:VOLUME_UUID [--window ...]

Each window gets POLICIES/NAME/{manifest.header.bin,trusted-key.bin,verification.json}
and TREE/build/verified-root-NAME/{manifest.bin,hashes.bin,verification.json,...}.
The raw hash table (hashes.bin) is the userdata NAME.vroot object.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
# The kit lives in the assembled build tree (official source), not the device repo.
def kit_dir(tree):
    return tree / 'kits/VerifiedRoot'


def openssl_prefix():
    for candidate in ('/usr', '/usr/local', '/opt/homebrew/opt/openssl@3'):
        if (Path(candidate) / 'include/openssl/evp.h').is_file():
            return Path(candidate)
    raise SystemExit('OpenSSL 3 headers not found (apt install libssl-dev)')


def build_host_verifier(tree, kit, prefix):
    host = tree / 'build/verified-root-host'
    host.mkdir(parents=True, exist_ok=True)
    keys = host / 'keys'
    keys.mkdir(mode=0o700, exist_ok=True)
    os.chmod(keys, 0o700)
    private, public = keys / 'owner.pem', keys / 'owner-public.pem'
    if not private.exists():
        fd = os.open(private, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:3072',
                        '-out', str(private)], check=True, capture_output=True)
    os.chmod(private, 0o600)
    subprocess.run(['openssl', 'pkey', '-in', str(private), '-pubout', '-out', str(public)],
                   check=True, capture_output=True)
    library = host / 'verified-root.dylib'   # ELF .so; ctypes/dlopen ignores the extension
    cc = os.environ.get('HOST_CC', 'cc')
    subprocess.run([cc, '-std=c11', '-O2', '-Wall', '-Wextra', '-fPIC', '-shared',
                    '-I', str(kit / 'include'), '-I', str(prefix / 'include'),
                    str(kit / 'src/verified_root.c'), str(kit / 'tests/openssl_provider.c'),
                    '-L', str(prefix / 'lib'), '-L', str(prefix / 'lib/x86_64-linux-gnu'),
                    '-lcrypto', '-o', str(library)], check=True)
    # Smoke-load: the official verify_image.py/prepare use vr_host_open/vr_host_block.
    import ctypes
    lib = ctypes.CDLL(str(library))
    assert hasattr(lib, 'vr_host_open') and hasattr(lib, 'vr_host_block')
    return host, keys, library


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tree', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--window', action='append', required=True, metavar='NAME=IMAGE:VOLUME_UUID')
    parser.add_argument('--generation', type=int, default=1)
    args = parser.parse_args()
    tree = args.tree.resolve()
    kit = kit_dir(tree)
    if not (kit / 'tools/manifest.py').is_file():
        raise SystemExit(f'{kit}: assembled tree must carry kits/VerifiedRoot (run unixnu tree)')
    prefix = openssl_prefix()
    host, keys, library = build_host_verifier(tree, kit, prefix)
    anchors = set()
    for spec in args.window:
        name, sep, rest = spec.partition('=')
        image_text, sep2, volume = rest.rpartition(':')
        if not sep or not sep2 or not name or '/' in name:
            parser.error(f'--window {spec}: expected NAME=IMAGE:VOLUME_UUID')
        image, volume = Path(image_text).resolve(), str(uuid.UUID(volume)).upper()
        if not image.is_file():
            parser.error(f'{image}: not a regular file')
        work = tree / f'build/verified-root-{name}'
        if work.exists():
            shutil.rmtree(work)
        subprocess.run([sys.executable, str(kit / 'tools/manifest.py'), '--image', str(image),
                        '--private-key', str(keys / 'owner.pem'), '--public-key', str(keys / 'owner-public.pem'),
                        '--volume-uuid', volume, '--generation', str(args.generation), '--output', str(work)],
                       check=True, stdout=subprocess.DEVNULL)
        report = work / 'verification.json'
        subprocess.run([sys.executable, str(kit / 'tools/verify_image.py'), '--library', str(library),
                        '--manifest', str(work / 'manifest.bin'), '--trusted-key', str(work / 'trusted-key.bin'),
                        '--image', str(image), '--volume-uuid', volume, '--minimum-generation', str(args.generation),
                        '--output', str(report)], check=True)
        envelope = (work / 'manifest.bin').read_bytes()
        record = json.loads(report.read_text())
        if (record['volume_uuid'] != volume or envelope[56:88].hex() != record['image_sha256'] or
                len(envelope) != 544 + 32 * record['blocks_verified']):
            raise SystemExit(f'{name}: the signed manifest does not describe {image}')
        destination = args.output / name
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'manifest.header.bin').write_bytes(envelope[:544])
        shutil.copyfile(work / 'trusted-key.bin', destination / 'trusted-key.bin')
        shutil.copyfile(report, destination / 'verification.json')
        anchors.add(hashlib.sha256((work / 'trusted-key.bin').read_bytes()).hexdigest())
        print(f'{name}: {record["blocks_verified"]} blocks, image {record["image_sha256"]}, '
              f'table {work / "hashes.bin"} ({name}.vroot)', flush=True)
    if len(anchors) != 1:
        raise SystemExit('the windows were not signed by one owner key')
    print('owner key anchor sha256', anchors.pop(), flush=True)


if __name__ == '__main__':
    main()
