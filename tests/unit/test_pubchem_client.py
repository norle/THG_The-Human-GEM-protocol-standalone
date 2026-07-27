from thg_protocol.annotation.metabolites import identify_metabolite
from thg_protocol.services.pubchem import PubChemCompound, StaticPubChemClient


def test_pubchem_static_client_is_injectable_and_offline():
    client = StaticPubChemClient(
        {"glucose": PubChemCompound(5793, "C6H12O6", ("glucose", "C00031"))}
    )
    result = identify_metabolite("glucose", "C6H12O6", "MAM00001c", client=client)
    assert result is not None
    assert "5793" in result
