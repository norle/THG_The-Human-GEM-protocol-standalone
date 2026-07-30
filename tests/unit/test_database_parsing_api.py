from thg_protocol.database_parsing import parse_pathway_links
from thg_protocol.services.kegg import StaticKeggClient


def test_parse_pathway_links_uses_flat_file_fallback() -> None:
    client = StaticKeggClient(
        pages={
            "https://rest.kegg.jp/get/hsa00190":
            "ENTRY hsa00190\nREACTION     R00001 R00002\n"
        }
    )
    _, reactions = parse_pathway_links(
        '<pathway name="path:hsa00190"></pathway>', client=client
    )
    assert {item[0][0] for item in reactions} == {"R00001", "R00002"}
