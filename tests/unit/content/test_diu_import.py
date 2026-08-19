"""Tests for development-time DIU Imperium normalization."""

import json
from pathlib import Path

import pytest

from dune_imperium.content.diu import (
    DiuCardGroup,
    DiuDataError,
    audit_diu_imperium,
    expected_imperium_cards,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.types import AgentIcon


def _source_records() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for source_id, expected in enumerate(expected_imperium_cards(), start=1):
        name = (
            "Branching Paths"
            if expected.card_id == "branching_path"
            else expected.name
        )
        record: dict[str, object] = {"id": source_id, "name": name}
        if expected.group is DiuCardGroup.STARTING:
            record["starting_deck"] = True
            record["amount"] = expected.copies
        elif expected.group is DiuCardGroup.RESERVE:
            record["reserve"] = True
            record["quantity"] = expected.copies
        else:
            record["quantity"] = expected.copies
        records.append(record)
    return records


def _write_source(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(records), encoding="utf-8")


def test_audit_matches_all_local_identities_and_normalizes_aliases(
    tmp_path: Path,
) -> None:
    records = _source_records()
    prepare = next(record for record in records if record["name"] == "Prepare the Way")
    prepare["agent_icons"] = ["green", "blue"]
    prepare["factions"] = ["bene_gesserit"]
    prepare["agent_effects"] = [
        {
            "type": "conditional",
            "check": [{"type": "influence", "target": "bene_gesserit"}],
            "reward": [
                {"type": "draw", "deck": "deck", "amount": 1},
            ],
        }
    ]
    path = tmp_path / "imperium.JSON"
    _write_source(path, records)

    audit = audit_diu_imperium(path)
    normalized = audit.card("prepare_the_way")

    assert len(audit.cards) == 63
    assert audit.copy_mismatches == ()
    assert normalized.agent_icons == (AgentIcon.LANDSRAAD, AgentIcon.CITY)
    assert normalized.factions == (Faction.BENE_GESSERIT,)
    assert normalized.effect_types == ("conditional", "influence", "draw")
    assert dict(audit.effect_type_counts) == {
        "conditional": 1,
        "draw": 1,
        "influence": 1,
    }


def test_audit_reports_but_does_not_adopt_diu_copy_counts(tmp_path: Path) -> None:
    records = _source_records()
    card = next(record for record in records if record["name"] == "Sardaukar Soldier")
    card["quantity"] = 3
    path = tmp_path / "imperium.JSON"
    _write_source(path, records)

    audit = audit_diu_imperium(path)

    assert len(audit.copy_mismatches) == 1
    mismatch = audit.copy_mismatches[0]
    assert mismatch.card_id == "sardaukar_soldier"
    assert mismatch.declared == 3
    assert mismatch.expected == 1


def test_audit_rejects_an_unknown_agent_icon(tmp_path: Path) -> None:
    records = _source_records()
    records[0]["agent_icon"] = ["purple"]
    path = tmp_path / "imperium.JSON"
    _write_source(path, records)

    with pytest.raises(DiuDataError, match="unknown DIU Agent icon"):
        audit_diu_imperium(path)


def test_audit_rejects_missing_cards(tmp_path: Path) -> None:
    records = _source_records()[:-1]
    path = tmp_path / "imperium.JSON"
    _write_source(path, records)

    with pytest.raises(DiuDataError, match="missing cards"):
        audit_diu_imperium(path)
