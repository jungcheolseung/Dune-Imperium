"""Annotated x86-64 disassembly of IL2CPP methods.

usage: il2dis.py <method-name-substring | 0xADDR> ...

Comments name called methods (incl. shared generic instances), decode lazily
initialised metadata globals (TypeInfo:/MethodRef:/MethodDef:/Str:/FieldInfo:),
float constants (f32=/f64=) and, for the known builds, IL2CPP runtime helpers (rt:).

Comments starting with '~' come from tracking registers through the function in
address order: `this` (rdi on entry to an instance method), objects loaded from
known fields or made by rt:object_new, klass pointers, and static field blocks.
They name instance fields (~Type.field), static fields (~static Type.field) and
virtual call slots (~vslot N Type::Method, the static receiver type's vtable).
At a jump target a register keeps its type only if the fall-through path and every
earlier jump to it agree; targets of backward jumps keep only callee-saved
registers. The receiver's static type can be a base class, so a ~vslot names the
base's method, not the override that runs.
"""

import bisect
import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG, X86_REG_RIP
from il2meta import (
    BIN,
    DATA_END,
    DATA_START,
    MT,
    MT_FLAGS,
    RAW,
    STATICS_OFFSET,
    STUBS,
    VTABLE_OFFSET,
    addr_methods,
    addr_mis,
    addr_name,
    build_guid,
    decode_usage,
    fqn,
    layout,
    load_commands,
    ptr_typedef,
    type_is_reference,
    type_ptr,
    u64,
    usage_index,
    vtable_method,
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
# a6cb3f9216f9489d803b76004ec9af53 (Steam Dune: Imperium 4.1.1.1804, reused for
# 4.1.2.1808 below); other builds get
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
# Steam 4.1.2.1808 (2026-10-03 update): every helper above sits at the same address
# with the same body, and the exception helpers load the same class names.
HELPERS_BY_BUILD["dad97e2021144d45b5b4f022e07bd3b3"] = HELPERS_BY_BUILD[
    "a6cb3f9216f9489d803b76004ec9af53"
]
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


REG64 = {}
for _r in ("ax", "bx", "cx", "dx"):
    for _n in (f"r{_r}", f"e{_r}", _r, f"{_r[0]}l", f"{_r[0]}h"):
        REG64[_n] = f"r{_r}"
for _r in ("si", "di", "bp", "sp"):
    for _n in (f"r{_r}", f"e{_r}", _r, f"{_r}l"):
        REG64[_n] = f"r{_r}"
for _k in range(8, 16):
    for _n in (f"r{_k}", f"r{_k}d", f"r{_k}w", f"r{_k}b"):
        REG64[_n] = f"r{_k}"
CALLEE_SAVED = {"rbx", "rbp", "r12", "r13", "r14", "r15"}
CALLER_SAVED = {"rax", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11"}
OBJECT_NEW = {a for a, n in HELPERS.items() if n.startswith("rt:object_new")}


def short(td):
    return fqn(td).rsplit(".", 1)[-1]


def _global_typedef(t):
    """Type definition of a TypeInfo:/Type: metadata global at address t."""
    u = usage_index(u64(t)) if DATA_START <= t < DATA_END else None
    if u and u[0] in (1, 2):
        try:
            return ptr_typedef(type_ptr(u[1]))
        except Exception:
            return None
    return None


def _field_tag(fields, off):
    f = fields.get(off)
    if f and type_is_reference(f[1]):
        td = ptr_typedef(type_ptr(f[1]))
        if td is not None:
            return ("obj", td)
    return None


def _return_tag(target):
    """Declared return type of a directly called method, if a reference type."""
    tags = set()
    for mi in addr_mis.get(target, []):
        ret = MT[mi][2]
        td = ptr_typedef(type_ptr(ret)) if ret >= 0 and type_is_reference(ret) else None
        tags.add(("obj", td) if td is not None else None)
    return tags.pop() if len(tags) == 1 else None


def _entry_state(a):
    """`this` in rdi for an instance method (all methods folded at a agree)."""
    mis = addr_mis.get(a, [])
    tds = {MT[mi][1] for mi in mis if not MT[mi][MT_FLAGS] & 0x10}
    if len(tds) == 1 and len(mis) == len(
        [mi for mi in mis if not MT[mi][MT_FLAGS] & 0x10]
    ):
        return {"rdi": ("obj", tds.pop())}
    return {}


def _mem_note(tag, disp):
    kind, td = tag
    if kind == "statics":
        f = layout(td)[1].get(disp)
        return f"~static {short(td)}.{f[0]}" if f else None
    if kind == "obj" and disp > 8:
        f = layout(td)[0].get(disp)
        return f"~{short(td)}.{f[0]}" if f else None
    if kind == "klass" and VTABLE_OFFSET and disp >= VTABLE_OFFSET:
        slot, part = divmod(disp - VTABLE_OFFSET, 16)
        if part in (0, 8):
            n = vtable_method(td, slot)
            if n:
                return f"~vslot {slot}{'' if part == 0 else ' method'} {n}"
    return None


def _new_tag(state, ins, src):
    """Type tag of the value a 64-bit mov/lea loads from operand src."""
    if src.type == X86_OP_REG:
        return state.get(REG64.get(ins.reg_name(src.reg)))
    if src.type != X86_OP_MEM or src.mem.index != 0:
        return None
    if src.mem.base == X86_REG_RIP:
        td = _global_typedef(ins.address + ins.size + src.mem.disp)
        if td is None:
            return None
        return ("tip", td) if ins.mnemonic == "lea" else ("klass", td)
    if ins.mnemonic != "mov":
        return None
    tag = state.get(REG64.get(ins.reg_name(src.mem.base)))
    if not tag:
        return None
    kind, td = tag
    disp = src.mem.disp
    if kind == "tip" and disp == 0:
        return ("klass", td)
    if kind == "klass" and disp == STATICS_OFFSET:
        return ("statics", td)
    if kind == "statics":
        return _field_tag(layout(td)[1], disp)
    if kind == "obj":
        return ("klass", td) if disp == 0 else _field_tag(layout(td)[0], disp)
    return None


def _jump_tables(insns, a, e):
    """{address of `jmp reg`: [(case, target)]} for the compiler's relative jump
    tables: `lea T, [rip + table]; movsxd R, dword ptr [T + I*4]; add R, T; jmp R`.
    The case count comes from the bounds check (`cmp I, N` before it); a coroutine's
    MoveNext switches on <>1__state this way, so case k is usually state k."""
    tables = {}
    for i, ins in enumerate(insns[:-3]):
        ops = ins.operands
        if not (
            ins.mnemonic == "lea"
            and len(ops) == 2
            and ops[1].type == X86_OP_MEM
            and ops[1].mem.base == X86_REG_RIP
        ):
            continue
        mov, add, jmp = insns[i + 1 : i + 4]
        if not (
            mov.mnemonic == "movsxd"
            and add.mnemonic == "add"
            and jmp.mnemonic == "jmp"
            and jmp.operands
            and jmp.operands[0].type == X86_OP_REG
        ):
            continue
        tab = ins.address + ins.size + ops[1].mem.disp
        bound = None
        for prev in reversed(insns[max(0, i - 8) : i]):
            pops = prev.operands
            if prev.mnemonic == "cmp" and len(pops) == 2 and pops[1].type == X86_OP_IMM:
                bound = pops[1].imm
                break
        if bound is None or not 0 <= bound < 512:
            continue
        targets = []
        for k in range(bound + 1):
            t = (tab + struct.unpack_from("<i", BIN, tab + 4 * k)[0]) & (2**64 - 1)
            if a <= t < e:
                targets.append((k, t))
        if targets:
            tables[jmp.address] = targets
    return tables


def _meet(states):
    """Registers whose type every incoming path agrees on."""
    if not states:
        return {}
    first, rest = states[0], states[1:]
    return {r: v for r, v in first.items() if all(s.get(r) == v for s in rest)}


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
    insns = list(md.disasm(bytes(BIN[a:e]), a))
    labels = {
        op.imm
        for ins in insns
        if ins.mnemonic.startswith("j")
        for op in ins.operands
        if op.type == X86_OP_IMM and a <= op.imm < e
    }
    backward = {
        op.imm
        for ins in insns
        if ins.mnemonic.startswith("j")
        for op in ins.operands
        if op.type == X86_OP_IMM and a <= op.imm <= ins.address
    }
    pending = {}
    tables = _jump_tables(insns, a, e)
    cases = {}
    for _jmp, _targets in tables.items():
        for k, t in _targets:
            cases.setdefault(t, []).append(k)
            labels.add(t)
            if t <= _jmp:
                backward.add(t)
    state, falls = _entry_state(a), True
    for ins in insns:
        if ins.address in labels:
            incoming = ([state] if falls else []) + (
                [pending.pop(ins.address)] if ins.address in pending else []
            )
            state = _meet(incoming)
            if ins.address in backward:
                state = {r: v for r, v in state.items() if r in CALLEE_SAVED}
        elif not falls:
            state = {}
        cm = []
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base not in (0, X86_REG_RIP):
                tag = state.get(REG64.get(ins.reg_name(op.mem.base)))
                note = _mem_note(tag, op.mem.disp) if tag and not op.mem.index else None
                if note:
                    cm.append(note)
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
        new, dest = None, None
        ops = ins.operands
        if (
            ins.mnemonic in ("mov", "lea")
            and len(ops) == 2
            and ops[0].type == X86_OP_REG
            and ops[0].size == 8
        ):
            dest = REG64.get(ins.reg_name(ops[0].reg))
            new = _new_tag(state, ins, ops[1])
        if ins.mnemonic == "call":
            made = state.get("rdi")
            for r in CALLER_SAVED:
                state.pop(r, None)
            if ops and ops[0].type == X86_OP_IMM and ops[0].imm in OBJECT_NEW:
                if made and made[0] == "klass":
                    state["rax"] = ("obj", made[1])
            elif ops and ops[0].type == X86_OP_IMM:
                ret = _return_tag(ops[0].imm)
                if ret:
                    state["rax"] = ret
        else:
            for r in ins.regs_access()[1]:
                state.pop(REG64.get(ins.reg_name(r)), None)
        if dest and new:
            state[dest] = new
        for _k, t in tables.get(ins.address, ()):
            if t > ins.address:
                prev = pending.get(t)
                pending[t] = dict(state) if prev is None else _meet([prev, state])
        if ins.mnemonic.startswith("j") and ops and ops[0].type == X86_OP_IMM:
            if ins.address < ops[0].imm < e:
                prev = pending.get(ops[0].imm)
                pending[ops[0].imm] = (
                    dict(state) if prev is None else _meet([prev, state])
                )
        target = ops[0].imm if ops and ops[0].type == X86_OP_IMM else None
        noreturn = target is not None and "noreturn" in (annotate_addr(target) or "")
        falls = not (
            ins.mnemonic in ("jmp", "ret", "ud2")
            or (ins.mnemonic == "call" and noreturn)
        )
        if ins.address in tables:
            cm.append(f"jump table, {len(tables[ins.address])} cases")
        if ins.address in cases:
            ks = ",".join(str(k) for k in sorted(cases[ins.address]))
            out.append(f"; ---- jump-table case {ks} ----")
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
