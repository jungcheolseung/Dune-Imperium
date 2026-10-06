"""Where the project keeps its own local files: inside the checkout.

User decision (2026-10-06): nothing the project writes or keeps for itself
lives outside the project directory. Save files and the search AI's network
sit under the checkout this package runs from, in git-ignored folders
(``.gitignore``), next to ``checkpoints/`` and ``assets/``. Every ``uv run``
here uses an editable install, so ``PROJECT_ROOT`` is that checkout; a git
worktree under ``.claude/worktrees/`` has its own.
"""

from pathlib import Path
from typing import Final

PROJECT_ROOT: Final = Path(__file__).resolve().parents[2]
# The play server's save files (``--saves-dir`` overrides it).
SAVES_DIR: Final = PROJECT_ROOT / "saves"
# The search AI seat's network, usually a symlink to a weights-only copy in
# the same folder (``--search-checkpoint`` overrides it).
SEARCH_CHECKPOINT: Final = PROJECT_ROOT / "checkpoints" / "play" / "search.pt"
