"""Ports of the app's ``ConflictAbilities`` classes of the original game.

The 18 Conflict cards of the original Dune: Imperium (``catalog.ORIGINAL_
CONFLICT_ARCHETYPES``) list three ability classes each, one per place
(``<Card>First/Second/ThirdAbility``, 54 in all); each follows the app's AI for that
class, and the detailed notes are kept privately (``docs/app-ai-plan.md`` §12).

Every class derives straight from ``ConflictAbilities.ConflictAbility``
(``generic.ConflictAbility``) and, unlike an Uprising card, carries its own rewards: no
``ConflictRewardArchetypes``, no ``GenericConflictAbility``. constructor sets
``ConflictPlace`` (1, 2, 3), ``Cost`` is ``NoCost`` (but for Machinations 1st and
Terrible Purpose 1st, whose ``Cost`` asks for faction or trash targets; our engine owns
that legality), ``BeginExecution`` gains the whole reward (and asks its choices, below).
None overrides ``GetPossibleRewardVP``, so ``ConflictAbility.GetPossibleRewardVP``
answers (1st place: the card's ``VictoryPoints``). ``ConflictPlayable.ConflictValue``
adds the ``ValueForPlayer`` of the three.

Each class's ``ValueForPlayer`` starts from ``AbilityDefinition.ValueForPlayer`` (an
empty summer) and adds the terms below in the app's order (the sum is a float, so the
order is kept). Prices are the profile's (``GetVictoryPointValue``, ``GetSpiceValue``
...); ``f64`` multipliers and doublings are the app's own literals.

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

_CA = "ability.conflict.original."


def _twice(price: float) -> float:
    """a price counted twice."""

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

    For each ``FactionTrack`` target in target order (no shuffle):
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


@port(_CA + "skirmish_a_first")
class SkirmishAFirstAbility(ConflictAbility):
    """``ability.conflict.original.skirmish_a_first``.

    constructor: ``ConflictPlace`` 1. Skirmish A, first place: 1 VP.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict SkirmishA First VP", p.victory_point_value(1))
        return v


@port(_CA + "skirmish_a_second")
class SkirmishASecondAbility(ConflictAbility):
    """``ability.conflict.original.skirmish_a_second``.

    constructor: ``ConflictPlace`` 2. Skirmish A, second place: 1 Water.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict SkirmishA Second Water", p.water_value(1))
        return v


@port(_CA + "skirmish_a_third")
class SkirmishAThirdAbility(ConflictAbility):
    """``ability.conflict.original.skirmish_a_third``.

    constructor: ``ConflictPlace`` 3. Skirmish A, third place: 1 Spice.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict SkirmishA Third Spice", p.spice_value(1))
        return v


# -- Skirmish B --------------------------------------------------------


@port(_CA + "skirmish_b_first")
class SkirmishBFirstAbility(ConflictAbility):
    """``ability.conflict.original.skirmish_b_first``.

    constructor: ``ConflictPlace`` 1. Skirmish B, first place: 1 VP.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict SkirmishB First VP", p.victory_point_value(1))
        return v


@port(_CA + "skirmish_b_second")
class SkirmishBSecondAbility(ConflictAbility):
    """``ability.conflict.original.skirmish_b_second``.

    constructor: ``ConflictPlace`` 2. Skirmish B, second place: 2 Solari, then 1
    Intrigue.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict SkirmishB Second Solari", p.solari_value(2))
        v.add("Conflict SkirmishB Second Intrigue", p.intrigue_value())
        return v


@port(_CA + "skirmish_b_third")
class SkirmishBThirdAbility(ConflictAbility):
    """``ability.conflict.original.skirmish_b_third``.

    constructor: ``ConflictPlace`` 3. Skirmish B, third place: 2 Solari.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict SkirmishB Third Solari", p.solari_value(2))
        return v


# -- Skirmish C --------------------------------------------------------


@port(_CA + "skirmish_c_first")
class SkirmishCFirstAbility(ConflictAbility):
    """``ability.conflict.original.skirmish_c_first``.

    constructor: ``ConflictPlace`` 1. Skirmish C, first place: 1 Spice, then one
    Influence of any faction.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict SkirmishC First Spice", p.spice_value(1))
        v.add("Conflict SkirmishC First Influence", gain_any_influence_value(p, 1).sum)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SkirmishCFirstAbility.Evaluate``.

        The "gain one Influence of your choice" prompt (``Targets``
        = ``MakeGainAnyFactionInfluenceTargeting``): ``GetGainInfluenceValue(
        track.Faction, 1)`` of every faction track in target order,
        ``UpdateSelectionTargets`` keeping the first strict maximum. Unlike
        ``GainAnyInfluenceAbility.Evaluate`` there is no +100 boost. The House
        Hagal branch (``HagalMode == 1``) is unreachable.
        """

        return influence_track_answer(p, request, 1, "SkirmishC First")


@port(_CA + "skirmish_c_second")
class SkirmishCSecondAbility(ConflictAbility):
    """``ability.conflict.original.skirmish_c_second``.

    constructor: ``ConflictPlace`` 2. Skirmish C, second place: 2 Spice (the Spice price
    doubled).
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict SkirmishC Second Spice", _twice(p.spice_value(1)))
        return v


@port(_CA + "skirmish_c_third")
class SkirmishCThirdAbility(ConflictAbility):
    """``ability.conflict.original.skirmish_c_third``.

    constructor: ``ConflictPlace`` 3. Skirmish C, third place: 1 Spice.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict SkirmishC Third Spice", p.spice_value(1))
        return v


# -- Skirmish D --------------------------------------------------------


@port(_CA + "skirmish_d_first")
class SkirmishDFirstAbility(ConflictAbility):
    """``ability.conflict.original.skirmish_d_first``.

    constructor: ``ConflictPlace`` 1. Skirmish D, first place: 2 Solari, then one
    Influence of any faction.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict SkirmishD First Solari", p.solari_value(2))
        v.add("Conflict SkirmishD First Influence", gain_any_influence_value(p, 1).sum)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SkirmishDFirstAbility.Evaluate``: the same code as
        ``SkirmishCFirstAbility.Evaluate`` (``Targets``)."""

        return influence_track_answer(p, request, 1, "SkirmishD First")


@port(_CA + "skirmish_d_second")
class SkirmishDSecondAbility(ConflictAbility):
    """``ability.conflict.original.skirmish_d_second``.

    constructor: ``ConflictPlace`` 2. Skirmish D, second place: 3 Solari.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict SkirmishD Second Solari", p.solari_value(3))
        return v


@port(_CA + "skirmish_d_third")
class SkirmishDThirdAbility(ConflictAbility):
    """``ability.conflict.original.skirmish_d_third``.

    constructor: ``ConflictPlace`` 3. Skirmish D, third place: 2 Solari.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict SkirmishD Third Solari", p.solari_value(2))
        return v


# -- Cloak and Dagger --------------------------------------------------


@port(_CA + "cloak_and_dagger_first")
class CloakAndDaggerFirstAbility(ConflictAbility):
    """``ability.conflict.original.cloak_and_dagger_first``.

    constructor: ``ConflictPlace`` 1. Cloak and Dagger, first place: one Influence of
    any faction, then 2 Intrigue (the Intrigue price doubled).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add(
            "Conflict Cloak and Dagger First Influence",
            gain_any_influence_value(p, 1).sum,
        )
        v.add("Conflict Cloak and Dagger First Intrigue", _twice(p.intrigue_value()))
        return v

    def evaluate_faction(self, p: Profile, request: Request) -> Answer:
        """``CloakAndDaggerFirstAbility.EvaluateFaction``.

        The ``SelectFaction`` prompt of its ``BeginExecution`` (after the two
        Intrigue cards), valued by this method instead of ``Evaluate``: it
        builds its own ``AIChoiceContext`` and then does what
        ``SkirmishCFirstAbility.Evaluate`` does, for 1 Influence.
        """

        return influence_track_answer(p, request, 1, "Cloak and Dagger First")


@port(_CA + "cloak_and_dagger_second")
class CloakAndDaggerSecondAbility(ConflictAbility):
    """``ability.conflict.original.cloak_and_dagger_second``.

    constructor: ``ConflictPlace`` 2. Cloak and Dagger, second place: 1 Spice, then 1
    Intrigue.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Cloak and Dagger Second Spice", p.spice_value(1))
        v.add("Conflict Cloak and Dagger Second Intrigue", p.intrigue_value())
        return v


@port(_CA + "cloak_and_dagger_third")
class CloakAndDaggerThirdAbility(ConflictAbility):
    """``ability.conflict.original.cloak_and_dagger_third``.

    constructor: ``ConflictPlace`` 3. Cloak and Dagger, third place: the better of 1
    Intrigue and 1 Spice (the printed -OR-).
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add(
            "Conflict Cloak and Dagger Third Resource",
            _math_max(p.intrigue_value(), p.spice_value(1)),
        )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CloakAndDaggerThirdAbility.Evaluate``.

        The printed "-OR-" is a custom choice of two options (``Targets``
; ``BeginExecution`` draws the Intrigue for answer 0 and
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


@port(_CA + "desert_power_first")
class DesertPowerFirstAbility(ConflictAbility):
    """``ability.conflict.original.desert_power_first``.

    constructor: ``ConflictPlace`` 1. Desert Power, first place: 1 VP, then 1 Water.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Desert Power First VP", p.victory_point_value(1))
        v.add("Conflict Desert Power First Water", p.water_value(1))
        return v


@port(_CA + "desert_power_second")
class DesertPowerSecondAbility(ConflictAbility):
    """``ability.conflict.original.desert_power_second``.

    constructor: ``ConflictPlace`` 2. Desert Power, second place: 1 Spice, then 1 Water.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Desert Power Second Spice", p.spice_value(1))
        v.add("Conflict Desert Power Second Water", p.water_value(1))
        return v


@port(_CA + "desert_power_third")
class DesertPowerThirdAbility(ConflictAbility):
    """``ability.conflict.original.desert_power_third``.

    constructor: ``ConflictPlace`` 3. Desert Power, third place: 1 Spice.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Desert Power Third Spice", p.spice_value(1))
        return v


# -- Guild Bank Raid ---------------------------------------------------


@port(_CA + "guild_bank_raid_first")
class GuildBankRaidFirstAbility(ConflictAbility):
    """``ability.conflict.original.guild_bank_raid_first``.

    constructor: ``ConflictPlace`` 1. Guild Bank Raid, first place: 6 Solari.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Guild Bank Raid First Solari", p.solari_value(6))
        return v


@port(_CA + "guild_bank_raid_second")
class GuildBankRaidSecondAbility(ConflictAbility):
    """``ability.conflict.original.guild_bank_raid_second``.

    constructor: ``ConflictPlace`` 2. Guild Bank Raid, second place: 4 Solari.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Guild Bank Raid Second Solari", p.solari_value(4))
        return v


@port(_CA + "guild_bank_raid_third")
class GuildBankRaidThirdAbility(ConflictAbility):
    """``ability.conflict.original.guild_bank_raid_third``.

    constructor: ``ConflictPlace`` 3. Guild Bank Raid, third place: 2 Solari.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Guild Bank Raid Third Solari", p.solari_value(2))
        return v


# -- Machinations ------------------------------------------------------


@port(_CA + "machinations_first")
class MachinationsFirstAbility(ConflictAbility):
    """``ability.conflict.original.machinations_first``.

    constructor: ``ConflictPlace`` 1. Machinations, first place: the two best single
    Influence gains (``gain_any_two_value``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        return gain_any_two_value(p, "Conflict Machinations First Influence")

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``MachinationsFirstAbility.Evaluate``: the code of
        ``GainAnyTwoInfluenceConflictAbility.Evaluate`` (``gain_any_two_
        evaluate``): the two best tracks, value ``Math.Max(0.5, sum)``
        (``Targets`` asks for exactly two)."""

        return gain_any_two_evaluate(p, request, "Machinations First")


@port(_CA + "machinations_second")
class MachinationsSecondAbility(ConflictAbility):
    """``ability.conflict.original.machinations_second``.

    constructor: ``ConflictPlace`` 2. Machinations, second place: 1 Water, then 2
    Solari.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Machinations Second Water", p.water_value(1))
        v.add("Conflict Machinations Second Solari", p.solari_value(2))
        return v


@port(_CA + "machinations_third")
class MachinationsThirdAbility(ConflictAbility):
    """``ability.conflict.original.machinations_third``.

    constructor: ``ConflictPlace`` 3. Machinations, third place: 1 Water.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Machinations Third Water", p.water_value(1))
        return v


# -- Raid Stockpiles ---------------------------------------------------


@port(_CA + "raid_stockpiles_first")
class RaidStockpilesFirstAbility(ConflictAbility):
    """``ability.conflict.original.raid_stockpiles_first``.

    constructor: ``ConflictPlace`` 1. Raid Stockpiles, first place: 3 Spice (the Spice
    price times 3.0), then 1 Intrigue.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Raid Stockpiles First Spice", p.spice_value(1) * 3.0)
        v.add("Conflict Raid Stockpiles First Intrigue", p.intrigue_value())
        return v


@port(_CA + "raid_stockpiles_second")
class RaidStockpilesSecondAbility(ConflictAbility):
    """``ability.conflict.original.raid_stockpiles_second``.

    constructor: ``ConflictPlace`` 2. Raid Stockpiles, second place: 2 Spice (the Spice
    price doubled).
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Raid Stockpiles Second Spice", _twice(p.spice_value(1)))
        return v


@port(_CA + "raid_stockpiles_third")
class RaidStockpilesThirdAbility(ConflictAbility):
    """``ability.conflict.original.raid_stockpiles_third``.

    constructor: ``ConflictPlace`` 3. Raid Stockpiles, third place: 1 Spice.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Raid Stockpiles Third Spice", p.spice_value(1))
        return v


# -- Secure Imperial Basin ---------------------------------------------


@port(_CA + "secure_imperial_basin_first")
class SecureImperialBasinFirstAbility(ConflictAbility):
    """``ability.conflict.original.secure_imperial_basin_first``.

    constructor: ``ConflictPlace`` 1. Secure Imperial Basin, first place: 1 VP, then the
    Spice control of the Basin (``ControlSpiceValue``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Secure Imperial Basin First VP", p.victory_point_value(1))
        v.add(
            "Conflict Secure Imperial Basin First Gain Control", p.control_spice_value()
        )
        return v


@port(_CA + "secure_imperial_basin_second")
class SecureImperialBasinSecondAbility(ConflictAbility):
    """``ability.conflict.original.secure_imperial_basin_second``.

    constructor: ``ConflictPlace`` 2. Secure Imperial Basin, second place: 2 Water (the
    Water price doubled).
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Secure Imperial Basin Second Water", _twice(p.water_value(1)))
        return v


@port(_CA + "secure_imperial_basin_third")
class SecureImperialBasinThirdAbility(ConflictAbility):
    """``ability.conflict.original.secure_imperial_basin_third``.

    constructor: ``ConflictPlace`` 3. Secure Imperial Basin, third place: 1 Water.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Secure Imperial Basin Third Water", p.water_value(1))
        return v


# -- Siege of Arrakeen -------------------------------------------------


@port(_CA + "siege_of_arrakeen_first")
class SiegeOfArrakeenFirstAbility(ConflictAbility):
    """``ability.conflict.original.siege_of_arrakeen_first``.

    constructor: ``ConflictPlace`` 1. Siege of Arrakeen, first place: 1 VP, then the
    Solari control of Arrakeen (``ControlSolariValue``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Siege Of Arrakeen First VP", p.victory_point_value(1))
        v.add("Conflict Siege Of Arrakeen First Gain Control", p.control_solari_value())
        return v


@port(_CA + "siege_of_arrakeen_second")
class SiegeOfArrakeenSecondAbility(ConflictAbility):
    """``ability.conflict.original.siege_of_arrakeen_second``.

    constructor: ``ConflictPlace`` 2. Siege of Arrakeen, second place: 4 Solari.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Siege Of Arrakeen Second Solari", p.solari_value(4))
        return v


@port(_CA + "siege_of_arrakeen_third")
class SiegeOfArrakeenThirdAbility(ConflictAbility):
    """``ability.conflict.original.siege_of_arrakeen_third``.

    constructor: ``ConflictPlace`` 3. Siege of Arrakeen, third place: 2 Solari.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Siege Of Arrakeen Third Solari", p.solari_value(2))
        return v


# -- Siege of Carthag --------------------------------------------------


@port(_CA + "siege_of_carthag_first")
class SiegeOfCarthagFirstAbility(ConflictAbility):
    """``ability.conflict.original.siege_of_carthag_first``.

    constructor: ``ConflictPlace`` 1. Siege of Carthag, first place: 1 VP, then the
    Solari control of Carthag (``ControlSolariValue``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Siege Of Carthag First VP", p.victory_point_value(1))
        v.add("Conflict Siege Of Carthag First Gain Control", p.control_solari_value())
        return v


@port(_CA + "siege_of_carthag_second")
class SiegeOfCarthagSecondAbility(ConflictAbility):
    """``ability.conflict.original.siege_of_carthag_second``.

    constructor: ``ConflictPlace`` 2. Siege of Carthag, second place: 2 Solari, then 1
    Intrigue (the app prices 2 Solari although its ``BeginExecution`` gains 1 Spice: a
    valuation slip kept).
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Siege Of Carthag Second Solari", p.solari_value(2))
        v.add("Conflict Siege Of Carthag Second Intrigue", p.intrigue_value())
        return v


@port(_CA + "siege_of_carthag_third")
class SiegeOfCarthagThirdAbility(ConflictAbility):
    """``ability.conflict.original.siege_of_carthag_third``.

    constructor: ``ConflictPlace`` 3. Siege of Carthag, third place: 1 Spice.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Siege Of Carthag Third Spice", p.spice_value(1))
        return v


# -- Sort Through the Chaos --------------------------------------------


@port(_CA + "sort_through_the_chaos_first")
class SortThroughTheChaosFirstAbility(ConflictAbility):
    """``ability.conflict.original.sort_through_the_chaos_first``.

    constructor: ``ConflictPlace`` 1. Sort Through the Chaos, first place: 1 Intrigue,
    the Mentat, 2 Solari.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Sort Through the Chaos First Intrigue", p.intrigue_value())
        v.add("Conflict Sort Through the Chaos First Mentat", p.mentat_value())
        v.add("Conflict Sort Through the Chaos First Solari", p.solari_value(2))
        return v


@port(_CA + "sort_through_the_chaos_second")
class SortThroughTheChaosSecondAbility(ConflictAbility):
    """``ability.conflict.original.sort_through_the_chaos_second``.

    constructor: ``ConflictPlace`` 2. Sort Through the Chaos, second place: 1 Intrigue,
    2 Solari.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Sort Through the Chaos Second Intrigue", p.intrigue_value())
        v.add("Conflict Sort Through the Chaos Second Solari", p.solari_value(2))
        return v


@port(_CA + "sort_through_the_chaos_third")
class SortThroughTheChaosThirdAbility(ConflictAbility):
    """``ability.conflict.original.sort_through_the_chaos_third``.

    constructor: ``ConflictPlace`` 3. Sort Through the Chaos, third place: 2 Solari.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Sort Through the Chaos Third Solari", p.solari_value(2))
        return v


# -- Terrible Purpose --------------------------------------------------


@port(_CA + "terrible_purpose_first")
class TerriblePurposeFirstAbility(ConflictAbility):
    """``ability.conflict.original.terrible_purpose_first``.

    constructor: ``ConflictPlace`` 1. Terrible Purpose, first place: 1 VP, the trash
    (``TrashCardValue``, ``TrashMod``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

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
        """``TerriblePurposeFirstAbility.Evaluate``.

        ``GetCardToTrash(targets, 1.0)`` over the ``FindTrashTargets`` list of
        ``Targets``: with a card, its score ``+ 10.0`` names that card; without one the
        answer is ``10.0`` with an empty target array (the black-X trash is optional):
        the AI always answers, and trashes only a card ``GetCardToTrash`` accepts.
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


@port(_CA + "terrible_purpose_second")
class TerriblePurposeSecondAbility(ConflictAbility):
    """``ability.conflict.original.terrible_purpose_second``.

    constructor: ``ConflictPlace`` 2. Terrible Purpose, second place: 1 Water, then 1
    Spice.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Terrible Purpose Second Water", p.water_value(1))
        v.add("Conflict Terrible Purpose Second Spice", p.spice_value(1))
        return v


@port(_CA + "terrible_purpose_third")
class TerriblePurposeThirdAbility(ConflictAbility):
    """``ability.conflict.original.terrible_purpose_third``.

    constructor: ``ConflictPlace`` 3. Terrible Purpose, third place: 1 Spice.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Terrible Purpose Third Spice", p.spice_value(1))
        return v


# -- Battle for Arrakeen -----------------------------------------------


@port(_CA + "battle_for_arrakeen_first")
class BattleForArrakeenFirstAbility(ConflictAbility):
    """``ability.conflict.original.battle_for_arrakeen_first``.

    constructor: ``ConflictPlace`` 1. Battle for Arrakeen, first place: 2 VP, then the
    Solari control of Arrakeen (``ControlSolariValue``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Battle of Arrakeen First VP", p.victory_point_value(2))
        v.add(
            "Conflict Battle of Arrakeen First Gain Control", p.control_solari_value()
        )
        return v


@port(_CA + "battle_for_arrakeen_second")
class BattleForArrakeenSecondAbility(ConflictAbility):
    """``ability.conflict.original.battle_for_arrakeen_second``.

    constructor: ``ConflictPlace`` 2. Battle for Arrakeen, second place: the best of 1
    Intrigue, 2 Spice and 3 Solari (the printed "choose two").
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

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
        """``BattleForArrakeenSecondAbility.Evaluate``.

        The printed "choose two" is a custom choice of three options
        (``Targets``: 0 draws 1 Intrigue, 1 gains 2 Spice, 2 gains
        3 Solari). The list ``[(IntrigueValue, 0), (2 * GetSpiceValue(1), 1),
        (GetSolariValue(3), 2)]`` is sorted with ``List.Sort`` and the
        comparison ``b.CompareTo(a)`` (``Evaluate``): best first, by
        .NET's three-element sorting network (``dotnet_sort3``, not stable).
        The first two options answer (``IntListTargetResponse``, in that
        order) at the sum of their values (``Take(2)`` and ``Evaluate``).
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


@port(_CA + "battle_for_arrakeen_third")
class BattleForArrakeenThirdAbility(ConflictAbility):
    """``ability.conflict.original.battle_for_arrakeen_third``.

    constructor: ``ConflictPlace`` 3. Battle for Arrakeen, third place: 2 Solari, then 1
    Intrigue.
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Battle of Arrakeen Third Solari", p.solari_value(2))
        v.add("Conflict Battle of Arrakeen Third Intrigue", p.intrigue_value())
        return v


# -- Battle for Carthag ------------------------------------------------


@port(_CA + "battle_for_carthag_first")
class BattleForCarthagFirstAbility(ConflictAbility):
    """``ability.conflict.original.battle_for_carthag_first``.

    constructor: ``ConflictPlace`` 1. Battle for Carthag, first place: 2 VP, then the
    Solari control of Carthag (``ControlSolariValue``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Battle of Carthag First VP", p.victory_point_value(2))
        v.add("Conflict Battle of Carthag First Gain Control", p.control_solari_value())
        return v


@port(_CA + "battle_for_carthag_second")
class BattleForCarthagSecondAbility(ConflictAbility):
    """``ability.conflict.original.battle_for_carthag_second``.

    constructor: ``ConflictPlace`` 2. Battle for Carthag, second place: 3 Spice (the
    Spice price times 3.0), then 1 Intrigue.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Battle of Carthag Second Spice", p.spice_value(1) * 3.0)
        v.add("Conflict Battle of Carthag Second Intrigue", p.intrigue_value())
        return v


@port(_CA + "battle_for_carthag_third")
class BattleForCarthagThirdAbility(ConflictAbility):
    """``ability.conflict.original.battle_for_carthag_third``.

    constructor: ``ConflictPlace`` 3. Battle for Carthag, third place: 3 Spice (the
    Spice price times 3.0).
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Battle of Carthag Third Spice", p.spice_value(1) * 3.0)
        return v


# -- Battle for Imperial Basin -----------------------------------------


@port(_CA + "battle_for_imperial_basin_first")
class BattleForImperialBasinFirstAbility(ConflictAbility):
    """``ability.conflict.original.battle_for_imperial_basin_first``.

    constructor: ``ConflictPlace`` 1. Battle for Imperial Basin, first place: 2 VP, then
    the Spice control of the Basin (``ControlSpiceValue``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Battle of Imperial Basin First VP", p.victory_point_value(2))
        v.add(
            "Conflict Battle of Imperial Basin First Gain Control",
            p.control_spice_value(),
        )
        return v


@port(_CA + "battle_for_imperial_basin_second")
class BattleForImperialBasinSecondAbility(ConflictAbility):
    """``ability.conflict.original.battle_for_imperial_basin_second``.

    constructor: ``ConflictPlace`` 2. Battle for Imperial Basin, second place: 5 Spice
    (the Spice price times 5.0).
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Battle of Imperial Basin Second Spice", p.spice_value(1) * 5.0)
        return v


@port(_CA + "battle_for_imperial_basin_third")
class BattleForImperialBasinThirdAbility(ConflictAbility):
    """``ability.conflict.original.battle_for_imperial_basin_third``.

    constructor: ``ConflictPlace`` 3. Battle for Imperial Basin, third place: 3 Spice
    (the Spice price times 3.0).
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Battle of Imperial Basin Third Spice", p.spice_value(1) * 3.0)
        return v


# -- Grand Vision ------------------------------------------------------


@port(_CA + "grand_vision_first")
class GrandVisionFirstAbility(ConflictAbility):
    """``ability.conflict.original.grand_vision_first``.

    constructor: ``ConflictPlace`` 1. Grand Vision, first place: two Influence with one
    faction (``GetGainInfluenceValue(None, 2)``), then 1 Intrigue.
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add(
            "Conflict Grand Vision First Influence", gain_any_influence_value(p, 2).sum
        )
        v.add("Conflict Grand Vision First Intrigue", p.intrigue_value())
        return v

    def evaluate_faction(self, p: Profile, request: Request) -> Answer:
        """``GrandVisionFirstAbility.EvaluateFaction``.

        The ``SelectFaction`` prompt of its ``BeginExecution``
        (``GainFactionInfluence(faction, 2)``): the same code as Cloak and
        Dagger's, but ``GetGainInfluenceValue(faction, 2)``.
        """

        return influence_track_answer(p, request, 2, "Grand Vision First")


@port(_CA + "grand_vision_second")
class GrandVisionSecondAbility(ConflictAbility):
    """``ability.conflict.original.grand_vision_second``.

    constructor: ``ConflictPlace`` 2. Grand Vision, second place: 3 Spice (the Spice
    price times 3.0), then 1 Intrigue.
    """

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

        v = Summer()
        v.add("Conflict Grand Vision Second Spice", p.spice_value(1) * 3.0)
        v.add("Conflict Grand Vision Second Intrigue", p.intrigue_value())
        return v


@port(_CA + "grand_vision_third")
class GrandVisionThirdAbility(ConflictAbility):
    """``ability.conflict.original.grand_vision_third``.

    constructor: ``ConflictPlace`` 3. Grand Vision, third place: 3 Spice (the Spice
    price times 3.0).
    """

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``."""

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
