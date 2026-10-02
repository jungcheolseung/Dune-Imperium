"""Annotated x86-64 disassembly of IL2CPP methods.

usage: il2dis.py <method-name-substring | 0xADDR> ...

Comments name called methods (incl. shared generic instances), decode lazily
initialised metadata globals (TypeInfo:/MethodRef:/MethodDef:/Str:/FieldInfo:),
float constants (f32=/f64=) and, for the known build, IL2CPP runtime helpers (rt:).
"""

import bisect
import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP
from il2meta import (
    BIN,
    DATA_END,
    DATA_START,
    RAW,
    STUBS,
    addr_methods,
    addr_name,
    build_guid,
    decode_usage,
    load_commands,
    u64,
)

# LC_FUNCTION_STARTS (0x26): uleb128 deltas from the start of __TEXT.
fstarts = []
for _cmd, _off, _size in load_commands():
    if _cmd == 0x26:
        _dataoff, _datasize = struct.unpack_from("<II", RAW, _off + 8)
        _p, _addr = _dataoff, 0
        while _p < _dataoff + _datasize:
            _v = _sh = 0
            while True:
                _b = RAW[_p]
                _p += 1
                _v |= (_b & 0x7F) << _sh
                _sh += 7
                if _b < 0x80:
                    break
            if _v == 0:
                break
            _addr += _v
            fstarts.append(_addr)
fstarts = sorted(set(fstarts))

# IL2CPP runtime helpers have no metadata names. These labels were identified by hand
# (call patterns, noreturn tails, the exception class names their callees look up) for
# build 84d64e1237b54105aee1940811cd9e43 (Dire Wolf Game Room) and
# a6cb3f9216f9489d803b76004ec9af53 (Steam Dune: Imperium 4.1.1.1804); other builds get
# no rt: labels until someone re-identifies them (README.md, "앱이 업데이트되면").
# A trailing '?' marks a label inferred from call sites only.
HELPERS_BY_BUILD = {
    "a6cb3f9216f9489d803b76004ec9af53": {
        0x6B53A0: "rt:initialize_runtime_metadata(lazy)",
        0x6B53B0: "rt:initialize_runtime_metadata(alt)",
        0x6B52E0: "rt:write_barrier",
        0x6B5700: "rt:throw_NullReferenceException(noreturn)",
        0x6B5710: "rt:throw_IndexOutOfRange(noreturn)",
        0x6B56F0: "rt:throw_exception?(noreturn)",
        0x6B5580: "rt:raise_exception?(noreturn)",
        0x6B55A0: "rt:run_class_static_ctor",
        0x6B56D0: "rt:object_new(klass)",
        0x6B54E0: "rt:SZArrayNew(klass,len)",
        0x6B55B0: "rt:IsInst(obj,klass)?",
        0x6B55C0: "rt:Box(klass,&value)?",
        0x6B55D0: "rt:Unbox(obj)?",
        0x6FBF20: "rt:init_class(klass)->klass?",
        0x6FBFA0: "rt:init_method_rgctx(method)?",
        0x6FC370: "rt:interface_lookup_slowpath(obj,itf,slot)?",
    },
    "84d64e1237b54105aee1940811cd9e43": {
        0x39A840: "rt:initialize_runtime_metadata(lazy)",
        0x39A850: "rt:initialize_runtime_metadata(alt)",
        0x39A790: "rt:write_barrier",
        0x39AB40: "rt:throw_NullReferenceException(noreturn)",
        0x39AA00: "rt:run_class_static_ctor",
        0x39AB30: "rt:object_new(klass)",
        0x39A940: "rt:SZArrayNew(klass,len)",
        0x39AB50: "rt:throw_IndexOutOfRange(noreturn)",
        0x3184B0: "rt:throw_exception?(noreturn)",
    },
}
HELPERS = HELPERS_BY_BUILD.get(build_guid(), {})

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True
FLOAT32 = (
    "movss",
    "mulss",
    "addss",
    "subss",
    "divss",
    "comiss",
    "ucomiss",
    "maxss",
    "minss",
    "cvt",
)
FLOAT64 = ("movsd", "mulsd", "addsd", "subsd", "divsd", "comisd", "ucomisd")


def func_end(a):
    i = bisect.bisect_right(fstarts, a)
    return fstarts[i] if i < len(fstarts) else a + 0x4000


def annotate_addr(t):
    if t in HELPERS:
        return HELPERS[t]
    n = addr_name(t)
    if n:
        return n
    if STUBS[0] <= t < STUBS[1]:
        return f"stub_{t:x}"
    return None


def disasm(a, maxlen=0x6000):
    e = min(func_end(a), a + maxlen)
    out = []
    for ins in md.disasm(bytes(BIN[a:e]), a):
        cm = []
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                t = ins.address + ins.size + op.mem.disp
                if DATA_START <= t < DATA_END:
                    v = u64(t)
                    d = decode_usage(v)
                    if d:
                        cm.append(f"[{t:#x}] {d}")
                    else:
                        n = annotate_addr(v) if v else None
                        cm.append(f"[{t:#x}]" + (f"->{n}" if n else f"={v:#x}"))
                elif t < len(BIN):
                    n = annotate_addr(t)
                    if n:
                        cm.append(n)
                    elif ins.mnemonic.startswith(FLOAT32):
                        cm.append(f"f32={struct.unpack_from('<f', BIN, t)[0]}")
                    elif ins.mnemonic.startswith(FLOAT64):
                        cm.append(f"f64={struct.unpack_from('<d', BIN, t)[0]}")
                    else:
                        cm.append(f"{t:#x}")
            elif op.type == X86_OP_IMM and (
                ins.mnemonic in ("call", "jmp")
                or (ins.mnemonic.startswith("j") and not a <= op.imm < e)
            ):
                n = annotate_addr(op.imm)
                if n:
                    cm.append(n)
        line = f"{ins.address:#x}: {ins.mnemonic} {ins.op_str}"
        if cm:
            line += "    ; " + " | ".join(cm)
        out.append(line)
    return out


def find_methods(sub):
    return [(a, n) for a, ns in addr_methods.items() for n in ns if sub in n]


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        targets = (
            [(int(arg, 16), addr_name(int(arg, 16)) or arg)]
            if arg.startswith("0x")
            else find_methods(arg)
        )
        for a, n in targets:
            print(f"===== {n} @ {a:#x}")
            print("\n".join(disasm(a)))
