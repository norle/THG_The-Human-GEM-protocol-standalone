import cobra
import numpy as np

from thg_protocol.cell_specific import reduce_model_by_activity


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
