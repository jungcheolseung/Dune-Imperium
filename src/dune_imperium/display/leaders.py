"""Hand-authored English text for the printed Leader abilities.

The content manifest stores only ability and Signet Ring *names*; the
behaviour lives in ``rules/leader_abilities.py``. The wording here follows
the image-verified audit ``docs/implementation-audits/leaders.md``, which
quotes the printed card text (4-player values where the card carries an
asterisk). Keys are leader *face* ids, so Lady Jessica's flip side has its
own entry.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class LeaderFaceText:
    """Display text for one printed Leader face."""

    ability_text: str
    signet_text: str
    notes: tuple[str, ...] = ()


LEADER_FACE_TEXTS: Mapping[str, LeaderFaceText] = MappingProxyType(
    {
        "gurney_halleck": LeaderFaceText(
            ability_text=(
                "Reveal turn: If you have 6 or more strength in the"
                " Conflict: Gain 1 Persuasion (4-player value)"
            ),
            signet_text="Recruit 1 troop",
        ),
        "lady_amber_metulli": LeaderFaceText(
            ability_text="Reveal turn: You may retreat one of your troops",
            signet_text=(
                "Gain 1 solari. If you have an Alliance: Gain 1 spice"
            ),
        ),
        "feyd_rautha_harkonnen": LeaderFaceText(
            ability_text=(
                "Reveal turn, once: Recall one of your placed Spies"
                " → Gain 2 swords"
            ),
            signet_text=(
                "Move your Feyd token one space right on your Training"
                " track and earn the reward printed on the new space"
            ),
        ),
        "lady_jessica": LeaderFaceText(
            ability_text=(
                "When you send an Agent to a Bene Gesserit board space:"
                " you may return all of your memories to your supply,"
                " Draw 1 card per memory, and flip to Reverend Mother"
                " Jessica"
            ),
            signet_text=(
                "Pay 1 spice → Draw 1 Intrigue card and move 1 troop from"
                " your supply to the Bene Gesserit board area as a memory"
            ),
        ),
        "reverend_mother_jessica": LeaderFaceText(
            ability_text=(
                "Once during each turn: after your Agent resolves a Bene"
                " Gesserit or Fremen board space, you may pay 1 water to"
                " repeat that space's printed effect (Influence is not"
                " repeated)"
            ),
            signet_text="Pay 1 spice → Gain 1 water",
        ),
        "lady_margot_fenring": LeaderFaceText(
            ability_text=(
                "When you reach 2 Bene Gesserit Influence: Gain 2 spice"
            ),
            signet_text=(
                "Place a Spy on an observation post connected to a City"
                " board space"
            ),
        ),
        "muad_dib": LeaderFaceText(
            ability_text=(
                "Reveal turn: If you have one or more sandworms in the"
                " Conflict: Draw 1 Intrigue card"
            ),
            signet_text="Draw 1 card",
        ),
        "princess_irulan": LeaderFaceText(
            ability_text=(
                "When you reach 2 Emperor Influence: Draw 1 Intrigue card"
            ),
            signet_text=(
                "You may choose one: Acquire a card that costs 1 to your"
                " hand — or Trash a card from your hand; if it costs 1 or"
                " more, Gain 2 spice"
            ),
        ),
        "staban_tuek": LeaderFaceText(
            ability_text=(
                "Whenever another player sends an Agent to a Maker board"
                " space you are spying on: Gain 1 spice"
            ),
            signet_text=(
                "Place a Spy on any observation post. If it connects to a"
                " Landsraad space: you may pay 1 spice → Gain 3 solari."
                " If it connects to a Faction space: you may pay 2 solari"
                " → Draw 1 Intrigue card"
            ),
            notes=(
                "Limited Allies: starts the game without Diplomacy in the"
                " deck",
            ),
        ),
        "shaddam_corrino_iv": LeaderFaceText(
            ability_text=(
                "Set aside both Sardaukar contracts; only you may acquire"
                " them during the game"
            ),
            signet_text=(
                "Units can't be deployed to the Conflict this turn."
                " Choose: Gain 1 solari and Recruit 1 troop — or pay"
                " 3 solari → Gain 1 Influence with a Faction of your"
                " choice"
            ),
        ),
    }
)
