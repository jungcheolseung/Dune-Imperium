"""Static metadata reuse must not cache mutable inputs or game ownership."""

from types import MappingProxyType

import pytest

from dune_imperium.agents.app_ai import catalog
from dune_imperium.agents.app_ai.context import card_id
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.agents.app_ai.data.synthetic import SYNTHETIC
from dune_imperium.agents.app_ai.entities import Entity, Kind


def _custom(attributes: dict[str, object]) -> Archetype:
    return Archetype(
        short="test.metadata",
        kind="imperium",
        title="test",
        in_uprising=True,
        in_uprising_choam=True,
        attributes=MappingProxyType(attributes),
    )


def test_every_static_list_matches_uncached_attribute_conversion() -> None:
    for definition in (*ARCHETYPES.values(), *SYNTHETIC.values()):
        entity = Entity(Kind.CARD, "test", definition)
        for name, value in definition.attributes.items():
            expected = (
                tuple(str(item) for item in value)
                if isinstance(value, tuple)
                else (value,) if isinstance(value, str) else ()
            )
            assert entity.list_attr(name) == expected, (definition.short, name)
        assert entity.list_attr("no_such_attribute") == ()


def test_canonical_lists_are_reused_without_allocating_new_tuples() -> None:
    entity = catalog.card_entity("imperium:captured_mentat:0")
    assert entity.list_attr("WormAbilityIDs")
    assert entity.list_attr("WormAbilityIDs") is entity.list_attr("WormAbilityIDs")


def test_custom_mapping_and_mutable_values_are_read_afresh() -> None:
    attributes: dict[str, object] = {"Tags": ("first",), "Number": 2}
    entity = Entity(Kind.CARD, "test", _custom(attributes))
    assert entity.list_attr("Tags") == ("first",)
    attributes["Tags"] = "second"
    assert entity.list_attr("Tags") == ("second",)
    assert entity.list_attr("Number") == ()

    class MutableText:
        value = "before"

        def __str__(self) -> str:
            return self.value

    value = MutableText()
    attributes["Tags"] = (value, 3, False)
    assert entity.list_attr("Tags") == ("before", "3", "False")
    value.value = "after"
    assert entity.list_attr("Tags") == ("after", "3", "False")
    assert Entity(Kind.SPY, "post").list_attr("Tags") == ()


def test_same_short_name_does_not_share_another_archetypes_lists() -> None:
    canonical = catalog.card_entity("imperium:captured_mentat:0").archetype
    assert canonical is not None
    custom = Archetype(
        canonical.short, canonical.kind, canonical.title,
        canonical.in_uprising, canonical.in_uprising_choam, {"Tags": ("custom",)}
    )
    assert Entity(Kind.CARD, "test", custom).list_attr("Tags") == ("custom",)


def test_entities_keep_instance_and_owner_separate() -> None:
    first = catalog.card_entity("imperium:captured_mentat:0", 0)
    assert catalog.card_entity(first.ref, 0) is first
    assert catalog.card_entity(first.ref, 1).owner == 1
    assert catalog.card_entity(first.ref, 1) is not first
    assert catalog.card_entity("imperium:captured_mentat:1", 0).ref != first.ref
    assert catalog.card_entity(first.ref).owner is None


def test_entity_reuse_sees_changes_to_the_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = catalog.card_entity("imperium:captured_mentat:0", 0)
    monkeypatch.setitem(catalog.CARD_ARCHETYPES, "captured_mentat", "changed")
    definition = _custom({"Tags": ("changed",)})
    monkeypatch.setattr(catalog, "_archetype", lambda short: definition)
    changed = catalog.card_entity(original.ref, 0)
    assert changed is not original
    assert changed.archetype is definition
    assert changed.list_attr("Tags") == ("changed",)


def test_entity_cache_is_bounded_and_evicted_entities_still_match() -> None:
    first = catalog.card_entity("imperium:captured_mentat:0", 0)
    for index in range(catalog._CARD_ENTITY_CACHE_LIMIT + 1):
        catalog.card_entity(f"imperium:captured_mentat:{index}", 0)
    assert (
        catalog._static_card_entity.cache_info().currsize
        <= catalog._CARD_ENTITY_CACHE_LIMIT
    )
    assert catalog.card_entity(first.ref, 0) == first


def test_identifier_parse_cache_has_a_finite_size() -> None:
    for index in range(4100):
        assert card_id(f"player:0:starter:dagger:{index}") == "dagger"
    assert card_id.cache_info().currsize <= 4096
    assert card_id("contract:spice_spoils") == "spice_spoils"
    assert card_id("captured_mentat") == "captured_mentat"
