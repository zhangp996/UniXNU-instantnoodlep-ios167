#!/usr/bin/env python3
"""Device prelink wrapper for iOS 16.7.16 (20H392): catalogue the measured Libm inline
math pool, then run the official kits/XnuPrelink/emit_prelink.py unchanged.

The donor's com.apple.kec.Libm __TEXT_EXEC carries a block of double-precision constants
(offsets 0x1054-0x1520, 1228 bytes) that the instruction inventory would otherwise decode
as external PC-relative instructions. Measured on the actual 20H392 donor per the boundary
rule of scripts/audit-target-libm-inline-data.py: preceded by RET (c0035fd6), followed by
the next function's stp x29,x30,[sp,#-0x10]! (fd7bbfa9), read only through 30 ADR/literal
loads, no incoming direct branch, and all 12 tripping words inside it. This is the same
pool the official apollo iOS 16.5 record catalogues (identical prefix and sha256).
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'kits/XnuPrelink'))
import emit_prelink

LIBM_POOL_20H392 = (
    '0000807f0000004100008040db0f493f', 1228,
    '73df5b757c53532583e3686b7d93df11ec1f5dd8c201d05502654a7812cc385f',
)
if LIBM_POOL_20H392 not in emit_prelink.MATH_LITERAL_POOLS:
    emit_prelink.MATH_LITERAL_POOLS = emit_prelink.MATH_LITERAL_POOLS + (LIBM_POOL_20H392,)

emit_prelink.main()
