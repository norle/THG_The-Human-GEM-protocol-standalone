import cobra

from thg_protocol.model_build import build_model
from thg_protocol.services.biocyc import StaticBioCycClient
from thg_protocol.services.ensembl import EnsemblAnnotation, StaticEnsemblClient
from thg_protocol.services.kegg import StaticKeggClient


def test_model_build_uses_static_services_and_explicit_outputs(tmp_path):
    source = tmp_path / "input.xml"
    output = tmp_path / "nested" / "output.xml"
    cache = tmp_path / "cache"
    errors = tmp_path / "reports" / "errors.json"

    model = cobra.Model("toy")
    metabolite = cobra.Metabolite("a_c", formula="C1", compartment="c")
    reaction = cobra.Reaction("R1")
    reaction.add_metabolites({metabolite: -1})
    reaction.annotation["kegg.reaction"] = "R00001"
    reaction.annotation["ec-code"] = "1.1.1.1"
    reaction.gene_reaction_rule = "GENE1"
    model.compartments["c"] = "cytosol"
    model.add_reactions([reaction])
    cobra.io.write_sbml_model(model, source)

    report = build_model(
        source,
        output,
        cache_dir=cache,
        errors_path=errors,
        kegg_client=StaticKeggClient(reaction_entries={"R00001": "ENTRY R00001"}),
        biocyc_client=StaticBioCycClient(ec_pages={("META", "1.1.1.1"): "EC page"}),
        ensembl_client=StaticEnsemblClient(
            annotations={"GENE1": EnsemblAnnotation("ENSG0001")}
        ),
    )

    assert report.kegg_reactions == 1
    assert report.biocyc_ec_pages == 1
    assert report.ensembl_genes == 1
    assert report.errors == []
    assert output.exists()
    assert errors.exists()
    assert {path.name for path in cache.iterdir()} == {
        "kegg_reaction_entries.json",
        "biocyc_ec_pages.json",
        "ensembl_annotations.json",
    }

    rebuilt = cobra.io.read_sbml_model(output)
    assert rebuilt.reactions.R1.annotation["kegg.reaction.entry"]
    assert rebuilt.genes.GENE1.annotation["ensembl"] == "ENSG0001"
