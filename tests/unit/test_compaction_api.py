from types import SimpleNamespace

from thg_protocol.analysis import are_reactions_proportional


def test_proportional_reaction_detection_is_direction_aware() -> None:
    a = SimpleNamespace(metabolites={"a": -1, "b": 1})
    b = SimpleNamespace(metabolites={"a": 2, "b": -2})
    assert are_reactions_proportional(a, b) == (True, -2.0, True)
