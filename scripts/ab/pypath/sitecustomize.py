"""Registers the scratch variants of ``hvariants.py`` on interpreter start.

Lives on ``PYTHONPATH`` as ``sitecustomize`` so Python 3.14's spawn/forkserver
tournament workers register them too (``scripts/ab/cells.py`` sets the path; by
hand: ``PYTHONPATH=scripts/ab/pypath uv run dune-imperium-tournament ...``).
"""

try:
    import hvariants

    from dune_imperium.agents import registry
except ImportError:  # some other interpreter on this PYTHONPATH
    pass
else:
    hvariants.register(registry)
    hvariants.register_rollout(registry)
    import os

    if os.environ.get("DUNE_PROBE_CKPT"):
        # Network probes need torch; only load it when a probe is asked for.
        import netprobes

        netprobes.register(registry)
