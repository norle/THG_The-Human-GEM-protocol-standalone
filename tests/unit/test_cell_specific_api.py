from types import SimpleNamespace

import cobra
import numpy as np
from scipy.io import savemat

from thg_protocol.cell_specific import (
    extract_ensembl_ids,
    extract_gene_annotation_pairs,
    extract_sgpr_rules,
    reduce_model_by_activity,
    replace_gene_symbols,
    replace_index_tokens,
)


def test_reduce_model_by_activity_is_non_mutating_and_writes_output(tmp_path):
    model = cobra.Model("cell")
    model.compartments["c"] = "cytosol"
    a = cobra.Metabolite("a_c", compartment="c", formula="C1")
    b = cobra.Metabolite("b_c", compartment="c", formula="C1")
    first = cobra.Reaction("R1")
    first.add_metabolites({a: -1, b: 1})
    first.gene_reaction_rule = "G1"
    second = cobra.Reaction("R2")
    second.add_metabolites({b: -1})
    second.gene_reaction_rule = "G2"
    model.add_reactions([first, second])

    output = tmp_path / "nested" / "tailored.xml"
    tailored, report = reduce_model_by_activity(
        model,
        np.array([[1, 1, 0], [0, 0, 0]]),
        preserve_reactions=("R2",),
        output_path=output,
    )

    assert report.total_reactions == 2
    assert report.removed_reactions == 0
    assert report.retained_reactions == 2
    assert tailored.reactions.R1.gene_reaction_rule == "G1"
    assert len(model.reactions) == 2
    assert output.exists()


def test_reduce_model_by_activity_removes_zero_presence_rows():
    model = cobra.Model("cell")
    model.compartments["c"] = "cytosol"
    a = cobra.Metabolite("a_c", compartment="c")
    b = cobra.Metabolite("b_c", compartment="c")
    first = cobra.Reaction("R1")
    first.add_metabolites({a: -1, b: 1})
    second = cobra.Reaction("R2")
    second.add_metabolites({b: -1})
    model.add_reactions([first, second])

    tailored, report = reduce_model_by_activity(
        model,
        [[1, 0], [0, 0]],
    )

    assert tailored.reactions.has_id("R1")
    assert not tailored.reactions.has_id("R2")
    assert report.removed_reactions == 1
    assert report.orphan_metabolites_removed == 0


def test_reduce_model_by_activity_loads_single_sample_csv_and_mat(tmp_path):
    model = cobra.Model("cell")
    model.add_reactions([cobra.Reaction("R1"), cobra.Reaction("R2")])
    activity = np.array([[1], [0]])
    csv_path = tmp_path / "activity.csv"
    mat_path = tmp_path / "activity.mat"
    np.savetxt(csv_path, activity, delimiter=",")
    savemat(mat_path, {"all_Solutions_matrix5": activity})

    for path in (csv_path, mat_path):
        tailored, report = reduce_model_by_activity(model, path)
        assert tailored.reactions.has_id("R1")
        assert not tailored.reactions.has_id("R2")
        assert report.removed_reactions == 1


def test_transcriptomics_helpers_transform_model_annotations(tmp_path):
    genes = [SimpleNamespace(id="HGNC1"), SimpleNamespace(id="x_ENSG000001")]
    reactions = [
        SimpleNamespace(
            annotation={"sGPR": "https://example/sGPR/rule-1"},
            gene_reaction_rule="x(0) and x(1)",
        ),
        SimpleNamespace(annotation={}, gene_reaction_rule="HGNC1 or ENSG000001"),
    ]
    model = SimpleNamespace(genes=genes, reactions=reactions)

    assert extract_sgpr_rules(model) == ["rule-1", None]
    assert extract_ensembl_ids(model) == ["", "ENSG000001"]
    assert replace_index_tokens(model, ["ENSG000010", "ENSG000011"]) == [
        "(ENSG000010) and (ENSG000011)",
        "HGNC1 or ENSG000001",
    ]
    assert replace_gene_symbols(model, {"HGNC1": "ENSG000099"})[1] == (
        "ENSG000099 or ENSG000001"
    )

    xml = tmp_path / "annotations.xml"
    xml.write_text(
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description><rdf:li rdf:resource="urn:hgnc.symbol/HGNC1"/>'
        '<rdf:li rdf:resource="urn:ensembl/ENSG000099"/></rdf:Description>'
        '<rdf:Description><rdf:li rdf:resource="urn:hgcn.symbol/HGNC1"/>'
        '<rdf:li rdf:resource="urn:ensembl/ENSG000100"/></rdf:Description>'
        "</rdf:RDF>",
        encoding="utf-8",
    )
    assert extract_gene_annotation_pairs(xml) == {
        "HGNC1": ["ENSG000099", "ENSG000100"]
    }
