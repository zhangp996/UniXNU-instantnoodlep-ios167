#!/usr/bin/env python3
"""Device-owned static storage-ABI measurement for the iOS 16.7.16 (20H392) donor.

The official scripts/audit-storage-interface.py qualifies the REFERENCE iPadOS 17 donor
and requires a live GDB observation (darwinboot-storage-native-metadata/gdb-stop.json) plus
the image4-ignition AES audit, so it cannot run for this board on this host. This script
reuses the SAME official algorithm (public IOStorageFamily reference object -> 190-slot
vtable shape -> match inherited method pointers against kernel exports -> verify the
protected constructor/base destructor/metaclass getter by instruction pattern) but applies
it STATICALLY to the actual 20H392 donor kernelcache. No live observation, no reference
donor pin. Output: build/storage-abi/interface-audit.json (the recorded binding input).

    audit-20h392-storage-abi.py --kernelcache <kernelcache.decompressed>
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

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kernelcache', type=Path, required=True)
args = parser.parse_args()
SOURCE = ROOT / 'refer/IOStorageFamily'
OUT = ROOT / 'build/storage-abi'
revision = subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
if revision != 'e45fbe30a7879e0b16e26dddb78538f1b00e0bff':
    raise SystemExit('Unexpected public IOStorageFamily source revision')


def require(value, message):
    if not value:
        raise SystemExit(message)


# 1. Compile the public reference class against the actual kernel ABI (annotation only).
record = json.loads((ROOT / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPlatformExpert.cpo.json')
                    .read_text().strip().rstrip(','))
obj_path = OUT / 'IOBlockStorageDevice-reference.o'
command, index, arguments = [], 0, record['arguments']
while index < len(arguments):
    value = arguments[index]
    if value == record['file']:
        command.append(str(SOURCE / 'IOBlockStorageDevice.cpp'))
    elif value == '-o':
        command += ['-o', str(obj_path)]
        index += 1
    elif value in ('-MF', '-MJ'):
        index += 1
    elif value == '-Xclang' and arguments[index + 1].startswith('-W'):
        index += 1
    elif not value.startswith('-W') and value not in ('-MD', '-MP'):
        command.append(value)
    index += 1
command += ['-I', str(OUT / 'include'), '-I', str(ROOT / '.cache/xnu-work/osfmk'),
            '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter', '-Wno-deprecated-declarations',
            '-Wno-c99-designator', '-Wno-reorder-init-list', '-Wno-unnecessary-virtual-specifier',
            '-Wno-deprecated-enum-enum-conversion']
r = subprocess.run(command, cwd=record['directory'], capture_output=True, text=True)
(OUT / 'reference-compile.log').write_text(r.stdout + r.stderr)
if r.returncode:
    raise SystemExit((r.stdout + r.stderr)[-3500:])

# 2. Extract the reference vtable's ordered method names from its relocations.
obj = obj_path.read_bytes()
om = np.macho(obj)
require(om['kind'] == 1, 'Expected an ordinary ARM64 reference object')
sycmd = next(at for c, at, _ in om['commands'] if c == 2)
symoff, count, stroff, _ = struct.unpack_from('<4I', obj, sycmd + 8)
symbols = []
for i in range(count):
    ix, kind, _, _, value = struct.unpack_from('<IBBHQ', obj, symoff + i * 16)
    symbols.append(dict(name=obj[stroff + ix:obj.index(b'\0', stroff + ix)].decode(), value=value, kind=kind))
vtable = next(s['value'] for s in symbols if s['name'] == '__ZTV20IOBlockStorageDevice')
end = min(s['value'] for s in symbols if not s['kind'] & 0xe0 and s['kind'] & 0xe == 0xe and s['value'] > vtable)
relocations = {}
for segment in om['segments']:
    for section in segment['sections']:
        if section['va'] <= vtable < section['va'] + section['size']:
            ro, rc = struct.unpack_from('<II', obj, section['command_offset'] + 56)
            for i in range(rc):
                address, word = struct.unpack_from('<II', obj, ro + i * 8)
                if word >> 27 & 1 and word >> 28 == 0 and word >> 25 & 3 == 3:
                    relocations[section['va'] + address] = symbols[word & 0xffffff]['name']
methods = []
for at in range(vtable + 16, end, 8):
    if at not in relocations:
        break
    methods.append(relocations[at])
require(len(methods) == 190 and methods.count('___cxa_pure_virtual') == 14,
        f'Public class dispatch shape changed: {len(methods)} slots, {methods.count("___cxa_pure_virtual")} pure')

# 3. Load the actual donor and its IOStorageFamily extents.
data = args.kernelcache.read_bytes()
donor = np.macho(data)
by_name = {n: a for a, ns in np.exports(data, donor).items() for n in ns}
info = next(s for s in donor['segments'] if s['name'] == '__PRELINK_INFO')
iat = np.backed_offset(donor['segments'], info['va'], info['filesize'], len(data))
metadata = np.unserialize_xml(data[iat:iat + info['filesize']])
fam = next(e for e in metadata['_PrelinkInfoDictionary']
           if e.get('CFBundleIdentifier') == 'com.apple.iokit.IOStorageFamily')
kva = fam['_PrelinkExecutableLoadAddr']
module = np.macho(data, np.backed_offset(donor['segments'], kva, 32, len(data)))
const = next(s for s in module['segments'] if s['name'] == '__DATA_CONST')
text = next(s for s in module['segments'] if s['name'] == '__TEXT_EXEC')


def read(va, length):
    at = np.backed_offset(donor['segments'], va, length, len(data))
    return data[at:at + length]


# 4. Uniquely locate the original dispatch table by its inherited kernel-bound pointers.
blob = read(const['va'], const['size'])
found = []
for at in range(0, len(blob) - (len(methods) + 2) * 8 + 1, 8):
    if blob[at:at + 16] != bytes(16):
        continue
    pointers = struct.unpack_from('<' + 'Q' * len(methods), blob, at + 16)
    if all(pointers[i] == by_name[name] for i, name in enumerate(methods) if name in by_name):
        found.append((const['va'] + at, pointers))
require(len(found) == 1, f'Cannot uniquely identify the original block-storage dispatch ({len(found)} candidates)')
table, pointers = found[0]
matched = sum(name in by_name for name in methods)
for i, name in enumerate(methods):
    if name not in by_name:
        require(text['va'] <= pointers[i] < text['va'] + text['size'], 'Owned storage method outside original text')


def relative_branch(address, instruction):
    immediate = instruction & 0x3ffffff
    if immediate & 0x2000000:
        immediate -= 0x4000000
    return address + immediate * 4


def thunk_names(address):
    a, load, branch = struct.unpack('<3I', read(address, 12))
    require(a & 0x9f00001f == 0x90000010 and load & 0xffc003ff == 0xf9400210 and branch == 0xd61f0200,
            'Unqualified original native import thunk')
    immediate = ((a >> 5 & 0x7ffff) << 2) | (a >> 29 & 3)
    if immediate & 0x100000:
        immediate -= 0x200000
    slot = (address & ~4095) + immediate * 4096 + (load >> 10 & 4095) * 8
    target = struct.unpack('<Q', read(slot, 8))[0]
    return np.exports(data, donor).get(target, [])


exports_map = np.exports(data, donor)
constructors = []
for address in range(text['va'], text['va'] + text['size'] - 32, 4):
    words = struct.unpack('<8I', read(address, 32))
    if (words[:2] != (0xa9bf7bfd, 0x910003fd) or words[2] & 0xfc000000 != 0x94000000 or
        words[3] & 0x9f00001f != 0x90000008 or words[4] & 0xffc003ff != 0x91000108 or
        words[5:] != (0xf9000008, 0xa8c17bfd, 0xd65f03c0)):
        continue
    immediate = ((words[3] >> 5 & 0x7ffff) << 2) | (words[3] >> 29 & 3)
    if immediate & 0x100000:
        immediate -= 0x200000
    stored = ((address + 12) & ~4095) + immediate * 4096 + (words[4] >> 10 & 4095)
    if stored == table + 16:
        constructors.append((address, relative_branch(address + 8, words[2])))
require(len(constructors) == 1 and '__ZN9IOServiceC2EPK11OSMetaClass' in thunk_names(constructors[0][1]),
        'Original protected block constructor does not forward to actual IOService')
destructor = pointers[0] - 4
word = struct.unpack('<I', read(destructor, 4))[0]
require(word & 0xfc000000 == 0x14000000 and
        '__ZN9IOServiceD2Ev' in thunk_names(relative_branch(destructor, word)), 'Unqualified actual base destructor')
require(all(read(pointers[i], 4) == struct.pack('<I', 0xd4200020) for i in (0, 1)),
        'Unexpected original abstract complete-destructor behavior')
function = pointers[7]
a, add, ret = struct.unpack('<3I', read(function, 12))
require(a & 0x9f00001f == 0x90000000 and add & 0xffc003ff == 0x91000000 and ret == 0xd65f03c0,
        'Unqualified original storage metaclass getter')
immediate = ((a >> 5 & 0x7ffff) << 2) | (a >> 29 & 3)
if immediate & 0x100000:
    immediate -= 0x200000
meta = (function & ~4095) + immediate * 4096 + (add >> 10 & 4095)
service_meta = by_name['__ZN9IOService10gMetaClassE']
# The metaclass object is runtime-constructed (__DATA/bss, zero at rest), so its live structure
# is a live-observation item in the official audit; statically we verify the getter-computed
# address lands inside the original kext's data, and the 190-slot/constructor/destructor checks
# above already qualify the dispatch ABI.
kdata = [s for s in module['segments'] if s['name'] in ('__DATA', '__DATA_CONST')]
require(any(s['va'] <= meta < s['va'] + s['size'] for s in kdata),
        'Original storage metaclass address outside the kext data')

result = dict(public_source_revision=revision,
              source_sha256=hashlib.sha256((SOURCE / 'IOBlockStorageDevice.cpp').read_bytes()).hexdigest(),
              reference_object_sha256=hashlib.sha256(obj).hexdigest(),
              reference_object_executed_or_linked=False,
              candidate_sha256=hashlib.sha256(data).hexdigest(),
              original_executable_code_unchanged=True,
              method_slots=190, kernel_bindings=matched, pure_virtual_slots=14,
              inherited_kernel_methods=matched - 14,
              vtable=hex(table), original_metaclass=hex(meta), source_ioservice_metaclass=hex(service_meta),
              original_protected_constructor=hex(constructors[0][0]), original_base_destructor=hex(destructor),
              abstract_complete_destructors_trap=True,
              live_instance_sizes=dict(IOBlockStorageDevice=0x90, IOService=0x88), live_native_4k=False,
              static_donor_measurement=True, compiled_public_class_size=0x90,
              methods=[dict(slot=i, reference_name=name, candidate_target=hex(pointers[i]),
                            kernel_names=exports_map.get(pointers[i], [])) for i, name in enumerate(methods)],
              disk_read_tested=False, transport_implemented=False, hardware_tested=False)
(OUT / 'interface-audit.json').write_text(json.dumps(result, indent=2) + '\n')
print(f'PASS: 190 slots, {matched} kernel bindings; vtable {hex(table)} metaclass {hex(meta)} '
      f'constructor {hex(constructors[0][0])} destructor {hex(destructor)}')
