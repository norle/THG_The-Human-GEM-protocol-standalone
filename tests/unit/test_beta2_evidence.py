from thg_protocol.curation.beta2 import resolve_compartment


def test_cco_component_of_resolves_to_configured_id():
    result = resolve_compartment(
        "mitochondrial inner membrane",
        "CCO-IMEM",
        {
            "CCO-IMEM": {
                "name": "mitochondrial inner membrane",
                "component_of": ["CCO-MIT"],
            },
            "CCO-MIT": {"name": "mitochondrion"},
        },
        {"x": "mitochondria", "i": "cytosol"},
    )
    assert result["target_compartment_id"] == "x"
    assert result["resolution_method"] == "cco-component-of"


def test_cco_does_not_guess_from_a_broad_term():
    result = resolve_compartment(
        "membrane",
        None,
        {"CCO-MEM": {"name": "membrane", "superclasses": []}},
        {"m": "mitochondria"},
    )
    assert result["status"] == "rejected"
    assert result["reason"] == "location-not-in-registry"
