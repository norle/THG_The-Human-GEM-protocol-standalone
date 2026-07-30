from pathlib import Path

from thg_protocol.pathway.kegg_listing import list_pathway_reactions
from thg_protocol.services.kegg import StaticKeggClient


def test_list_pathway_reactions_uses_injected_client(tmp_path: Path) -> None:
    pathways = tmp_path / "pathways.tsv"
    pathways.write_text("hsa00001\tExample\n", encoding="utf-8")
    client = StaticKeggClient(
        pages={
            "https://rest.kegg.jp/get/hsa00001/kgml": (
                '<pathway name="path:hsa00001">'
                '<entry name="rn:R00001 rn:R00002"/></pathway>'
            )
        }
    )
    output = list_pathway_reactions(
        pathways, tmp_path / "nested" / "result.tsv", client=client
    )
    assert output.read_text(encoding="utf-8").splitlines()[-1] == (
        "hsa00001\tExample\tR00001 R00002"
    )
