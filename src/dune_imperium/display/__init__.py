"""English display text generated from the same data the engine executes.

This package is framework neutral: it may import ``content`` and ``rules``
but never the HTTP server, so any future front end (web, TUI, replay tools)
can reuse it. Text is generated from structured effect data wherever that
data exists; hand-authored lines are limited to content whose behaviour
lives in imperative rules code, and their wording follows the image-verified
audit documents under ``docs/implementation-audits/`` and the cited rules
summaries under ``docs/rules/``.
"""

from dune_imperium.display.cards import personal_card_text
from dune_imperium.display.effect_dsl_text import intrigue_card_text
from dune_imperium.display.images import image_filename
from dune_imperium.display.leaders import LEADER_FACE_TEXTS, LeaderFaceText
from dune_imperium.display.spaces import (
    space_is_implemented,
    space_notes,
    space_option_count,
    space_option_effects,
)
from dune_imperium.display.structs import (
    conflict_rewards_texts,
    contract_condition_text,
    contract_reward_text,
)

__all__ = [
    "LEADER_FACE_TEXTS",
    "LeaderFaceText",
    "conflict_rewards_texts",
    "contract_condition_text",
    "contract_reward_text",
    "image_filename",
    "intrigue_card_text",
    "personal_card_text",
    "space_is_implemented",
    "space_notes",
    "space_option_count",
    "space_option_effects",
]
