"""Build the tables the Ghidra decompile script reads, from a Steam app dump.

Plan 16.11 (decompiler trial, 2026-10-28). The Steam Dune app's GameAssembly
is IL2CPP and stripped; our dump already names its methods (``methods.tsv``,
``generics.tsv``) and its annotated asm names the metadata globals
(``MethodRef:``, ``TypeInfo:``, ``Str:`` ...) and static fields
(``~static Class.Field``). This writes, into the dump's git-ignored
``ghidra/`` folder (app-derived, never into this repository):

- ``labels.tsv``: address -> name for methods, generic instances, metadata
  globals and runtime helpers;
- ``statics.tsv``: TypeInfo global -> static-field offset -> field name (a
  short class name shared by several classes is resolved by the TypeInfo the
  same function loaded before);
- ``starts.tsv``: every method start, so each function's body ends at the
  next one.

    uv run --no-project python scripts/dwgr/ghidra_tables.py \
        assets/reference/dune-steam-app/<build>

Then run ``scripts/dwgr/ghidra/DecompileTyped.java`` headless (analysis off)
with ``labels.tsv statics.tsv starts.tsv targets.txt outdir`` as its
arguments; see plan 16.11 for the launcher that keeps Ghidra's settings and
temporary files inside the project.
"""

import collections
import pathlib
import re
import sys


def _short(name: str) -> str:
    return re.split(r"[./]", name)[-1]


def main() -> None:
    root = pathlib.Path(sys.argv[1])
    dump = root / "dump"
    out = root / "ghidra"
    out.mkdir(exist_ok=True)
    labels: dict[int, str] = {}
    starts: set[int] = set()
    for table in ("methods.tsv", "generics.tsv"):
        for line in (dump / table).read_text().splitlines():
            if not line.startswith("0x"):
                continue
            address, name = line.split("\t")[:2]
            starts.add(int(address, 16))
            labels.setdefault(int(address, 16), re.sub(r"\s+", "_", name)[:400])
    glob = re.compile(r";\s*\[(0x[0-9a-f]+)\]\s+(?:=0x[0-9a-f]+\s*)?([A-Za-z]+:.*)$")
    call = re.compile(r"(?:call|jmp)\s+(0x[0-9a-f]+)\s+;\s*(rt:[^\s(]+)")
    typeinfo_line = re.compile(
        r";\s*\[(0x[0-9a-f]+)\]\s+(?:=0x[0-9a-f]+\s*)?TypeInfo:(\S+)"
    )
    static_line = re.compile(
        r"\[\w+(?: \+ 0x([0-9a-f]+))?\]\s+;\s*~static (.+)\.([^.\s]+)\s*$"
    )
    texts = [f.read_text(errors="replace") for f in (dump / "asm").rglob("*.asm")]
    for text in texts:
        for line in text.splitlines():
            if m := glob.search(line):
                name = re.sub(r"\s+", "_", m.group(2).strip())[:400]
                labels.setdefault(int(m.group(1), 16), name)
            if m := call.search(line):
                labels.setdefault(int(m.group(1), 16), m.group(2))
    typeinfo = {
        name[len("TypeInfo:") :]: address
        for address, name in labels.items()
        if name.startswith("TypeInfo:")
    }
    by_short = collections.defaultdict(list)
    for full, address in typeinfo.items():
        by_short[_short(full)].append(address)
    fields: dict[int, dict[int, str]] = collections.defaultdict(dict)
    unresolved = 0
    for text in texts:
        seen: list[tuple[str, int]] = []
        for line in text.splitlines():
            if line.startswith("====="):
                seen = []
            elif m := typeinfo_line.search(line):
                seen.append((m.group(2), int(m.group(1), 16)))
            elif m := static_line.search(line):
                short = _short(m.group(2))
                candidates = by_short.get(short, [])
                address = (
                    candidates[0]
                    if len(candidates) == 1
                    else next(
                        (a for full, a in reversed(seen) if _short(full) == short), None
                    )
                )
                if address is None:
                    unresolved += 1
                    continue
                fields[address][int(m.group(1) or "0", 16)] = m.group(3)
    (out / "labels.tsv").write_text(
        "".join(f"{a:#x}\t{n}\n" for a, n in sorted(labels.items()))
    )
    (out / "starts.tsv").write_text("".join(f"{a:#x}\n" for a in sorted(starts)))
    (out / "statics.tsv").write_text(
        "".join(
            f"{a:#x}\t{o:#x}\t{f}\n"
            for a, offsets in sorted(fields.items())
            for o, f in sorted(offsets.items())
        )
    )
    print(
        f"labels {len(labels)}, starts {len(starts)}, static classes {len(fields)}, "
        f"unresolved static uses {unresolved}"
    )


if __name__ == "__main__":
    main()
