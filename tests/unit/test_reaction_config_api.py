import pytest

from thg_protocol.reaction_config import (
    DEFAULT_BIOCHEMICAL_SBO,
    build_reaction_entry,
    default_lower_bound,
    upsert_reaction_entry,
)


def test_default_lower_bound_detects_reversibility():
    assert default_lower_bound("1 A[c] + 2 B[c] --> 1 C[c]") == 0.0
    assert default_lower_bound("1 A[c] <=> 1 B[c]") == -1000.0
    assert default_lower_bound("1 A[c] -->") == 0.0


def test_build_reaction_entry_applies_defaults_and_strips_required_fields():
    entry = build_reaction_entry(
        reaction_id=" R_Test ",
        name=" Test reaction ",
        equation=" 1 A[c] <=> 1 B[c] ",
    )

    assert entry == {
        "id": "R_Test",
        "name": "Test reaction",
        "description": "",
        "equation": "1 A[c] <=> 1 B[c]",
        "subsystem": "",
        "ec": "",
        "gpr": "",
        "lower_bound": -1000.0,
        "upper_bound": 1000.0,
        "sbo": DEFAULT_BIOCHEMICAL_SBO,
    }


def test_build_reaction_entry_rejects_missing_required_fields():
    with pytest.raises(ValueError, match="reaction_id is required"):
        build_reaction_entry(reaction_id="", name="name", equation="A --> B")

    with pytest.raises(ValueError, match="name is required"):
        build_reaction_entry(reaction_id="R_Test", name="", equation="A --> B")

    with pytest.raises(ValueError, match="equation is required"):
        build_reaction_entry(reaction_id="R_Test", name="name", equation="")


def test_upsert_reaction_entry_adds_reactions_without_mutating_input():
    config = {"metadata": {"name": "example"}}
    entry = build_reaction_entry(
        reaction_id="R_Test", name="Test reaction", equation="1 A[c] --> 1 B[c]"
    )

    updated = upsert_reaction_entry(config, entry)

    assert config == {"metadata": {"name": "example"}}
    assert updated["metadata"] == {"name": "example"}
    assert updated["reactions"] == [entry]


def test_upsert_reaction_entry_requires_overwrite_for_duplicate_ids():
    config = {
        "reactions": [
            build_reaction_entry(
                reaction_id="R_Test", name="Old reaction", equation="1 A[c] -->"
            )
        ]
    }
    replacement = build_reaction_entry(
        reaction_id="R_Test", name="New reaction", equation="1 A[c] <=> 1 B[c]"
    )

    with pytest.raises(ValueError, match="already exists"):
        upsert_reaction_entry(config, replacement)

    updated = upsert_reaction_entry(config, replacement, overwrite=True)
    assert updated["reactions"] == [replacement]
