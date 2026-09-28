"""IL2CPP metadata + binary map for the macOS Dire Wolf Game Room build.

Parses global-metadata.dat (version 31) and the stripped x86_64 GameAssembly.dylib
and exposes, at import time:

  method_addr[methodIndex] -> code address, addr_methods[addr] -> [names]
  generic_addr[addr] -> [methodSpec indices]   (shared generic instances)
  fqn(typeIndex), mname(methodIndex), type_name(il2cppTypeIndex)
  methodspec_name(i), type_fields(typeIndex), field_default(fieldIndex)
  decode_usage(value)  -- lazily initialised metadata globals (TypeInfo, MethodRef,
                          Str, ...)

Addresses are file offsets; this build maps __TEXT and __DATA at vmaddr == fileoff
(checked below). The CodeRegistration / MetadataRegistration / codeGenModules
locations are found by searching, so the module survives app updates as long as
the metadata version and the struct layouts stay the same.

Game location: $DWGR_APP (the .app's Contents directory) or the default Steam path.
"""

import os
import struct

DEFAULT_APP = os.path.expanduser(
    "~/Library/Application Support/Steam/steamapps/common/DireWolfGameRoom/"
    "DireWolfGameRoom.app/Contents"
)
C = os.environ.get("DWGR_APP", DEFAULT_APP)
DATA_DIR = os.path.join(C, "Resources", "Data")
MD = open(
    os.path.join(DATA_DIR, "il2cpp_data", "Metadata", "global-metadata.dat"), "rb"
).read()
BIN = open(os.path.join(C, "Frameworks", "GameAssembly.dylib"), "rb").read()


def build_guid():
    try:
        for line in open(os.path.join(DATA_DIR, "boot.config")):
            if line.startswith("build-guid="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


# ---------------------------------------------------------------- metadata
_sanity, METADATA_VERSION = struct.unpack_from("<Ii", MD, 0)
if _sanity != 0xFAB11BAF or METADATA_VERSION != 31:
    raise SystemExit(
        f"unsupported global-metadata (sanity {_sanity:#x}, "
        f"version {METADATA_VERSION}); "
        "the struct layouts below are for version 31"
    )
H = struct.unpack_from("<64i", MD, 8)
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
]
SEC = {n: (H[2 * i], H[2 * i + 1]) for i, n in enumerate(HN)}


def mstr(idx):
    o = SEC["string"][0] + idx
    return MD[o : MD.index(b"\0", o)].decode("utf-8", "replace")


def table(name, fmt):
    off, size = SEC[name]
    sz = struct.calcsize(fmt)
    return [struct.unpack_from(fmt, MD, off + i * sz) for i in range(size // sz)]


# Il2CppTypeDefinition v31 (88 bytes): 16 int32 (name, namespace, byval, declaring,
# parent, element, genericContainer, flags, fieldStart, methodStart, eventStart,
# propertyStart, nestedTypesStart, interfacesStart, vtableStart,
# interfaceOffsetsStart), 8 uint16 (method_count, property_count, field_count,
# event_count, nested_type_count, vtable_count, interfaces_count,
# interface_offsets_count), bitfield, token.
TD = table("typeDefinitions", "<16i8H2I")
TD_FIELD_START, TD_METHOD_START, TD_NESTED_START = 8, 9, 12
TD_METHOD_COUNT, TD_FIELD_COUNT, TD_NESTED_COUNT = 16, 18, 20
# Il2CppMethodDefinition v31: name, declaringType, returnType, returnParamToken,
# paramStart, genericContainer, token, then 4 uint16.
MT = table("methods", "<7i4H")
IM = table("images", "<10i")  # name, assembly, typeStart, typeCount, ...
FD = table("fields", "<3i")  # name, typeIndex, token
SL = table("stringLiteral", "<2I")  # length, dataIndex
NESTED = table("nestedTypes", "<i")
FIELDREFS = table("fieldRefs", "<2i")


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
def u64(a):
    return struct.unpack_from("<Q", BIN, a)[0]


def u32(a):
    return struct.unpack_from("<I", BIN, a)[0]


def i32(a):
    return struct.unpack_from("<i", BIN, a)[0]


def load_commands():
    if u32(0) != 0xFEEDFACF:
        raise SystemExit(
            "GameAssembly.dylib is not a thin 64-bit Mach-O "
            "(fat binaries are not handled)"
        )
    ncmds, off, res = u32(16), 32, []
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", BIN, off)
        res.append((cmd, off, size))
        off += size
    return res


SEGMENTS, SECTIONS = {}, {}
for _cmd, _off, _size in load_commands():
    if _cmd == 0x19:  # LC_SEGMENT_64
        segname = BIN[_off + 8 : _off + 24].split(b"\0")[0].decode()
        vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<4Q", BIN, _off + 24)
        nsects = u32(_off + 64)
        SEGMENTS[segname] = (vmaddr, vmsize, fileoff, filesize)
        for s in range(nsects):
            so = _off + 72 + 80 * s
            sect = BIN[so : so + 16].split(b"\0")[0].decode()
            addr, size = struct.unpack_from("<2Q", BIN, so + 32)
            SECTIONS[(segname, sect)] = (addr, size)
for _seg in ("__TEXT", "__DATA"):
    if SEGMENTS[_seg][0] != SEGMENTS[_seg][2]:
        raise SystemExit(
            f"{_seg} vmaddr != fileoff; address translation is not implemented"
        )
DATA_START = SEGMENTS["__DATA"][0]
DATA_END = DATA_START + SEGMENTS["__DATA"][1]
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
    return BIN[p : p + 256].split(b"\0")[0]


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
    {codeGenModulesCount, codeGenModules}. Find it from the companions-shared module."""
    name = b"companions-shared.dll\0"
    s = BIN.find(name, *CSTR)
    while s != -1 and BIN[s - 1] != 0:
        s = BIN.find(name, s + 1, CSTR[1])
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
    o = SEC["genericParameters"][0] + idx * 16
    return mstr(struct.unpack_from("<iiHHHH", MD, o)[1])


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
FDV = {fi: (ti, di) for fi, ti, di in table("fieldDefaultValues", "<3i")}


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
    if tn in ("int", "uint", "short", "ushort", "long", "ulong", "char"):
        v, _ = _rcu32(o)
        if tn in ("int", "short", "long"):
            if v == 0xFFFFFFFF:
                return -(2**31)
            neg, v = v & 1, v >> 1
            return -(v + 1) if neg else v
        return v
    if tn == "float":
        return struct.unpack_from("<f", MD, o)[0]
    if tn == "double":
        return struct.unpack_from("<d", MD, o)[0]
    if tn == "string":
        ln, n = _rcu32(o)
        return MD[o + n : o + n + ln].decode("utf-8", "replace")
    return f"<{tn}@{di}>"


def static_array_bytes(field_index, length):
    """Raw bytes of a <PrivateImplementationDetails> RVA field (e.g. the int[]
    round tables)."""
    _, di = FDV[field_index]
    o = SEC["fieldAndParameterDefaultValueData"][0] + di
    return MD[o : o + length]


if __name__ == "__main__":
    print(f"build-guid {build_guid()}  metadata v{METADATA_VERSION}")
    print(
        f"CodeRegistration {CR:#x}, codeGenModules {CGM_ARRAY:#x} x{CGM_COUNT}, "
        f"MetadataRegistration {MR:#x}"
    )
    print(
        f"{len(TD)} types, {len(MT)} methods, {len(method_addr)} method addresses, "
        f"{len(generic_addr)} generic instance addresses"
    )
