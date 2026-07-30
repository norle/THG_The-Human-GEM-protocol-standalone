from thg_protocol.gpr.location import resolve_locations
from thg_protocol.services.location import StaticLocationClient


def test_location_resolution_uses_static_page_and_compatibility_shape() -> None:
    client = StaticLocationClient(
        pages={
            "https://www.uniprot.org/uniprotkb/G1_HUMAN.txt": "mitochondria"
        }
    )
    result = resolve_locations(
        "GENE1",
        ["GENE1"],
        ["G1"],
        allowed_locations={"Cytosol", "Mitochondria"},
        location_client=client,
    )
    assert result[0] == {"Mitochondria": "(GENE1*1)"}
    assert result[3] == {"G1": ["GENE1"]}
