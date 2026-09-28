"""Direct call/jmp sites (E8/E9 rel32) into a method, with the owning method.

usage: il2xref.py <method-name-substring | 0xADDR> ...

Indirect uses (delegates, virtual/interface calls) are not found; search the
disassembly for the MethodDef:/MethodRef: global instead.
"""

import bisect
import re
import struct
import sys

from il2dis import fstarts
from il2meta import BIN, CODE, addr_methods, addr_name


def owner(a):
    i = bisect.bisect_right(fstarts, a) - 1
    s = fstarts[i] if i >= 0 else 0
    return s, addr_name(s)


def xrefs(target):
    res = []
    for m in re.finditer(rb"[\xe8\xe9]", BIN[CODE[0] : CODE[1]]):
        i = CODE[0] + m.start()
        if i + 5 + struct.unpack_from("<i", BIN, i + 1)[0] == target:
            res.append(i)
    return res


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        if arg.startswith("0x"):
            targets = [(int(arg, 16), addr_name(int(arg, 16)))]
        else:
            targets = [(a, n) for a, ns in addr_methods.items() for n in ns if arg in n]
        for a, n in targets:
            print(f"== xrefs to {n} @ {a:#x}")
            for i in xrefs(a):
                s, on = owner(i)
                print(f"   {i:#x}  in {on} @ {s:#x}")
