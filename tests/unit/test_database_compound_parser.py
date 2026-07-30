from thg_protocol.database_parsing import parse_kegg_compound_entry
from thg_protocol.services.kegg import StaticKeggClient


def test_compound_parser_handles_same_as_primary_entry() -> None:
    client = StaticKeggClient(
        pages={
            "https://rest.kegg.jp/get/C00001": (
                "ENTRY       C00001\nNAME        water;\nFORMULA     H2O\n"
            )
        }
    )
    result = parse_kegg_compound_entry(
        "ENTRY       G00001\nNAME        glycan;\nFORMULA     C6H12O6\n"
        "REMARK      Same as: C00001\n",
        "G00001",
        client=client,
    )
    assert result[1] == [("H2O", "C6H12O6")]
    assert result[3] == ["water"]
