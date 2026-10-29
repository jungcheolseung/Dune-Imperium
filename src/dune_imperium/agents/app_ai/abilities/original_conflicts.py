"""Ports of the app's ``ConflictAbilities.BaseSet.*`` classes.

The 18 Conflict cards of the original Dune: Imperium (``catalog.ORIGINAL_
CONFLICT_ARCHETYPES``) list three ability classes each, one per place
(``<Card>First/Second/ThirdAbility``, 54 in all), read from the P3d
decompilation (assets ``ghidra/p3d-types/<class>.c``) and confirmed in the
annotated disassembly (``dump/asm/worm-canis.dll/<class>.asm``);
``docs/app-ai-plan.md`` §12. Addresses are build
dad97e2021144d45b5b4f022e07bd3b3.

Every class derives straight from ``ConflictAbilities.ConflictAbility``
(``generic.ConflictAbility``) and, unlike an Uprising card, carries its own
rewards: no ``ConflictRewardArchetypes``, no ``GenericConflictAbility``.
``.ctor`` sets ``ConflictPlace`` (1, 2, 3), ``Cost`` is ``NoCost`` (but for
Machinations 1st and Terrible Purpose 1st, whose ``Cost`` asks for faction
or trash targets; our engine owns that legality), ``BeginExecution`` gains the
whole reward (and asks its choices, below). None overrides
``GetPossibleRewardVP``, so ``ConflictAbility::GetPossibleRewardVP`` @0x4b6ea00
answers (1st place: the card's ``VictoryPoints``). ``WormConflictPlayable::
ConflictValue`` @0x4829dc0 adds the ``ValueForPlayer`` of the three.

Each class's ``ValueForPlayer`` starts from ``WormAbilityDefinition::
ValueForPlayer`` (an empty summer) and adds the terms below in the app's
order (the sum is a float, so the order is kept). Prices are the profile's
(``GetVictoryPointValue``, ``GetSpiceValue`` ...); ``f64`` multipliers and
doublings (``addsd xmm0, xmm0``) are the app code's own literals.

The choices the app asks through its own evaluator (``Targets`` +
``Evaluate``, or the ``SelectFaction`` prompt valued by ``EvaluateFaction``):

- Skirmish C and D 1st, Cloak and Dagger 1st, Grand Vision 1st: one faction
  track, the best ``GetGainInfluenceValue(f, n)`` (``influence_track_
  answer``; ``evaluate`` or ``evaluate_faction``);
- Machinations 1st: two different tracks (``gain_any_two_evaluate``);
- Terrible Purpose 1st: the trash (``GetCardToTrash``, optional);
- Cloak and Dagger 3rd: one of two options; Battle for Arrakeen 2nd: two of
  three.

Request / answer encoding (``abilities/generic.py``): the candidates of a
prompt are ``request.infos[0]`` (``Kind.TRACK`` entities, ``Kind.CARD``
entities, or custom-choice ``options``); ``Answer.response`` holds one item
per target info, ``None`` is the untouched choice.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Request,
    port,
)
from dune_imperium.agents.app_ai.abilities.board import (
    _dsum,
    _math_max,
    gain_any_two_evaluate,
    gain_any_two_value,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    ConflictAbility,
    _targets,
    gain_any_influence_value,
)
from dune_imperium.agents.app_ai.choice import first_strictly_best
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_CA = "worm.canis.abilities.ConflictAbilities.BaseSet."


def _twice(price: float) -> float:
    """``addsd xmm0, xmm0``: a price counted twice."""

    return price + price


def _double_compare(a: float, b: float) -> int:
    """``Double.CompareTo``: ``a.CompareTo(b)`` (NaN sorts first)."""

    if a < b:
        return -1
    if a > b:
        return 1
    if a == b:
        return 0
    if a != a:
        return 0 if b != b else -1
    return 1


def dotnet_sort3(items: Sequence[tuple[float, int]]) -> list[tuple[float, int]]:
    """``List<(double, int)>.Sort`` of three elements with the comparison
    ``(x, y) => y.Item1.CompareTo(x.Item1)`` (best first).

    ``ArraySortHelper.IntroSort`` handles a partition of three with three
    ``SwapIfGreater(keys, comparer, i, j)`` calls: (0, 1), (0, 2), (1, 2),
    each swapping when ``comparer(keys[i], keys[j]) > 0``. That network is not
    stable: of equal values the later one can land first.
    """

    keys = list(items)
    if len(keys) != 3:
        raise ValueError("the app sorts exactly three options")
    for i, j in ((0, 1), (0, 2), (1, 2)):
        if _double_compare(keys[j][0], keys[i][0]) > 0:
            keys[i], keys[j] = keys[j], keys[i]
    return keys


def influence_track_answer(
    p: Profile, request: Request, amount: int, label: str
) -> Answer:
    """The "gain ``amount`` Influence with a faction of your choice" prompt of
    Skirmish C/D, Cloak and Dagger and Grand Vision (their ``Evaluate`` or
    ``EvaluateFaction``, the same code).

    For each ``WormFactionTrack`` target in target order (no shuffle):
    ``GetGainInfluenceValue(track.Faction, amount, -1, false)`` and
    ``UpdateSelectionTargets(sum, src, [track.id])``, which keeps the first
    strictly best (``first_strictly_best``; the first call always sticks). The
    House Hagal branch (``HagalMode == 1``) is unreachable.
    """

    scored = [
        (track, p.gain_influence_value(track.ref, amount, -1, False).sum)
        for track in _targets(request, Kind.TRACK)
    ]
    best = first_strictly_best(scored)
    if best is None:
        return Answer(0.0, None, f"{label} | no track")
    track, value = best
    return Answer(value, ((track.ref,),), f"{label} | {track.ref} | {value}")


# ===========================================================================
# The 18 cards, in the order of ``catalog.ORIGINAL_CONFLICT_ARCHETYPES``
# ===========================================================================

# -- Skirmish A --------------------------------------------------------


@port(_CA + "SkirmishAFirstAbility")
class SkirmishAFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SkirmishAFirstAbility``.

    ctor 0x4ba0a00: ``ConflictPlace`` 1. Skirmish A, first place: 1 VP.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba0c30."""

        v = Summer()
        v.add("Conflict SkirmishA First VP", p.victory_point_value(1))
        return v


@port(_CA + "SkirmishASecondAbility")
class SkirmishASecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SkirmishASecondAbility``.

    ctor 0x4ba11d0: ``ConflictPlace`` 2. Skirmish A, second place: 1 Water.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba13e0."""

        v = Summer()
        v.add("Conflict SkirmishA Second Water", p.water_value(1))
        return v


@port(_CA + "SkirmishAThirdAbility")
class SkirmishAThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SkirmishAThirdAbility``.

    ctor 0x4ba1930: ``ConflictPlace`` 3. Skirmish A, third place: 1 Spice.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba1b40."""

        v = Summer()
        v.add("Conflict SkirmishA Third Spice", p.spice_value(1))
        return v


# -- Skirmish B --------------------------------------------------------


@port(_CA + "SkirmishBFirstAbility")
class SkirmishBFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SkirmishBFirstAbility``.

    ctor 0x4ba2090: ``ConflictPlace`` 1. Skirmish B, first place: 1 VP.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba22c0."""

        v = Summer()
        v.add("Conflict SkirmishB First VP", p.victory_point_value(1))
        return v


@port(_CA + "SkirmishBSecondAbility")
class SkirmishBSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SkirmishBSecondAbility``.

    ctor 0x4ba2860: ``ConflictPlace`` 2. Skirmish B, second place: 2 Solari, then 1
    Intrigue.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba2a70."""

        v = Summer()
        v.add("Conflict SkirmishB Second Solari", p.solari_value(2))
        v.add("Conflict SkirmishB Second Intrigue", p.intrigue_value())
        return v


@port(_CA + "SkirmishBThirdAbility")
class SkirmishBThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SkirmishBThirdAbility``.

    ctor 0x4ba3150: ``ConflictPlace`` 3. Skirmish B, third place: 2 Solari.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba3360."""

        v = Summer()
        v.add("Conflict SkirmishB Third Solari", p.solari_value(2))
        return v


# -- Skirmish C --------------------------------------------------------


@port(_CA + "SkirmishCFirstAbility")
class SkirmishCFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SkirmishCFirstAbility``.

    ctor 0x4ba38b0: ``ConflictPlace`` 1. Skirmish C, first place: 1 Spice, then one
    Influence of any faction.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba3b80."""

        v = Summer()
        v.add("Conflict SkirmishC First Spice", p.spice_value(1))
        v.add("Conflict SkirmishC First Influence", gain_any_influence_value(p, 1).sum)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SkirmishCFirstAbility::Evaluate`` @0x4ba3d40.

        The "gain one Influence of your choice" prompt (``Targets`` @0x4ba39a0
        = ``MakeGainAnyFactionInfluenceTargeting``): ``GetGainInfluenceValue(
        track.Faction, 1)`` of every faction track in target order,
        ``UpdateSelectionTargets`` keeping the first strict maximum. Unlike
        ``GainAnyInfluenceAbility::Evaluate`` there is no +100 boost. The House
        Hagal branch (``HagalMode == 1``) is unreachable.
        """

        return influence_track_answer(p, request, 1, "SkirmishC First")


@port(_CA + "SkirmishCSecondAbility")
class SkirmishCSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SkirmishCSecondAbility``.

    ctor 0x4ba4a40: ``ConflictPlace`` 2. Skirmish C, second place: 2 Spice (the
    Spice price doubled).
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba4c50."""

        v = Summer()
        v.add("Conflict SkirmishC Second Spice", _twice(p.spice_value(1)))
        return v


@port(_CA + "SkirmishCThirdAbility")
class SkirmishCThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SkirmishCThirdAbility``.

    ctor 0x4ba51a0: ``ConflictPlace`` 3. Skirmish C, third place: 1 Spice.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba53b0."""

        v = Summer()
        v.add("Conflict SkirmishC Third Spice", p.spice_value(1))
        return v


# -- Skirmish D --------------------------------------------------------


@port(_CA + "SkirmishDFirstAbility")
class SkirmishDFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SkirmishDFirstAbility``.

    ctor 0x4ba5900: ``ConflictPlace`` 1. Skirmish D, first place: 2 Solari, then one
    Influence of any faction.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba5bd0."""

        v = Summer()
        v.add("Conflict SkirmishD First Solari", p.solari_value(2))
        v.add("Conflict SkirmishD First Influence", gain_any_influence_value(p, 1).sum)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SkirmishDFirstAbility::Evaluate`` @0x4ba5d90: the same code as
        ``SkirmishCFirstAbility::Evaluate`` (``Targets`` @0x4ba59f0)."""

        return influence_track_answer(p, request, 1, "SkirmishD First")


@port(_CA + "SkirmishDSecondAbility")
class SkirmishDSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SkirmishDSecondAbility``.

    ctor 0x4ba6980: ``ConflictPlace`` 2. Skirmish D, second place: 3 Solari.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba6b90."""

        v = Summer()
        v.add("Conflict SkirmishD Second Solari", p.solari_value(3))
        return v


@port(_CA + "SkirmishDThirdAbility")
class SkirmishDThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SkirmishDThirdAbility``.

    ctor 0x4ba70e0: ``ConflictPlace`` 3. Skirmish D, third place: 2 Solari.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba72f0."""

        v = Summer()
        v.add("Conflict SkirmishD Third Solari", p.solari_value(2))
        return v


# -- Cloak and Dagger --------------------------------------------------


@port(_CA + "CloakAndDaggerFirstAbility")
class CloakAndDaggerFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.CloakAndDaggerFirstAbility``.

    ctor 0x4b8e600: ``ConflictPlace`` 1. Cloak and Dagger, first place: one
    Influence of any faction, then 2 Intrigue (the Intrigue price doubled).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b8e830."""

        v = Summer()
        v.add(
            "Conflict Cloak and Dagger First Influence",
            gain_any_influence_value(p, 1).sum,
        )
        v.add("Conflict Cloak and Dagger First Intrigue", _twice(p.intrigue_value()))
        return v

    def evaluate_faction(self, p: Profile, request: Request) -> Answer:
        """``CloakAndDaggerFirstAbility::EvaluateFaction`` @0x4b8e9f0.

        The ``SelectFaction`` prompt of its ``BeginExecution`` (after the two
        Intrigue cards), valued by this method instead of ``Evaluate``: it
        builds its own ``WormAIChoiceContext`` and then does what
        ``SkirmishCFirstAbility::Evaluate`` does, for 1 Influence.
        """

        return influence_track_answer(p, request, 1, "Cloak and Dagger First")


@port(_CA + "CloakAndDaggerSecondAbility")
class CloakAndDaggerSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.CloakAndDaggerSecondAbility``.

    ctor 0x4b90080: ``ConflictPlace`` 2. Cloak and Dagger, second place: 1 Spice,
    then 1 Intrigue.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b90290."""

        v = Summer()
        v.add("Conflict Cloak and Dagger Second Spice", p.spice_value(1))
        v.add("Conflict Cloak and Dagger Second Intrigue", p.intrigue_value())
        return v


@port(_CA + "CloakAndDaggerThirdAbility")
class CloakAndDaggerThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.CloakAndDaggerThirdAbility``.

    ctor 0x4b90970: ``ConflictPlace`` 3. Cloak and Dagger, third place: the better
    of 1 Intrigue and 1 Spice (the printed -OR-).
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b90c60."""

        v = Summer()
        v.add(
            "Conflict Cloak and Dagger Third Resource",
            _math_max(p.intrigue_value(), p.spice_value(1)),
        )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CloakAndDaggerThirdAbility::Evaluate`` @0x4b90e20.

        The printed "-OR-" is a custom choice of two options (``Targets``
        @0x4b90a60; ``BeginExecution`` draws the Intrigue for answer 0 and
        gains the Spice for answer 1): ``UpdateSelectionResponses`` first with
        ``IntrigueValue`` for ``IntTargetResponse(0)``, then with
        ``GetSpiceValue(1)`` for ``IntTargetResponse(1)``, each replacing the
        stored answer only when strictly better (a tie keeps the Intrigue).
        """

        best = first_strictly_best([(0, p.intrigue_value()), (1, p.spice_value(1))])
        assert best is not None
        option, value = best
        return Answer(value, ((option,),), f"Cloak and Dagger Third | option {option}")


# -- Desert Power ------------------------------------------------------


@port(_CA + "DesertPowerFirstAbility")
class DesertPowerFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.DesertPowerFirstAbility``.

    ctor 0x4b91bd0: ``ConflictPlace`` 1. Desert Power, first place: 1 VP, then 1
    Water.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b91e00."""

        v = Summer()
        v.add("Conflict Desert Power First VP", p.victory_point_value(1))
        v.add("Conflict Desert Power First Water", p.water_value(1))
        return v


@port(_CA + "DesertPowerSecondAbility")
class DesertPowerSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.DesertPowerSecondAbility``.

    ctor 0x4b92540: ``ConflictPlace`` 2. Desert Power, second place: 1 Spice, then 1
    Water.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b92750."""

        v = Summer()
        v.add("Conflict Desert Power Second Spice", p.spice_value(1))
        v.add("Conflict Desert Power Second Water", p.water_value(1))
        return v


@port(_CA + "DesertPowerThirdAbility")
class DesertPowerThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.DesertPowerThirdAbility``.

    ctor 0x4b92e40: ``ConflictPlace`` 3. Desert Power, third place: 1 Spice.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b93050."""

        v = Summer()
        v.add("Conflict Desert Power Third Spice", p.spice_value(1))
        return v


# -- Guild Bank Raid ---------------------------------------------------


@port(_CA + "GuildBankRaidFirstAbility")
class GuildBankRaidFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.GuildBankRaidFirstAbility``.

    ctor 0x4b959a0: ``ConflictPlace`` 1. Guild Bank Raid, first place: 6 Solari.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b95bb0."""

        v = Summer()
        v.add("Conflict Guild Bank Raid First Solari", p.solari_value(6))
        return v


@port(_CA + "GuildBankRaidSecondAbility")
class GuildBankRaidSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.GuildBankRaidSecondAbility``.

    ctor 0x4b96100: ``ConflictPlace`` 2. Guild Bank Raid, second place: 4 Solari.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b96310."""

        v = Summer()
        v.add("Conflict Guild Bank Raid Second Solari", p.solari_value(4))
        return v


@port(_CA + "GuildBankRaidThirdAbility")
class GuildBankRaidThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.GuildBankRaidThirdAbility``.

    ctor 0x4b96860: ``ConflictPlace`` 3. Guild Bank Raid, third place: 2 Solari.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b96a70."""

        v = Summer()
        v.add("Conflict Guild Bank Raid Third Solari", p.solari_value(2))
        return v


# -- Machinations ------------------------------------------------------


@port(_CA + "MachinationsFirstAbility")
class MachinationsFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.MachinationsFirstAbility``.

    ctor 0x4b96fc0: ``ConflictPlace`` 1. Machinations, first place: the two best
    single Influence gains (``gain_any_two_value``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b972c0."""

        return gain_any_two_value(p, "Conflict Machinations First Influence")

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``MachinationsFirstAbility::Evaluate`` @0x4b977b0: the code of
        ``GainAnyTwoInfluenceConflictAbility::Evaluate`` (``gain_any_two_
        evaluate``): the two best tracks, value ``Math.Max(0.5, sum)``
        (``Targets`` @0x4b970b0 asks for exactly two)."""

        return gain_any_two_evaluate(p, request, "Machinations First")


@port(_CA + "MachinationsSecondAbility")
class MachinationsSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.MachinationsSecondAbility``.

    ctor 0x4b99230: ``ConflictPlace`` 2. Machinations, second place: 1 Water, then 2
    Solari.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b99440."""

        v = Summer()
        v.add("Conflict Machinations Second Water", p.water_value(1))
        v.add("Conflict Machinations Second Solari", p.solari_value(2))
        return v


@port(_CA + "MachinationsThirdAbility")
class MachinationsThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.MachinationsThirdAbility``.

    ctor 0x4b99b30: ``ConflictPlace`` 3. Machinations, third place: 1 Water.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b99d40."""

        v = Summer()
        v.add("Conflict Machinations Third Water", p.water_value(1))
        return v


# -- Raid Stockpiles ---------------------------------------------------


@port(_CA + "RaidStockpilesFirstAbility")
class RaidStockpilesFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.RaidStockpilesFirstAbility``.

    ctor 0x4b9a290: ``ConflictPlace`` 1. Raid Stockpiles, first place: 3 Spice (the
    Spice price times 3.0), then 1 Intrigue.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b9a4a0."""

        v = Summer()
        v.add("Conflict Raid Stockpiles First Spice", p.spice_value(1) * 3.0)
        v.add("Conflict Raid Stockpiles First Intrigue", p.intrigue_value())
        return v


@port(_CA + "RaidStockpilesSecondAbility")
class RaidStockpilesSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.RaidStockpilesSecondAbility``.

    ctor 0x4b9ab90: ``ConflictPlace`` 2. Raid Stockpiles, second place: 2 Spice (the
    Spice price doubled).
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b9ada0."""

        v = Summer()
        v.add("Conflict Raid Stockpiles Second Spice", _twice(p.spice_value(1)))
        return v


@port(_CA + "RaidStockpilesThirdAbility")
class RaidStockpilesThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.RaidStockpilesThirdAbility``.

    ctor 0x4b9b2f0: ``ConflictPlace`` 3. Raid Stockpiles, third place: 1 Spice.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b9b500."""

        v = Summer()
        v.add("Conflict Raid Stockpiles Third Spice", p.spice_value(1))
        return v


# -- Secure Imperial Basin ---------------------------------------------


@port(_CA + "SecureImperialBasinFirstAbility")
class SecureImperialBasinFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SecureImperialBasinFirstAbility``.

    ctor 0x4b9ba50: ``ConflictPlace`` 1. Secure Imperial Basin, first place: 1 VP,
    then the Spice control of the Basin (``ControlSpiceValue``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b9bca0."""

        v = Summer()
        v.add("Conflict Secure Imperial Basin First VP", p.victory_point_value(1))
        v.add(
            "Conflict Secure Imperial Basin First Gain Control", p.control_spice_value()
        )
        return v


@port(_CA + "SecureImperialBasinSecondAbility")
class SecureImperialBasinSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SecureImperialBasinSecondAbility``.

    ctor 0x4b9c5a0: ``ConflictPlace`` 2. Secure Imperial Basin, second place: 2
    Water (the Water price doubled).
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b9c7b0."""

        v = Summer()
        v.add("Conflict Secure Imperial Basin Second Water", _twice(p.water_value(1)))
        return v


@port(_CA + "SecureImperialBasinThirdAbility")
class SecureImperialBasinThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SecureImperialBasinThirdAbility``.

    ctor 0x4b9cd00: ``ConflictPlace`` 3. Secure Imperial Basin, third place: 1
    Water.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b9cf10."""

        v = Summer()
        v.add("Conflict Secure Imperial Basin Third Water", p.water_value(1))
        return v


# -- Siege of Arrakeen -------------------------------------------------


@port(_CA + "SiegeOfArrakeenFirstAbility")
class SiegeOfArrakeenFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SiegeOfArrakeenFirstAbility``.

    ctor 0x4b9d460: ``ConflictPlace`` 1. Siege of Arrakeen, first place: 1 VP, then
    the Solari control of Arrakeen (``ControlSolariValue``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b9d6b0."""

        v = Summer()
        v.add("Conflict Siege Of Arrakeen First VP", p.victory_point_value(1))
        v.add("Conflict Siege Of Arrakeen First Gain Control", p.control_solari_value())
        return v


@port(_CA + "SiegeOfArrakeenSecondAbility")
class SiegeOfArrakeenSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SiegeOfArrakeenSecondAbility``.

    ctor 0x4b9dfb0: ``ConflictPlace`` 2. Siege of Arrakeen, second place: 4 Solari.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b9e1c0."""

        v = Summer()
        v.add("Conflict Siege Of Arrakeen Second Solari", p.solari_value(4))
        return v


@port(_CA + "SiegeOfArrakeenThirdAbility")
class SiegeOfArrakeenThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SiegeOfArrakeenThirdAbility``.

    ctor 0x4b9e710: ``ConflictPlace`` 3. Siege of Arrakeen, third place: 2 Solari.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b9e920."""

        v = Summer()
        v.add("Conflict Siege Of Arrakeen Third Solari", p.solari_value(2))
        return v


# -- Siege of Carthag --------------------------------------------------


@port(_CA + "SiegeOfCarthagFirstAbility")
class SiegeOfCarthagFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SiegeOfCarthagFirstAbility``.

    ctor 0x4b9ee70: ``ConflictPlace`` 1. Siege of Carthag, first place: 1 VP, then
    the Solari control of Carthag (``ControlSolariValue``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b9f080."""

        v = Summer()
        v.add("Conflict Siege Of Carthag First VP", p.victory_point_value(1))
        v.add("Conflict Siege Of Carthag First Gain Control", p.control_solari_value())
        return v


@port(_CA + "SiegeOfCarthagSecondAbility")
class SiegeOfCarthagSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SiegeOfCarthagSecondAbility``.

    ctor 0x4b9f9b0: ``ConflictPlace`` 2. Siege of Carthag, second place: 2 Solari,
    then 1 Intrigue (the app prices 2 Solari although its ``BeginExecution`` gains 1
    Spice: a valuation slip kept).
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b9fbc0."""

        v = Summer()
        v.add("Conflict Siege Of Carthag Second Solari", p.solari_value(2))
        v.add("Conflict Siege Of Carthag Second Intrigue", p.intrigue_value())
        return v


@port(_CA + "SiegeOfCarthagThirdAbility")
class SiegeOfCarthagThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SiegeOfCarthagThirdAbility``.

    ctor 0x4ba02a0: ``ConflictPlace`` 3. Siege of Carthag, third place: 1 Spice.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba04b0."""

        v = Summer()
        v.add("Conflict Siege Of Carthag Third Spice", p.spice_value(1))
        return v


# -- Sort Through the Chaos --------------------------------------------


@port(_CA + "SortThroughTheChaosFirstAbility")
class SortThroughTheChaosFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SortThroughTheChaosFirstAbility``.

    ctor 0x4ba7840: ``ConflictPlace`` 1. Sort Through the Chaos, first place: 1
    Intrigue, the Mentat, 2 Solari.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba7a80."""

        v = Summer()
        v.add("Conflict Sort Through the Chaos First Intrigue", p.intrigue_value())
        v.add("Conflict Sort Through the Chaos First Mentat", p.mentat_value())
        v.add("Conflict Sort Through the Chaos First Solari", p.solari_value(2))
        return v


@port(_CA + "SortThroughTheChaosSecondAbility")
class SortThroughTheChaosSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SortThroughTheChaosSecondAbility``.

    ctor 0x4ba8700: ``ConflictPlace`` 2. Sort Through the Chaos, second place: 1
    Intrigue, 2 Solari.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba8910."""

        v = Summer()
        v.add("Conflict Sort Through the Chaos Second Intrigue", p.intrigue_value())
        v.add("Conflict Sort Through the Chaos Second Solari", p.solari_value(2))
        return v


@port(_CA + "SortThroughTheChaosThirdAbility")
class SortThroughTheChaosThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.SortThroughTheChaosThirdAbility``.

    ctor 0x4ba9000: ``ConflictPlace`` 3. Sort Through the Chaos, third place: 2
    Solari.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba9210."""

        v = Summer()
        v.add("Conflict Sort Through the Chaos Third Solari", p.solari_value(2))
        return v


# -- Terrible Purpose --------------------------------------------------


@port(_CA + "TerriblePurposeFirstAbility")
class TerriblePurposeFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.TerriblePurposeFirstAbility``.

    ctor 0x4ba9760: ``ConflictPlace`` 1. Terrible Purpose, first place: 1 VP, the
    trash (``TrashCardValue``, ``TrashMod``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4ba9a50."""

        v = Summer()
        v.add("Conflict Terrible Purpose First VP", p.victory_point_value(1))
        v.add("Conflict Terrible Purpose First Trash", p.trash_card_value())
        v.add("Conflict Terrible Purpose First Trash Specific", p.trash_mod())
        return v

    #: ``f64=1.0`` of ``Evaluate``: the ``minTrashValue`` of ``GetCardToTrash``.
    MIN_TRASH_VALUE: ClassVar[float] = 1.0
    #: ``f64=10.0`` of ``Evaluate``: added to the trash score, or the value of
    #: trashing nothing.
    TRASH_BOOST: ClassVar[float] = 10.0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TerriblePurposeFirstAbility::Evaluate`` @0x4ba9c20.

        ``GetCardToTrash(targets, 1.0)`` over the ``FindTrashTargets`` list of
        ``Targets`` @0x4ba9850: with a card, its score ``+ 10.0`` (``addsd``)
        names that card; without one the answer is ``10.0`` with an empty
        target array (the black-X trash is optional): the AI always answers,
        and trashes only a card ``GetCardToTrash`` accepts.
        """

        card, score = p.card_to_trash(
            _targets(request, Kind.CARD), self.MIN_TRASH_VALUE
        )
        if card is None:
            return Answer(self.TRASH_BOOST, ((),), "Terrible Purpose First | nothing")
        return Answer(
            score + self.TRASH_BOOST,
            ((card.ref,),),
            f"Terrible Purpose First | trashing: {card.ref}",
        )


@port(_CA + "TerriblePurposeSecondAbility")
class TerriblePurposeSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.TerriblePurposeSecondAbility``.

    ctor 0x4baa7e0: ``ConflictPlace`` 2. Terrible Purpose, second place: 1 Water,
    then 1 Spice.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4baa9f0."""

        v = Summer()
        v.add("Conflict Terrible Purpose Second Water", p.water_value(1))
        v.add("Conflict Terrible Purpose Second Spice", p.spice_value(1))
        return v


@port(_CA + "TerriblePurposeThirdAbility")
class TerriblePurposeThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.TerriblePurposeThirdAbility``.

    ctor 0x4bab0e0: ``ConflictPlace`` 3. Terrible Purpose, third place: 1 Spice.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4bab2f0."""

        v = Summer()
        v.add("Conflict Terrible Purpose Third Spice", p.spice_value(1))
        return v


# -- Battle for Arrakeen -----------------------------------------------


@port(_CA + "BattleForArrakeenFirstAbility")
class BattleForArrakeenFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.BattleForArrakeenFirstAbility``.

    ctor 0x4b87e20: ``ConflictPlace`` 1. Battle for Arrakeen, first place: 2 VP,
    then the Solari control of Arrakeen (``ControlSolariValue``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b88070."""

        v = Summer()
        v.add("Conflict Battle of Arrakeen First VP", p.victory_point_value(2))
        v.add(
            "Conflict Battle of Arrakeen First Gain Control", p.control_solari_value()
        )
        return v


@port(_CA + "BattleForArrakeenSecondAbility")
class BattleForArrakeenSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.BattleForArrakeenSecondAbility``.

    ctor 0x4b88970: ``ConflictPlace`` 2. Battle for Arrakeen, second place: the best
    of 1 Intrigue, 2 Spice and 3 Solari (the printed "choose two").
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b88c60."""

        v = Summer()
        v.add(
            "Conflict Battle of Arrakeen Second Best Resource",
            _math_max(
                p.intrigue_value(),
                _math_max(_twice(p.spice_value(1)), p.solari_value(3)),
            ),
        )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BattleForArrakeenSecondAbility::Evaluate`` @0x4b88e50.

        The printed "choose two" is a custom choice of three options
        (``Targets`` @0x4b88a60: 0 draws 1 Intrigue, 1 gains 2 Spice, 2 gains
        3 Solari). The list ``[(IntrigueValue, 0), (2 * GetSpiceValue(1), 1),
        (GetSolariValue(3), 2)]`` is sorted with ``List.Sort`` and the
        comparison ``b.CompareTo(a)`` (``<Evaluate>b__10_0``): best first, by
        .NET's three-element sorting network (``dotnet_sort3``, not stable).
        The first two options answer (``IntListTargetResponse``, in that
        order) at the sum of their values (``Take(2)`` and ``<Evaluate>b__10_2``).
        """

        options = [
            (p.intrigue_value(), 0),
            (_twice(p.spice_value(1)), 1),
            (p.solari_value(3), 2),
        ]
        first, second, _ = dotnet_sort3(options)
        value = _dsum([first[0], second[0]])
        return Answer(
            value,
            ((first[1], second[1]),),
            f"Battle For Arrakeen Second | options {first[1]}, {second[1]}",
        )


@port(_CA + "BattleForArrakeenThirdAbility")
class BattleForArrakeenThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.BattleForArrakeenThirdAbility``.

    ctor 0x4b8a720: ``ConflictPlace`` 3. Battle for Arrakeen, third place: 2 Solari,
    then 1 Intrigue.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b8a930."""

        v = Summer()
        v.add("Conflict Battle of Arrakeen Third Solari", p.solari_value(2))
        v.add("Conflict Battle of Arrakeen Third Intrigue", p.intrigue_value())
        return v


# -- Battle for Carthag ------------------------------------------------


@port(_CA + "BattleForCarthagFirstAbility")
class BattleForCarthagFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.BattleForCarthagFirstAbility``.

    ctor 0x4b8b010: ``ConflictPlace`` 1. Battle for Carthag, first place: 2 VP, then
    the Solari control of Carthag (``ControlSolariValue``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b8b260."""

        v = Summer()
        v.add("Conflict Battle of Carthag First VP", p.victory_point_value(2))
        v.add("Conflict Battle of Carthag First Gain Control", p.control_solari_value())
        return v


@port(_CA + "BattleForCarthagSecondAbility")
class BattleForCarthagSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.BattleForCarthagSecondAbility``.

    ctor 0x4b8bb60: ``ConflictPlace`` 2. Battle for Carthag, second place: 3 Spice
    (the Spice price times 3.0), then 1 Intrigue.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b8bd70."""

        v = Summer()
        v.add("Conflict Battle of Carthag Second Spice", p.spice_value(1) * 3.0)
        v.add("Conflict Battle of Carthag Second Intrigue", p.intrigue_value())
        return v


@port(_CA + "BattleForCarthagThirdAbility")
class BattleForCarthagThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.BattleForCarthagThirdAbility``.

    ctor 0x4b8c460: ``ConflictPlace`` 3. Battle for Carthag, third place: 3 Spice
    (the Spice price times 3.0).
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b8c670."""

        v = Summer()
        v.add("Conflict Battle of Carthag Third Spice", p.spice_value(1) * 3.0)
        return v


# -- Battle for Imperial Basin -----------------------------------------


@port(_CA + "BattleForImperialBasinFirstAbility")
class BattleForImperialBasinFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.BattleForImperialBasinFirstAbility``.

    ctor 0x4b8cbd0: ``ConflictPlace`` 1. Battle for Imperial Basin, first place: 2
    VP, then the Spice control of the Basin (``ControlSpiceValue``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b8ce20."""

        v = Summer()
        v.add("Conflict Battle of Imperial Basin First VP", p.victory_point_value(2))
        v.add(
            "Conflict Battle of Imperial Basin First Gain Control",
            p.control_spice_value(),
        )
        return v


@port(_CA + "BattleForImperialBasinSecondAbility")
class BattleForImperialBasinSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.BattleForImperialBasinSecondAbility``.

    ctor 0x4b8d720: ``ConflictPlace`` 2. Battle for Imperial Basin, second place: 5
    Spice (the Spice price times 5.0).
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b8d930."""

        v = Summer()
        v.add("Conflict Battle of Imperial Basin Second Spice", p.spice_value(1) * 5.0)
        return v


@port(_CA + "BattleForImperialBasinThirdAbility")
class BattleForImperialBasinThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.BattleForImperialBasinThirdAbility``.

    ctor 0x4b8de90: ``ConflictPlace`` 3. Battle for Imperial Basin, third place: 3
    Spice (the Spice price times 3.0).
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b8e0a0."""

        v = Summer()
        v.add("Conflict Battle of Imperial Basin Third Spice", p.spice_value(1) * 3.0)
        return v


# -- Grand Vision ------------------------------------------------------


@port(_CA + "GrandVisionFirstAbility")
class GrandVisionFirstAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.GrandVisionFirstAbility``.

    ctor 0x4b935a0: ``ConflictPlace`` 1. Grand Vision, first place: two Influence
    with one faction (``GetGainInfluenceValue(None, 2)``), then 1 Intrigue.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b937d0."""

        v = Summer()
        v.add(
            "Conflict Grand Vision First Influence", gain_any_influence_value(p, 2).sum
        )
        v.add("Conflict Grand Vision First Intrigue", p.intrigue_value())
        return v

    def evaluate_faction(self, p: Profile, request: Request) -> Answer:
        """``GrandVisionFirstAbility::EvaluateFaction`` @0x4b93990.

        The ``SelectFaction`` prompt of its ``BeginExecution``
        (``GainFactionInfluence(faction, 2)``): the same code as Cloak and
        Dagger's, but ``GetGainInfluenceValue(faction, 2)``.
        """

        return influence_track_answer(p, request, 2, "Grand Vision First")


@port(_CA + "GrandVisionSecondAbility")
class GrandVisionSecondAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.GrandVisionSecondAbility``.

    ctor 0x4b94930: ``ConflictPlace`` 2. Grand Vision, second place: 3 Spice (the
    Spice price times 3.0), then 1 Intrigue.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b94b40."""

        v = Summer()
        v.add("Conflict Grand Vision Second Spice", p.spice_value(1) * 3.0)
        v.add("Conflict Grand Vision Second Intrigue", p.intrigue_value())
        return v


@port(_CA + "GrandVisionThirdAbility")
class GrandVisionThirdAbility(ConflictAbility):
    """``ConflictAbilities.BaseSet.GrandVisionThirdAbility``.

    ctor 0x4b95230: ``ConflictPlace`` 3. Grand Vision, third place: 3 Spice (the
    Spice price times 3.0).
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4b95440."""

        v = Summer()
        v.add("Conflict Grand Vision Third Spice", p.spice_value(1) * 3.0)
        return v


#: The place abilities whose own prompt picks one faction track, with the
#: Influence they gain: ``evaluate`` (``Targets`` +
#: ``MakeGainAnyFactionInfluenceTargeting``) of Skirmish C/D, ``evaluate_
#: faction`` (the ``SelectFaction`` prompt) of Cloak and Dagger / Grand Vision.
TRACK_CHOICE_ABILITIES: tuple[type[ConflictAbility], ...] = (
    SkirmishCFirstAbility,
    SkirmishDFirstAbility,
    CloakAndDaggerFirstAbility,
    GrandVisionFirstAbility,
)


def track_choice_answer(
    ability: ConflictAbility, p: Profile, request: Request
) -> Answer | None:
    """The answer of a ``TRACK_CHOICE_ABILITIES`` ability to its prompt (its
    ``Evaluate`` or ``EvaluateFaction``), None for any other ability."""

    if isinstance(ability, SkirmishCFirstAbility | SkirmishDFirstAbility):
        return ability.evaluate(p, request)
    if isinstance(ability, CloakAndDaggerFirstAbility | GrandVisionFirstAbility):
        return ability.evaluate_faction(p, request)
    return None
