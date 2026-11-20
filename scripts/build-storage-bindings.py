#!/usr/bin/env python3
"""Device-owned storage binding layer for NativeUfs (iOS 16.7.16 / 20H392).

Binds the concrete UFS block driver's inherited IOBlockStorageDevice imports to the
addresses statically measured from the actual donor by audit-20h392-storage-abi.py
(build/storage-abi/interface-audit.json), then re-archives libShengUfs.a with the binding
object. This is the archive form the alioth/nx769j records describe: the component build
compiles the driver object; the board supplies the binding layer against kernelcache
symbols. No live candidate is required (the audit is the pinned donor record).

    build-storage-bindings.py [--component NativeUfs]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(os.environ.get('UNIXNU_TREE') or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT / 'kits/XnuPrelink'))
import native_prelink as np
sys.path.insert(0, str(ROOT / 'scripts'))
from kernel_target import TRIPLE

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--component', default='NativeUfs')
args = parser.parse_args()
out = ROOT / 'build/sheng-ufs'
audit = json.loads((ROOT / 'build/storage-abi/interface-audit.json').read_text())
if not audit.get('static_donor_measurement') or audit['method_slots'] != 190 or not audit['abstract_complete_destructors_trap']:
    raise SystemExit('First measure the original donor storage ABI (audit-20h392-storage-abi.py)')

obj_path = out / 'NativeUfs.o'
obj = obj_path.read_bytes()
image = np.macho(obj)
offset = next(at for c, at, _ in image['commands'] if c == 2)
sy, count, st, _ = struct.unpack_from('<4I', obj, offset + 8)
symbols = []
for i in range(count):
    ix, kind, _, _, value = struct.unpack_from('<IBBHQ', obj, sy + i * 16)
    symbols.append((obj[st + ix:obj.index(b'\0', st + ix)].decode(), value, kind))

possible = {r['reference_name']: int(r['candidate_target'], 16) for r in audit['methods'] if not r['kernel_names']}
possible.update({r['reference_name']: int(r['candidate_target'], 16) for r in audit['methods'] if r['kernel_names']})
possible.update({'__ZN20IOBlockStorageDeviceC2EPK11OSMetaClass': int(audit['original_protected_constructor'], 16),
                 '__ZN20IOBlockStorageDeviceD2Ev': int(audit['original_base_destructor'], 16),
                 '__ZN20IOBlockStorageDevice10gMetaClassE': int(audit['original_metaclass'], 16),
                 '__ZTV20IOBlockStorageDevice': int(audit['vtable'], 16)})
undefined = [name for name, value, kind in symbols if kind == 1 and 'IOBlockStorageDevice' in name]
if any(name not in possible for name in undefined):
    missing = [n for n in undefined if n not in possible]
    raise SystemExit('Unqualified original storage import: ' + ', '.join(missing))
if any(re.search(r'IOBlockStorageDeviceD[01]Ev$', n) for n in undefined):
    raise SystemExit('Concrete driver must not invoke abstract complete/deleting destruction')
bindings = {name: possible[name] for name in undefined}
assembly = out / 'original-bindings.S'
assembly.write_text(''.join(f'.globl {name}\n.set {name}, {value:#x}\n' for name, value in sorted(bindings.items())))
subprocess.run(['xcrun', 'clang', '-target', TRIPLE, '-Werror', '-Wno-incompatible-sysroot',
                '-c', str(assembly), '-o', str(out / 'original-bindings.o')], check=True)
archive = out / 'libShengUfs.a'
archive.unlink(missing_ok=True)
subprocess.run(['xcrun', 'ar', 'rcs', str(archive), str(obj_path), str(out / 'original-bindings.o')], check=True)
(out / 'bindings.json').write_text(json.dumps(dict(
    donor_sha256=audit['candidate_sha256'], compiled_object_sha256=hashlib.sha256(obj).hexdigest(),
    virtual_methods=190, unresolved_original_imports=0,
    bindings={name: hex(value) for name, value in bindings.items()},
    original_code_modified=False, static_donor_measurement=True, hardware_tested=False), indent=2) + '\n')
print(f'PASS: bound {len(bindings)} genuine original storage imports into {archive}')
for name, value in sorted(bindings.items()):
    print(' ', hex(value), name)
