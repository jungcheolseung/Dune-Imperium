"""English display text generated from the same data the engine executes.

This package is framework neutral: it may import ``content`` and ``rules``
but never the HTTP server, so any future front end (web, TUI, replay tools)
can reuse it. Text is generated from structured effect data wherever that
data exists; hand-authored lines are limited to content whose behaviour
lives in imperative rules code, and their wording follows the image-verified
audit documents under ``docs/implementation-audits/`` and the cited rules
summaries under ``docs/rules/``.
"""

from dune_imperium.display.actions import (
    agent_card_icon_text,
    agent_card_icon_text_ko,
    effect_action_text,
    effect_action_text_ko,
)
from dune_imperium.display.cards import personal_card_text, personal_card_text_ko
from dune_imperium.display.effect_dsl_text import intrigue_card_text
from dune_imperium.display.effect_dsl_text_ko import intrigue_card_text_ko
from dune_imperium.display.icons import ICON_NAMES, available_icons, icon_filename
from dune_imperium.display.images import (
    load_card_manifest,
    required_image_keys,
    resolve_card_images,
)
from dune_imperium.display.leaders import LEADER_FACE_TEXTS, LeaderFaceText
from dune_imperium.display.spaces import (
    board_effect_action_text,
    board_icon_text,
    space_is_implemented,
    space_notes,
    space_option_count,
    space_option_effects,
)
from dune_imperium.display.structs import (
    conflict_rewards_texts,
    conflict_rewards_texts_ko,
    contract_condition_text,
    contract_condition_text_ko,
    contract_reward_text,
    contract_reward_text_ko,
)
from dune_imperium.display.token_images import (
    STRENGTH_TOKEN_COLORS,
    available_strength_tokens,
    strength_token_filenames,
)

__all__ = [
    "ICON_NAMES",
    "LEADER_FACE_TEXTS",
    "LeaderFaceText",
    "STRENGTH_TOKEN_COLORS",
    "agent_card_icon_text",
    "agent_card_icon_text_ko",
    "available_icons",
    "available_strength_tokens",
    "board_effect_action_text",
    "board_icon_text",
    "conflict_rewards_texts",
    "conflict_rewards_texts_ko",
    "contract_condition_text",
    "contract_condition_text_ko",
    "contract_reward_text",
    "contract_reward_text_ko",
    "effect_action_text",
    "effect_action_text_ko",
    "icon_filename",
    "intrigue_card_text",
    "intrigue_card_text_ko",
    "load_card_manifest",
    "personal_card_text",
    "personal_card_text_ko",
    "required_image_keys",
    "resolve_card_images",
    "space_is_implemented",
    "space_notes",
    "space_option_count",
    "space_option_effects",
    "strength_token_filenames",
]
