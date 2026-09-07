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
        # Bloodlines Leaders (card faces, 2026-09-07).
        "chani": LeaderFaceText(
            ability_text=(
                "Tactician: Whenever you retreat or lose any number of troops"
                " from the Conflict, advance your Tactics token that many"
                " spaces, earning rewards as you reach them (space 6: 1 spice;"
                " end: 1 water, then reset to the starting space)"
            ),
            signet_text=(
                "Retreat any number of your troops — or with 2 Fremen"
                " Influence: pay 1 water → Recruit 2 troops"
            ),
        ),
        "count_hasimir_fenring": LeaderFaceText(
            ability_text="Assassin: Whenever you trash a card: Gain 1 solari",
            signet_text=(
                "You may trash a card in your play area — or place a Spy on an"
                " Emperor observation post"
            ),
        ),
        "duncan_idaho": LeaderFaceText(
            ability_text=(
                "Ginaz Swordmaster: The Swordmaster board space costs you 2 less"
            ),
            signet_text=(
                "You may take the Agent you sent this turn and deploy it to the"
                " Conflict as a 2-strength unit that can't be retreated"
                " (3 strength with your Swordmaster)"
            ),
        ),
        "esmar_tuek": LeaderFaceText(
            ability_text=(
                "Tuek's Sietch: Whenever you send an Agent to Tuek's Sietch:"
                " Gain 1 solari. Whenever an opponent sends an Agent there:"
                " Draw 1 Intrigue card"
            ),
            signet_text=(
                "Place 1 bonus spice on Tuek's Sietch — or take 1 bonus spice"
                " from a Maker board space"
            ),
        ),
        "gaius_helen_mohiam": LeaderFaceText(
            ability_text=(
                "Clandestine: Each card you play has the Spy icon. Whenever you"
                " could recall a Spy to Gather Intelligence, you must"
            ),
            signet_text=(
                "Place a Spy on a Landsraad observation post — or pay 1 spice"
                " → Place a Spy"
            ),
        ),
        "piter_de_vries": LeaderFaceText(
            ability_text=(
                "Twisted Genius: Game start: shuffle the Twisted Intrigue deck"
                " face down near you. Round start: draw a Twisted Intrigue card"
                " (these count as Intrigue cards and can be stolen)"
            ),
            signet_text=(
                "Recruit 1 troop; you can't deploy this troop to the Conflict"
                " this turn"
            ),
        ),
        "steersman_y_rkoon": LeaderFaceText(
            ability_text=(
                "Strange Form: you start with no water and without Signet Ring"
                " in your deck. Hungry for Spice: whenever you gain 3 or more"
                " spice in a single turn: Draw 1 card"
            ),
            signet_text=(
                "Plot Course (no Signet Ring): at game start shuffle the"
                " Navigation cards, draw five and place four face down in"
                " order. Whenever you reach 2 Influence with a Faction, play"
                " the next Navigation card (from the left)"
            ),
        ),
        "kota_odax_of_ix": LeaderFaceText(
            ability_text=(
                "Secret Project: Game Start: Peek at the bottom Tech tile of each"
                " stack. Place one face down here. Whenever you could acquire a"
                " Tech tile, you may choose this one. It costs 1 spice less"
            ),
            signet_text=(
                "Gain 1 spice — or trash one of your Tech tiles → Draw 1 Intrigue"
                " card, Draw 1 card"
            ),
        ),
        "liet_kynes": LeaderFaceText(
            ability_text=(
                "Arrakis Planetologist: Ignore the Influence requirement of"
                " Sietch Tabr. You summon no sandworms; for each one you"
                " would, instead: you may trash a card, Gain 1 spice and"
                " Draw 1 Intrigue card (even under the Shield Wall)"
            ),
            signet_text=(
                "If you sent an Agent this turn to a Landsraad space and have"
                " 2 Emperor Influence: Gain 1 water; a City space: Gain 1"
                " solari; a Spice Trade space: Gain 1 spice"
            ),
        ),
    }
)
