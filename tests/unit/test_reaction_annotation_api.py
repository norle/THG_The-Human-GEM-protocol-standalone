from thg_protocol.annotation import reactions


def test_reaction_annotation_api_exposes_characterized_helper_names():
    assert "jaccard" in reactions.__all__
    assert "execute_jaccard" in reactions.__all__
    assert "identify_reaction" in reactions.__all__


def test_reaction_annotation_api_exposes_characterized_helpers():
    assert reactions.jaccard(["a", "b"], ["b", "c"]) == 1 / 3
    assert reactions.execute_jaccard.__module__ == "thg_protocol.annotation.reactions"
    assert reactions.identify_reaction.__module__ == "thg_protocol.annotation.reactions"
