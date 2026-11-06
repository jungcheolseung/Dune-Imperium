"""Arrakeen Scouts subcommittees [Scouts subcommittee: <name>].

Uprising's lines first. The app shows a different line for three of them in
the original game's schedules (same definition, plain wording instead of
``.uprising``); the original game's wording is a record of its own, an
``imperium_`` id (docs/base-game-and-ix-plan.md 20.2). The original game's
other subcommittees follow them (stage P8b). Effects are paraphrased in
``docs/rules/arrakeen-scouts.md``.
"""

from typing import Final

from dune_imperium.content.arrakeen_scouts.abilities import (
    scouts_option,
)
from dune_imperium.content.arrakeen_scouts.types import (
    ALL_POOLS,
    IMMORTALITY_POOLS,
    IMPERIUM_POOLS,
    UPRISING_POOLS,
    AppDefinition,
    Subcommittee,
)

SUBCOMMITTEES: Final[tuple[Subcommittee, ...]] = (
    # --- Tier 0 -------------------------------------------------------------------
    Subcommittee(
        subcommittee_id="appropriations",
        name="Appropriations",
        tier=0,
        option=scouts_option("appropriations"),
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Subcommittee_E_Appropriations", 1),
    ),
    Subcommittee(
        subcommittee_id="intelligence",
        name="Intelligence",
        tier=0,
        option=scouts_option("intelligence"),
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Subcommittee_E_Intelligence", 8),
    ),
    Subcommittee(
        subcommittee_id="readiness",
        name="Readiness",
        tier=0,
        option=scouts_option("readiness"),
        pools=ALL_POOLS,
        app=AppDefinition("Def_Subcommittee_E_Readiness", 2),
    ),
    Subcommittee(
        subcommittee_id="choam_coordination",
        name="CHOAM Coordination",
        tier=0,
        option=scouts_option("choam_coordination"),
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Subcommittee_E_CHOAMCoordination", 13),
        choam_only=True,
    ),
    Subcommittee(
        subcommittee_id="growth_project",
        name="Growth Project",
        tier=0,
        option=scouts_option("growth_project"),
        pools=IMMORTALITY_POOLS,
        app=AppDefinition("Def_Subcommittee_E_GrowthProject", 10),
    ),
    # --- Tier 1 -------------------------------------------------------------------
    Subcommittee(
        subcommittee_id="oversight",
        name="Oversight",
        tier=1,
        option=scouts_option("oversight"),
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Subcommittee_M_Oversight", 3),
    ),
    Subcommittee(
        subcommittee_id="investigations",
        name="Investigations",
        tier=1,
        option=scouts_option("investigations"),
        pools=ALL_POOLS,
        app=AppDefinition("Def_Subcommittee_M_Investigations", 4),
    ),
    Subcommittee(
        subcommittee_id="forecasting",
        name="Forecasting",
        tier=1,
        option=scouts_option("forecasting"),
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Subcommittee_M_Forecasting", 14),
    ),
    Subcommittee(
        subcommittee_id="choam_management",
        name="CHOAM Management",
        tier=1,
        option=scouts_option("choam_management"),
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Subcommittee_M_CHOAMManagement", 15),
        choam_only=True,
    ),
    Subcommittee(
        subcommittee_id="analytics",
        name="Analytics",
        tier=1,
        option=scouts_option("analytics"),
        pools=IMMORTALITY_POOLS,
        app=AppDefinition("Def_Subcommittee_M_Analytics", 11),
    ),
    # --- Tier 2 -------------------------------------------------------------------
    Subcommittee(
        subcommittee_id="relations",
        name="Relations",
        tier=2,
        option=scouts_option("relations"),
        pools=ALL_POOLS,
        app=AppDefinition("Def_Subcommittee_L_Relations", 5),
    ),
    Subcommittee(
        subcommittee_id="contingencies",
        name="Contingencies",
        tier=2,
        option=scouts_option("contingencies"),
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Subcommittee_L_Contingencies", 16),
    ),
    Subcommittee(
        subcommittee_id="leverage",
        name="Leverage",
        tier=2,
        option=scouts_option("leverage"),
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Subcommittee_L_Leverage", 17),
    ),
    Subcommittee(
        subcommittee_id="tleilaxu_relations",
        name="Tleilaxu Relations",
        tier=2,
        option=scouts_option("tleilaxu_relations"),
        pools=IMMORTALITY_POOLS,
        app=AppDefinition("Def_Subcommittee_L_TleilaxuRelations", 12),
    ),
    # --- The original game's own (stage P8b) ----------------------------------------
    # The first three share their app definition with the Uprising record of
    # the same name (the app words them differently by schedule).
    Subcommittee(
        subcommittee_id="imperium_appropriations",
        name="Appropriations",
        tier=0,
        option=scouts_option("imperium_appropriations"),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Subcommittee_E_Appropriations", 1),
    ),
    Subcommittee(
        subcommittee_id="imperium_intelligence",
        name="Intelligence",
        tier=0,
        option=scouts_option("imperium_intelligence"),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Subcommittee_E_Intelligence", 8),
    ),
    Subcommittee(
        subcommittee_id="imperium_oversight",
        name="Oversight",
        tier=1,
        option=scouts_option("imperium_oversight"),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Subcommittee_M_Oversight", 3),
    ),
    Subcommittee(
        subcommittee_id="joint_forces",
        name="Joint Forces",
        tier=1,
        option=scouts_option("joint_forces"),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Subcommittee_M_JointForces", 9),
    ),
    Subcommittee(
        subcommittee_id="development",
        name="Development",
        tier=2,
        option=scouts_option("development"),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Subcommittee_L_Development", 6),
    ),
    Subcommittee(
        subcommittee_id="political_affairs",
        name="Political Affairs",
        tier=2,
        option=scouts_option("political_affairs"),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Subcommittee_L_PoliticalAffairs", 7),
    ),
)

SUBCOMMITTEES_BY_ID: Final = {entry.subcommittee_id: entry for entry in SUBCOMMITTEES}
