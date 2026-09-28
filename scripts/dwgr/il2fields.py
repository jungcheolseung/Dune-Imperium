"""Fields (absolute offsets, types, enum/literal defaults) and methods of types.

usage: il2fields.py <FullTypeName> | <substring*> ...
  nested types use '/', e.g. grm.companions.spice.ScheduleController/<>c
"""

import sys

from il2meta import (
    MT,
    TD,
    TD_FIELD_START,
    TD_METHOD_COUNT,
    TD_METHOD_START,
    field_default,
    fqn,
    method_addr,
    mstr,
    type_fields,
    type_name,
)

if __name__ == "__main__":
    for arg in sys.argv[1:]:
        for ti, t in enumerate(TD):
            n = fqn(ti)
            if not (arg == n or (arg.endswith("*") and arg[:-1] in n)):
                continue
            par = type_name(t[4]) if t[4] >= 0 else None
            print(f"== {n}  (parent {par})")
            for j, (off, fn, ft) in enumerate(type_fields(ti)):
                dv = field_default(t[TD_FIELD_START] + j)
                print(
                    f"   field +{off if off is not None else '?'}  {fn} : {ft}"
                    + (f"  = {dv!r}" if dv is not None else "")
                )
            for j in range(t[TD_METHOD_COUNT]):
                mi = t[TD_METHOD_START] + j
                print(f"   method {method_addr.get(mi, 0):#x}  {mstr(MT[mi][0])}")
