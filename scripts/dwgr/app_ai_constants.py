"""Extract the Dune: Imperium app AI constant tables from the local IL2CPP dump.

usage: python app_ai_constants.py [--dump DIR] [--out DIR] [--check MD]
                                  [--assemblies worm-canis.dll,...]

Standard library only. Reads (never writes) the dump of one app build:

- ``dump/asm/worm-canis.dll/worm.canis.ai.AIConstantsRef.asm`` (Hard, the base
  class), ``...AIMediumConstantsRef.asm`` and ``...AIEasyConstantsRef.asm``: the
  type listing at the top of each file and the ``===== Type::get_X @ 0xADDR``
  getter bodies;
- ``dump/worm-canis.dll.cs``: the same three type listings (cross-check);
- ``dump/asm/worm-canis.dll/worm.canis.ai.AIConstants.asm``: the static
  constructor that fills ``AIConstants.loadedConstants`` (AI level -> table);
- every ``dump/asm/<assembly>/*.asm`` of the chosen assemblies, to find which
  methods read each getter.

Writes ``constants.json`` and ``constants.md`` into ``--out``.

Getter values. Each getter body must be exactly one instruction between the
``push rbp; mov rbp, rsp`` prologue and the ``pop rbp; ret`` epilogue:
``movsd xmm0, [rip+d] ; f64=V`` (double V; the dump prints ``repr(float)``, so
V round-trips), ``xorps xmm0, xmm0`` (0.0), ``mov eax, imm`` / ``xor eax, eax``
(int). Anything else is reported under ``nonliteral`` with its asm.

Vtable slots. Slot = index of the getter in the AIConstantsRef listing + 4
(slots 0-3 are System.Object's), a virtual call is ``call [klass + 0x138 +
16*slot]`` and loads its MethodInfo from ``[klass + 0x140 + 16*slot]``. The
script checks this against every ``~vslot N ... AIConstantsRef::get_X``
annotation in the scanned asm (N must equal the computed slot).

Readers. A getter is read at a site when the code accesses
``qword ptr [K + 0x138 + 16*slot]`` and K is the klass of an AIConstantsRef
object. Three detectors, unioned:

1. annotation: the line carries ``~vslot N <AI*ConstantsRef>::get_X``;
2. tracked: an unannotated access whose base register, followed backwards in
   address order through ``mov`` copies, stack spills (``[rbp - x]``) and the
   klass load ``mov K, [X]``, comes from ``call WormAIProfile::get_Constants``,
   a field named ``constants`` (``~...constants`` annotation, or the closure
   field ``WormImperiumPlayable/<>c__DisplayClass2_0.constants`` at +0x10 of
   ``this``) or a static ``AIConstants.*ConstantsRef`` field;
3. merged: the compiler merged several getter calls into one indirect call:
   adjacent ``mov e?x, OFF`` / ``mov e?x, OFF+8`` pairs that feed a later
   ``[K + reg]`` access (``call [r8+rcx]``, or ``mov rdx,[rsi+rdx]; jmp rdx``);
   the pair counts when the object register X of the merge site's klass load
   ``mov K, [X]`` resolves to the constants object at the pair.

Every other access to a getter's call offset is classified too: annotated as
another type's vslot (not a reader) or unresolved (listed for manual review).

The backward tracking ignores control flow (it follows address order, like
the dump's own ``~`` annotations), so a ``tracked`` hit should be read as
"the nearest preceding definition is the constants object".
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

DEFAULT_DUMP = os.path.expanduser(
    "~/Workspace/tabletop-ai/Dune-Imperium-assets/reference/dune-steam-app/"
    "dad97e2021144d45b5b4f022e07bd3b3/dump"
)
NS = "worm.canis.ai."
CLASSES = {  # class -> difficulty name
    "AIConstantsRef": "Hard",
    "AIMediumConstantsRef": "Medium",
    "AIEasyConstantsRef": "Easy",
}
VTABLE_OFFSET = 0x138
SYSTEM_OBJECT_SLOTS = 4
GET_CONSTANTS_NAME = "worm.canis.ai.WormAIProfile::get_Constants"
# Closure fields of type AIConstantsRef (worm-canis.dll.cs): (declaring type, offset).
CONSTANTS_FIELDS = {
    ("worm.canis.entities.WormImperiumPlayable/<>c__DisplayClass2_0", 0x10)
}

GPR = {}
for _r64, _aliases in {
    "rax": "eax ax al ah",
    "rbx": "ebx bx bl bh",
    "rcx": "ecx cx cl ch",
    "rdx": "edx dx dl dh",
    "rsi": "esi si sil",
    "rdi": "edi di dil",
    "rbp": "ebp bp bpl",
    "rsp": "esp sp spl",
}.items():
    GPR[_r64] = _r64
    for _a in _aliases.split():
        GPR[_a] = _r64
for _n in range(8, 16):
    for _s in ("", "d", "w", "b"):
        GPR[f"r{_n}{_s}"] = f"r{_n}"
CALLER_SAVED = {"rax", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11"}
NO_WRITE = {
    "cmp",
    "test",
    "push",
    "bt",
    "ucomisd",
    "ucomiss",
    "comisd",
    "comiss",
    "nop",
}

LINE_RE = re.compile(r"^(0x[0-9a-f]+): (\S+)(?: (.*?))?\s*$")
HEADER_RE = re.compile(r"^===== (.+?) @ (0x[0-9a-f]+)\s*$")
LISTING_METHOD_RE = re.compile(r"^\s+method (0x[0-9a-f]+) (.*?)(\S+) (\w+)\((.*)\)\s*$")
MEM_DISP_RE = re.compile(r"qword ptr \[(r\w+) \+ (0x[0-9a-f]+)\]")
MEM_REGREG_RE = re.compile(r"qword ptr \[(r\w+) \+ (r\w+)\]")
MEM_PLAIN_RE = re.compile(r"^qword ptr \[(r\w+)\]$")
MEM_STACK_RE = re.compile(
    r"^qword ptr \[(rbp - 0x[0-9a-f]+|rsp(?: \+ 0x[0-9a-f]+)?)\]$"
)
MOV_IMM32_RE = re.compile(r"^(e[a-d]x|e[sd]i|r\d+d), (0x[0-9a-f]+|\d+)$")
VSLOT_RE = re.compile(r"~vslot (\d+) (method )?(\S+)::(\S+)")
CALL_TARGET_RE = re.compile(r"^(0x[0-9a-f]+)$")


# ---------------------------------------------------------------- parsing


class Ins:
    __slots__ = ("addr", "mn", "ops", "cm", "text")

    def __init__(self, addr, mn, ops, cm, text):
        self.addr, self.mn, self.ops, self.cm, self.text = addr, mn, ops, cm, text

    def operands(self):
        return split_operands(self.ops)


def split_operands(ops):
    out, depth, cur = [], 0, []
    for ch in ops or "":
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur).strip())
    return out


def parse_ins(line):
    if not line.startswith("0x"):
        return None
    code, sep, cm = line.partition("    ; ")
    m = LINE_RE.match(code.rstrip())
    if not m:
        return None
    return Ins(
        int(m.group(1), 16),
        m.group(2),
        (m.group(3) or "").strip(),
        cm.strip() if sep else "",
        line.rstrip("\n"),
    )


def iter_methods(path):
    """Yield (method name, method address, [raw lines]) for each ===== block."""
    name = addr = None
    lines = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("====="):
                if name is not None:
                    yield name, addr, lines
                m = HEADER_RE.match(line)
                name, addr = (
                    (m.group(1), int(m.group(2), 16)) if m else (line.strip(), 0)
                )
                lines = []
            elif name is not None:
                if line.startswith("0x") or line.startswith("; ----"):
                    lines.append(line)
                elif line.strip():
                    # a type listing (`// typeIndex N`, `type X : Y {`) ends the block
                    yield name, addr, lines
                    name, lines = None, []
    if name is not None:
        yield name, addr, lines


def parse_type_listing(text, full_type):
    """Methods of `type <full_type> : ... {` in a .cs listing or .asm header."""
    out = []
    inside = False
    for line in text.splitlines():
        if not inside:
            if re.match(rf"^(?:\w+ )*type {re.escape(full_type)} :", line):
                inside = True
            continue
        if line.startswith("}"):
            break
        m = LISTING_METHOD_RE.match(line)
        if m:
            mods = m.group(2).split()
            out.append(
                {
                    "addr": int(m.group(1), 16),
                    "virtual": "virtual" in mods,
                    "ret": m.group(3),
                    "name": m.group(4),
                }
            )
    return out


def parse_getter_body(lines):
    """Return (kind, value, literal_addr, asm) for one getter block."""
    ins = [i for i in (parse_ins(x) for x in lines) if i]
    body = []
    for k, i in enumerate(ins):
        if i.mn == "nop" or i.mn.startswith("nop"):
            continue
        if k == 0 and i.mn == "push" and i.ops == "rbp":
            continue
        if k == 1 and i.mn == "mov" and i.ops == "rbp, rsp":
            continue
        if i.mn in ("ret",) or (i.mn == "pop" and i.ops == "rbp"):
            continue
        body.append((k, i))
    asm = [i.text for i in ins]
    if len(body) != 1:
        return "nonliteral", None, None, asm
    k, i = body[0]
    if i.mn == "movsd" and i.ops.startswith("xmm0, qword ptr [rip + "):
        m = re.search(r"f64=(\S+)", i.cm)
        disp = int(re.search(r"\[rip \+ (0x[0-9a-f]+)\]", i.ops).group(1), 16)
        nxt = ins[k + 1].addr if k + 1 < len(ins) else None
        lit = nxt + disp if nxt is not None else None
        if not m:
            return "nonliteral", None, lit, asm
        return "double", float(m.group(1)), lit, asm
    if i.mn in ("xorps", "xorpd", "pxor") and i.ops == "xmm0, xmm0":
        return "double", 0.0, None, asm
    if i.mn == "mov" and i.ops.startswith("eax, "):
        v = i.ops.split(", ", 1)[1]
        try:
            return "int", int(v, 0), None, asm
        except ValueError:
            return "nonliteral", None, None, asm
    if i.mn == "xor" and i.ops == "eax, eax":
        return "int", 0, None, asm
    return "nonliteral", None, None, asm


# ---------------------------------------------------------------- tracking

CONST = "CONST"
ADDR_CONST = "ADDR_CONST"


def writes(ins, reg):
    """Does `ins` write the 64-bit register `reg`? Returns 'call', True or False."""
    if ins.mn == "call":
        return "call"
    if ins.mn in NO_WRITE or ins.mn.startswith("j") or ins.mn == "ret":
        return False
    if ins.mn in ("cdq", "cqo") and reg == "rdx":
        return True
    if ins.mn in ("div", "idiv", "mul") and reg in ("rax", "rdx"):
        return True
    ops = ins.operands()
    if not ops:
        return False
    if GPR.get(ops[0]) == reg:
        return True
    if ins.mn == "xchg" and len(ops) > 1 and GPR.get(ops[1]) == reg:
        return True
    return False


def call_target_name(ins):
    return ins.cm.split(";")[0].strip() if ins.cm else ""


class Method:
    """One disassembled method with a small backward value tracker.

    `resolve(loc, i)` answers "what does `loc` hold just before instruction i?"
    for a 64-bit register name or a stack slot ('stk:rbp - 0x38'). It walks
    backwards through the method; at a basic-block start (a jump target or a
    jump-table case) it follows every predecessor (fall-through and each jump)
    and returns their common answer. Paths that loop back are ignored.
    Answers: CONST (the AIConstantsRef object), ADDR_CONST (address of a field
    that holds it), ('KLASS', inner) (the klass of `inner`), or 'UNK:...'.
    """

    BUDGET = 200000

    def __init__(self, name, addr, raw):
        self.name, self.addr = name, addr
        self.declaring = name.rsplit("::", 1)[0]
        self.ins = []
        self.jt_starts = set()
        pending_case = False
        for line in raw:
            if line.startswith("; ---- jump-table case"):
                pending_case = True
                continue
            i = parse_ins(line)
            if i:
                if pending_case:
                    self.jt_starts.add(len(self.ins))
                    pending_case = False
                self.ins.append(i)
        index = {i.addr: k for k, i in enumerate(self.ins)}
        self.jump_srcs = defaultdict(list)
        for k, i in enumerate(self.ins):
            if i.mn.startswith("j") and CALL_TARGET_RE.match(i.ops):
                t = index.get(int(i.ops, 16))
                if t is not None:
                    self.jump_srcs[t].append(k)
        self.block_starts = set(self.jump_srcs) | self.jt_starts
        self._memo = {}

    @staticmethod
    def unconditional(ins):
        return ins.mn in ("jmp", "ret", "ud2") or (
            ins.mn == "call" and "(noreturn)" in ins.cm
        )

    def resolve(self, loc, i):
        self._budget = self.BUDGET
        self._visited = set()
        r = self._before(loc, i)
        return "UNK:only loops" if r is None else r

    def _before(self, loc, i):
        while True:
            self._budget -= 1
            if self._budget <= 0:
                return "UNK:budget"
            if i <= 0:
                return f"UNK:entry {loc}"
            if i in self.block_starts:
                key = (loc, i)
                if key in self._memo:
                    return self._memo[key]
                if key in self._visited:
                    return None
                self._visited.add(key)
                preds = []
                if not self.unconditional(self.ins[i - 1]):
                    preds.append(i - 1)
                preds += self.jump_srcs.get(i, [])
                results = [self._examine(loc, p) for p in preds]
                if i in self.jt_starts:
                    results.append("UNK:jump-table case")
                self._visited.discard(key)
                results = [r for r in results if r is not None]
                if not results:
                    return None
                if all(r == results[0] for r in results):
                    out = results[0]
                else:
                    out = "UNK:merge of " + "; ".join(
                        sorted({str(r)[:80] for r in results})
                    )
                if "UNK:budget" not in str(out):
                    self._memo[key] = out
                return out
            r = self._write(loc, i - 1)
            if r is not None:
                return r
            i -= 1

    def _examine(self, loc, j):
        r = self._write(loc, j)
        return r if r is not None else self._before(loc, j)

    def _write(self, loc, j):
        """Result if instruction j defines `loc`, else None."""
        ins = self.ins[j]
        if loc.startswith("stk:"):
            slot = loc[4:]
            if ins.ops.startswith(f"qword ptr [{slot}], ") and ins.mn == "mov":
                s = ins.operands()[1]
                if s in GPR and GPR[s] == s:
                    return self._before(s, j)
                return "UNK:spill of " + s
            if ins.ops.startswith(f"qword ptr [{slot}]") and ins.mn not in NO_WRITE:
                return "UNK:" + ins.text
            return None
        w = writes(ins, loc)
        if w == "call":
            if loc == "rax":
                tgt = call_target_name(ins)
                return (
                    CONST
                    if tgt == GET_CONSTANTS_NAME
                    else "UNK:call " + (tgt or ins.ops)
                )
            if loc in CALLER_SAVED:
                return "UNK:clobbered by call " + (call_target_name(ins) or ins.ops)
            return None
        if not w:
            return None
        ops = ins.operands()
        if ins.mn == "lea" and re.search(r"~\S*\.constants\b", ins.cm):
            return ADDR_CONST
        if ins.mn != "mov" or len(ops) != 2:
            return "UNK:" + ins.text
        src = ops[1]
        if src in GPR and GPR[src] == src:
            return self._before(src, j)
        if re.search(
            r"~(?:static "
            r")?\S*(?:\.constants\b|AIConstants\.(?:Easy|Medium|Hard)AIConstantsRef)",
            ins.cm,
        ):
            return CONST
        m = MEM_PLAIN_RE.match(src)
        if m:
            inner = self._before(m.group(1), j)
            if inner == ADDR_CONST:
                return CONST
            return ("KLASS", inner)
        m = MEM_STACK_RE.match(src)
        if m:
            return self._before("stk:" + m.group(1), j)
        m = re.match(r"^qword ptr \[(r\w+) \+ (0x[0-9a-f]+)\]$", src)
        if m:
            base, off = m.group(1), int(m.group(2), 16)
            if (self.declaring, off) not in CONSTANTS_FIELDS:
                return f"UNK:field +{off:#x} of {base}"
            inner = self._before(base, j)
            if inner == "UNK:entry rdi":
                return CONST
            return f"UNK:field +{off:#x} of " + (
                inner if isinstance(inner, str) else "klass"
            )
        return "UNK:" + ins.text


def excluded_receiver(r):
    """Why the receiver of a vtable read cannot be an AIConstantsRef, or ''.

    The type listings (checked by `constants_sources`) show that an
    AIConstantsRef value only comes from WormAIProfile::get_Constants, the
    static fields of worm.canis.ai.AIConstants, the parameter of
    AIConstants::SetInstance and the closure field
    WormImperiumPlayable/<>c__DisplayClass2_0.constants (+0x10). So a receiver
    that is a method argument, the return value of any other call, or a field
    at another offset is some other type.
    """
    if isinstance(r, str) and (
        r.startswith("UNK:field +") or r.startswith("UNK:merge of UNK:field +")
    ):
        # the base register holds an object (or a static-field block), not a klass:
        # `[base + off]` is a field / static-field read, not a vtable slot
        return "base is a field value, not a klass pointer (" + r[4:60] + ")"
    if not (isinstance(r, tuple) and r[0] == "KLASS" and isinstance(r[1], str)):
        return ""
    inner = r[1]
    if inner.startswith("UNK:entry r"):
        return "receiver is an argument/this (" + inner[4:] + ")"
    if inner.startswith("UNK:call ") and GET_CONSTANTS_NAME not in inner:
        return "receiver returned by " + inner[9:]
    m = re.match(r"UNK:field \+(0x[0-9a-f]+) of", inner)
    if m and int(m.group(1), 16) != 0x10:
        return f"receiver loaded from field +{m.group(1)}"
    return ""


def constants_sources(dump):
    """Every line of the .cs listings that mentions an AI*ConstantsRef type,
    other than the three classes' own getters/ctors and type headers."""
    out = []
    for fn in sorted(os.listdir(dump)):
        if not fn.endswith(".cs"):
            continue
        cur = None
        with open(os.path.join(dump, fn), encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"^(?:\w+ )*type (\S+) :", line)
                if m:
                    cur = m.group(1)
                if (
                    "ConstantsRef" not in line
                    or line.startswith("type ")
                    or re.match(r"^(?:\w+ )+type ", line)
                ):
                    continue
                if cur in {NS + c for c in CLASSES} and (
                    "get_" in line or ".ctor" in line
                ):
                    continue
                if not re.search(
                    r"\bworm\.canis\.ai\.AI(?:Medium|Easy)?ConstantsRef\b", line
                ):
                    continue
                out.append(f"{fn}: {cur}: {line.strip()}")
    return out


EXPECTED_SOURCES = {
    "worm.canis.entities.WormImperiumPlayable/<>c__DisplayClass2_0": (
        "field +16 worm.canis.ai.AIConstantsRef constants"
    ),
    "worm.canis.ai.WormAIProfile": "worm.canis.ai.AIConstantsRef get_Constants()",
    "worm.canis.ai.AIConstants": "AIConstantsRef",
}


def is_klass_of_const(r):
    return isinstance(r, tuple) and r[0] == "KLASS" and r[1] == CONST


# ---------------------------------------------------------------- reader scan


def scan_readers(asm_dirs, slot_of_name, name_of_slot, call_offsets):
    """Return (sites, raw_other, raw_unresolved, vslot_mismatch, stats)."""
    lo = min(call_offsets) - 8
    hi = max(call_offsets) + 8
    sites = defaultdict(list)  # slot -> [site dict]
    raw_other = defaultdict(list)  # slot -> [site] annotated as other type
    raw_unres = defaultdict(list)  # slot -> [site] unresolved
    vslot_mismatch = []
    stats = defaultdict(int)
    source_methods = set()
    const_classes = {NS + c for c in CLASSES}
    for d in asm_dirs:
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".asm"):
                continue
            path = os.path.join(d, fn)
            for name, maddr, raw in iter_methods(path):
                blob = "".join(raw)
                if (
                    (
                        "0x48fca90" in blob
                        or re.search(r"~\S*\.constants\b", blob)
                        or re.search(
                            r"~static AIConstants\.(?:Easy|Medium|Hard)AIConstantsRef",
                            blob,
                        )
                    )
                    and not name.startswith(NS + "AIConstants::")
                    and name != GET_CONSTANTS_NAME
                ):
                    source_methods.add(f"{name} @ {maddr:#x}")
                # fast pre-filter: any access/immediate in the getter offset range?
                if "qword ptr [r" not in blob:
                    continue
                cand = False
                for m in re.finditer(r"(?:\+ |, )(0x[0-9a-f]{3,4})\b", blob):
                    v = int(m.group(1), 16)
                    if lo <= v <= hi:
                        cand = True
                        break
                if not cand:
                    continue
                stats["methods_scanned"] += 1
                meth = Method(name, maddr, raw)
                if any(
                    t in name
                    for t in (
                        ".AIConstantsRef::",
                        ".AIMediumConstantsRef::",
                        ".AIEasyConstantsRef::",
                    )
                ):
                    continue
                regreg_idx = [
                    k for k, i in enumerate(meth.ins) if MEM_REGREG_RE.search(i.ops)
                ]
                for k, ins in enumerate(meth.ins):
                    # --- direct displacement accesses
                    for m in MEM_DISP_RE.finditer(ins.ops):
                        base, off = m.group(1), int(m.group(2), 16)
                        if not (lo <= off <= hi):
                            continue
                        rel = off - VTABLE_OFFSET
                        if rel % 16 == 0:
                            slot, is_mi = rel // 16, False
                        elif rel % 16 == 8:
                            slot, is_mi = (rel - 8) // 16, True
                        else:
                            continue
                        if slot not in name_of_slot:
                            continue
                        if is_mi:
                            continue  # MethodInfo loads corroborate; count call offsets
                        # a vtable read: `call/jmp [K+off]` or `mov reg, [K+off]`
                        if ins.mn not in ("call", "jmp"):
                            ops = ins.operands()
                            if not (
                                ins.mn == "mov"
                                and len(ops) == 2
                                and ops[0] in GPR
                                and ops[1] == m.group(0)
                            ):
                                continue
                        vs = VSLOT_RE.search(ins.cm)
                        site = {
                            "method": f"{name} @ {maddr:#x}",
                            "site": f"{ins.addr:#x}",
                            "asm": ins.text.strip(),
                        }
                        annotated_const = bool(vs and vs.group(3) in const_classes)
                        if (vs and not annotated_const) or (not vs and "~" in ins.cm):
                            raw_other[slot].append(
                                {**site, "annotation": vs.group(0) if vs else ins.cm}
                            )
                            continue
                        if annotated_const:
                            n = vs.group(4)
                            if (
                                int(vs.group(1)) != slot
                                or slot_of_name.get(n.removeprefix("get_")) != slot
                            ):
                                vslot_mismatch.append(
                                    {
                                        **site,
                                        "annotation": vs.group(0),
                                        "computed_slot": slot,
                                    }
                                )
                        r = meth.resolve(base, k)
                        tracked = is_klass_of_const(r)
                        if annotated_const or tracked:
                            how = (
                                "annotated+tracked"
                                if (annotated_const and tracked)
                                else ("annotated" if annotated_const else "tracked")
                            )
                            if annotated_const and not tracked:
                                site["tracker"] = (
                                    r if isinstance(r, str) else "klass of " + str(r[1])
                                )
                            sites[slot].append({**site, "how": how})
                        else:
                            why = excluded_receiver(r)
                            if why:
                                raw_other[slot].append({**site, "annotation": why})
                            else:
                                raw_unres[slot].append(
                                    {
                                        **site,
                                        "receiver": r
                                        if isinstance(r, str)
                                        else "klass of " + str(r[1]),
                                    }
                                )
                    # --- merged pairs
                    if regreg_idx and ins.mn == "mov" and k + 1 < len(meth.ins):
                        m1 = MOV_IMM32_RE.match(ins.ops)
                        nx = meth.ins[k + 1]
                        m2 = MOV_IMM32_RE.match(nx.ops) if nx.mn == "mov" else None
                        if m1 and m2:
                            a, b = int(m1.group(2), 0), int(m2.group(2), 0)
                            if abs(a - b) == 8:
                                call_off = a if (a - VTABLE_OFFSET) % 16 == 0 else b
                                call_reg = GPR[
                                    m1.group(1) if call_off == a else m2.group(1)
                                ]
                                slot = (call_off - VTABLE_OFFSET) // 16
                                if (
                                    call_off - VTABLE_OFFSET
                                ) % 16 == 0 and slot in name_of_slot:
                                    merge = next(
                                        (
                                            x
                                            for x in regreg_idx
                                            if x > k
                                            and GPR.get(
                                                MEM_REGREG_RE.search(
                                                    meth.ins[x].ops
                                                ).group(2)
                                            )
                                            == call_reg
                                        ),
                                        None,
                                    )
                                    site = {
                                        "method": f"{name} @ {maddr:#x}",
                                        "site": f"{ins.addr:#x}",
                                        "asm": ins.text.strip()
                                        + " ; "
                                        + nx.text.strip(),
                                    }
                                    ok, why = merged_receiver_ok(
                                        meth, k, merge, call_reg
                                    )
                                    if merge is not None:
                                        site["merge_site"] = (
                                            f"{meth.ins[merge].addr:#x}: "
                                            f"{meth.ins[merge].mn} "
                                            f"{meth.ins[merge].ops}"
                                        )
                                    if ok:
                                        sites[slot].append({**site, "how": "merged"})
                                    else:
                                        raw_unres[slot].append(
                                            {**site, "receiver": why}
                                        )
    stats["source_methods"] = sorted(source_methods)
    return sites, raw_other, raw_unres, vslot_mismatch, stats


def merged_receiver_ok(meth, k, merge, call_reg):
    if merge is None:
        return False, "no [K + reg] access after the pair"
    acc = meth.ins[merge]
    m = MEM_REGREG_RE.search(acc.ops)
    kreg, ireg = m.group(1), m.group(2)
    # the index register must be the pair's call-offset register, or a register
    # loaded from [K + call_reg] that is then called/jumped to (tail form)
    if GPR.get(ireg) != call_reg:
        return (
            False,
            f"merge {acc.ops}: index {ireg} is not the call-offset register {call_reg}",
        )
    # find the klass load `mov K, [X]` before the merge site
    for j in range(merge - 1, k, -1):
        ins = meth.ins[j]
        w = writes(ins, kreg)
        if w == "call":
            if kreg in CALLER_SAVED:
                return False, "klass register clobbered"
            continue
        if w:
            ops = ins.operands()
            mm = (
                MEM_PLAIN_RE.match(ops[1])
                if ins.mn == "mov" and len(ops) == 2
                else None
            )
            if not mm:
                return False, "klass register from " + ins.text
            x = mm.group(1)
            r = meth.resolve(x, k)  # object register's value at the pair
            if r == CONST:
                return True, ""
            return False, f"object {x} at pair: {r}"
    return False, "no klass load between pair and merge site"


# ---------------------------------------------------------------- level map


def parse_level_map(asm_path):
    field_class = {}
    level_field = {}
    last_typeinfo = None
    r14_class = None
    r14_field = None
    esi = None
    evidence = []
    for name, _addr, raw in iter_methods(asm_path):
        if not name.endswith("::.cctor"):
            continue
        for i in (parse_ins(x) for x in raw):
            if not i:
                continue
            m = re.search(r"TypeInfo:worm\.canis\.ai\.(\w+)$", i.cm)
            if m and i.mn == "lea":
                last_typeinfo = m.group(1)
            if i.mn == "call" and "rt:object_new" in i.cm:
                r14_class = last_typeinfo
            m = re.search(r"~static AIConstants\.(\w+ConstantsRef)$", i.cm)
            if (
                m
                and i.mn == "mov"
                and i.ops.startswith("qword ptr")
                and i.ops.endswith(", r14")
            ):
                field_class[m.group(1)] = r14_class
            if m and i.mn == "mov" and i.ops.startswith("r14, "):
                r14_field = m.group(1)
            if i.mn == "xor" and i.ops == "esi, esi":
                esi = 0
            elif i.mn == "mov" and i.ops.startswith("esi, "):
                try:
                    esi = int(i.ops.split(", ")[1], 0)
                except ValueError:
                    esi = None
            if (
                i.mn in ("call", "jmp")
                and "ConcurrentDictionary`2<int,object>::set_Item" in i.cm
            ):
                level_field[esi] = r14_field
                evidence.append(
                    f"{i.addr:#x}: set_Item(key={esi}, value=static {r14_field})"
                )
    level_map = {}
    for lvl, fld in sorted(level_field.items()):
        cls = field_class.get(fld)
        level_map[str(lvl)] = CLASSES.get(cls, f"?{cls}")
    return level_map, field_class, evidence


# ------------------------------------------ cross-check with 11-difficulty-tables.md


def parse_reference_md(path):
    """Groups, per-slot values and reader addresses from 11-difficulty-tables.md."""
    groups = []  # (title, [slots])
    ref = {}  # slot -> {hard, medium, easy, differs, readers:set, truncated}
    cur = None
    in_constants = False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("## "):
                in_constants = line.strip() == "## Constants used"
                continue
            if not in_constants:
                continue
            if line.startswith("### "):
                cur = (line[4:].strip(), [])
                groups.append(cur)
                continue
            if (
                not line.startswith("| ")
                or cur is None
                or line.startswith("| Getter")
                or line.startswith("|---")
            ):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 4:
                continue
            m = re.search(r"\((\d+)(?:-(\d+))?(?:, 0x[0-9a-f]+)?\)", cells[0])
            if not m:
                continue
            s0 = int(m.group(1))
            s1 = int(m.group(2)) if m.group(2) else s0
            slots = list(range(s0, s1 + 1))
            cur[1].extend(slots)

            def vals(cell, n):
                if cell == "=":
                    return None
                parts = [p.strip() for p in cell.split("/")]
                if len(parts) != n:
                    return "PARSE?" + cell
                return [float(p) for p in parts]

            hard = vals(cells[1], len(slots))
            med = vals(cells[2], len(slots))
            easy = vals(cells[3], len(slots))
            readers = (
                set(int(a, 16) for a in re.findall(r"@ ?(0x[0-9a-f]+)", cells[4]))
                if len(cells) > 4
                else set()
            )
            truncated = (
                bool(re.search(r"\+\d+ more", cells[4])) if len(cells) > 4 else False
            )
            for n, s in enumerate(slots):
                ref[s] = {
                    "hard": hard[n] if isinstance(hard, list) else hard,
                    "medium": med[n] if isinstance(med, list) else None,
                    "easy": easy[n] if isinstance(easy, list) else None,
                    "differs": "(differs)" in cells[0],
                    "readers": readers,
                    "row_slots": slots,
                    "truncated": truncated,
                    "row_title": cells[0],
                }
    return groups, ref


# ---------------------------------------------------------------- binary check


def binary_check(manifest, getters):
    """Decode every getter body straight from GameAssembly.dylib (independent of
    the dump's text) and compare with the extracted values."""
    import hashlib
    import struct

    path = os.path.join(
        manifest.get("contents", ""), "Frameworks", "GameAssembly.dylib"
    )
    res = {"path": path, "checked": 0, "mismatches": []}
    if not os.path.exists(path):
        res["skipped"] = "binary not found"
        return res
    with open(path, "rb") as f:
        data = f.read()
    want = manifest.get("sha256", {}).get("GameAssembly.dylib")
    res["sha256_matches_manifest"] = hashlib.sha256(data).hexdigest() == want
    if not res["sha256_matches_manifest"]:
        res["skipped"] = (
            "sha256 differs from dump/manifest.json (another build installed)"
        )
        return res
    if (
        struct.unpack_from(">I", data, 0)[0] == 0xCAFEBABE
    ):  # universal binary: take x86_64
        for k in range(struct.unpack_from(">I", data, 4)[0]):
            cputype, _, off, size, _ = struct.unpack_from(">5I", data, 8 + 20 * k)
            if cputype == 0x01000007:
                data = data[off : off + size]
                break
    segs = []
    ncmds, off = struct.unpack_from("<I", data, 16)[0], 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", data, off)
        if cmd == 0x19:  # LC_SEGMENT_64
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from(
                "<4Q", data, off + 24
            )
            segs.append((vmaddr, filesize, fileoff))
        off += size

    def read(addr, n):
        for vm, fs, fo in segs:
            if vm <= addr and addr + n <= vm + fs:
                return data[fo + addr - vm : fo + addr - vm + n]
        raise ValueError(f"{addr:#x} not file-backed")

    def decode(addr):
        b = read(addr, 16)
        if b[:4] != bytes.fromhex("554889e5"):
            return None, "no push rbp; mov rbp, rsp"
        b = b[4:]
        if b[:4] == bytes.fromhex("f20f1005"):
            disp = struct.unpack_from("<i", b, 4)[0]
            lit = addr + 4 + 8 + disp
            tail = b[8:10]
            val = struct.unpack("<d", read(lit, 8))[0]
        elif b[:3] == bytes.fromhex("0f57c0"):
            tail, val = b[3:5], 0.0
        elif b[:1] == b"\xb8":
            tail, val = b[5:7], struct.unpack_from("<i", b, 1)[0]
        elif b[:2] == bytes.fromhex("31c0"):
            tail, val = b[2:4], 0
        else:
            return None, "undecoded " + b.hex()
        if tail != bytes.fromhex("5dc3"):
            return None, "no pop rbp; ret after the literal"
        return val, ""

    for g in getters:
        for level, cls in (("hard", None), ("medium", "Medium"), ("easy", "Easy")):
            if cls is None:
                addr = int(g["address"], 16)
            elif cls in g["overridden_by"]:
                addr = int(g["override_address"][cls], 16)
            else:
                continue  # inherited: same bytes as hard
            val, err = decode(addr)
            res["checked"] += 1
            if (
                err
                or val != g[level]
                or (isinstance(val, int) != isinstance(g[level], int))
            ):
                res["mismatches"].append(
                    f"{g['name']} {level} @ {addr:#x}: binary {val!r} {err}, "
                    f"extracted {g[level]!r}"
                )
    return res


# ---------------------------------------------------------------- main


def short(method):
    """'worm.canis.ai.WormAIProfile::GetX @ 0x..' -> 'WormAIProfile::GetX @0x..'."""
    m = re.match(r"^(.*?)::(.*) @ (0x[0-9a-f]+)$", method)
    if not m:
        return method
    typ = m.group(1)
    outer, _, nested = typ.partition("/")
    outer = outer.rsplit(".", 1)[-1]
    typ = outer + ("/" + nested if nested else "")
    return f"{typ}::{m.group(2)} @{m.group(3)}"


def fmt(v):
    if v is None:
        return "—"
    if isinstance(v, int):
        return str(v)
    return repr(v)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dump", default=DEFAULT_DUMP)
    ap.add_argument("--out", default=None, help="default: <dump>/../analysis/ai/spec")
    ap.add_argument(
        "--check",
        default=None,
        help="default: <dump>/../analysis/ai/11-difficulty-tables.md",
    )
    ap.add_argument(
        "--assemblies",
        default="worm-canis.dll",
        help="comma list of dump/asm/<assembly> to scan",
    )
    a = ap.parse_args(argv)
    dump = a.dump
    out = a.out or os.path.join(
        os.path.dirname(dump.rstrip("/")), "analysis", "ai", "spec"
    )
    check = a.check or os.path.join(
        os.path.dirname(dump.rstrip("/")), "analysis", "ai", "11-difficulty-tables.md"
    )
    asm_dir = os.path.join(dump, "asm", "worm-canis.dll")
    problems = []

    with open(os.path.join(dump, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    with open(
        os.path.join(dump, "worm-canis.dll.cs"), encoding="utf-8", errors="replace"
    ) as f:
        cs_text = f.read()

    tables = {}
    for cls in CLASSES:
        path = os.path.join(asm_dir, f"{NS}{cls}.asm")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        listing = parse_type_listing(text, NS + cls)
        cs_listing = parse_type_listing(cs_text, NS + cls)
        if [(x["addr"], x["ret"], x["name"]) for x in listing] != [
            (x["addr"], x["ret"], x["name"]) for x in cs_listing
        ]:
            problems.append(
                f"{cls}: .asm header listing differs from worm-canis.dll.cs listing"
            )
        bodies = {}
        for name, addr, raw in iter_methods(path):
            bodies[name.rsplit("::", 1)[1]] = (addr, raw)
        tables[cls] = (listing, bodies)

    # ---- base getters and slots
    base_listing, base_bodies = tables["AIConstantsRef"]
    getters = []
    slot_of_name = {}
    name_of_slot = {}
    vidx = 0
    prev_addr = None
    nonliteral = []
    for m in base_listing:
        if not m["virtual"]:
            continue
        if not m["name"].startswith("get_"):
            problems.append(f"AIConstantsRef: virtual non-getter {m['name']}")
            continue
        slot = vidx + SYSTEM_OBJECT_SLOTS
        vidx += 1
        if prev_addr is not None and m["addr"] != prev_addr + 16:
            problems.append(
                f"AIConstantsRef: {m['name']} at {m['addr']:#x} is not 16 bytes after "
                "the previous getter"
            )
        prev_addr = m["addr"]
        nm = m["name"][4:]
        addr, raw = base_bodies[m["name"]]
        if addr != m["addr"]:
            problems.append(
                f"{nm}: listing address {m['addr']:#x} != block address {addr:#x}"
            )
        kind, val, lit, asm = parse_getter_body(raw)
        g = {
            "name": nm,
            "slot": slot,
            "call_offset": hex(VTABLE_OFFSET + 16 * slot),
            "type": m["ret"],
            "address": hex(m["addr"]),
            "hard": val,
            "medium": val,
            "easy": val,
            "overridden_by": [],
            "literal_address": {"hard": hex(lit) if lit else None},
        }
        if kind == "nonliteral" or (kind == "int") != (m["ret"] == "int"):
            nonliteral.append(
                {"class": "AIConstantsRef", "name": nm, "type": m["ret"], "asm": asm}
            )
            g["hard"] = g["medium"] = g["easy"] = None
        getters.append(g)
        slot_of_name[nm] = slot
        name_of_slot[slot] = nm

    # ---- overrides
    for cls, level in (
        ("AIMediumConstantsRef", "medium"),
        ("AIEasyConstantsRef", "easy"),
    ):
        listing, bodies = tables[cls]
        for m in listing:
            if not m["virtual"]:
                continue
            nm = m["name"][4:]
            if nm not in slot_of_name:
                problems.append(f"{cls}: {m['name']} has no base getter")
                continue
            g = getters[slot_of_name[nm] - SYSTEM_OBJECT_SLOTS]
            if g["type"] != m["ret"]:
                problems.append(
                    f"{cls}: {nm} returns {m['ret']}, base returns {g['type']}"
                )
            addr, raw = bodies[m["name"]]
            kind, val, lit, asm = parse_getter_body(raw)
            if kind == "nonliteral":
                nonliteral.append(
                    {"class": cls, "name": nm, "type": m["ret"], "asm": asm}
                )
                val = None
            g[level] = val
            g["overridden_by"].append(CLASSES[cls])
            g.setdefault("override_address", {})[CLASSES[cls]] = hex(addr)
            g["literal_address"][level] = hex(lit) if lit else None

    med_set = {g["name"] for g in getters if "Medium" in g["overridden_by"]}
    easy_set = {g["name"] for g in getters if "Easy" in g["overridden_by"]}
    override_check = {
        "medium_count": len(med_set),
        "easy_count": len(easy_set),
        "same_set": med_set == easy_set,
        "only_medium": sorted(med_set - easy_set),
        "only_easy": sorted(easy_set - med_set),
    }
    if not override_check["same_set"]:
        problems.append("Medium and Easy override different getters")

    # ---- where an AIConstantsRef value can come from (justifies excluded_receiver)
    sources = constants_sources(dump)
    for line in sources:
        typ = line.split(": ", 2)[1]
        exp = EXPECTED_SOURCES.get(typ)
        if exp is None or exp not in line:
            problems.append(f"unexpected AIConstantsRef source in the listings: {line}")

    # ---- level map
    level_map, field_class, level_evidence = parse_level_map(
        os.path.join(asm_dir, NS + "AIConstants.asm")
    )

    # ---- readers
    asm_dirs = [
        os.path.join(dump, "asm", x.strip())
        for x in a.assemblies.split(",")
        if x.strip()
    ]
    call_offsets = [VTABLE_OFFSET + 16 * s for s in name_of_slot]
    sites, raw_other, raw_unres, vslot_mismatch, stats = scan_readers(
        asm_dirs, slot_of_name, name_of_slot, call_offsets
    )
    source_methods = stats.pop("source_methods")
    reader_methods = {x["method"] for v in sites.values() for x in v}
    sources_without_reader = sorted(set(source_methods) - reader_methods)
    for v in vslot_mismatch:
        problems.append(f"vslot annotation disagrees with computed slot: {v}")
    for g in getters:
        s = sites.get(g["slot"], [])
        g["readers"] = sorted(
            {x["method"] for x in s}, key=lambda t: (t.split(" @ ")[0], t)
        )
        g["reader_sites"] = sorted(s, key=lambda x: (x["method"], x["site"]))
        g["other_type_hits"] = len(raw_other.get(g["slot"], []))
        g["unresolved_hits"] = raw_unres.get(g["slot"], [])

    # ---- cross-check with 11-difficulty-tables.md
    groups, ref = ([], {})
    xcheck = {
        "value_mismatch": [],
        "differs_mismatch": [],
        "missing_slots": [],
        "reader_missing_here": [],
        "reader_extra_here": [],
    }
    if os.path.exists(check):
        groups, ref = parse_reference_md(check)
        for g in getters:
            r = ref.get(g["slot"])
            if r is None:
                xcheck["missing_slots"].append(g["slot"])
                continue
            exp_h = r["hard"]
            exp_m = r["medium"] if r["medium"] is not None else exp_h
            exp_e = r["easy"] if r["easy"] is not None else exp_h
            for lvl, exp in (("hard", exp_h), ("medium", exp_m), ("easy", exp_e)):
                if not isinstance(exp, float) or g[lvl] is None or float(g[lvl]) != exp:
                    xcheck["value_mismatch"].append(
                        f"{g['name']} ({g['slot']}) {lvl}: here {g[lvl]!r}, 11 says "
                        f"{exp!r}"
                    )
            if r["differs"] != bool(g["overridden_by"]):
                xcheck["differs_mismatch"].append(g["name"])
        # readers compared per table row (rows merge Early/Mid/Late triples)
        seen_rows = set()
        for g in getters:
            r = ref.get(g["slot"])
            if r is None or tuple(r["row_slots"]) in seen_rows:
                continue
            seen_rows.add(tuple(r["row_slots"]))
            mine = set()
            for s in r["row_slots"]:
                for x in sites.get(s, []):
                    mine.add(int(x["method"].rsplit("@ ", 1)[1], 16))
            for addr in sorted(r["readers"] - mine):
                xcheck["reader_missing_here"].append(
                    f"{r['row_title']}: 11 lists {addr:#x}"
                )
            if not r["truncated"]:
                for addr in sorted(mine - r["readers"]):
                    xcheck["reader_extra_here"].append(
                        f"{r['row_title']}: also read by {addr:#x}"
                    )

    # ---- independent check against the binary itself
    bincheck = binary_check(manifest, getters)
    for mm in bincheck["mismatches"]:
        problems.append("binary: " + mm)

    # ---- write json
    os.makedirs(out, exist_ok=True)
    doc = {
        "build_guid": manifest.get("build_guid"),
        "app_version": manifest.get("app_version"),
        "source": {
            "hard": f"{NS}AIConstantsRef",
            "medium": f"{NS}AIMediumConstantsRef",
            "easy": f"{NS}AIEasyConstantsRef",
            "scanned_assemblies": [os.path.basename(x) for x in asm_dirs],
        },
        "slot_rule": (
            "slot = listing index + 4; call [klass + 0x138 + 16*slot]; MethodInfo at +8"
        ),
        "level_map": level_map,
        "level_map_evidence": {
            "static_fields": field_class,
            "cctor": f"{NS}AIConstants::.cctor",
            "set_item_calls": level_evidence,
            "lookup": (
                "worm.canis.ai.WormAIProfile::get_Constants @ 0x48fca90 reads "
                "loadedConstants[AILevel]"
            ),
        },
        "override_check": override_check,
        "binary_check": bincheck,
        "constants_sources": sources,
        "nonliteral": nonliteral,
        "problems": problems,
        "cross_check_11": xcheck,
        "scan_stats": dict(stats),
        "methods_obtaining_constants": len(source_methods),
        "methods_obtaining_constants_list": source_methods,
        "methods_obtaining_constants_without_reader": sources_without_reader,
        "getters": getters,
    }
    with open(os.path.join(out, "constants.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")

    write_md(
        os.path.join(out, "constants.md"),
        doc,
        getters,
        groups,
        sites,
        raw_unres,
        raw_other,
    )

    print(
        f"getters: {len(getters)}; overridden by Medium {len(med_set)}, Easy "
        f"{len(easy_set)}, same set: {override_check['same_set']}"
    )
    print(f"level_map: {level_map}")
    if bincheck.get("skipped"):
        print("binary check: " + bincheck["skipped"])
    else:
        n_bad = len(bincheck["mismatches"])
        print(f"binary check: {bincheck['checked']} bodies, {n_bad} mismatches")
    print(f"nonliteral: {len(nonliteral)}; problems: {len(problems)}")
    print(f"never read: {sum(1 for g in getters if not g['readers'])}")
    print("cross-check 11: " + ", ".join(f"{k}={len(v)}" for k, v in xcheck.items()))
    for p in problems:
        print("PROBLEM:", p)
    print("wrote", os.path.join(out, "constants.json"), "and constants.md")
    return 0


def write_md(path, doc, getters, groups, sites, raw_unres, raw_other):
    by_slot = {g["slot"]: g for g in getters}
    L = []
    w = L.append
    w("# AI constant tables (mechanical extraction)")
    w("")
    w(
        f"Build `{doc['build_guid']}` (Steam *Dune: Imperium* {doc['app_version']}). "
        "Generated by "
        "`scripts/dwgr/app_ai_constants.py` (standard library only) from the local "
        "dump; do not edit by hand — "
        "rerun the script. The same data, with every reader site, is in "
        "`constants.json` next to this file."
    )
    w("")
    w("## How to read this")
    w("")
    w(
        "- **Slot** = vtable slot of the getter in `worm.canis.ai.AIConstantsRef` "
        "(listing index + 4). A call site "
        "reaches it as `call [klass + 0x138 + 16*slot]` and loads its MethodInfo from "
        "`+8`, so the slot cannot drift "
        "between Hard and the two subclasses: Medium and Easy override getters in "
        "place."
    )
    w(
        "- **Hard / Medium / Easy** are the literal each getter returns on that "
        "level. A Medium or Easy cell in "
        "*italics* is inherited from Hard (the getter is not overridden); a **bold** "
        "cell is an override."
    )
    w(
        "- **Levels** (`AIConstants::.cctor` fills `loadedConstants`; "
        "`WormAIProfile::get_Constants @ 0x48fca90` "
        "indexes it by the seat's `AILevel`): "
        + ", ".join(f"{k} → {v}" for k, v in doc["level_map"].items())
        + "."
    )
    w(
        "- **Readers** = methods that call the getter on an AIConstantsRef object "
        "(annotated `~vslot`, "
        "tracked unannotated access, or merged `mov ecx/edx, off` + `call [r8+rcx]` "
        "dispatch). `—` = never read "
        "in the scanned assemblies ("
        + ", ".join(doc["source"]["scanned_assemblies"])
        + ")."
    )
    w(
        "- Detection tags after a reader: `m` = only reached through a merged "
        "indirect call, `t` = only through an "
        "unannotated access found by register tracking (the dump's `~` annotation "
        "missed it)."
    )
    w("")
    w("## Checks")
    w("")
    oc = doc["override_check"]
    w(
        f"- Getters: {len(getters)} (types: "
        + ", ".join(
            f"{t} {sum(1 for g in getters if g['type'] == t)}"
            for t in sorted({g["type"] for g in getters})
        )
        + ")."
    )
    w(
        f"- Overrides: Medium {oc['medium_count']}, Easy {oc['easy_count']}, same "
        f"set: **{oc['same_set']}**"
        + (
            f" (only Medium: {oc['only_medium']}, only Easy: {oc['only_easy']})"
            if not oc["same_set"]
            else ""
        )
        + "."
    )
    bc = doc["binary_check"]
    if bc.get("skipped"):
        w(f"- Binary check: skipped ({bc['skipped']}).")
    else:
        w(
            f"- Binary check: {bc['checked']} getter bodies (437 Hard + the "
            "Medium/Easy overrides) decoded straight "
            "from `GameAssembly.dylib` (sha256 = dump manifest; prologue, one literal "
            "instruction, `pop rbp; ret`; "
            f"the double read from the rip-relative literal): {len(bc['mismatches'])} "
            "mismatches with the values "
            "parsed from the dump text."
        )
    n_ann = sum(
        1
        for g in getters
        for x in g["reader_sites"]
        if x["how"].startswith("annotated")
    )
    n_mis = sum(1 for p in doc["problems"] if p.startswith("vslot annotation"))
    w(
        f"- Slot rule: each of the {n_ann} reader sites the dump annotates as `~vslot "
        "N ...ConstantsRef::get_X` has "
        "N = listing index + 4 of `get_X` and accesses `[klass + 0x138 + 16*N]` "
        f"({n_mis} disagreements)."
    )
    w(
        "- Checked once outside this script (2026-10-05, needs capstone/il2meta, so "
        "not part of this stdlib run): "
        "the IL2CPP metadata vtables of type definitions 1145/1146/1147 "
        "(AIConstantsRef / Medium / Easy) have 441 "
        "slots each and name, for every one of the 437 slots, the getter this table "
        "puts there (Medium and Easy "
        "point to their own method in exactly the 29 overridden slots); 22 getters x "
        "3 levels were also decoded with "
        "capstone from the binary; and the 283 Dune-owned shared generics "
        "(`generics.tsv` rows `worm.*`, one "
        "`il2dis.py` run) contain no `get_Constants` call, no `constants` field and "
        "no access the reader scan "
        "attributes to the constants object."
    )
    w(
        f"- Getter bodies that are not a single literal: {len(doc['nonliteral'])}"
        + (
            ""
            if not doc["nonliteral"]
            else " — listed under *Non-literal getters* below"
        )
        + "."
    )
    w(
        f"- Structural problems: {len(doc['problems'])}"
        + ("" if not doc["problems"] else ":")
    )
    for p in doc["problems"]:
        w(f"  - {p}")
    x = doc["cross_check_11"]
    w(
        "- Cross-check against `11-difficulty-tables.md` (values per slot, the "
        "`(differs)` marker, and the readers "
        "of each table row by method address): "
        + ", ".join(f"{k} {len(v)}" for k, v in x.items())
        + "."
    )
    for k, v in x.items():
        for item in v:
            w(f"  - {k}: {item}")
    never = [g for g in getters if not g["readers"]]
    w(
        f"- Never read: {len(never)} getters: "
        + ", ".join(f"`{g['name']}` ({g['slot']})" for g in never)
        + "."
    )
    w(
        "- Reader sites by detector: "
        + ", ".join(
            f"{h} {sum(1 for g in getters for s in g['reader_sites'] if s['how'] == h)}"
            for h in ("annotated+tracked", "annotated", "tracked", "merged")
        )
        + "."
    )
    w("")

    # groups
    grouped = set()
    group_list = list(groups) if groups else []
    rest = [s for s in sorted(by_slot) if not any(s in gs for _, gs in group_list)]
    if rest:
        group_list.append(("Not in any group of 11-difficulty-tables.md", rest))
    for title, slots in group_list:
        if not slots:
            continue
        w(f"## {title}")
        w("")
        w("| Getter | Slot | Type | Hard (2, 3) | Medium (1) | Easy (0) | Readers |")
        w("|---|---|---|---|---|---|---|")
        for s in slots:
            if s in grouped or s not in by_slot:
                continue
            grouped.add(s)
            g = by_slot[s]
            med = (
                f"**{fmt(g['medium'])}**"
                if "Medium" in g["overridden_by"]
                else f"*{fmt(g['medium'])}*"
            )
            easy = (
                f"**{fmt(g['easy'])}**"
                if "Easy" in g["overridden_by"]
                else f"*{fmt(g['easy'])}*"
            )
            rd = []
            for meth in g["readers"]:
                hows = {x["how"] for x in g["reader_sites"] if x["method"] == meth}
                tag = ""
                if hows == {"merged"}:
                    tag = " `m`"
                elif hows <= {"tracked", "merged"} and "tracked" in hows:
                    tag = " `t`"
                rd.append(short(meth) + tag)
            w(
                f"| {g['name']} | {s} | {g['type']} | {fmt(g['hard'])} | {med} | "
                f"{easy} | " + ("<br>".join(rd) if rd else "—") + " |"
            )
        w("")

    if doc["nonliteral"]:
        w("## Non-literal getters")
        w("")
        for n in doc["nonliteral"]:
            w(f"### {n['class']}::get_{n['name']} ({n['type']})")
            w("")
            w("```")
            for line in n["asm"]:
                w(line)
            w("```")
            w("")

    w("## Reader sites found only by tracking or merged dispatch")
    w("")
    w(
        "The dump's `~` annotations miss these; each was attributed to the constants "
        "object by the script."
    )
    w("")
    w("| Getter (slot) | Method | Site | How | Asm |")
    w("|---|---|---|---|---|")
    for g in getters:
        for x in g["reader_sites"]:
            if x["how"] in ("tracked", "merged"):
                w(
                    f"| {g['name']} ({g['slot']}) | {short(x['method'])} | "
                    f"{x['site']} | {x['how']} | "
                    f"`{x['asm'].split(': ', 1)[-1].split('    ;')[0]}`"
                    + (f" → `{x['merge_site']}`" if "merge_site" in x else "")
                    + " |"
                )
    w("")
    ann_only = [
        (g, x) for g in getters for x in g["reader_sites"] if x["how"] == "annotated"
    ]
    if ann_only:
        w("## Annotated sites the tracker could not confirm")
        w("")
        w(
            "Counted as readers (the annotation names an AIConstantsRef getter); the "
            "backward tracker stopped at:"
        )
        w("")
        for g, x in ann_only:
            w(
                f"- {g['name']} ({g['slot']}): {short(x['method'])} {x['site']} — "
                f"{x.get('tracker', '')}"
            )
        w("")
    w("## Unresolved accesses to getter offsets")
    w("")
    w(
        "Vtable reads at a getter's call offset (or merged-pair immediates) whose "
        "receiver is neither annotated as "
        "another type, nor provably another type (an argument, another call's result, "
        "a field other than the "
        "closure's `constants`), nor traced to the constants object. They are NOT "
        "counted as readers. Listed for "
        "every getter that has no confirmed reader, and for all getters when the "
        "access sits in a method that "
        "obtains the constants object (possible missed reader)."
    )
    w("")
    const_methods = set(doc["methods_obtaining_constants_list"])
    rows = 0
    for g in getters:
        for x in g["unresolved_hits"]:
            if g["readers"] and x["method"] not in const_methods:
                continue
            rows += 1
            w(
                f"- {g['name']} ({g['slot']}, off {g['call_offset']}): "
                f"{short(x['method'])} {x['site']} "
                f"`{x['asm'].split(': ', 1)[-1].split('    ;')[0]}` — receiver: "
                f"{x['receiver'][:160]}"
            )
    if not rows:
        w("(none)")
    w("")
    w("## Methods that obtain the constants object")
    w("")
    w(
        f"{doc['methods_obtaining_constants']} methods call "
        "`WormAIProfile::get_Constants`, touch a `constants` "
        "field or a static `AIConstants.*ConstantsRef` field (outside `AIConstants` "
        "itself). Those with no "
        "reader site found:"
    )
    w("")
    if doc["methods_obtaining_constants_without_reader"]:
        for mth in doc["methods_obtaining_constants_without_reader"]:
            w(f"- {short(mth)}")
    else:
        w("(none — every one of them reads at least one getter)")
    w("")
    tot_unres = sum(len(g["unresolved_hits"]) for g in getters)
    tot_other = sum(g["other_type_hits"] for g in getters)
    n_in_src = sum(
        1 for g in getters for x in g["unresolved_hits"] if x["method"] in const_methods
    )
    w(
        f"Totals over all getters: {tot_other} accesses at a getter offset that are "
        "annotated as another type or provably another type (not readers), "
        f"{tot_unres} unresolved, of which {n_in_src} sit in a method that obtains "
        "the constants object (the lists are in `constants.json`: `other_type_hits` "
        "is a count, `unresolved_hits` the sites)."
    )
    w("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())
