"""Shared pytest setup: a test run's temporary files stay inside the project.

User decision (2026-10-06): nothing the project makes lives outside the
project directory, temporary files included. ``tmp_path`` and every
``tempfile`` call of a test run (and of the processes it starts, through
``TMPDIR``) land in the git-ignored ``tmp/pytest/`` of this checkout.
pytest numbers its run folders there and keeps the last three, so two runs
side by side do not clobber each other.
"""

import os
import tempfile

from dune_imperium.paths import TMP_DIR

_TEST_TMP = TMP_DIR / "pytest"
_TEST_TMP.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(_TEST_TMP)
tempfile.tempdir = str(_TEST_TMP)
