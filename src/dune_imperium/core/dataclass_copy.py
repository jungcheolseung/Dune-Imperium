"""Constructor-preserving copies for the two large immutable state records."""

from dataclasses import fields, is_dataclass, replace
from inspect import signature
from typing import Any, cast


def positional_dataclass_replace[T](cls: type[T]) -> type[T]:
    """Give ``copy.replace`` direct field reads without skipping construction.

    The engine copies its large states several times per decision. Gathering
    every field through dataclass metadata and ``getattr`` on every copy is
    avoidable: compile the reads once from the declared fields, as dataclasses
    compiles its initializer. The same constructor still runs, including all
    invariant checks and PlayerState's public-hand normalization.

    Unusual constructor layouts keep the standard implementation. Unknown
    changes and subclasses also use it, preserving rejection and subclass
    construction instead of dropping fields or calling the wrong constructor.
    """

    if not is_dataclass(cls):
        raise TypeError("positional replacement requires a dataclass")
    declared = fields(cls)
    names = tuple(field.name for field in declared)
    if any(not field.init or field.kw_only for field in declared) or tuple(
        signature(cls).parameters
    ) != names:
        return cls

    namespace: dict[str, Any] = {
        "_cls": cls,
        "_fields": frozenset(names),
        "_standard_replace": replace,
    }
    arguments = ",\n        ".join(
        f"changes.get({name!r}, self.{name})" for name in names
    )
    source = (
        "def __replace__(self, /, **changes):\n"
        "    if type(self) is not _cls or not changes.keys() <= _fields:\n"
        "        return _standard_replace(self, **changes)\n"
        f"    return _cls(\n        {arguments}\n    )\n"
    )
    filename = f"<{cls.__module__}.{cls.__qualname__}.__replace__>"
    exec(compile(source, filename, "exec"), namespace)
    method = namespace["__replace__"]
    method.__module__ = cls.__module__
    method.__qualname__ = f"{cls.__qualname__}.__replace__"
    cast(Any, cls).__replace__ = method
    return cls
