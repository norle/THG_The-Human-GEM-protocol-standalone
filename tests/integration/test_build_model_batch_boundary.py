import cobra

from thg_protocol.services.biocyc import StaticBioCycClient
from thg_protocol.services.ensembl import StaticEnsemblClient
from thg_protocol.services.kegg import StaticKeggClient


def test_batch_builder_accepts_explicit_paths_and_injected_clients(tmp_path):
    assert StaticBioCycClient().get_ec_html("1.1.1.1") == ""
    assert StaticKeggClient().get_reaction_entries([]) == {}
    assert StaticEnsemblClient().annotate([]) == {}


def test_package_batch_builder_is_the_maintained_api(tmp_path):
    from thg_protocol.model_build import build_model_batch

    input_model = tmp_path / "input.xml"
    output_model = tmp_path / "results" / "output.xml"
    cache_dir = tmp_path / "cache"
    cobra.io.write_sbml_model(cobra.Model("toy"), input_model)

    report = build_model_batch(
        input_model,
        output_model,
        cache_dir=cache_dir,
        biocyc_client=StaticBioCycClient(),
        kegg_client=StaticKeggClient(),
        ensembl_client=StaticEnsemblClient(),
    )

    assert report.output_path == output_model
    assert output_model.exists()
