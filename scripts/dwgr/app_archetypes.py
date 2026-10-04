"""Extract every archetype's authored attributes and ability list (Steam app dump).

The Steam Dune: Imperium app (``worm-canis.dll``) authors each card, leader,
board space, conflict card, conflict reward and contract as a class under
``worm.canis.archetypes.*`` whose constructor stores its data with
``ObjectAttributes::Has<T>(AttributeDefinition key, T value)``: the set list,
the name, the agent icons, the persuasion cost, the AI's acquire/trash values,
the ability classes, and so on. This script reads those constructors from the
local per-type disassembly (``dump/asm/worm-canis.dll/*.asm``, written by
``il2dump.py --asm``) and writes them out as data.

It does not pattern-match the listing line by line. It runs a small symbolic
interpreter over each ``.ctor`` along the path the real code takes on a warm
start: static constructors already ran, allocations succeed, and every
``List<T>.Add`` takes its inline fast path (the ``AddWithResize`` slow path is
the same element written a second time, so following both would duplicate
it). Each ``Has`` call records ``(attribute, value)``; values are decoded with
the declared attribute type from the type listing (enum names, lists, arrays,
dictionaries, localisation keys, archetype and ability references).

Outputs (outside every repository; README "출력은 어느 저장소에도 넣지 않는다"):

- ``archetypes.json``: one record per archetype (see ``build_record``).
- ``archetypes.md``: counts per kind, attribute coverage and undecoded stores.
  The hand-validation table and the cross-check notes are kept in a section of
  that file that this script preserves between runs (between the markers
  ``<!-- manual:begin -->`` and ``<!-- manual:end -->``).

Standard library only; reads only the local dump and the localisation file.

    uv run --no-project python scripts/dwgr/app_archetypes.py
    uv run --no-project python scripts/dwgr/app_archetypes.py --only CapturedMentat
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

_ASSETS = Path(
    "/Users/cs/Workspace/tabletop-ai/Dune-Imperium-assets/reference/dune-steam-app"
)
_BUILD = _ASSETS / "dad97e2021144d45b5b4f022e07bd3b3"
DEFAULT_DUMP = _BUILD / "dump"
# The newer build has no localisation extraction; the 4.1.1 one has the same keys.
DEFAULT_LOC = _ASSETS / "a6cb3f9216f9489d803b76004ec9af53" / "loc" / "en_US.json"
DEFAULT_OUT = _BUILD / "analysis" / "ai" / "spec"

ARCH_NS = "worm.canis.archetypes."
ATTR_OWNERS = {"worm.canis.data.WormAttributes", "Canis.attributes.CoreAttributes"}

KIND_BY_ENTITY = {
    "Imperium": "imperium",
    "Intrigue": "intrigue",
    "Leader": "leader",
    "Space": "space",
    "Conflict": "conflict",
    "ConflictReward": "conflict_reward",
    "Contract": "contract",
}
KIND_BY_IMPERIUM_TYPE = {"Starter": "starter", "Reserve": "reserve"}

# Runtime helpers that never return (the IsInst failure path calls 0x6b5760
# without an annotation).
NORETURN_ADDRS = {0x6B5760}

REG64 = [
    "rax",
    "rbx",
    "rcx",
    "rdx",
    "rsi",
    "rdi",
    "rbp",
    "rsp",
    "r8",
    "r9",
    "r10",
    "r11",
    "r12",
    "r13",
    "r14",
    "r15",
]
_ALIAS = {}
for _r, _d, _w, _b in [
    ("rax", "eax", "ax", "al"),
    ("rbx", "ebx", "bx", "bl"),
    ("rcx", "ecx", "cx", "cl"),
    ("rdx", "edx", "dx", "dl"),
    ("rsi", "esi", "si", "sil"),
    ("rdi", "edi", "di", "dil"),
    ("rbp", "ebp", "bp", "bpl"),
    ("rsp", "esp", "sp", "spl"),
]:
    _ALIAS.update({_r: (_r, 64), _d: (_r, 32), _w: (_r, 16), _b: (_r, 8)})
for _n in range(8, 16):
    _ALIAS.update(
        {
            f"r{_n}": (f"r{_n}", 64),
            f"r{_n}d": (f"r{_n}", 32),
            f"r{_n}w": (f"r{_n}", 16),
            f"r{_n}b": (f"r{_n}", 8),
        }
    )
for _n in range(16):
    _ALIAS[f"xmm{_n}"] = (f"xmm{_n}", 128)


# --------------------------------------------------------------------------
# Type listings
# --------------------------------------------------------------------------


class Listing:
    """Types, static field offsets and enum constants from the ``*.dll.cs`` listings."""

    def __init__(self, paths):
        self.base = {}  # type -> parent
        self.static_fields = {}  # type -> {offset: (name, type)}
        self.enums = {}  # enum type -> {value: name}
        type_re = re.compile(r"^(?:[a-z]+ )*type (\S+)(?: : (\S+))? \{")
        field_re = re.compile(r"^\s*field \+(\d+) (.*)$")
        for path in paths:
            cur = None
            is_enum = False
            for line in (
                Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
            ):
                m = type_re.match(line)
                if m:
                    cur = m.group(1)
                    self.base[cur] = m.group(2)
                    is_enum = m.group(2) in (
                        "int",
                        "byte",
                        "short",
                        "long",
                        "uint",
                        "ushort",
                        "sbyte",
                        "ulong",
                    )
                    if is_enum:
                        self.enums.setdefault(cur, {})
                    continue
                if line.startswith("}"):
                    cur = None
                    continue
                if cur is None:
                    continue
                f = field_re.match(line)
                if not f:
                    continue
                off, rest = f.groups()
                default = None
                if " = " in rest:
                    rest, default = rest.split(" = ", 1)
                toks = rest.split(" ")
                static = ""
                while toks and toks[0] in ("static", "const"):
                    static += toks.pop(0) + " "
                if len(toks) < 2:
                    continue
                name, ftype = toks[-1], " ".join(toks[:-1])
                if static.startswith("static const"):
                    if is_enum and default is not None:
                        try:
                            self.enums[cur].setdefault(int(default, 0), name)
                        except ValueError:
                            pass
                    continue
                if static:
                    self.static_fields.setdefault(cur, {})[int(off)] = (name, ftype)

    def static_field(self, typ, off):
        return self.static_fields.get(typ, {}).get(off)

    def enum_name(self, enum_type, value):
        names = self.enums.get(enum_type)
        if names is None:
            return value
        if value in names:
            return names[value]
        # [Flags] enums: decompose into single-bit members when that is exact.
        if value > 0:
            parts, rest = [], value
            for v, n in sorted(names.items()):
                if v > 0 and v & (v - 1) == 0 and rest & v:
                    parts.append(n)
                    rest &= ~v
            if parts and rest == 0:
                return "|".join(parts)
        return f"{enum_type.rsplit('.', 1)[-1]}({value})"

    def is_subclass(self, typ, ancestor):
        seen = set()
        while typ and typ not in seen:
            if typ == ancestor:
                return True
            seen.add(typ)
            typ = self.base.get(typ)
        return False


# --------------------------------------------------------------------------
# Disassembly parsing
# --------------------------------------------------------------------------

_INS_RE = re.compile(r"^(0x[0-9a-f]+): (\S+)(?: (.*))?$")
_BLOCK_RE = re.compile(r"^===== (\S+)::(\S+) @ (0x[0-9a-f]+)$")


class Ins:
    __slots__ = ("addr", "mnem", "ops", "comment", "text")

    def __init__(self, addr, mnem, ops, comment, text):
        self.addr, self.mnem, self.ops, self.comment, self.text = (
            addr,
            mnem,
            ops,
            comment,
            text,
        )


def parse_methods(asm_text):
    """Return {(type, method): (addr, [Ins])} for every method block in an .asm file."""
    out = OrderedDict()
    cur = None
    for line in asm_text.splitlines():
        b = _BLOCK_RE.match(line)
        if b:
            cur = []
            out[(b.group(1), b.group(2))] = (int(b.group(3), 16), cur)
            continue
        if cur is None:
            continue
        m = _INS_RE.match(line)
        if not m:
            continue
        rest = m.group(3) or ""
        ops_text, _, comment = rest.partition(";")
        ops = split_operands(ops_text.strip())
        cur.append(Ins(int(m.group(1), 16), m.group(2), ops, comment.strip(), line))
    return out


def split_operands(text):
    if not text:
        return []
    parts, depth, buf = [], 0, ""
    for ch in text:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    parts.append(buf.strip())
    return parts


_MEM_RE = re.compile(r"^(?:(byte|word|dword|qword|xmmword) ptr )?(?:[a-z]s:)?\[(.*)\]$")


def parse_mem(op):
    """Return (size, base, index, scale, disp) for a memory operand, or None."""
    m = _MEM_RE.match(op)
    if not m:
        return None
    size = {"byte": 1, "word": 2, "dword": 4, "qword": 8, "xmmword": 16}.get(
        m.group(1) or "", 0
    )
    base = index = None
    scale = 1
    disp = 0
    for sign, term in re.findall(r"([+-]?)\s*([^+-]+)", m.group(2).replace(" ", "")):
        neg = sign == "-"
        if "*" in term:
            r, s = term.split("*")
            index, scale = r, int(s, 0)
        elif term in _ALIAS or term == "rip":
            base = term
        else:
            v = int(term, 0)
            disp += -v if neg else v
    return size, base, index, scale, disp


def parse_imm(op):
    try:
        return int(op, 0)
    except ValueError:
        return None


def to_signed(v, bits):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


# --------------------------------------------------------------------------
# Symbolic values
# --------------------------------------------------------------------------


class V:
    """A symbolic value. ``k`` is the kind; the other fields depend on it."""

    __slots__ = ("k", "a", "b")

    def __init__(self, k, a=None, b=None):
        self.k, self.a, self.b = k, a, b

    def __repr__(self):
        return f"V({self.k},{self.a!r},{self.b!r})"


def imm(v):
    return V("imm", v)


UNKNOWN = V("unknown")


class HObj:
    """A heap object built by the constructor."""

    def __init__(self, cls, kind, elem=None, length=None):
        self.cls = cls  # TypeInfo name
        self.kind = kind  # list | dict | array | loctext | archid | struct | object
        self.elem = elem  # element type(s)
        self.length = length
        self.items = []  # list elements / dict (k, v) pairs
        self.slots = {}  # array index -> value, struct fields
        self.text = None  # LocalizableText key / ArchetypeID guid


def obj_kind(cls):
    if cls.startswith("System.Collections.Generic.List`1<"):
        return "list", cls[len("System.Collections.Generic.List`1<") : -1]
    if cls.startswith("System.Collections.Generic.Dictionary`2<"):
        return "dict", split_generic_args(
            cls[len("System.Collections.Generic.Dictionary`2<") : -1]
        )
    if cls == "Canis.utils.localization.LocalizableText":
        return "loctext", None
    if cls == "Canis.utils.ids.ArchetypeID":
        return "archid", None
    return "object", None


def split_generic_args(text):
    out, depth, buf = [], 0, ""
    for ch in text:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    out.append(buf)
    return out


# --------------------------------------------------------------------------
# Interpreter
# --------------------------------------------------------------------------


class EmuError(Exception):
    pass


class Store:
    __slots__ = ("key_owner", "key", "key_type", "value", "variant", "addr", "snippet")

    def __init__(self, key_owner, key, key_type, value, variant, addr, snippet):
        self.key_owner, self.key, self.key_type = key_owner, key, key_type
        self.value, self.variant, self.addr, self.snippet = (
            value,
            variant,
            addr,
            snippet,
        )


class Emulator:
    def __init__(self, listing, ins_list, trace=False):
        self.L = listing
        self.ins = ins_list
        self.index = {i.addr: n for n, i in enumerate(ins_list)}
        self.regs = {r: UNKNOWN for r in REG64}
        for n in range(16):
            self.regs[f"xmm{n}"] = UNKNOWN
        self.regs["rdi"] = V("this")
        self.stack = {}  # rbp-relative displacement -> V
        self.flags = None
        self.stores = []
        self.notes = []  # anything the interpreter had to guess or skip
        self.trace = trace

    # ---- registers -------------------------------------------------------
    def get_reg(self, name):
        full, bits = _ALIAS[name]
        v = self.regs[full]
        if v.k == "imm" and bits < 64 and bits != 128:
            return imm(v.a & ((1 << bits) - 1))
        return v

    def set_reg(self, name, v):
        full, bits = _ALIAS[name]
        if v.k == "imm" and bits == 32:
            v = imm(v.a & 0xFFFFFFFF)
        self.regs[full] = v

    # ---- operands --------------------------------------------------------
    def read(self, op, ins):
        if op in _ALIAS:
            return self.get_reg(op)
        n = parse_imm(op)
        if n is not None:
            return imm(n)
        mem = parse_mem(op)
        if mem is None:
            raise EmuError(f"operand {op!r} at {ins.addr:#x}")
        return self.load(mem, ins)

    def global_label(self, ins):
        """The '[0xADDR] Label' annotation of a rip-relative operand."""
        m = re.match(r"\[(0x[0-9a-f]+)\](?:=\S+)?\s*(.*)$", ins.comment)
        if not m:
            return None, None
        return int(m.group(1), 16), m.group(2).strip()

    def deref_global(self, label):
        if label.startswith("TypeInfo:"):
            return V("klass", label[len("TypeInfo:") :])
        if label.startswith("Str:"):
            s = label[len("Str:") :]
            if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
                s = s[1:-1]
            return V("str", s)
        if label.startswith(("MethodRef:", "MethodDef:")):
            return V("mref", label.split(":", 1)[1])
        return V("unknown", label)

    def load(self, mem, ins):
        size, base, index, scale, disp = mem
        if base == "rip":
            f = re.search(r"\bf(64|32)=(\S+)", ins.comment)
            if f:
                return V("dbl", float(f.group(2)))
            _, label = self.global_label(ins)
            if label is None:
                raise EmuError(f"rip-relative load without a label at {ins.addr:#x}")
            return self.deref_global(label)
        if base is None:
            return UNKNOWN
        b = self.get_reg(base)
        if base == "rbp" and index is None:
            v = self.stack.get(disp)
            if v is None:
                return UNKNOWN
            if size == 4 and v.k == "nullable":
                return imm(1 if v.b is not None else 0)  # hasValue as a dword
            return v
        if index is not None:
            return UNKNOWN
        if b.k == "gptr" and disp == 0:
            return self.deref_global(b.b)
        if b.k == "klass":
            if disp == 0xB8:
                return V("sblock", b.a)
            return V("klassfield", b.a, disp)
        if b.k == "sblock":
            f = self.L.static_field(b.a, disp)
            if f is None:
                self.notes.append(
                    f"{ins.addr:#x}: unknown static field {b.a}+{disp:#x}"
                )
                return V("sfield", b.a, (f"+{disp:#x}", "?"))
            return V("sfield", b.a, f)
        if b.k == "obj":
            o = b.a
            if o.kind == "list" and disp == 0x10:
                return V("items", o)
            if o.kind == "array" and disp == 0x18:
                return imm(o.length)
            return V("objfield", o, disp)
        if b.k == "items" and disp == 0x18:
            return V("capacity", b.a)
        return UNKNOWN

    def store(self, op, v, ins):
        if op in _ALIAS:
            self.set_reg(op, v)
            return
        mem = parse_mem(op)
        if mem is None:
            raise EmuError(f"store operand {op!r} at {ins.addr:#x}")
        size, base, index, scale, disp = mem
        if base == "rip" or base is None:
            return  # one-time metadata-init flags
        if base == "rbp" and index is None:
            # Nullable<T> locals are zeroed (hasValue = false) before their .ctor
            # runs; a register spill is kept as is.
            if size == 16:  # movaps [rbp-X], xmm0 zeroing a Nullable<double>
                self.stack[disp] = imm(0)
                self.stack[disp + 8] = v
                return
            self.stack[disp] = v
            return
        b = self.get_reg(base)
        if b.k == "items":
            if disp != 0x20 or index is None:
                raise EmuError(f"unexpected list store {ins.text}")
            b.a.items.append(v)
            return
        if b.k == "obj":
            o = b.a
            if o.kind == "array" and index is None:
                esize = size or 8
                i = (disp - 0x20) // esize
                o.slots[i] = v
                return
            if o.kind == "list" and disp in (0x18, 0x1C):
                return  # _size / _version bookkeeping of the inline Add
            o.slots[disp] = v
            return
        if b.k == "this":
            return  # this.archetypeID = archID
        self.notes.append(
            f"{ins.addr:#x}: store to untracked memory: {ins.text.split(': ', 1)[1]}"
        )

    # ---- control flow ----------------------------------------------------
    def is_noreturn_at(self, addr):
        n = self.index.get(addr)
        if n is None:
            return False
        i = self.ins[n]
        if i.mnem != "call":
            return False
        tgt = parse_imm(i.ops[0]) if i.ops else None
        return (
            "noreturn" in i.comment
            or "throw" in i.comment
            or "raise_exception" in i.comment
            or tgt in NORETURN_ADDRS
        )

    def decide(self, ins, fallthrough):
        target = parse_imm(ins.ops[0])
        if self.is_noreturn_at(target):
            return False
        if fallthrough is not None and self.is_noreturn_at(fallthrough):
            return True
        f = self.flags
        if f is None:
            raise EmuError(f"conditional jump without flags at {ins.addr:#x}")
        kind, a, b, a_op, b_op = f
        cc = ins.mnem
        if kind == "cmp":
            # cmp dword ptr [klass+0xe4], 0: the class's static constructor has run.
            if a.k == "klassfield" and a.b == 0xE4 and b.k == "imm" and b.a == 0:
                return {"jne": True, "je": False}[cc]
            # cmp byte ptr [rip+X], 0: the method's metadata is initialised.
            if a_op.startswith("byte ptr [rip") and b.k == "imm" and b.a == 0:
                return {"jne": True, "je": False}[cc]
            # cmp size, items.Length: List<T>.Add fast path (there is room).
            if b.k == "capacity":
                return {"jae": False, "jb": True, "jbe": True, "ja": False}[cc]
            if a.k == "imm" and b.k == "imm":
                x, y = a.a, b.a
                return {
                    "je": x == y,
                    "jne": x != y,
                    "jae": x >= y,
                    "jb": x < y,
                    "ja": x > y,
                    "jbe": x <= y,
                }[cc]
        if kind == "test":
            if a is b or (a_op == b_op):
                nz = a.k in ("obj", "items", "klass", "this", "sblock", "str", "sfield")
                if a.k == "imm":
                    nz = a.a != 0
                elif not nz:
                    raise EmuError(f"test of unknown value at {ins.addr:#x}: {a!r}")
                return {"je": not nz, "jne": nz}[cc]
        raise EmuError(f"undecided branch at {ins.addr:#x}: {ins.text} flags={f!r}")

    # ---- calls -----------------------------------------------------------
    def call(self, ins):
        c = ins.comment
        target = parse_imm(ins.ops[0]) if ins.ops else None
        R = self.get_reg
        if (
            "initialize_runtime_metadata" in c
            or "write_barrier" in c
            or "run_class_static_ctor" in c
            or "WormArchetype::.ctor" in c
            or "canis.archetypes.Archetype::.ctor" in c
            or "System.Object::.ctor" in c
        ):
            return
        if "noreturn" in c or target in NORETURN_ADDRS:
            raise EmuError(f"reached a no-return call at {ins.addr:#x}")
        if "rt:object_new" in c:
            k = R("rdi")
            if k.k != "klass":
                raise EmuError(f"object_new of {k!r} at {ins.addr:#x}")
            kind, elem = obj_kind(k.a)
            self.regs["rax"] = V("obj", HObj(k.a, kind, elem))
            return
        if "rt:SZArrayNew" in c:
            k, n = R("rdi"), R("rsi")
            if k.k != "klass" or n.k != "imm" or not k.a.endswith("[]"):
                raise EmuError(f"SZArrayNew({k!r},{n!r}) at {ins.addr:#x}")
            self.regs["rax"] = V("obj", HObj(k.a, "array", k.a[:-2], n.a))
            return
        if "LocalizableText::.ctor" in c or "ArchetypeID::.ctor" in c:
            o, s = R("rdi"), R("rsi")
            if o.k != "obj" or s.k != "str":
                raise EmuError(f"text ctor({o!r},{s!r}) at {ins.addr:#x}")
            o.a.text = s.a
            return
        if re.search(r"System\.Nullable`1<[^>]*>::\.ctor", c):
            p = R("rdi")
            if p.k != "stackptr":
                raise EmuError(f"Nullable ctor on {p!r} at {ins.addr:#x}")
            if "Nullable`1<double>" in c:
                x = R("xmm0")
                if x.k != "dbl":
                    raise EmuError(f"Nullable<double> of {x!r} at {ins.addr:#x}")
                self.stack[p.a] = V("nullable", "double?", x.a)
                self.stack[p.a + 8] = x
            else:
                x = R("esi")
                if x.k != "imm":
                    raise EmuError(f"Nullable of {x!r} at {ins.addr:#x}")
                t = "bool?" if "Nullable`1<bool>" in c else "int?"
                self.stack[p.a] = V("nullable", t, to_signed(x.a, 32))
            return
        if "ObjectAttributes::Has<" in c:
            self.record_has(ins)
            return
        if "AddWithResize" in c:
            lst = R("rdi")
            if lst.k != "obj" or lst.a.kind != "list":
                raise EmuError(f"AddWithResize on {lst!r} at {ins.addr:#x}")
            lst.a.items.append(
                R("esi") if "Int32Enum" in c or "<int>" in c else R("rsi")
            )
            self.notes.append(f"{ins.addr:#x}: took an AddWithResize slow path")
            return
        if re.search(r"(List`1|Dictionary`2)<.*>::\.ctor", c):
            return
        if re.search(r"Dictionary`2<.*>::Add$", c):
            d = R("rdi")
            if d.k != "obj" or d.a.kind != "dict":
                raise EmuError(f"Dictionary.Add on {d!r} at {ins.addr:#x}")
            if "Int32Enum,int" in c:
                d.a.items.append((R("esi"), R("edx")))
            else:
                d.a.items.append((R("rsi"), R("rdx")))
            return
        if "InfluenceRequirement::Make" in c:
            o = HObj("worm.canis.data.attributes.InfluenceRequirement", "struct")
            o.slots = {"Faction": R("edi"), "Amount": R("esi")}
            self.regs["rax"] = V("obj", o)
            return
        if "System.Linq.Enumerable::Repeat<" in c:  # Decks.*: Repeat(archID, n)
            x, cnt = R("rdi"), R("esi")
            if cnt.k != "imm":
                raise EmuError(f"Repeat count {cnt!r} at {ins.addr:#x}")
            o = HObj("IEnumerable", "list", "Canis.utils.ids.ArchetypeID")
            o.items = [x] * cnt.a
            self.regs["rax"] = V("obj", o)
            return
        if "System.Linq.Enumerable::Concat<" in c:  # Decks.*: Concat(a, b)
            a, b = R("rdi"), R("rsi")
            if a.k != "obj" or b.k != "obj":
                raise EmuError(f"Concat({a!r},{b!r}) at {ins.addr:#x}")
            o = HObj("IEnumerable", "list", "Canis.utils.ids.ArchetypeID")
            o.items = list(a.a.items) + list(b.a.items)
            self.regs["rax"] = V("obj", o)
            return
        if "rt:IsInst" in c:
            self.regs["rax"] = R("rdi")
            return
        self.notes.append(f"{ins.addr:#x}: unmodelled call {c or ins.ops}")
        self.regs["rax"] = V("unknown", c)

    def record_has(self, ins):
        key = self.get_reg("rsi")
        mref = self.get_reg("rcx")
        variant = mref.a if mref.k == "mref" else ins.comment
        if key.k != "sfield" or key.a not in ATTR_OWNERS:
            raise EmuError(f"Has<> with key {key!r} at {ins.addr:#x}")
        name, ftype = key.b
        if "Has<System.Nullable`1<double>>" in ins.comment:
            value = self.get_reg("xmm0")
            has = self.get_reg("edx")
            if has.k == "imm" and has.a == 0:
                value = V("null")
        else:
            value = self.get_reg("rdx")
        start = max(0, self.index[ins.addr] - 12)
        snippet = "\n".join(i.text for i in self.ins[start : self.index[ins.addr] + 1])
        self.stores.append(Store(key.a, name, ftype, value, variant, ins.addr, snippet))

    # ---- main loop -------------------------------------------------------
    def run(self, max_steps=50000):
        n = 0
        steps = 0
        while True:
            steps += 1
            if steps > max_steps:
                raise EmuError("step limit")
            if n >= len(self.ins):
                raise EmuError("ran off the end of the method")
            ins = self.ins[n]
            if self.trace:
                print(f"  {ins.text}", file=sys.stderr)
            m, ops = ins.mnem, ins.ops
            nxt = n + 1
            fallthrough = self.ins[nxt].addr if nxt < len(self.ins) else None
            if m in ("push", "pop", "nop", "endbr64"):
                pass
            elif m == "ret":
                return self.regs["rax"]
            elif m in ("add", "sub") and ops[0] in ("rsp",):
                pass
            elif m == "mov" or m == "movsxd" or m == "movzx":
                v = self.read(ops[1], ins)
                if m == "movsxd" and v.k == "imm":
                    v = imm(to_signed(v.a, 32) & 0xFFFFFFFFFFFFFFFF)
                if m == "movzx" and ops[1].startswith("word ptr") and v.k == "nullable":
                    pass  # a Nullable<bool> read as a word keeps its decoded form
                self.store(ops[0], v, ins)
            elif m == "lea":
                mem = parse_mem(ops[1])
                size, base, index, scale, disp = mem
                if base == "rip":
                    addr, label = self.global_label(ins)
                    self.set_reg(ops[0], V("gptr", addr, label or ""))
                elif base == "rbp" and index is None:
                    self.set_reg(ops[0], V("stackptr", disp))
                elif (
                    base is not None and index is None and self.get_reg(base).k == "imm"
                ):
                    self.set_reg(ops[0], imm(self.get_reg(base).a + disp))
                else:
                    self.set_reg(ops[0], V("addr", ops[1]))
            elif m in ("xorps", "xorpd", "pxor") and ops[0] == ops[1]:
                self.set_reg(ops[0], V("dbl", 0.0))
            elif m == "xor" and ops[0] == ops[1]:
                self.set_reg(ops[0], imm(0))
                self.flags = None
            elif m in ("movsd", "movss", "movaps", "movapd", "movups", "movq"):
                v = self.read(ops[1], ins)
                if m == "movsd" and v.k == "nullable":
                    v = UNKNOWN
                self.store(ops[0], v, ins)
            elif m == "cmp" or m == "test":
                a = self.read(ops[0], ins)
                b = self.read(ops[1], ins)
                self.flags = (m, a, b, ops[0], ops[1])
            elif m in (
                "inc",
                "dec",
                "add",
                "sub",
                "and",
                "or",
                "xor",
                "shl",
                "shr",
                "sar",
                "neg",
            ):
                if ops[0] in _ALIAS:
                    a = self.get_reg(ops[0])
                    b = self.read(ops[1], ins) if len(ops) > 1 else imm(1)
                    if a.k == "imm" and b.k == "imm":
                        fn = {
                            "inc": lambda x, y: x + 1,
                            "dec": lambda x, y: x - 1,
                            "add": lambda x, y: x + y,
                            "sub": lambda x, y: x - y,
                            "and": lambda x, y: x & y,
                            "or": lambda x, y: x | y,
                            "xor": lambda x, y: x ^ y,
                            "shl": lambda x, y: x << y,
                            "shr": lambda x, y: x >> y,
                            "sar": lambda x, y: x >> y,
                            "neg": lambda x, y: -x,
                        }[m]
                        self.set_reg(ops[0], imm(fn(a.a, b.a) & 0xFFFFFFFFFFFFFFFF))
                    else:
                        self.set_reg(ops[0], V("addr", ins.text))
                self.flags = None
            elif m == "jmp":
                tgt = parse_imm(ops[0])
                if tgt not in self.index:
                    # tail call out of the method
                    self.call(ins)
                    return self.regs["rax"]
                nxt = self.index[tgt]
            elif m.startswith("j"):
                taken = self.decide(ins, fallthrough)
                if taken:
                    nxt = self.index[parse_imm(ops[0])]
            elif m == "call":
                self.call(ins)
            elif m == "cdqe":
                pass
            else:
                raise EmuError(f"unmodelled instruction {ins.text}")
            n = nxt


# --------------------------------------------------------------------------
# Value decoding
# --------------------------------------------------------------------------


def strip_attrdef(ftype):
    p = "Canis.attributes.AttributeDefinition`1<"
    if ftype.startswith(p) and ftype.endswith(">"):
        return ftype[len(p) : -1]
    return ftype


class Decoder:
    def __init__(self, listing, guid_to_arch):
        self.L = listing
        self.guid_to_arch = guid_to_arch
        self.undecoded = []

    def short_arch(self, typ):
        return typ[len(ARCH_NS) :] if typ.startswith(ARCH_NS) else typ

    def decode(self, t, v):
        """Decode ``v`` of declared C# type ``t``; raise ValueError when it cannot."""
        if v.k == "null":
            return None
        if t.startswith("System.Nullable`1<"):
            inner = t[len("System.Nullable`1<") : -1]
            if v.k == "nullable":
                if v.b is None:
                    return None
                return self.scalar(inner, v.b)
            if v.k == "dbl" and inner == "double":
                return v.a
            if v.k == "imm":
                # A Nullable passed as packed bytes: hasValue in the low byte.
                if inner == "bool":
                    return None if (v.a & 0xFF) == 0 else bool((v.a >> 8) & 0xFF)
                return (
                    None
                    if (v.a & 0xFF) == 0
                    else self.scalar(inner, to_signed(v.a >> 32, 32))
                )
            raise ValueError(f"nullable from {v!r}")
        if t == "string":
            if v.k == "str":
                return v.a
            raise ValueError(f"string from {v!r}")
        if t == "Canis.utils.localization.LocalizableText":
            if v.k == "obj" and v.a.kind == "loctext":
                return v.a.text
            raise ValueError(f"LocalizableText from {v!r}")
        if t == "Canis.utils.ids.ArchetypeID":
            return self.arch_ref(v)
        if t == "Canis.utils.ids.AbilityID":
            if v.k == "sfield" and v.b[0] == "AbilityID":
                return v.a
            raise ValueError(f"AbilityID from {v!r}")
        if t.startswith("System.Collections.Generic.List`1<"):
            inner = t[len("System.Collections.Generic.List`1<") : -1]
            if v.k == "obj" and v.a.kind == "list":
                return [self.elem(inner, e) for e in v.a.items]
            raise ValueError(f"list from {v!r}")
        if t.endswith("[]"):
            inner = t[:-2]
            if v.k == "obj" and v.a.kind == "array":
                out = []
                for i in range(v.a.length):
                    e = v.a.slots.get(i)
                    out.append(None if e is None else self.elem(inner, e))
                return out
            raise ValueError(f"array from {v!r}")
        if t.startswith("System.Collections.Generic.Dictionary`2<"):
            kt, vt = split_generic_args(
                t[len("System.Collections.Generic.Dictionary`2<") : -1]
            )
            if v.k == "obj" and v.a.kind == "dict":
                return {str(self.elem(kt, k)): self.elem(vt, x) for k, x in v.a.items}
            raise ValueError(f"dictionary from {v!r}")
        if t == "worm.canis.data.attributes.InfluenceRequirement":
            if v.k == "obj" and v.a.kind == "struct":
                return {
                    "Faction": self.scalar(
                        "worm.canis.data.enums.Factions", v.a.slots["Faction"].a
                    ),
                    "Amount": to_signed(v.a.slots["Amount"].a, 32),
                }
            raise ValueError(f"InfluenceRequirement from {v!r}")
        if v.k == "imm":
            return self.scalar(t, to_signed(v.a, 32))
        raise ValueError(f"{t} from {v!r}")

    def elem(self, t, v):
        if v.k == "imm":
            return self.scalar(t, to_signed(v.a, 32))
        return self.decode(t, v)

    def scalar(self, t, x):
        if t == "bool":
            return bool(x)
        if t == "double":
            return float(x)
        if t in ("int", "long", "short", "byte"):
            return x
        if t in self.L.enums:
            return self.L.enum_name(t, x)
        return x

    def arch_ref(self, v):
        if v.k == "sfield" and v.b[0] == "archID":
            return self.short_arch(v.a)
        if v.k == "obj" and v.a.kind == "archid":
            typ = self.guid_to_arch.get(v.a.text)
            return self.short_arch(typ) if typ else {"archetype_guid": v.a.text}
        raise ValueError(f"ArchetypeID from {v!r}")


# --------------------------------------------------------------------------
# Archetype discovery and records
# --------------------------------------------------------------------------

SKIP_PARTS = ("Hagal", "Challenge", "Tutorial")


def archetype_files(asm_dir):
    out = []
    for p in sorted(Path(asm_dir).glob(ARCH_NS + "*.asm")):
        name = p.name[: -len(".asm")]
        rest = name[len(ARCH_NS) :]
        if "." not in rest:  # WormArchetype, WormArchetypes, WormArchetypeExtensions
            continue
        if (
            any(part in rest.split(".")[0] for part in SKIP_PARTS)
            or ".Skirmish." in name
        ):
            continue
        out.append((name, p))
    return out


def cctor_guid(methods, typ):
    blk = methods.get((typ, ".cctor"))
    if not blk:
        return None
    last = None
    for ins in blk[1]:
        m = re.search(r"Str:'([^']*)'", ins.comment)
        if m:
            last = m.group(1)
        if ins.mnem == "call" and "ArchetypeID::.ctor" in ins.comment:
            return last
    return None


GAME_UPRISING = frozenset({"Uprising"})
GAME_UPRISING_CHOAM = frozenset({"Uprising", "CHOAMModule"})


def set_rule(set_list, removed, enabled):
    """SetList meets the enabled sets and RemovedFromSetList does not.

    SetupPhase applies it as IsInSets (SetList.Any(enabled)) when it filters
    the Imperium, intrigue and conflict decks, and removes spaces and level-II
    conflicts with IsRemovedFromSets (BeginSetup b__4 @ 0x4a42190, CreateDecks
    b__17 @ 0x4a41900).
    """
    sl = set(set_list) if isinstance(set_list, list) else set()
    rm = set(removed) if isinstance(removed, list) else set()
    return bool(sl & enabled) and not (rm & enabled)


def refine_membership(records, decks):
    """Replace the SetList rule where setup code decides membership otherwise."""
    by = {r["short"]: r for r in records}
    starter = set(decks.get("StandardStarterDeck", {}).get("cards", []))
    reserve = set(decks.get("UprisingReserveDeck", {}).get("cards", []))
    for r in records:
        a = r["attributes"]
        g = r["in_game"]
        if r["kind"] in ("starter", "reserve") or r["short"] in starter | reserve:
            inside = r["short"] in starter or r["short"] in reserve
            g["uprising"] = g["uprising_choam"] = inside
            g["basis"] = (
                "Decks.StandardStarterDeck / Decks.UprisingReserveDeck (SetupPhase); "
                "Epic mode uses EpicStarterDeck instead"
            )
        elif r["kind"] == "imperium" and a.get("ImperiumType") == "Promo":
            g["uprising"] = g["uprising_choam"] = False
            g["basis"] = (
                "ImperiumType Promo: the Imperium deck takes IsImperiumArchetype(Main) "
                "&& "
                "IsInSets (CreateDecks b__0 @ 0x4a415b0, b__2 @ 0x4a41660)"
            )
        elif r["kind"] == "contract":
            ok = "Uprising" in r["set_list"] and "RiseOfIx" not in r["set_list"]
            g["uprising"] = False
            g["uprising_choam"] = ok
            g["basis"] = (
                "contract deck filter IsContractArchetype && IsInSet(Uprising) && "
                "!IsInSet(RiseOfIx) (CreateDecks b__10_25 @ 0x4a411f0); without "
                "CHOAMModule no space, conflict or card in the game has a GainContract "
                "ability"
            )
    for r in records:
        rewards = r["attributes"].get("ConflictRewardArchetypes")
        if r["kind"] != "conflict" or not isinstance(rewards, list):
            continue
        for place, child in enumerate(rewards, 1):
            c = by.get(child)
            if c is None:
                continue
            c["reward_of"] = r["short"]
            c["reward_place"] = place
            c["in_game"]["uprising"] = r["in_game"]["uprising"]
            c["in_game"]["uprising_choam"] = r["in_game"]["uprising_choam"]
            c["in_game"]["basis"] = "parent conflict " + r["short"]
            if c["title"] is None and r["title"]:
                c["label"] = f"{r['title']} - reward {place}"
    for r in records:
        a = r["attributes"]
        if r["kind"] == "contract":
            refs = a.get("ReferencedArchetypeIDs") or []
            gains = [
                f"{k} {a[k]}"
                for k in (
                    "Solari",
                    "Spice",
                    "Water",
                    "Troops",
                    "TechNegotiator",
                    "IntrigueCard",
                    "VictoryPoints",
                )
                if k in a
            ]
            r["label"] = (
                f"{r['short'].rsplit('.', 1)[-1]}: {a.get('ContractType')}"
                + (
                    f" at {'/'.join(x.rsplit('.', 1)[-1] for x in refs)}"
                    if refs
                    else ""
                )
                + (f" -> {', '.join(gains)}" if gains else "")
            )
    for r in records:
        ups = r["attributes"].get("LeaderUpgradeArchetypes")
        if isinstance(ups, list):
            for u in ups:
                if u in by:
                    by[u]["upgrade_of"] = r["short"]


DECKS_TYPE = "worm.canis.data.decks.Decks"


def extract_decks(asm_dir, listing, decoder):
    """Run every ``Decks.*Deck()`` method and return {method: [archetype short names]}.

    SetupPhase uses StandardStarterDeck (EpicStarterDeck in Epic mode,
    ImmortalityStarterDeck with Immortality) and UprisingReserveDeck when the
    Uprising set is enabled (StandardReserveDeck otherwise); the Leader*Deck
    lists are only used by Skirmish rules modifiers.
    """
    path = Path(asm_dir) / (DECKS_TYPE + ".asm")
    out = OrderedDict()
    failures = []
    if not path.exists():
        return out, [{"type": DECKS_TYPE, "error": "no asm file"}]
    methods = parse_methods(path.read_text(encoding="utf-8", errors="replace"))
    for (typ, meth), (addr, ins) in methods.items():
        if typ != DECKS_TYPE or not meth.endswith("Deck"):
            continue
        emu = Emulator(listing, ins)
        try:
            ret = emu.run()
            names = decoder.decode(
                "System.Collections.Generic.List`1<Canis.utils.ids.ArchetypeID>", ret
            )
        except (EmuError, ValueError) as e:
            failures.append(
                {"type": f"{typ}::{meth}", "ctor": f"{addr:#x}", "error": str(e)}
            )
            continue
        out[meth] = {"addr": f"{addr:#x}", "cards": names}
    return out, failures


def build_record(typ, ctor_addr, emu, decoder, loc):
    attrs = OrderedDict()
    undecoded = []
    dup = []
    raw_ability_ids = None
    for s in emu.stores:
        t = strip_attrdef(s.key_type)
        try:
            val = decoder.decode(t, s.value)
        except (ValueError, KeyError, AttributeError) as e:
            val = {"undecoded": s.snippet, "reason": str(e)}
            undecoded.append(
                {"attribute": s.key, "addr": f"{s.addr:#x}", "reason": str(e)}
            )
        if s.key in attrs:
            dup.append(s.key)
        attrs[s.key] = val
        if s.key == "WormAbilityIDs":
            raw_ability_ids = val
    name_key = attrs.get("Name")
    entity = attrs.get("EntityType")
    imp_type = attrs.get("ImperiumType")
    kind = KIND_BY_ENTITY.get(entity, "other")
    if kind == "imperium" and imp_type in KIND_BY_IMPERIUM_TYPE:
        kind = KIND_BY_IMPERIUM_TYPE[imp_type]
    set_list = attrs.get("SetList") or []
    removed = attrs.get("RemovedFromSetList") or []

    def in_game(enabled):
        return set_rule(set_list, removed, enabled)

    rec = OrderedDict()
    rec["type"] = typ
    rec["short"] = typ[len(ARCH_NS) :]
    rec["kind"] = kind
    rec["title_key"] = name_key if isinstance(name_key, str) else None
    rec["title"] = loc.get(name_key) if isinstance(name_key, str) else None
    rec["set_list"] = set_list
    rec["removed_from"] = removed
    rec["in_game"] = OrderedDict(
        [
            ("uprising", in_game(GAME_UPRISING)),
            ("uprising_choam", in_game(GAME_UPRISING_CHOAM)),
            ("basis", "SetList"),
        ]
    )
    rec["attributes"] = attrs
    rec["ability_ids"] = raw_ability_ids if isinstance(raw_ability_ids, list) else []
    custom = attrs.get("CustomAbilityIDs")
    if custom is not None:
        rec["custom_ability_ids"] = custom
    rec["ctor"] = f"{ctor_addr:#x}"
    if dup:
        rec["duplicate_stores"] = dup
    if undecoded:
        rec["undecoded"] = undecoded
    if emu.notes:
        rec["interpreter_notes"] = emu.notes
    return rec


def run(args):
    dump = Path(args.dump)
    asm_dir = dump / "asm" / "worm-canis.dll"
    listing = Listing([dump / "worm-canis.dll.cs", dump / "Canis.dll.cs"])
    loc = json.loads(Path(args.loc).read_text(encoding="utf-8"))

    files = archetype_files(asm_dir)
    parsed = []
    guid_to_arch = {}
    for name, path in files:
        methods = parse_methods(path.read_text(encoding="utf-8", errors="replace"))
        typ = name
        if not listing.is_subclass(typ, "canis.archetypes.Archetype"):
            continue
        g = cctor_guid(methods, typ)
        if g:
            guid_to_arch[g] = typ
        parsed.append((typ, methods, g))

    decoder = Decoder(listing, guid_to_arch)
    records = []
    failures = []
    for typ, methods, guid in parsed:
        if args.only and not any(o in typ for o in args.only):
            continue
        blk = methods.get((typ, ".ctor"))
        if not blk:
            failures.append({"type": typ, "error": "no .ctor"})
            continue
        addr, ins = blk
        emu = Emulator(listing, ins, trace=args.trace)
        try:
            emu.run()
        except EmuError as e:
            failures.append({"type": typ, "ctor": f"{addr:#x}", "error": str(e)})
            continue
        rec = build_record(typ, addr, emu, decoder, loc)
        rec["arch_guid"] = guid
        records.append(rec)

    decks, deck_failures = extract_decks(asm_dir, listing, decoder)
    failures.extend(deck_failures)
    for rec in records:
        member = OrderedDict()
        for meth, d in decks.items():
            n = sum(1 for c in d["cards"] if c == rec["short"])
            if n:
                member[meth] = n
        if member:
            rec["decks"] = member
    refine_membership(records, decks)
    for rec in records:
        if rec["kind"] == "conflict_reward" and isinstance(
            rec["attributes"].get("GameText"), str
        ):
            rec["reward_text"] = loc.get(rec["attributes"]["GameText"])

    out_dir = Path(args.out)
    if args.only:
        json.dump(records, sys.stdout, indent=1, ensure_ascii=False)
        print()
        for f in failures:
            print("FAILED", f, file=sys.stderr)
        return 1 if failures else 0
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "archetypes.json").write_text(
        json.dumps(records, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_summary(
        out_dir / "archetypes.md", records, failures, dump, Path(args.loc), decks
    )
    print(f"{len(records)} archetypes -> {out_dir / 'archetypes.json'}")
    for f in failures:
        print("FAILED", f, file=sys.stderr)
    return 1 if failures else 0


MANUAL_BEGIN = "<!-- manual:begin -->"
MANUAL_END = "<!-- manual:end -->"


def write_summary(path, records, failures, dump, loc_path, decks):
    manual = ""
    if path.exists():
        old = path.read_text(encoding="utf-8")
        if MANUAL_BEGIN in old and MANUAL_END in old:
            manual = old[
                old.index(MANUAL_BEGIN) : old.index(MANUAL_END) + len(MANUAL_END)
            ]
    if not manual:
        placeholder = "(hand validation and cross-checks go here)"
        manual = f"{MANUAL_BEGIN}\n\n{placeholder}\n\n{MANUAL_END}"

    kinds = Counter(r["kind"] for r in records)
    kinds_up = Counter(r["kind"] for r in records if r["in_game"]["uprising_choam"])
    kinds_up0 = Counter(r["kind"] for r in records if r["in_game"]["uprising"])
    attr_count = Counter()
    attr_kinds = {}
    for r in records:
        for k in r["attributes"]:
            attr_count[k] += 1
            attr_kinds.setdefault(k, Counter())[r["kind"]] += 1
    lines = []
    lines.append("# Archetype extraction (Steam Dune: Imperium app, build dad97e20)")
    lines.append("")
    lines.append(
        "Generated by `scripts/dwgr/app_archetypes.py` from "
        f"`{dump}/asm/worm-canis.dll/worm.canis.archetypes.*.asm` (the `.ctor` of "
        "every "
        "archetype class except `Hagal*`), titles from "
        f"`{loc_path}`. Data: `archetypes.json` next to this file. "
        "The script rewrites everything except the hand-written section between the "
        "`manual` markers."
    )
    lines.append("")
    lines.append("## Record format")
    lines.append("")
    lines.append(
        "- `type`, `short` (type minus `worm.canis.archetypes.`), `kind` "
        "(from `EntityType`; `Imperium` splits by `ImperiumType` into "
        "`starter`/`reserve`/"
        "`imperium` (Main and Promo); TechTile, Tleilaxu, LeaderUpgrade -> `other`)."
    )
    lines.append(
        "- `title_key` = the `CoreAttributes.Name` localisation key, `title` = its "
        "en_US text."
    )
    lines.append(
        "- `set_list`, `removed_from` = `WormAttributes.SetList` / "
        "`RemovedFromSetList` "
        "(enum `worm.canis.data.enums.Set` names; `CHOAMModule` = 4001)."
    )
    lines.append(
        "- `in_game.uprising` / `in_game.uprising_choam`: whether a 4-player Uprising "
        "game "
        "without / with the CHOAM module contains it, with `in_game.basis`. Default "
        "basis "
        "`SetList`: SetList meets {Uprising} (resp. {Uprising, CHOAMModule}) and "
        "RemovedFromSetList does not. Exceptions: starter and reserve cards come from "
        "`Decks` (below); `ImperiumType = Promo` cards are not in the Imperium deck "
        "(it takes `ImperiumType = Main` only); contracts use the contract-deck filter "
        "(Uprising and not RiseOfIx) and count only with the CHOAM module; a conflict "
        "reward "
        "follows its conflict (`reward_of`, `reward_place`, `label`, `reward_text`)."
    )
    lines.append(
        "- `label` (contracts, conflict rewards): a readable name built from the data, "
        "because those archetypes have no localised title."
    )
    lines.append(
        "- `attributes`: every `ObjectAttributes::Has<T>(key, value)` store in the "
        "constructor, keyed by the `WormAttributes`/`CoreAttributes` static field "
        "name, in "
        "store order; enum values by name, lists in element order, `LocalizableText` "
        "as its "
        "key, `ArchetypeID` as the referenced archetype's short name, `AbilityID` as "
        "the "
        "ability class's full name."
    )
    lines.append(
        "- `ability_ids` = `WormAbilityIDs` in list order; `custom_ability_ids` = "
        "`CustomAbilityIDs` when present (conflict rewards use it instead)."
    )
    lines.append(
        "- `ctor` = constructor address, `arch_guid` = the GUID its `.cctor` gives "
        "`archID`."
    )
    lines.append("")
    lines.append("## Counts per kind")
    lines.append("")
    lines.append("| kind | all sets | in Uprising | in Uprising + CHOAM |")
    lines.append("|---|---:|---:|---:|")
    for k in sorted(kinds):
        lines.append(
            f"| {k} | {kinds[k]} | {kinds_up0.get(k, 0)} | {kinds_up.get(k, 0)} |"
        )
    lines.append(
        f"| **total** | {sum(kinds.values())} | {sum(kinds_up0.values())} | "
        f"{sum(kinds_up.values())} |"
    )
    lines.append("")
    lines.append("## Fixed decks (`worm.canis.data.decks.Decks`)")
    lines.append("")
    lines.append(
        "Starter and reserve cards, and leaders in Skirmish mode, come from these "
        "lists, "
        "not from `SetList`. `SetupPhase` builds the starter deck from "
        "`StandardStarterDeck` (`EpicStarterDeck` in Epic mode) and the reserve from "
        "`UprisingReserveDeck` when the Uprising set is enabled; the `Leader*Deck` "
        "lists are "
        "called only from Skirmish rules modifiers. Each record carries `decks` "
        "(method -> copies) when it is in one."
    )
    lines.append("")
    lines.append("| method | addr | cards (copies) |")
    lines.append("|---|---|---|")
    for meth, d in decks.items():
        cnt = Counter(d["cards"])
        order = list(OrderedDict.fromkeys(d["cards"]))
        cards = ", ".join(f"{c.rsplit('.', 1)[-1]} x{cnt[c]}" for c in order)
        lines.append(f"| `{meth}` | {d['addr']} | {cards} |")
    lines.append("")
    lines.append("## Attributes seen")
    lines.append("")
    lines.append("| attribute | archetypes | by kind |")
    lines.append("|---|---:|---|")
    for k, n in sorted(attr_count.items(), key=lambda x: (-x[1], x[0])):
        bk = ", ".join(f"{kk} {vv}" for kk, vv in sorted(attr_kinds[k].items()))
        lines.append(f"| `{k}` | {n} | {bk} |")
    lines.append("")
    lines.append("## Undecoded stores and interpreter notes")
    lines.append("")
    und = [(r["short"], u) for r in records for u in r.get("undecoded", [])]
    notes = [(r["short"], n) for r in records for n in r.get("interpreter_notes", [])]
    dups = [(r["short"], d) for r in records for d in r.get("duplicate_stores", [])]
    if not und and not notes and not failures and not dups:
        lines.append("None: every store decoded, every constructor ran to its `ret`.")
    for s, u in und:
        lines.append(
            f"- undecoded `{s}` `{u['attribute']}` at {u['addr']}: {u['reason']}"
        )
    for s, n in notes:
        lines.append(f"- note `{s}`: {n}")
    for s, d in dups:
        lines.append(
            f"- `{s}` stores `{d}` more than once (the last store wins in the JSON)"
        )
    for f in failures:
        lines.append(f"- FAILED `{f['type']}`: {f['error']}")
    lines.append("")
    lines.append(manual)
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dump", default=str(DEFAULT_DUMP))
    ap.add_argument("--loc", default=str(DEFAULT_LOC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument(
        "--only", action="append", help="print records whose type contains this text"
    )
    ap.add_argument(
        "--trace", action="store_true", help="print each executed instruction"
    )
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
