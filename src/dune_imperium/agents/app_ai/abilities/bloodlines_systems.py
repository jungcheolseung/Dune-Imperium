"""App-style Bloodlines system abilities (docs/app-ai/bloodlines-systems.md).

The app has no Bloodlines, so none of these is a port: each class is the
app-style ability ``bloodlines-systems.md`` specifies, registered under its
``worm.canis.abilities.AppStyle.Bloodlines.<Name>`` id and subclassing the app
base class the spec names, so the existing machinery (``AgentAbility``'s
signet merge, ``GetSpecificAcquireBonus``, ``abilities_of``) treats them like
ports. Values come only from the profile's prices (docs/app-ai-plan.md §11.3,
§11.4) and the new profile helpers of ``profile/bloodlines.py``; plan §11.7
overrides the spec where they differ. Section and D-numbers below are those
of ``bloodlines-systems.md``.

Covered (every ability id of the spec's archetypes):

- §2 Sardaukar Commanders and Skills: ``SkillRevealAbility``,
  ``CannySkillAbility``, ``FierceSkillAbility``, ``LoyalSkillAbility``,
  ``DesperateSkillAbility``, ``AcquireCommanderAbility`` (the six Commander
  spaces, ``catalog`` overlay), ``RecruitCommanderAbility`` (the playmat's
  paid re-buy);
- §3 the Tech Module tiles: ``AcquireEffectsBonusAbility``,
  ``AdvancedDataAnalysisAbility``, ``SpyDronesAbility``,
  ``RapidDropshipsAbility``, ``ForbiddenWeaponsAbility``,
  ``GeneLockedVault{Acquired,}Ability``, ``ServoReceivers{Acquired,}Ability``,
  ``PlasteelBladesAbility`` and the hook-less tile abilities (their terms live
  in the shared profile methods, §9);
- §4 the nine leaders and their Signet Rings;
- §5 Navigation: ``NavigationAbility`` and ``NavigationCard1Ability`` …
  ``NavigationCard10Ability``;
- §6 Tuek's Sietch: ``TueksSietchDeferredAbility``.

Request / answer encoding (on top of ``abilities/generic.py``'s; the window
stage builds the requests and maps the answers back to our actions):

- entity targets (Skills, Tech tiles, cards, spaces, faction tracks) are the
  entities of ``request.infos[0]`` and the answer is ``((ref,),)``;
- an either-or (a signet's branches, an acquire effect's choice, Forbidden
  Weapons, Tuek's Sietch) lists the offered branch indices (each class's
  ``ClassVar`` constants) in ``request.infos[0].options``, a branch's own
  targets in ``request.infos[1]`` (entities, or options for counts); the
  answer is ``((branch,),)`` or ``((branch,), (ref_or_count,))``;
- ``()`` = "use this ability" with no sub-target, or the empty answer of an
  Explicit prompt at 0.5 (a declined Commander, as ``AcquireTechAbility``);
  ``None`` = nothing chosen (value 0: decline an optional prompt).
"""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, ClassVar, Final

from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Answer,
    Request,
    ResponseItem,
    SelectionMode,
    Timing,
    abilities_of,
    port,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    DeferredAbility,
    TriggeredAbility,
    app_isinstance,
    collect_first,
    contract_value_for_player,
    value_for_reveal_abilities,
)
from dune_imperium.agents.app_ai.abilities.leaders import SignetAbility
from dune_imperium.agents.app_ai.abilities.tech import TechTileAcquiredAbility
from dune_imperium.agents.app_ai.catalog import (
    FACTION_NAMES,
    LEADER_ARCHETYPES,
    leader_entity,
    skill_id_of,
    space_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.core.actions import ActionValue

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_AS: Final = "worm.canis.abilities.AppStyle.Bloodlines."
#: Esmar Tuek's leader id (``content/uprising/leaders.py``).
_ESMAR: Final = "esmar_tuek"
_SIGNET_ABILITY: Final = "worm.canis.abilities.ActivatedAbilities.SignetAbility"
_APP_TO_FACTION: Final = {app: ours for ours, app in FACTION_NAMES.items()}

#: Forbidden Weapons' swords (``rules/tech.py`` ``apply_tech_choice``; the
#: tile face's "3 swords").
FORBIDDEN_WEAPONS_STRENGTH: Final = 3
#: The cost of the Fedaykin draw (1 water, ``[Chani card]``) and the Fremen
#: Influence it needs (``rules/leader_abilities.py``).
_FEDAYKIN_FREMEN: Final = 2
#: Judge of the Change's Emperor Influence condition (``[Liet Kynes card]``).
_JUDGE_EMPEROR: Final = 2
#: Restricted-post Spy signets use Arrakis Informant's V, which gives nothing
#: with more than 2 Spies out (``cmp eax,2; jg``, leaders §7.2; D32).
_INFORMANT_MAX_SPIES: Final = 2
#: Into the Fray's Agent unit and Duncan's Swordmaster unit (``rules/
#: strength.py``): only the unit count matters to ``GetUnitsToDeploy``'s
#: selection of a single unit (the sum test runs before the unit's strength
#: is added), so the port's count form is used (§4.3, OPEN 4).
_INTO_THE_FRAY_UNITS: Final = 1


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _Pick:
    """``WormAIChoiceSelectionWithTargets.UpdateSelectionTargets`` (UST).

    The first call always sticks, later calls replace the stored answer only
    when strictly better (``abilities/tech.py`` ``_Choice``).
    """

    def __init__(self) -> None:
        self.value = 0.0
        self.response: tuple[ResponseItem, ...] | None = None
        self.label = ""

    def update(
        self, value: float, response: tuple[ResponseItem, ...], label: str
    ) -> None:
        if self.response is None or value > self.value:
            self.value = value
            self.response = response
            self.label = label

    def answer(self, default_label: str) -> Answer:
        return Answer(self.value, self.response, self.label or default_label)


def _targets(request: Request, index: int, kind: Kind) -> list[Entity]:
    """The entities of ``kind`` in ``request.infos[index]``."""

    if len(request.infos) <= index:
        return []
    return [e for e in request.infos[index].entities if e.kind is kind]


def _options(request: Request, index: int) -> tuple[int, ...]:
    """The option indices of ``request.infos[index]``."""

    if len(request.infos) <= index:
        return ()
    return request.infos[index].options


def _agent_frame(p: Profile) -> Mapping[str, ActionValue] | None:
    return p.ctx.own_frame_context("agent_effects")


def _in_agent_turn_with_space(p: Profile) -> Entity | None:
    """This Agent turn's space, while the seat is in its own Agent turn."""

    context = _agent_frame(p)
    if context is None:
        return None
    space_id = context.get("space_id")
    if not isinstance(space_id, str) or not space_id:
        return None
    return space_entity(space_id, p.ctx.board)


def _influence_requirements(entity: Entity) -> list[tuple[str, int]]:
    """``InfluenceRequirements`` as (our faction id, amount) pairs."""

    raw = entity.attr("InfluenceRequirements", ())
    pairs: list[tuple[str, int]] = []
    if isinstance(raw, tuple):
        for req in raw:
            if isinstance(req, Mapping):
                faction = _APP_TO_FACTION.get(str(req.get("Faction")))
                amount = req.get("Amount")
                if faction is not None and isinstance(amount, int):
                    pairs.append((faction, amount))
    return pairs


def _desperate_reason(p: Profile) -> str | None:
    """``DeviousStrengthAbility::Evaluate``'s use test (leaders §3.1; D9).

    "Last Round" in the final round; otherwise the interest reaches the upper
    posture bound with an opponent's estimate within 5 (strict), or the lower
    bound with one within 2.
    """

    if p.is_final_round():
        return "Last Round"
    lower, upper = p.conflict_posture_bounds()
    interest = p.current_conflict_interest().sum
    mine = p.est_strength().sum
    opponents = [p.est_opponent_strength(o.player_id).sum for o in p.ctx.opponents]
    if interest >= upper and any(abs(mine - s) < 5 for s in opponents):
        return "High conflict interest"
    if interest >= lower and any(abs(mine - s) < 2 for s in opponents):
        return "Mid conflict interest"
    return None


def deploy_window_open(p: Profile) -> bool:
    """``DeployWindowOpen()`` (§2.2): a deployment the recruit can join.

    The seat's own Agent turn whose deploy key is still unused
    (``pending_combat_deployment``: a Combat space or a Combat icon), or its
    Reveal turn with a Combat icon (``combat_deployment``). A recruited
    Commander has its own deploy room (OQ-070).
    """

    context = _agent_frame(p)
    if context is not None:
        return context.get("pending_combat_deployment") is True
    reveal = p.ctx.own_frame_context("reveal")
    return reveal is not None and reveal.get("combat_deployment") is True


# ---------------------------------------------------------------------------
# §2 Sardaukar Commanders and Skills
# ---------------------------------------------------------------------------


@port(_AS + "SkillRevealAbility")
class SkillRevealAbility(TriggeredAbility):
    """``AS.SkillRevealAbility`` (Charismatic, Driven, Hardy; §2.2).

    Paid automatically when the Reveal begins with a Commander in the
    Conflict; no Evaluate. Precedent ``RevealAbility`` ``ValueAttributes``.
    """

    timing: ClassVar[Timing] = Timing.REVEAL
    _ATTRIBUTES: ClassVar[tuple[Attr, ...]] = (
        Attr.SPICE,
        Attr.PERSUASION,
        Attr.TROOPS,
    )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """The Skill's printed Reveal gain at its resource price (Persuasion:
        arc value and buy gains, ``GetResourceValue``)."""

        s = Summer()
        for attr in self._ATTRIBUTES:
            n = self.owner.int_attr(attr.value)
            if n > 0:
                s.add("Skill " + attr.value, p.resource_value(attr, n, False))
        return s


def _agent_on_landsraad(p: Profile, with_entities: Sequence[Entity]) -> bool:
    """Canny's condition (§2.2): an own Agent on a Landsraad (Pentagon) space,
    or the space being valued is one."""

    for entity in with_entities:
        if entity.kind is Kind.SPACE and entity.attr("AgentIcon") == "Pentagon":
            return True
    board = p.ctx.board
    return any(
        space_entity(space_id, board).attr("AgentIcon") == "Pentagon"
        for space_id in p.ctx.me.agent_locations
    )


@port(_AS + "CannySkillAbility")
class CannySkillAbility(TriggeredAbility):
    """``AS.CannySkillAbility``: 2 swords with an Agent on a Landsraad space."""

    timing: ClassVar[Timing] = Timing.COMBAT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        s = Summer()
        if _agent_on_landsraad(p, with_entities):
            s.add("Canny", p.strength_value(self.owner.int_attr("Strength"), False))
        return s


@port(_AS + "FierceSkillAbility")
class FierceSkillAbility(TriggeredAbility):
    """``AS.FierceSkillAbility``: 1 sword, +1 with an opposing sandworm."""

    timing: ClassVar[Timing] = Timing.COMBAT
    #: The +1 sword printed for an opposing sandworm (``sardaukar.py``).
    WORM_BONUS: ClassVar[int] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        n = self.owner.int_attr("Strength")
        if any(op.sandworms_conflict > 0 for op in p.ctx.opponents):
            n += self.WORM_BONUS
        s = Summer()
        s.add("Fierce", p.strength_value(n, False))
        return s


@port(_AS + "LoyalSkillAbility")
class LoyalSkillAbility(TriggeredAbility):
    """``AS.LoyalSkillAbility``: 2 swords with 3 Emperor Influence."""

    timing: ClassVar[Timing] = Timing.COMBAT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        s = Summer()
        me = p.ctx.me
        if all(
            getattr(me.influence, faction) >= amount
            for faction, amount in _influence_requirements(self.owner)
        ):
            s.add("Loyal", p.strength_value(self.owner.int_attr("Strength"), False))
        return s


@port(_AS + "DesperateSkillAbility")
class DesperateSkillAbility(DeferredAbility):
    """``AS.DesperateSkillAbility``: Reveal turn, trash the Skill for 3 swords
    (§2.2, D9). Optional; ``trash_skill_for_strength``."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``rules/sardaukar.py`` ``legal_skill_trash_actions``: a Commander
        in the Conflict."""

        return p.ctx.me.commanders_conflict >= 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        s = Summer()
        s.add("Desperate", p.strength_value(self.owner.int_attr("Strength"), False))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """Devious Strength's conditions with 3 swords (D9): 100 when used."""

        reason = _desperate_reason(p)
        if reason is None:
            return Answer(0.0, None, "Desperate: keep")
        skills = _targets(request, 0, Kind.SKILL)
        skill = skills[0] if skills else self.owner
        return Answer(100.0, ((skill_id_of(skill.ref),),), "Desperate | " + reason)


@port(_AS + "AcquireCommanderAbility")
class AcquireCommanderAbility(DeferredAbility):
    """``AS.AcquireCommanderAbility`` on the six Commander spaces (§2.2, §6).

    Owner = the space. Explicit (the pending Commander icon blocks
    ``finish_agent_turn``, OQ-095), never immediate: it waits in the
    post-action list. Request: the offered (eligible face-up) Skills as SKILL
    entities in face-up order, none when the Commander comes without one.
    Answer: ``((skill,),)``, ``((),)`` (a Commander without a Skill) or the
    decline ``()`` at 0.5.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """D4: ``max(0, best net)``, 0 once the space's Commander is gone or
        when its cost cannot be paid beside the space's (WaterOfLife
        precedent)."""

        s = Summer()
        space = self.owner
        if space.ref not in p.ctx.commander_space_ids:
            return s
        cost = p.commander_cost()
        if not p.can_agent_ability_be_played_with_space(space, Attr.SOLARI, cost):
            return s
        nets = [
            p.commander_acquire_net(skill_id, (space,))
            for skill_id in p.ctx.eligible_skill_ids()
        ]
        best = max(nets) if nets else p.commander_acquire_net(None, (space,))
        s.add("Sardaukar Commander", max(0.0, best))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``AcquireTechAbility::Evaluate`` precedent (D3): the first strictly
        best net, else the empty answer at 0.5 (decline)."""

        pick = _Pick()
        skills = _targets(request, 0, Kind.SKILL)
        for skill in skills:
            net = p.commander_acquire_net(skill_id_of(skill.ref), (self.owner,))
            pick.update(net, ((skill.ref,),), f"Sardaukar Commander | {skill.ref}")
        if not skills:
            net = p.commander_acquire_net(None, (self.owner,))
            pick.update(net, ((),), "Sardaukar Commander | no Skill")
        if not (0.0 < pick.value):
            pick.update(0.5, (), "Sardaukar Commander | decline")
        return pick.answer("Sardaukar Commander")


@port(_AS + "RecruitCommanderAbility")
class RecruitCommanderAbility(DeferredAbility):
    """``AS.RecruitCommanderAbility``: the once-per-turn paid re-buy from the
    supply (playmat custom row; §2.2, D5). Optional, timing None."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """Our engine's ``recruit_sardaukar_commander`` conditions
        (``rules/sardaukar.py`` ``_can_pay_commander_recruit``)."""

        me = p.ctx.me
        return (
            not me.commander_recruited_turn
            and me.commanders_supply > 0
            and me.resources.solari >= p.commander_cost()
        )

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """D5: the net when > 0; 100 (Mercenaries' value) while a deploy
        window is open, so the recruit resolves before the deploy key."""

        net = p.recruit_net()
        if net <= 0:
            return Answer(0.0, None, "Recruit Commander: no")
        if deploy_window_open(p):
            return Answer(100.0, (), "Recruit Commander | before deploy")
        return Answer(net, (), "Recruit Commander")


# ---------------------------------------------------------------------------
# §3 Tech Module tiles
# ---------------------------------------------------------------------------


@port(_AS + "AcquireEffectsBonusAbility")
class AcquireEffectsBonusAbility(Ability):
    """``AS.AcquireEffectsBonusAbility`` (§3.3, D17; plan §11.5): prices the
    acquire effects ``GetAcquireEffectsValue`` values at 0 (SAV only)."""

    def specific_acquire_value(self, p: Profile) -> Summer:
        s = Summer()
        for effect in self.owner.list_attr("AcquireEffectList"):
            if effect == "Intrigue":  # ChaumurkyAbility SAV
                s.add("Acquire Intrigue", p.intrigue_value())
            elif effect == "Trash":  # DisposalFacilityAcquiredAbility V
                s.add("Acquire Trash", p.trash_card_value() + p.trash_mod())
            elif effect == "PlaceSpy":  # PlaceSpyAbility V
                s.add("Acquire Spy", p.spy_value().sum)
            elif effect == "Contract":  # GainContractAbility V
                s.add("Acquire Contract", contract_value_for_player(p).sum)
        return s


class _FlipAbility(DeferredAbility):
    """A tile's Flip activation: Optional, once per round (§3.3, rix-tech
    §1.3, §7.4; not an app class)."""

    tech_id: ClassVar[str] = ""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """The tile is owned and not flipped this round."""

        return p.ctx.has_tech(self.tech_id) and self.tech_id not in (
            p.ctx.tech_flipped()
        )


@port(_AS + "AdvancedDataAnalysisAbility")
class AdvancedDataAnalysisAbility(_FlipAbility):
    """``AS.AdvancedDataAnalysisAbility`` (Flip: an Intrigue card; the
    purchase boxes a Spy)."""

    tech_id: ClassVar[str] = "advanced_data_analysis"

    def specific_acquire_value(self, p: Profile) -> Summer:
        """D22: the boxed Spy, ``−SpyValue`` (``RecallSpyValue`` precedent)."""

        s = Summer()
        s.add("Spy to box", -p.spy_value().sum)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """D23: always flip (Chaumurky "always play")."""

        return Answer(100.0, (), "Advanced Data Analysis | always flip")


@port(_AS + "SpyDronesAbility")
class SpyDronesAbility(_FlipAbility):
    """``AS.SpyDronesAbility`` (Flip: 1 Solari, a trash after a recall; the
    trash is the ``optional_trash`` follow-up)."""

    tech_id: ClassVar[str] = "spy_drones"

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """D23: always flip."""

        return Answer(100.0, (), "Spy Drones | always flip")


@port(_AS + "RapidDropshipsAbility")
class RapidDropshipsAbility(_FlipAbility):
    """``AS.RapidDropshipsAbility`` (Agent turn Flip: the Combat icon)."""

    tech_id: ClassVar[str] = "rapid_dropships"
    timing: ClassVar[Timing] = Timing.AGENT
    #: The garrison share a Combat icon opens (``[Bloodlines pp. 5, 12]``).
    GARRISON_ROOM: ClassVar[int] = 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """D24 (``TrainingDronesAbility`` precedent, inverted space test).

        Nothing when this turn already deploys as at a Combat space (a Combat
        space or an earlier icon: ``existing_troop_deployment_limit`` is 2, and
        more icons add nothing); else 100 when ``GetUnitsToDeploy`` would
        deploy a garrison unit.
        """

        context = _agent_frame(p)
        limit = 0 if context is None else context.get("existing_troop_deployment_limit")
        if isinstance(limit, int) and not isinstance(limit, bool):
            if limit >= self.GARRISON_ROOM:
                return Answer(0.0, None, "Rapid Dropships: already a Combat icon")
        me = p.ctx.me
        garrison = me.troops_garrison + me.commanders_garrison
        if p.units_to_deploy(garrison, self.GARRISON_ROOM) > 0:
            return Answer(100.0, (), "Rapid Dropships | 100")
        return Answer(0.0, None, "Rapid Dropships: nothing to deploy")


@port(_AS + "ForbiddenWeaponsAbility")
class ForbiddenWeaponsAbility(DeferredAbility):
    """``AS.ForbiddenWeaponsAbility`` (Reveal, must choose; §3.3, D20, D26).

    Request: ``infos[0].options`` the offered branches (``STRENGTH``,
    ``TRASH``); ``infos[1]`` the TRACK entities of the strength rows (none:
    the bare strength action). Answer ``((STRENGTH,), (faction,))``,
    ``((STRENGTH,),)`` or ``((TRASH,),)``; the Alliance recipient is the first
    offered (plan §11.5 precedent).
    """

    STRENGTH: ClassVar[int] = 0
    TRASH: ClassVar[int] = 1
    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def specific_acquire_value(self, p: Profile) -> Summer:
        """D20: the Shield Wall acquire icon at ``BlowWallValue`` when
        ``ShouldBlowWall`` (Sietch Tabr / ``ChooseBlowWall`` precedent)."""

        s = Summer()
        if p.ctx.shield_wall_present and p.should_blow_wall():
            s.add("Shield Wall", p.blow_wall_value().sum)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """A forced loss (D26): the least-bad branch, answered at
        ``max(v, 1.0)`` (``RecallSpyIntelligenceAbility``'s 1.0)."""

        pick = _Pick()
        branches = _options(request, 0)
        if self.STRENGTH in branches:
            tracks = _targets(request, 1, Kind.TRACK)
            swords = p.strength_value(FORBIDDEN_WEAPONS_STRENGTH, False)
            if tracks:
                for track in tracks:
                    loss = p.gain_influence_value(track.ref, -1, -1, False).sum
                    pick.update(
                        swords + loss,
                        ((self.STRENGTH,), (track.ref,)),
                        f"Forbidden Weapons | strength, lose {track.ref}",
                    )
            else:
                pick.update(swords, ((self.STRENGTH,),), "Forbidden Weapons | strength")
        if self.TRASH in branches:
            value = p.spice_value(-p.ctx.me.resources.spice) - p.held_tile_value(
                "forbidden_weapons"
            )
            pick.update(value, ((self.TRASH,),), "Forbidden Weapons | trash")
        if pick.response is None:
            return Answer(0.0, None, "Forbidden Weapons: nothing offered")
        value = pick.value if pick.value > 0 else 1.0
        return Answer(value, pick.response, pick.label)


@port(_AS + "GeneLockedVaultAcquiredAbility")
class GeneLockedVaultAcquiredAbility(TechTileAcquiredAbility):
    """``AS.GeneLockedVaultAcquiredAbility``: an Intrigue card OR a draw
    (§3.3, D19). Branches ``INTRIGUE``, ``CARD`` (``choice`` intrigue / card)."""

    INTRIGUE: ClassVar[int] = 0
    CARD: ClassVar[int] = 1

    def specific_acquire_value(self, p: Profile) -> Summer:
        s = Summer()
        s.add("Acquire Intrigue", p.intrigue_value())
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GainIntrigueAcquiredAbility`` V, then ``DrawImperiumAcquiredAbility``
        V; the draw replaces the Intrigue only when strictly greater."""

        pick = _Pick()
        pick.update(
            p.intrigue_value(), ((self.INTRIGUE,),), "Gene-Locked Vault | Intrigue"
        )
        pick.update(
            p.card_draw_value_with_buy_gains(),
            ((self.CARD,),),
            "Gene-Locked Vault | card",
        )
        return pick.answer("Gene-Locked Vault")


@port(_AS + "GeneLockedVaultAbility")
class GeneLockedVaultAbility(TriggeredAbility):
    """``AS.GeneLockedVaultAbility``: passive steal protection. An effect on
    opponents, worth 0 (plan §11.4; D38); no AI hook."""


@port(_AS + "ServoReceiversAcquiredAbility")
class ServoReceiversAcquiredAbility(TechTileAcquiredAbility):
    """``AS.ServoReceiversAcquiredAbility``: use the Leader's Signet Ring once
    (§3.3, D21). Always runs at once; the ``leader_signet`` window answers."""

    def specific_acquire_value(self, p: Profile) -> Summer:
        """The leader ``SignetAbility`` V with this Agent turn's space during
        the seat's own Agent turn, else with no space (OQ-062 (b));
        ``AgentAbility`` §2.2(d) precedent."""

        s = Summer()
        me = p.ctx.me
        if me.leader_id is None or me.leader_id not in LEADER_ARCHETYPES:
            return s
        space = _in_agent_turn_with_space(p)
        with_entities: tuple[Entity, ...] = () if space is None else (space,)
        leader = leader_entity(me.leader_id, me.leader_face_id)
        for ability in abilities_of(leader):
            if app_isinstance(ability, _SIGNET_ABILITY):
                s.merge(ability.value_for_player(p, with_entities))
        return s


@port(_AS + "ServoReceiversAbility")
class ServoReceiversAbility(TriggeredAbility):
    """``AS.ServoReceiversAbility``: the Signet Ring's Faction icons; read by
    the icon lists (§1.7, ``profile.icon_list``), no AI hook."""


@port(_AS + "PlasteelBladesAbility")
class PlasteelBladesAbility(TriggeredAbility):
    """``AS.PlasteelBladesAbility``: on every Commander recruit, trash the tile
    for an extra Skill (§3.3, D10). Request: the offered SKILL entities."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SkillValue(k*) − HeldTileValue(plasteel_blades)`` when > 0 with
        ``k*`` the first strictly best Skill; else nothing (``decline_skill``)."""

        best: tuple[Entity, float] | None = None
        for skill in _targets(request, 0, Kind.SKILL):
            value = p.skill_value(skill_id_of(skill.ref))
            if best is None or value > best[1]:
                best = (skill, value)
        if best is None:
            return Answer(0.0, None, "Plasteel Blades: no Skill")
        net = best[1] - p.held_tile_value("plasteel_blades")
        if net > 0:
            return Answer(net, ((best[0].ref,),), f"Plasteel Blades | {best[0].ref}")
        return Answer(0.0, None, "Plasteel Blades: keep the tile")


class _HooklessTileAbility(TriggeredAbility):
    """A tile ability with no AI hook: its value lives in a shared profile
    method (§9) or nowhere (no app reader)."""


@port(_AS + "PanopticonAbility")
class PanopticonAbility(_HooklessTileAbility):
    """``AS.PanopticonAbility``: the Reveal troop and the Endgame influence
    (automatic); the Reveal Spy is the reused ``PlaceSpyRevealAbility``."""


@port(_AS + "CHOAMTransportsAbility")
class CHOAMTransportsAbility(_HooklessTileAbility):
    """``AS.CHOAMTransportsAbility``: a draw per completed contract (term in
    ``ContractAbility.GetResourceValue``, D57); the Endgame VP has no reader."""


@port(_AS + "PlanetaryArrayAbility")
class PlanetaryArrayAbility(_HooklessTileAbility):
    """``AS.PlanetaryArrayAbility``: a draw on a Conflict win (term in
    ``RelativeConflictValue``, D58)."""


@port(_AS + "SuspensorSuitsAbility")
class SuspensorSuitsAbility(_HooklessTileAbility):
    """``AS.SuspensorSuitsAbility``: a deployed troop per Intrigue gained in
    the own turn (term in ``IntrigueValue``, D59)."""


@port(_AS + "DeliveryBayAbility")
class DeliveryBayAbility(_HooklessTileAbility):
    """``AS.DeliveryBayAbility``: Command (6+) 2 Solari (automatic; the
    preview key has no AI reader)."""


@port(_AS + "TrainingDepotAbility")
class TrainingDepotAbility(_HooklessTileAbility):
    """``AS.TrainingDepotAbility``: Command (6+) 2 swords (automatic)."""


@port(_AS + "GlowglobesAbility")
class GlowglobesAbility(_HooklessTileAbility):
    """``AS.GlowglobesAbility``: peek at the deck top (information, worth 0;
    plan §11.4, §1.6)."""


@port(_AS + "NavigationChamberAbility")
class NavigationChamberAbility(_HooklessTileAbility):
    """``AS.NavigationChamberAbility``: board spaces cost 1 less (each discount
    variant of a placement is its own target, §1.7, D60)."""


@port(_AS + "OrnithopterFleetAbility")
class OrnithopterFleetAbility(_HooklessTileAbility):
    """``AS.OrnithopterFleetAbility``: every battle icon is an Ornithopter
    (read by ``GetBattleIconValue``, §9)."""


@port(_AS + "SardaukarHighCommandAbility")
class SardaukarHighCommandAbility(_HooklessTileAbility):
    """``AS.SardaukarHighCommandAbility``: a Commander costs 1 less (the cost
    itself, ``commander_cost``)."""


# ---------------------------------------------------------------------------
# §4 Leaders and their Signet Rings
# ---------------------------------------------------------------------------


class _HooklessLeaderAbility(TriggeredAbility):
    """A leader ability with no AI hook (its terms, if any, are in the shared
    profile methods, §9)."""


# -- §4.1 Chani --


@port(_AS + "TacticianAbility")
class TacticianAbility(_HooklessLeaderAbility):
    """``AS.TacticianAbility``: the Tactics track (``TacticsReward`` in the
    Fedaykin E and the loss value)."""


@port(_AS + "FedaykinManeuverSignetAbility")
class FedaykinManeuverSignetAbility(SignetAbility):
    """``AS.FedaykinManeuverSignetAbility``: retreat any number of units OR
    (2 Fremen) pay 1 water to draw 2 (§4.1, D30). Optional.

    Branches ``RETREAT`` (``infos[1].options`` = the offered retreat counts)
    and ``WATER``; the answer's count is split troops first (§1.4,
    ``profile.retreat_split``).
    """

    RETREAT: ClassVar[int] = 0
    WATER: ClassVar[int] = 1

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """The draw branch only (Desert Scouts' V has no AI caller); with no
        space the affordability gate is skipped (WaterOfLife precedent)."""

        s = Summer()
        me = p.ctx.me
        space = collect_first(with_entities, Kind.SPACE)
        if me.influence.fremen >= _FEDAYKIN_FREMEN and (
            space is None
            or p.can_agent_ability_be_played_with_space(space, Attr.WATER, 1)
        ):
            s.add("Fedaykin Draw", max(0.0, p.water_value(-1) + p.draw_two_value()))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GetTroopsToRetreat`` over the units that can retreat at
        ``1.0 + TacticsReward(k)`` (Desert Scouts' 1.0), then the draw;
        nothing above 0: decline."""

        pick = _Pick()
        me = p.ctx.me
        branches = _options(request, 0)
        if self.RETREAT in branches:
            k = p.troops_to_retreat(me.troops_conflict + me.commanders_conflict)
            if k > 0 and k in _options(request, 1):
                pick.update(
                    1.0 + p.tactics_reward(k),
                    ((self.RETREAT,), (k,)),
                    f"Fedaykin Maneuver | retreat {k}",
                )
        if self.WATER in branches:
            pick.update(
                p.water_value(-1) + p.draw_two_value(),
                ((self.WATER,),),
                "Fedaykin Maneuver | water",
            )
        if pick.response is None or pick.value <= 0:
            return Answer(0.0, None, "Fedaykin Maneuver: decline")
        return pick.answer("Fedaykin Maneuver")


# -- §4.2 Count Hasimir Fenring --


@port(_AS + "AssassinAbility")
class AssassinAbility(_HooklessLeaderAbility):
    """``AS.AssassinAbility``: +1 Solari per trashed card (term in
    ``TrashCardValue``, D33)."""


def _informant_spy_value(p: Profile) -> float:
    """``ArrakisInformantAbility`` V (leaders §7.2; D32): ``SpyValue`` ×
    ``ArrakisInformantMod`` with 2 Spies out at most, else 0."""

    s = Summer()
    if len(p.ctx.me.spy_post_ids) > _INFORMANT_MAX_SPIES:
        return s.sum
    s.add("Place Spy Value", p.spy_value().sum)
    s.multiply("Arrakis Informant Spy", p.C.ArrakisInformantMod)
    return s.sum


@port(_AS + "CorrinoLiaisonSignetAbility")
class CorrinoLiaisonSignetAbility(SignetAbility):
    """``AS.CorrinoLiaisonSignetAbility``: trash a card in play OR a
    deep-cover Spy next to the Emperor (§4.2, D31, D32). Optional.

    Branches ``TRASH`` (``infos[1]`` = the in-play CARD entities) and ``SPY``
    (a placement or recall-first offered).
    """

    TRASH: ClassVar[int] = 0
    SPY: ClassVar[int] = 1

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``max(TrashAbility V (Assassin included), ArrakisInformant V)``."""

        s = Summer()
        trash = p.trash_card_value() + p.trash_mod()
        s.add("Corrino Liaison", max(trash, _informant_spy_value(p)))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """A junk card first (``TrashAbility::Evaluate``), else the Spy at
        ``SpyValue`` (``ArrakisInformantAbility`` E), else decline."""

        branches = _options(request, 0)
        if self.TRASH in branches:
            card, value = p.card_to_trash(_targets(request, 1, Kind.CARD), 1.0)
            if card is not None:
                return Answer(
                    value, ((self.TRASH,), (card.ref,)), "Corrino Liaison | trash"
                )
        if self.SPY in branches:
            return Answer(p.spy_value().sum, ((self.SPY,),), "Corrino Liaison | Spy")
        return Answer(0.0, None, "Corrino Liaison: decline")


# -- §4.3 Duncan Idaho --


@port(_AS + "GinazSwordmasterAbility")
class GinazSwordmasterAbility(_HooklessLeaderAbility):
    """``AS.GinazSwordmasterAbility``: Swordmaster costs 2 less (the runtime
    cost, ``generic.space_solari_cost``, D35)."""


@port(_AS + "IntoTheFraySignetAbility")
class IntoTheFraySignetAbility(SignetAbility):
    """``AS.IntoTheFraySignetAbility``: this turn's Agent joins the Conflict
    (§4.3, D34; ``DeployUnitsAbility``). Optional."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DeployValue(space)``; nothing without a space (no Agent)."""

        s = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None:
            s.add("Into the Fray", p.deploy_value(space))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """0.5 when ``GetUnitsToDeploy`` takes the Agent unit, else decline."""

        if p.units_to_deploy(_INTO_THE_FRAY_UNITS, _INTO_THE_FRAY_UNITS) > 0:
            return Answer(0.5, (), "Into the Fray | deploy")
        return Answer(0.0, None, "Into the Fray: stay")


# -- §4.4 Esmar Tuek --


@port(_AS + "TueksSietchLeaderAbility")
class TueksSietchLeaderAbility(_HooklessLeaderAbility):
    """``AS.TueksSietchLeaderAbility``: own visit +1 Solari (priced in
    ``TueksSietchDeferredAbility``), an opponent's visit draws Esmar an
    Intrigue (0, D38)."""


@port(_AS + "SmuggleSpiceSignetAbility")
class SmuggleSpiceSignetAbility(SignetAbility):
    """``AS.SmuggleSpiceSignetAbility``: a bonus spice onto Tuek's Sietch OR 1
    taken from a Maker space (§4.4, D36). Explicit (mandatory either-or).

    Branches ``PLACE`` and ``TAKE`` (``infos[1]`` = the SPACE entities holding
    bonus spice, board order).
    """

    PLACE: ClassVar[int] = 0
    TAKE: ClassVar[int] = 1

    def place_value(self, p: Profile, with_entities: Sequence[Entity] = ()) -> float:
        """``PlaceValue(with)`` (D36): ×``BonusSpiceMod`` when this turn's
        Tuek's Sietch choice (which pays the bonus) is still to come, 0 in the
        final round, else the spice later (plan §11.4)."""

        if p.tuek_sietch_choice_pending(with_entities):
            return p.spice_value(1) * p.C.BonusSpiceMod
        if p.is_final_round():
            return 0.0
        return p.spice_value(1)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        s = Summer()
        take = 0.0
        if any(amount > 0 for _, amount in p.ctx.state.maker_bonus_spice):
            take = p.spice_value(1)
        s.add("Smuggle Spice", max(take, self.place_value(p, with_entities)))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """Spice taken first (board order), the placement only if strictly
        better (``DesertSpaceDeferredAbility`` order)."""

        pick = _Pick()
        if self.TAKE in _options(request, 0):
            for space in _targets(request, 1, Kind.SPACE):
                pick.update(
                    p.spice_value(1),
                    ((self.TAKE,), (space.ref,)),
                    f"Smuggle Spice | take {space.ref}",
                )
        if self.PLACE in _options(request, 0):
            pick.update(self.place_value(p), ((self.PLACE,),), "Smuggle Spice | place")
        return pick.answer("Smuggle Spice")


# -- §4.5 Gaius Helen Mohiam --


@port(_AS + "ClandestineAbility")
class ClandestineAbility(_HooklessLeaderAbility):
    """``AS.ClandestineAbility``: the Spy icon on every card (icon lists,
    D40) and the forced Gather Intelligence (``SpaceAbility`` term, plan
    §11.7)."""


@port(_AS + "ListenersSignetAbility")
class ListenersSignetAbility(SignetAbility):
    """``AS.ListenersSignetAbility``: a Spy next to the Landsraad OR pay 1 spice
    for a Spy anywhere (§4.5, D32, D39). Optional.

    Branches ``LANDSRAAD`` (a Landsraad placement or recall-first offered) and
    ``PAY``.
    """

    LANDSRAAD: ClassVar[int] = 0
    PAY: ClassVar[int] = 1

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        s = Summer()
        if len(p.ctx.me.spy_post_ids) <= _INFORMANT_MAX_SPIES:
            s.add("Listeners Spy", _informant_spy_value(p))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        branches = _options(request, 0)
        if self.LANDSRAAD in branches:
            return Answer(
                p.spy_value().sum, ((self.LANDSRAAD,),), "Listeners | Landsraad"
            )
        if self.PAY in branches:
            value = p.spy_value().sum + p.spice_value(-1)
            if value > 0:
                return Answer(value, ((self.PAY,),), "Listeners | pay spice")
        return Answer(0.0, None, "Listeners: decline")


# -- §4.6 Piter De Vries, §4.7 Steersman Y'rkoon, §4.8 Liet Kynes --


@port(_AS + "TwistedGeniusAbility")
class TwistedGeniusAbility(_HooklessLeaderAbility):
    """``AS.TwistedGeniusAbility``: the Twisted deck (setup and the Round Start
    draw ask nothing). Harkonnen Advisor reuses ``WarmasterAbility`` (D41)."""


@port(_AS + "StrangeFormAbility")
class StrangeFormAbility(_HooklessLeaderAbility):
    """``AS.StrangeFormAbility``: no water, no Signet Ring."""


@port(_AS + "HungryForSpiceAbility")
class HungryForSpiceAbility(_HooklessLeaderAbility):
    """``AS.HungryForSpiceAbility``: a draw at 3 spice gained in a turn (term
    in ``SpaceAbility`` V, D42)."""


@port(_AS + "PlotCourseAbility")
class PlotCourseAbility(_HooklessLeaderAbility):
    """``AS.PlotCourseAbility``: the Navigation cards (term in
    ``GetGainInfluenceValue``, D43; the windows of §5)."""


@port(_AS + "ArrakisPlanetologistAbility")
class ArrakisPlanetologistAbility(_HooklessLeaderAbility):
    """``AS.ArrakisPlanetologistAbility``: sandworms replaced (term in
    ``GetResourceValue(SandWorms)``, D44)."""


@port(_AS + "JudgeOfTheChangeSignetAbility")
class JudgeOfTheChangeSignetAbility(SignetAbility):
    """``AS.JudgeOfTheChangeSignetAbility`` (§4.8, D45; ``FillCoffersAbility``
    precedent): runs by itself, V only."""

    def can_run_immediately(self, p: Profile) -> bool:
        return True

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """By the space's icon: Landsraad with 2 Emperor Influence water,
        City a Solari, Spice Trade a spice; nothing with no space."""

        s = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is None:
            return s
        icon = space.attr("AgentIcon")
        if icon == "Pentagon" and p.ctx.me.influence.emperor >= _JUDGE_EMPEROR:
            s.add("Judge Water", p.water_value(1))
        elif icon == "Circle":
            s.add("Judge Solari", p.solari_value(1))
        elif icon == "Triangle":
            s.add("Judge Spice", p.spice_value(1))
        return s


# -- §4.9 Kota Odax of Ix --


@port(_AS + "SecretProjectAbility")
class SecretProjectAbility(DeferredAbility):
    """``AS.SecretProjectAbility`` (setup ``tech_secret_project``; forced; V
    empty: the discount acts through ``tech_cost``). Request: the offered
    bottom tiles as TECH entities in stack order."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """D27 (``TechTileToAcquire`` ordering): the first tile of the stable
        descending ``AcquireValue`` order. A tile worth 0 is still the answer:
        the window takes it whatever its value (the prompt is forced)."""

        best: tuple[Entity, float] | None = None
        for tile in _targets(request, 0, Kind.TECH):
            value = p.tech_tile_acquire_value(tile).sum
            if best is None or value > best[1]:
                best = (tile, value)
        if best is None:
            return Answer(0.0, None, "Secret Project: no tile")
        return Answer(best[1], ((best[0].ref,),), f"Secret Project | {best[0].ref}")


@port(_AS + "ReverseEngineeringSignetAbility")
class ReverseEngineeringSignetAbility(SignetAbility):
    """``AS.ReverseEngineeringSignetAbility``: 1 spice OR trash an own tile for
    an Intrigue card and a draw (§4.9, D28). Explicit.

    Branches ``SPICE`` and ``TRASH`` (``infos[1]`` = the held TECH entities).
    """

    SPICE: ClassVar[int] = 0
    TRASH: ClassVar[int] = 1

    @staticmethod
    def trash_value(p: Profile, tile: str | Entity) -> float:
        """``Trash(t) = IntrigueValue + CardDrawValueWithBuyGains −
        HeldTileValue(t)``."""

        return (
            p.intrigue_value() + p.card_draw_value_with_buy_gains()
        ) - p.held_tile_value(tile)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``max(spice_value(1), max Trash(t))`` (Shaddam ``Math.Max``)."""

        s = Summer()
        value = p.spice_value(1)
        for tech_id in p.ctx.tech_ids():
            value = max(value, self.trash_value(p, tech_id))
        s.add("Reverse Engineering", value)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """Spice first; a tile only if strictly better."""

        pick = _Pick()
        branches = _options(request, 0)
        if self.SPICE in branches:
            pick.update(
                p.spice_value(1), ((self.SPICE,),), "Reverse Engineering | spice"
            )
        if self.TRASH in branches:
            for tile in _targets(request, 1, Kind.TECH):
                pick.update(
                    self.trash_value(p, tile),
                    ((self.TRASH,), (tile.ref,)),
                    f"Reverse Engineering | trash {tile.ref}",
                )
        return pick.answer("Reverse Engineering")


# ---------------------------------------------------------------------------
# §5 Navigation
# ---------------------------------------------------------------------------


@port(_AS + "NavigationAbility")
class NavigationAbility(DeferredAbility):
    """``AS.NavigationAbility``: one of Steersman Y'rkoon's Navigation cards
    (§5). Owner = the card (``catalog.navigation_entity``); each card is a
    subclass naming its printed number. The play is forced unless our engine
    offers ``decline_navigation`` (the window's call).

    Request: ``infos[0].options`` = the playable option indices offered;
    answer ``((option,),)``.
    """

    card_number: ClassVar[int] = 0

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def _slot_and_faction(self, p: Profile) -> tuple[int, str | None]:
        """The slot being played (else the next one) and its trigger."""

        slot = p.ctx.navigation_active_slot
        if slot <= 0:
            slot = len(p.ctx.navigation_played()) + 1
        faction = p.ctx.navigation_trigger_faction or None
        return slot, faction

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``NavigationValue(card, slot, F)``."""

        slot, faction = self._slot_and_faction(p)
        s = Summer()
        s.add(
            f"Navigation {self.card_number}",
            p.navigation_value(self.card_number, slot, faction),
        )
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """The first strictly best ``OptionValue`` of the offered options with
        the real slot and trigger (card 10: its exchange, played iff >= 2.0,
        D48)."""

        slot, faction = self._slot_and_faction(p)
        pick = _Pick()
        for option in _options(request, 0):
            value = p.navigation_option_value(self.card_number, option, slot, faction)
            pick.update(
                0.0 if value is None else value,
                ((option,),),
                f"Navigation {self.card_number} | option {option}",
            )
        return pick.answer(f"Navigation {self.card_number}")


def _navigation_class(number: int) -> type[NavigationAbility]:
    cls = type(
        f"NavigationCard{number}Ability",
        (NavigationAbility,),
        {
            "card_number": number,
            "__doc__": f"``AS.NavigationCard{number}Ability`` (§5).",
            "__module__": __name__,
        },
    )
    return port(_AS + f"NavigationCard{number}Ability")(cls)


NAVIGATION_CARD_ABILITIES: Final = tuple(_navigation_class(n) for n in range(1, 11))


# ---------------------------------------------------------------------------
# §6 Tuek's Sietch
# ---------------------------------------------------------------------------


@port(_AS + "TueksSietchDeferredAbility")
class TueksSietchDeferredAbility(DeferredAbility):
    """``AS.TueksSietchDeferredAbility``: 1 spice OR draw 1 (§6, D37;
    ``HaggaBasinUprisingDeferredAbility`` precedent). Explicit, timing None.
    Options ``SPICE`` (``take_tuek_sietch_spice``), ``CARD``
    (``take_tuek_sietch_card``). The bonus spice is priced by the space's
    ``SpaceAbility``."""

    SPICE: ClassVar[int] = 0
    CARD: ClassVar[int] = 1

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def _spice(self, p: Profile) -> float:
        return p.spice_value(self.owner.int_attr("PossibleSpice"))

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """The better of spice and a draw, plus Esmar's own +1 Solari."""

        s = Summer()
        spice = self._spice(p)
        draw = p.card_draw_value_with_buy_gains()
        if spice > draw:
            s.add("Tuek's Sietch Spice", spice)
        else:
            s.add("Tuek's Sietch Draw", draw)
        if p.ctx.me.leader_id == _ESMAR:
            s.add("Tuek's Sietch Solari", p.solari_value(1))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """Spice stored first; the draw only when strictly greater."""

        pick = _Pick()
        pick.update(self._spice(p), ((self.SPICE,),), "Tuek's Sietch | spice")
        pick.update(
            p.card_draw_value_with_buy_gains(), ((self.CARD,),), "Tuek's Sietch | card"
        )
        return pick.answer("Tuek's Sietch")


# ---------------------------------------------------------------------------
# Helpers the window stage calls (follow-ups the spec answers with existing
# evaluators)
# ---------------------------------------------------------------------------


def navigation_trash_pick(p: Profile, cards: Sequence[Entity]) -> Entity | None:
    """Navigation card 5's trash (§5, D47): ``ChroniclersInsightAbility``'s
    ranking over the offered cards.

    A junk card with a cost (``GetCardToTrash(paid, 0.0)``), else any junk
    card (``GetCardToTrash(cards, 0.0)``), else the paid card of cost < 3
    with the lowest Reveal value (first strict minimum), else None (decline).
    """

    paid = [c for c in cards if c.int_attr("PersuasionCost") > 0]
    card, _ = p.card_to_trash(paid, 0.0)
    if card is not None:
        return card
    card, _ = p.card_to_trash(list(cards), 0.0)
    if card is not None:
        return card
    best: Entity | None = None
    best_value = 0.0
    for candidate in paid:
        if candidate.int_attr("PersuasionCost") >= 3:  # b__14_1 literal 3
            continue
        reveal = value_for_reveal_abilities(candidate, p).sum
        if best is None or reveal < best_value:
            best, best_value = candidate, reveal
    return best


def navigation_one_faction(
    p: Profile, offered: Sequence[str], trigger: str | None
) -> str | None:
    """Navigation card 1's Faction (§5 follow-up 1): the first strictly best
    ``GetGainInfluenceValue(G, 1)`` among the offered G (``FACTIONS`` order)
    other than the trigger."""

    best: tuple[str, float] | None = None
    for faction in FACTIONS:
        if faction not in offered or faction == trigger:
            continue
        value = p.gain_influence_value(faction, 1, -1, False).sum
        if best is None or value > best[1]:
            best = (faction, value)
    return None if best is None else best[0]
