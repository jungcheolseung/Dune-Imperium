"""Arrakeen Scouts subcommittees [Scouts subcommittee: <name>].

The Uprising cost/reward lines (the app shows a different line for three of
them in base-game schedules; those are not played here). Effects are
paraphrased in ``docs/rules/arrakeen-scouts.md``.
"""

from typing import Final

from dune_imperium.content.arrakeen_scouts.abilities import (
    scouts_option,
)
from dune_imperium.content.arrakeen_scouts.types import (
    BOTH_POOLS,
    IMMORTALITY_ONLY,
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
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Subcommittee_E_Appropriations", 1),
    ),
    Subcommittee(
        subcommittee_id="intelligence",
        name="Intelligence",
        tier=0,
        option=scouts_option("intelligence"),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Subcommittee_E_Intelligence", 8),
    ),
    Subcommittee(
        subcommittee_id="readiness",
        name="Readiness",
        tier=0,
        option=scouts_option("readiness"),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Subcommittee_E_Readiness", 2),
    ),
    Subcommittee(
        subcommittee_id="choam_coordination",
        name="CHOAM Coordination",
        tier=0,
        option=scouts_option("choam_coordination"),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Subcommittee_E_CHOAMCoordination", 13),
        choam_only=True,
    ),
    Subcommittee(
        subcommittee_id="growth_project",
        name="Growth Project",
        tier=0,
        option=scouts_option("growth_project"),
        pools=IMMORTALITY_ONLY,
        app=AppDefinition("Def_Subcommittee_E_GrowthProject", 10),
    ),
    # --- Tier 1 -------------------------------------------------------------------
    Subcommittee(
        subcommittee_id="oversight",
        name="Oversight",
        tier=1,
        option=scouts_option("oversight"),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Subcommittee_M_Oversight", 3),
    ),
    Subcommittee(
        subcommittee_id="investigations",
        name="Investigations",
        tier=1,
        option=scouts_option("investigations"),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Subcommittee_M_Investigations", 4),
    ),
    Subcommittee(
        subcommittee_id="forecasting",
        name="Forecasting",
        tier=1,
        option=scouts_option("forecasting"),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Subcommittee_M_Forecasting", 14),
    ),
    Subcommittee(
        subcommittee_id="choam_management",
        name="CHOAM Management",
        tier=1,
        option=scouts_option("choam_management"),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Subcommittee_M_CHOAMManagement", 15),
        choam_only=True,
    ),
    Subcommittee(
        subcommittee_id="analytics",
        name="Analytics",
        tier=1,
        option=scouts_option("analytics"),
        pools=IMMORTALITY_ONLY,
        app=AppDefinition("Def_Subcommittee_M_Analytics", 11),
    ),
    # --- Tier 2 -------------------------------------------------------------------
    Subcommittee(
        subcommittee_id="relations",
        name="Relations",
        tier=2,
        option=scouts_option("relations"),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Subcommittee_L_Relations", 5),
    ),
    Subcommittee(
        subcommittee_id="contingencies",
        name="Contingencies",
        tier=2,
        option=scouts_option("contingencies"),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Subcommittee_L_Contingencies", 16),
    ),
    Subcommittee(
        subcommittee_id="leverage",
        name="Leverage",
        tier=2,
        option=scouts_option("leverage"),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Subcommittee_L_Leverage", 17),
    ),
    Subcommittee(
        subcommittee_id="tleilaxu_relations",
        name="Tleilaxu Relations",
        tier=2,
        option=scouts_option("tleilaxu_relations"),
        pools=IMMORTALITY_ONLY,
        app=AppDefinition("Def_Subcommittee_L_TleilaxuRelations", 12),
    ),
)

SUBCOMMITTEES_BY_ID: Final = {entry.subcommittee_id: entry for entry in SUBCOMMITTEES}
