import cobra

from thg_protocol.services.biocyc import StaticBioCycClient
from thg_protocol.services.ensembl import StaticEnsemblClient
from thg_protocol.services.kegg import StaticKeggClient


def test_batch_builder_accepts_explicit_paths_and_injected_clients(tmp_path):
    from build_model.build_model_batch import main

    input_model = tmp_path / "input.xml"
    output_model = tmp_path / "results" / "output.xml"
    output_errors = tmp_path / "results" / "errors.tsv"
    cache_dir = tmp_path / "cache"
    cobra.io.write_sbml_model(cobra.Model("toy"), input_model)

    result = main(
        input_model=input_model,
        output_model_final=output_model,
        output_errors=output_errors,
        cache_dir=cache_dir,
        biocyc_client=StaticBioCycClient(),
        kegg_client=StaticKeggClient(),
        ensembl_client=StaticEnsemblClient(),
    )

    assert result is None
    assert output_model.exists()
    assert cache_dir.exists()
    assert {
        path.name for path in cache_dir.iterdir()
    } >= {
        "ensembl_cache_batch.pkl",
        "kegg_reaction_cache_batch.pkl",
        "getgpr_cache_batch.pkl",
        "variables_batch.pkl",
    }
