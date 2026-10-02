"""IL2CPP metadata + binary map for the macOS Dire Wolf Unity apps.

Parses global-metadata.dat (version 31: Unity 2022.3, Dire Wolf Game Room;
version 39: Unity 6000.3, the Steam Dune: Imperium app) and the stripped x86_64
GameAssembly.dylib (thin, or the x86_64 slice of a universal binary; classic
rebase info or chained fixups) and exposes, at import time:

  method_addr[methodIndex] -> code address, addr_methods[addr] -> [names]
  generic_addr[addr] -> [methodSpec indices]   (shared generic instances)
  fqn(typeIndex), mname(methodIndex), type_name(il2cppTypeIndex)
  methodspec_name(i), type_fields(typeIndex), field_default(fieldIndex)
  decode_usage(value)  -- lazily initialised metadata globals (TypeInfo, MethodRef,
                          Str, ...)

Addresses are virtual addresses. BIN is a VM image of the slice: each segment's
file bytes at its vmaddr, zero-filled bss, and chained-fixup pointers decoded to
plain addresses (imports read as 0). RAW is the slice as stored in the file; load
commands and __LINKEDIT data use its file offsets. The CodeRegistration /
MetadataRegistration / codeGenModules locations are found by searching, so the
module survives app updates as long as the metadata version and the struct
layouts stay the same.

Metadata v38+ stores some indices in 1, 2 or 4 bytes depending on the size of the
table they index. Rows are normalised to the v31 tuple layout (a dropped field
reads -1, a null narrow index reads -1), so callers index them the same way for
both apps.

App: $IL2CPP_APP, either the .app's Contents directory or an alias from APPS
(dwgr, dune). $DWGR_APP is still read. Default: dwgr.
"""

import os
import struct

STEAM = "~/Library/Application Support/Steam/steamapps/common/"
APPS = {
    "dwgr": STEAM + "DireWolfGameRoom/DireWolfGameRoom.app/Contents",
    "dune": STEAM + "Dune Imperium/DuneImperium.app/Contents",
}
APP = os.environ.get("IL2CPP_APP") or os.environ.get("DWGR_APP") or "dwgr"
C = os.path.expanduser(APPS.get(APP, APP))
DATA_DIR = os.path.join(C, "Resources", "Data")
MD = open(
    os.path.join(DATA_DIR, "il2cpp_data", "Metadata", "global-metadata.dat"), "rb"
).read()


def build_guid():
    try:
        for line in open(os.path.join(DATA_DIR, "boot.config")):
            if line.startswith("build-guid="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


# ---------------------------------------------------------------- metadata
SUPPORTED_VERSIONS = (31, 39)
_sanity, METADATA_VERSION = struct.unpack_from("<Ii", MD, 0)
if _sanity != 0xFAB11BAF or METADATA_VERSION not in SUPPORTED_VERSIONS:
    raise SystemExit(
        f"unsupported global-metadata (sanity {_sanity:#x}, "
        f"version {METADATA_VERSION}); "
        f"the struct layouts below are for versions {SUPPORTED_VERSIONS}"
    )
HN = [
    "stringLiteral",
    "stringLiteralData",
    "string",
    "events",
    "properties",
    "methods",
    "parameterDefaultValues",
    "fieldDefaultValues",
    "fieldAndParameterDefaultValueData",
    "fieldMarshaledSizes",
    "parameters",
    "fields",
    "genericParameters",
    "genericParameterConstraints",
    "genericContainers",
    "nestedTypes",
    "interfaces",
    "vtableMethods",
    "interfaceOffsets",
    "typeDefinitions",
    "images",
    "assemblies",
    "fieldRefs",
    "referencedAssemblies",
    "attributeData",
    "attributeDataRange",
    "unresolvedIndirectCallParameterTypes",
    "unresolvedIndirectCallParameterRanges",
    "windowsRuntimeTypeNames",
    "windowsRuntimeStrings",
    "exportedTypeDefinitions",
]
# v38+ headers hold {offset, size, count} per section; older ones {offset, size}.
_STRIDE = 3 if METADATA_VERSION >= 38 else 2
H = struct.unpack_from(f"<{_STRIDE * len(HN)}i", MD, 8)
SEC = {n: (H[_STRIDE * i], H[_STRIDE * i + 1]) for i, n in enumerate(HN)}
if SEC["stringLiteral"][0] != 8 + 4 * len(H):
    raise SystemExit(
        "global-metadata header does not end where the first section starts"
    )


def _width(count):
    return 1 if count <= 0xFF else 2 if count <= 0xFFFF else 4


# Index widths in bytes (v38: type definition, generic container and Il2CppType
# indices; v39 adds parameter indices). The Il2CppType table lives in the binary,
# so its width is read off an interfaceOffsets row ({TypeIndex, int32 offset}).
if METADATA_VERSION >= 38:
    _count = {n: H[3 * i + 2] for i, n in enumerate(HN)}
    W_TYPEDEF = _width(_count["typeDefinitions"])
    W_GCONTAINER = _width(_count["genericContainers"])
    W_TYPE = SEC["interfaceOffsets"][1] // _count["interfaceOffsets"] - 4
    W_PARAM = _width(_count["parameters"]) if METADATA_VERSION >= 39 else 4
else:
    W_TYPEDEF = W_GCONTAINER = W_TYPE = W_PARAM = 4
_IX = {1: "B", 2: "H", 4: "i"}
TD_IX, GC_IX, TY_IX, PA_IX = (
    _IX[W_TYPEDEF],
    _IX[W_GCONTAINER],
    _IX[W_TYPE],
    _IX[W_PARAM],
)


def mstr(idx):
    o = SEC["string"][0] + idx
    return MD[o : MD.index(b"\0", o)].decode("utf-8", "replace")


def table(name, fmt, nullable=()):
    """Rows of a metadata section. `nullable` lists (column, width) pairs of narrow
    indices whose all-ones value means null; those read -1."""
    off, size = SEC[name]
    sz = struct.calcsize(fmt)
    rows = list(struct.iter_unpack(fmt, MD[off : off + size - size % sz]))
    fix = [(c, (1 << (8 * w)) - 1) for c, w in nullable if w < 4]
    if not fix:
        return rows
    out = []
    for r in rows:
        if any(r[c] == null for c, null in fix):
            r = list(r)
            for c, null in fix:
                if r[c] == null:
                    r[c] = -1
            r = tuple(r)
        out.append(r)
    return out


# Il2CppTypeDefinition, v31 tuple layout (88 bytes there): 16 int32 (name,
# namespace, byval, declaring, parent, element, genericContainer, flags, fieldStart,
# methodStart, eventStart, propertyStart, nestedTypesStart, interfacesStart,
# vtableStart, interfaceOffsetsStart), 8 uint16 (method_count, property_count,
# field_count, event_count, nested_type_count, vtable_count, interfaces_count,
# interface_offsets_count), bitfield, token. v35 dropped `element` (it reads -1 here)
# and v38 narrowed the type and generic container indices.
if METADATA_VERSION >= 35:
    _td = table(
        "typeDefinitions",
        f"<2i3{TY_IX}{GC_IX}I8i8H2I",
        [(2, W_TYPE), (3, W_TYPE), (4, W_TYPE), (5, W_GCONTAINER)],
    )
    TD = [r[:5] + (-1,) + r[5:] for r in _td]
else:
    TD = table("typeDefinitions", "<16i8H2I")
TD_FIELD_START, TD_METHOD_START, TD_NESTED_START = 8, 9, 12
TD_METHOD_COUNT, TD_FIELD_COUNT, TD_NESTED_COUNT = 16, 18, 20
# Il2CppMethodDefinition: name, declaringType, returnType, returnParamToken,
# paramStart, genericContainer, token, then 4 uint16.
MT = table(
    "methods",
    f"<i{TD_IX}{TY_IX}I{PA_IX}{GC_IX}I4H",
    [(1, W_TYPEDEF), (2, W_TYPE), (4, W_PARAM), (5, W_GCONTAINER)],
)
# Il2CppImageDefinition: name, assembly, typeStart, typeCount, exportedTypeStart,
# exportedTypeCount, entryPoint, token, customAttributeStart, customAttributeCount.
IM = table("images", f"<2i{TD_IX}I{TD_IX}IiIiI", [(2, W_TYPEDEF), (4, W_TYPEDEF)])
FD = table("fields", f"<i{TY_IX}I", [(1, W_TYPE)])  # name, typeIndex, token
PARAMS = table("parameters", f"<iI{TY_IX}", [(2, W_TYPE)])  # name, token, typeIndex
FIELDREFS = table("fieldRefs", f"<{TY_IX}i", [(0, W_TYPE)])  # typeIndex, fieldIndex
NESTED = table("nestedTypes", "<i")
# Il2CppStringLiteral: {length, dataIndex}; v35 dropped the length, so it is the gap
# to the next literal's data.
if METADATA_VERSION >= 35:
    _sl = [r[0] for r in table("stringLiteral", "<i")]
    _ends = sorted(set(_sl)) + [SEC["stringLiteralData"][1]]
    _next = {d: _ends[k + 1] for k, d in enumerate(_ends[:-1])}
    SL = [(_next[d] - d, d) for d in _sl]
else:
    SL = table("stringLiteral", "<2I")  # length, dataIndex
# Il2CppGenericParameter: ownerIndex (generic container), nameIndex,
# constraintsStart, constraintsCount, num, flags.
GP_FMT = f"<{GC_IX}ihhHH"
GP_SIZE = struct.calcsize(GP_FMT)


def strlit(i):
    ln, di = SL[i]
    o = SEC["stringLiteralData"][0] + di
    return MD[o : o + ln].decode("utf-8", "replace")


parent = {}
for _ti, _t in enumerate(TD):
    for _k in range(_t[TD_NESTED_COUNT]):
        parent[NESTED[_t[TD_NESTED_START] + _k][0]] = _ti


def fqn(ti):
    t = TD[ti]
    if ti in parent:
        return fqn(parent[ti]) + "/" + mstr(t[0])
    ns = mstr(t[1])
    return (ns + "." if ns else "") + mstr(t[0])


def mname(mi):
    m = MT[mi]
    return fqn(m[1]) + "::" + mstr(m[0])


# ---------------------------------------------------------------- Mach-O
def _x86_64_slice(data):
    if struct.unpack_from(">I", data, 0)[0] != 0xCAFEBABE:
        return data
    for k in range(struct.unpack_from(">I", data, 4)[0]):
        cputype, _, off, size, _ = struct.unpack_from(">5I", data, 8 + 20 * k)
        if cputype == 0x01000007:  # CPU_TYPE_X86_64
            return data[off : off + size]
    raise SystemExit("GameAssembly.dylib has no x86_64 slice")


RAW = _x86_64_slice(
    open(os.path.join(C, "Frameworks", "GameAssembly.dylib"), "rb").read()
)


def load_commands():
    if struct.unpack_from("<I", RAW, 0)[0] != 0xFEEDFACF:
        raise SystemExit("GameAssembly.dylib is not a 64-bit Mach-O")
    ncmds, off, res = struct.unpack_from("<I", RAW, 16)[0], 32, []
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", RAW, off)
        res.append((cmd, off, size))
        off += size
    return res


SEGMENTS, SECTIONS = {}, {}
for _cmd, _off, _size in load_commands():
    if _cmd == 0x19:  # LC_SEGMENT_64
        segname = RAW[_off + 8 : _off + 24].split(b"\0")[0].decode()
        vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<4Q", RAW, _off + 24)
        nsects = struct.unpack_from("<I", RAW, _off + 64)[0]
        SEGMENTS[segname] = (vmaddr, vmsize, fileoff, filesize)
        for s in range(nsects):
            so = _off + 72 + 80 * s
            sect = RAW[so : so + 16].split(b"\0")[0].decode()
            addr, size = struct.unpack_from("<2Q", RAW, so + 32)
            SECTIONS[(segname, sect)] = (addr, size)
if SEGMENTS["__TEXT"][0] != 0:
    raise SystemExit("__TEXT vmaddr != 0; this reader expects an unslid dylib")
BIN = bytearray(max(v + vs for v, vs, _, _ in SEGMENTS.values()))
for _v, _vs, _fo, _fs in SEGMENTS.values():
    BIN[_v : _v + _fs] = RAW[_fo : _fo + _fs]


def _apply_chained_fixups():
    """LC_DYLD_CHAINED_FIXUPS: rewrite every chained pointer in BIN as the plain
    address it rebases to (an import reads 0, as dyld fills it at load time)."""
    for cmd, off, _ in load_commands():
        if cmd != 0x80000034:
            continue
        dataoff = struct.unpack_from("<I", RAW, off + 8)[0]
        starts = dataoff + struct.unpack_from("<I", RAW, dataoff + 4)[0]
        for s in range(struct.unpack_from("<I", RAW, starts)[0]):
            seg_info = struct.unpack_from("<I", RAW, starts + 4 + 4 * s)[0]
            if not seg_info:
                continue
            si = starts + seg_info
            _, page_size, fmt, seg_off, _, page_count = struct.unpack_from(
                "<IHHQIH", RAW, si
            )
            if fmt not in (2, 6):  # DYLD_CHAINED_PTR_64, DYLD_CHAINED_PTR_64_OFFSET
                raise SystemExit(f"unsupported chained pointer format {fmt}")
            for p in range(page_count):
                start = struct.unpack_from("<H", RAW, si + 22 + 2 * p)[0]
                if start == 0xFFFF:  # DYLD_CHAINED_PTR_START_NONE
                    continue
                a = seg_off + p * page_size + start
                while True:
                    v = struct.unpack_from("<Q", BIN, a)[0]
                    nxt = (v >> 51) & 0xFFF
                    target = (
                        0 if v >> 63 else ((v >> 36) & 0xFF) << 56 | (v & 0xFFFFFFFFF)
                    )
                    struct.pack_into("<Q", BIN, a, target)
                    if not nxt:
                        break
                    a += 4 * nxt


_apply_chained_fixups()


def u64(a):
    return struct.unpack_from("<Q", BIN, a)[0]


def u32(a):
    return struct.unpack_from("<I", BIN, a)[0]


def i32(a):
    return struct.unpack_from("<i", BIN, a)[0]


_DATA_SEGS = [seg for name, seg in SEGMENTS.items() if name.startswith("__DATA")]
DATA_START = min(v for v, _, _, _ in _DATA_SEGS)
DATA_END = max(v + vs for v, vs, _, _ in _DATA_SEGS)
CSTR = (SECTIONS[("__TEXT", "__cstring")][0], sum(SECTIONS[("__TEXT", "__cstring")]))
CODE = (SECTIONS[("__TEXT", "__text")][0], SECTIONS[("__TEXT", "__stubs")][0])
STUBS = (SECTIONS[("__TEXT", "__stubs")][0], sum(SECTIONS[("__TEXT", "__stubs")]))


def find_ptrs(val, start=DATA_START, end=DATA_END):
    pat, res = struct.pack("<Q", val), []
    i = BIN.find(pat, start, end)
    while i != -1:
        if i % 8 == 0:
            res.append(i)
        i = BIN.find(pat, i + 1, end)
    return res


def cstring_at(p):
    if not (0 < p < len(BIN)):
        return None
    return bytes(BIN[p : p + 256].split(b"\0")[0])


def _is_module(p):
    """Il2CppCodeGenModule: {const char* moduleName; uint32 methodPointerCount;
    methodPointers*; ...}. Names are assembly file names ("companions-shared.dll")
    plus one "__Generated"."""
    if not (DATA_START <= p < DATA_END):
        return False
    name = cstring_at(u64(p)) or b""
    ptrs = u64(p + 16)
    return (
        0 < len(name) < 128
        and all(32 < c < 127 for c in name)
        and u32(p + 8) < 1_000_000
        and (ptrs == 0 or DATA_START <= ptrs < DATA_END)
    )


# ---------------------------------------------------------------- CodeRegistration
def _find_code_registration():
    """codeGenModules is an array of Il2CppCodeGenModule*; CodeRegistration ends with
    {codeGenModulesCount, codeGenModules}. Find it from any image's module name."""
    for im in IM:
        name = mstr(im[0]).encode() + b"\0"
        s = BIN.find(name, *CSTR)
        while s != -1 and BIN[s - 1] != 0:
            s = BIN.find(name, s + 1, CSTR[1])
        if s == -1:
            continue
        for mod in find_ptrs(s):
            for slot in find_ptrs(mod):
                start = slot
                while _is_module(u64(start - 8)):
                    start -= 8
                for ref in find_ptrs(start):
                    count = u64(ref - 8)
                    if 0 < count < 10000 and all(
                        _is_module(u64(start + 8 * k)) for k in range(count)
                    ):
                        return ref - 8 * 16, start, count
    raise SystemExit("CodeRegistration not found")


CR, CGM_ARRAY, CGM_COUNT = _find_code_registration()
# CodeRegistration v29+: reversePInvokeWrapperCount, reversePInvokeWrappers,
# genericMethodPointersCount, genericMethodPointers, genericAdjustorThunks,
# invokerPointersCount, invokerPointers, unresolvedIndirectCallCount,
# 3 x unresolved*CallPointers, interopDataCount, interopData,
# windowsRuntimeFactoryCount, windowsRuntimeFactoryTable, codeGenModulesCount,
# codeGenModules
gmpCount, gmp = u64(CR + 16), u64(CR + 24)

modules = {}
for _k in range(CGM_COUNT):
    _m = u64(CGM_ARRAY + 8 * _k)
    modules[cstring_at(u64(_m)).decode()] = (_m, u32(_m + 8), u64(_m + 16))

method_addr, addr_methods = {}, {}
for _im in IM:
    _iname = mstr(_im[0])
    if _iname not in modules:
        continue
    _m, _cnt, _mp = modules[_iname]
    for _k in range(_im[3]):
        _t = TD[_im[2] + _k]
        for _j in range(_t[TD_METHOD_COUNT]):
            _mi = _t[TD_METHOD_START] + _j
            _rid = MT[_mi][6] & 0xFFFFFF
            if 1 <= _rid <= _cnt:
                _a = u64(_mp + (_rid - 1) * 8)
                if _a:
                    method_addr[_mi] = _a
for _mi, _a in method_addr.items():
    addr_methods.setdefault(_a, []).append(mname(_mi))


# ---------------------------------------------------------------- MetadataRegistration
def _find_metadata_registration():
    """fieldOffsetsCount and typeDefinitionsSizesCount both equal the typedef count."""
    ntd = len(TD)
    pat = struct.pack("<Q", ntd)
    i = BIN.find(pat, DATA_START, DATA_END)
    while i != -1:
        if i % 8 == 0 and u64(i + 16) == ntd and DATA_START <= u64(i + 8) < DATA_END:
            return i - 8 * 10
        i = BIN.find(pat, i + 1, DATA_END)
    raise SystemExit("MetadataRegistration not found")


MR = _find_metadata_registration()
(
    genericClassesCount,
    genericClasses,
    genericInstsCount,
    genericInsts,
    genericMethodTableCount,
    genericMethodTable,
    typesCount,
    typesPtr,
    methodSpecsCount,
    methodSpecsPtr,
    fieldOffsetsCount,
    fieldOffsetsPtr,
    tdsCount,
    tdsPtr,
    _,
    _,
) = [u64(MR + 8 * _k) for _k in range(16)]

PRIM = {
    1: "void",
    2: "bool",
    3: "char",
    4: "sbyte",
    5: "byte",
    6: "short",
    7: "ushort",
    8: "int",
    9: "uint",
    10: "long",
    11: "ulong",
    12: "float",
    13: "double",
    14: "string",
    0x16: "TypedReference",
    0x18: "IntPtr",
    0x19: "UIntPtr",
    0x1C: "object",
}


def gparam_name(idx):
    o = SEC["genericParameters"][0] + idx * GP_SIZE
    return mstr(struct.unpack_from(GP_FMT, MD, o)[1])


_tcache = {}


def type_name_at(p, depth=0):
    if p in _tcache:
        return _tcache[p]
    if depth > 6:
        return "?"
    data, bits = u64(p), u32(p + 8)
    t = (bits >> 16) & 0xFF
    if t in PRIM:
        r = PRIM[t]
    elif t in (0x11, 0x12):
        r = fqn(data & 0xFFFFFFFF) if (data & 0xFFFFFFFF) < len(TD) else f"td?{data}"
    elif t == 0x15:
        base = type_name_at(u64(data), depth + 1)
        r = f"{base}<{','.join(ginst_names(u64(data + 8), depth + 1))}>"
    elif t == 0x1D:
        r = type_name_at(data, depth + 1) + "[]"
    elif t == 0x14:
        r = type_name_at(u64(data), depth + 1) + "[,]"
    elif t in (0x13, 0x1E):
        try:
            r = gparam_name(data & 0xFFFFFFFF)
        except Exception:
            r = "T?"
    elif t == 0x0F:
        r = type_name_at(data, depth + 1) + "*"
    else:
        r = f"type{t:#x}"
    _tcache[p] = r
    return r


def type_name(idx):
    return (
        type_name_at(u64(typesPtr + 8 * idx))
        if 0 <= idx < typesCount
        else f"type#{idx}"
    )


def ginst_names(ptr, depth=0):
    if not ptr:
        return []
    argc, argv = u32(ptr), u64(ptr + 8)
    return [type_name_at(u64(argv + 8 * k), depth + 1) for k in range(min(argc, 8))]


def methodspec_name(i):
    mdi, cii, mii = struct.unpack_from("<3i", BIN, methodSpecsPtr + 12 * i)
    m = MT[mdi]
    tn, nm = fqn(m[1]), mstr(m[0])
    if cii >= 0:
        tn += "<" + ",".join(ginst_names(u64(genericInsts + 8 * cii))) + ">"
    if mii >= 0:
        nm += "<" + ",".join(ginst_names(u64(genericInsts + 8 * mii))) + ">"
    return tn + "::" + nm


generic_addr = {}
for _i in range(genericMethodTableCount):
    _spec, _midx, _inv, _adj = struct.unpack_from(
        "<4i", BIN, genericMethodTable + 16 * _i
    )
    if 0 <= _midx < gmpCount:
        _a = u64(gmp + 8 * _midx)
        if _a:
            generic_addr.setdefault(_a, []).append(_spec)


def addr_name(a):
    if a in addr_methods:
        return " / ".join(addr_methods[a][:2])
    if a in generic_addr:
        specs = generic_addr[a]
        return methodspec_name(specs[0]) + (
            f" (+{len(specs) - 1} insts)" if len(specs) > 1 else ""
        )
    return None


MT_PARAM_START, MT_FLAGS, MT_PARAM_COUNT = 4, 7, 10


def method_signature(mi):
    """'ReturnType Name(ParamType name, ...)' of a method definition."""
    m = MT[mi]
    params = [PARAMS[m[MT_PARAM_START] + k] for k in range(m[MT_PARAM_COUNT])]
    args = ", ".join(f"{type_name(p[2])} {mstr(p[0])}" for p in params)
    return f"{type_name(m[2])} {mstr(m[0])}({args})"


def field_offset(ti, j):
    p = u64(fieldOffsetsPtr + 8 * ti)
    return i32(p + 4 * j) if p else None


def type_fields(ti):
    t = TD[ti]
    return [
        (
            field_offset(ti, j),
            mstr(FD[t[TD_FIELD_START] + j][0]),
            type_name(FD[t[TD_FIELD_START] + j][1]),
        )
        for j in range(t[TD_FIELD_COUNT])
    ]


def decode_usage(v):
    """Lazily initialised metadata globals hold (usageType << 29) | (index << 1) | 1
    until their first use."""
    if not (v & 1) or v > 0xFFFFFFFF:
        return None
    typ, idx = (v & 0xE0000000) >> 29, (v & 0x1FFFFFFE) >> 1
    try:
        if typ == 1:
            return "TypeInfo:" + type_name(idx)
        if typ == 2:
            return "Type:" + type_name(idx)
        if typ == 3:
            return "MethodDef:" + mname(idx)
        if typ == 4:
            ti, fj = FIELDREFS[idx]
            return f"FieldInfo:{type_name(ti)}#{fj}"
        if typ == 5:
            return "Str:" + repr(strlit(idx))
        if typ == 6:
            return "MethodRef:" + methodspec_name(idx)
        if typ == 7:
            return f"FieldRva:{idx}"
    except Exception:
        return f"usage{typ}:{idx}?"
    return None


# ------------------------------------------- default values (compressed, v29+)
FDV = {
    fi: (ti, di)
    for fi, ti, di in table("fieldDefaultValues", f"<i{TY_IX}i", [(1, W_TYPE)])
}


def _rcu32(o):
    b = MD[o]
    if b & 0x80 == 0:
        return b, 1
    if b & 0xC0 == 0x80:
        return ((b & 0x3F) << 8) | MD[o + 1], 2
    if b & 0xE0 == 0xC0:
        return ((b & 0x1F) << 24) | (MD[o + 1] << 16) | (MD[o + 2] << 8) | MD[o + 3], 4
    if b == 0xF0:
        return struct.unpack_from("<I", MD, o + 1)[0], 5
    if b == 0xFE:
        return 0xFFFFFFFE, 1
    if b == 0xFF:
        return 0xFFFFFFFF, 1
    return None, 1


def _rci32(o):
    """Signed compressed int: the sign sits in bit 0 of the unsigned encoding."""
    v, n = _rcu32(o)
    if v == 0xFFFFFFFF:
        return -(2**31), n
    return (-(v >> 1) - 1 if v & 1 else v >> 1), n


def field_default(fi):
    """Enum constants and literal defaults. For <PrivateImplementationDetails>
    static array fields (used by RuntimeHelpers.InitializeArray) this returns
    '<Type@dataIndex>'; read the bytes with static_array_bytes()."""
    if fi not in FDV:
        return None
    ti, di = FDV[fi]
    o = SEC["fieldAndParameterDefaultValueData"][0] + di
    tn = type_name(ti)
    if tn in ("byte", "sbyte", "bool"):
        return MD[o]
    if tn in ("int", "short", "long"):
        return _rci32(o)[0]
    if tn in ("uint", "ushort", "ulong", "char"):
        return _rcu32(o)[0]
    if tn == "float":
        return struct.unpack_from("<f", MD, o)[0]
    if tn == "double":
        return struct.unpack_from("<d", MD, o)[0]
    if tn == "string":
        ln, n = _rci32(o)
        return MD[o + n : o + n + ln].decode("utf-8", "replace")
    return f"<{tn}@{di}>"


def static_array_bytes(field_index, length):
    """Raw bytes of a <PrivateImplementationDetails> RVA field (e.g. the int[]
    round tables)."""
    _, di = FDV[field_index]
    o = SEC["fieldAndParameterDefaultValueData"][0] + di
    return MD[o : o + length]


if __name__ == "__main__":
    print(f"app {C}")
    print(
        f"build-guid {build_guid()}  metadata v{METADATA_VERSION}  index widths "
        f"typedef {W_TYPEDEF} gcontainer {W_GCONTAINER} type {W_TYPE} param {W_PARAM}"
    )
    print(
        f"CodeRegistration {CR:#x}, codeGenModules {CGM_ARRAY:#x} x{CGM_COUNT}, "
        f"MetadataRegistration {MR:#x}"
    )
    print(
        f"{len(TD)} types, {len(MT)} methods, {len(method_addr)} method addresses, "
        f"{len(generic_addr)} generic instance addresses"
    )
