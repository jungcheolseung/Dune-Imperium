"""Fast copies for immutable records the engine copies often."""

from dataclasses import MISSING, fields, is_dataclass, replace
from inspect import signature
from types import MemberDescriptorType
from typing import Any, cast


def positional_dataclass_replace[T](cls: type[T]) -> type[T]:
    """Give ``copy.replace`` direct field reads, and checks only where needed.

    The engine copies its large states several times per decision. Gathering
    every field through dataclass metadata and ``getattr`` on every copy is
    avoidable: compile the reads once from the declared fields, as dataclasses
    compiles its initializer. By default the same constructor still runs,
    including all invariant checks and PlayerState's public-hand
    normalization.

    A class that defines ``_check_copy(self, previous, changed)`` instead gets
    its copy built without the constructor -- every field set from the
    source, then the changed ones from the changes -- and then
    ``_check_copy`` runs the checks the changed fields need (``GameState``:
    most copies only push a decision frame or log an event, which no
    invariant reads). Such a class's ``_check_copy`` must do whatever of its
    ``__post_init__`` work the changed fields need (``PlayerState`` runs all
    of it, as its constructor would).

    On a slotted class the fields are set through their slot descriptors
    (``__set__``), which is what the frozen constructor's
    ``object.__setattr__`` reaches after looking each name up: the copy is
    the same object, written about twice as fast (2026-11 engine speed,
    docs/evaluation/2026-11-engine-speed.md).

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
        "_new": object.__new__,
        "_set": object.__setattr__,
    }
    guard = (
        "def __replace__(self, /, **changes):\n"
        "    if type(self) is not _cls or not changes.keys() <= _fields:\n"
        "        return _standard_replace(self, **changes)\n"
    )
    if hasattr(cls, "_check_copy"):
        slotted = all(
            isinstance(vars(cls).get(name), MemberDescriptorType) for name in names
        )
        if slotted:
            for index, name in enumerate(names):
                namespace[f"_slot{index}"] = vars(cls)[name].__set__
            sets = "\n    ".join(
                f"_slot{index}(new, self.{name})" for index, name in enumerate(names)
            )
        else:
            sets = "\n    ".join(f"_set(new, {name!r}, self.{name})" for name in names)
        source = (
            f"{guard}"
            "    new = _new(_cls)\n"
            f"    {sets}\n"
            "    for name, value in changes.items():\n"
            "        _set(new, name, value)\n"
            "    new._check_copy(self, changes.keys())\n"
            "    return new\n"
        )
    else:
        arguments = ",\n        ".join(
            f"changes.get({name!r}, self.{name})" for name in names
        )
        source = f"{guard}    return _cls(\n        {arguments}\n    )\n"
    filename = f"<{cls.__module__}.{cls.__qualname__}.__replace__>"
    exec(compile(source, filename, "exec"), namespace)
    method = namespace["__replace__"]
    method.__module__ = cls.__module__
    method.__qualname__ = f"{cls.__qualname__}.__replace__"
    cast(Any, cls).__replace__ = method
    return cls


def slot_initializer[T](cls: type[T]) -> type[T]:
    """Give a frozen slotted dataclass an initializer that writes its slots.

    The dataclass initializer of a frozen class sets each field with
    ``object.__setattr__``, which looks the name up and reaches the slot's
    member descriptor; this one calls each descriptor's ``__set__``
    directly, in the same order, with the same parameters and the same
    default objects. The object built is the same, about a third faster
    (2026-11 engine speed, round 3: the observation's views, built for
    every decision). Only a class whose initializer does nothing else
    takes it: every field an ``__init__`` parameter in declared order,
    none keyword-only or with a default factory, every field a slot. Any
    other class is returned unchanged.

    A class with a ``__post_init__`` takes it too (2026-11-11 engine speed,
    stage B: the engine's actions, events, frames and results): the
    dataclass initializer of a frozen class sets the fields and then calls
    ``self.__post_init__()``, and so does this one, after the same writes.
    """

    if not is_dataclass(cls):
        raise TypeError("a slot initializer requires a dataclass")
    declared = fields(cls)
    names = tuple(field.name for field in declared)
    if (
        any(
            not field.init
            or field.kw_only
            or field.default_factory is not MISSING
            or field.name == "self"
            or field.name.startswith("_")
            for field in declared
        )
        or tuple(signature(cls).parameters) != names
        or not all(
            isinstance(vars(cls).get(name), MemberDescriptorType) for name in names
        )
        or not _is_dataclass_initializer(cls, declared)
    ):
        return cls
    # A subclass constructs as the dataclass initializer did (its own
    # properties or descriptors over a field see the write).
    namespace: dict[str, Any] = {
        "_cls": cls,
        "_dataclass_init": cls.__init__,
        "_type": type,
    }
    parameters = []
    sets = [
        "if _type(self) is not _cls:\n"
        f"        return _dataclass_init(self, {', '.join(names)})"
    ]
    for index, field in enumerate(declared):
        namespace[f"_slot{index}"] = vars(cls)[field.name].__set__
        if field.default is MISSING:
            parameters.append(field.name)
        else:
            namespace[f"_default{index}"] = field.default
            parameters.append(f"{field.name}=_default{index}")
        sets.append(f"_slot{index}(self, {field.name})")
    if hasattr(cls, "__post_init__"):
        sets.append("self.__post_init__()")
    source = (
        f"def __init__(self, {', '.join(parameters)}):\n    "
        + "\n    ".join(sets)
        + "\n"
    )
    filename = f"<{cls.__module__}.{cls.__qualname__}.__init__>"
    exec(compile(source, filename, "exec"), namespace)
    method = namespace["__init__"]
    method.__module__ = cls.__module__
    method.__qualname__ = f"{cls.__qualname__}.__init__"
    # The same annotations, still evaluated only when asked for: the
    # signature reads as the dataclass initializer's did.
    method.__annotate__ = getattr(cast(Any, cls).__init__, "__annotate__", None)
    cast(Any, cls).__init__ = method
    return cls


def _is_dataclass_initializer(cls: type[Any], declared: tuple[Any, ...]) -> bool:
    """Whether ``cls.__init__`` is the one ``dataclass`` generated, with the
    fields' own defaults: a class's hand-written initializer is kept (Codex
    review r4)."""

    init = vars(cls).get("__init__")
    code = getattr(init, "__code__", None)
    if code is None or code.co_filename != "<string>" or code.co_name != "__init__":
        return False
    defaults = tuple(
        field.default for field in declared if field.default is not MISSING
    )
    given = init.__defaults__ or ()
    return len(given) == len(defaults) and all(
        a is b for a, b in zip(given, defaults, strict=True)
    )
