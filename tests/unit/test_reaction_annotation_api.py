from functions import function_reac_identification as legacy_reactions

from thg_protocol.annotation import reactions


def test_reaction_annotation_api_exposes_characterized_helper_names():
    assert "jaccard" in reactions.__all__
    assert "execute_jaccard" in reactions.__all__
    assert "identify_reaction" in reactions.__all__


def test_reaction_annotation_api_exposes_characterized_helpers():
    assert reactions.jaccard(["a", "b"], ["b", "c"]) == legacy_reactions.jaccard(
        ["a", "b"], ["b", "c"]
    )
    assert (
        reactions.execute_jaccard.__name__
        == legacy_reactions.execute_jaccard.__name__
    )
    assert (
        reactions.identify_reaction.__name__
        == legacy_reactions.identify_reaction.__name__
    )
