"""Record-corpus code that both an old and the current engine run.

A record corpus (``records.corpus``) is written by the engine that played
it, often an older one than the engine that later reads it. The code both
sides must agree on -- the canonical form of a state field, its digest, the
per-step trace codec and the per-step index keys -- lives here and imports
only the standard library: an old engine's driver
(``scripts/records/corpus_generate.py``) loads these files by path under
private module names, so they never meet that engine's own
``dune_imperium`` package. They read engine objects only through
``dataclasses.fields``, ``getattr`` with defaults and ``Enum.value``.
"""
