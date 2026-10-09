import cobra
import pytest

from thg_protocol.analysis.leakage import energy_generating_cycles, metabolite_leaks
from thg_protocol.validation import validate_model


def leaky_model():
    """``a -> b -> a + c`` makes ``c`` and ``a + d -> b -> a`` destroys ``d``."""
    model = cobra.Model("leaky")
    a, b, c, d, e = [
        cobra.Metabolite(f"{name}_c", compartment="c", formula="C", charge=0)
        for name in "abcde"
    ]
    equations = {
        "make": {a: -1, b: 1},
        "split": {b: -1, a: 1, c: 1},
        "absorb": {a: -1, d: -1, e: 1},
        "release": {e: -1, a: 1},
        "EX_c": {c: -1},
        "EX_d": {d: -1},
    }
    for identifier, stoichiometry in equations.items():
        reaction = cobra.Reaction(identifier, lower_bound=-1000, upper_bound=1000)
        reaction.add_metabolites(stoichiometry)
        model.add_reactions([reaction])
    model.reactions.release.lower_bound = 0
    model.reactions.split.lower_bound = 0
    model.objective = "EX_c"
    return model


def conserved_model():
    model = cobra.Model("conserved")
    a = cobra.Metabolite("a_c", compartment="c", formula="C", charge=0)
    b = cobra.Metabolite("b_c", compartment="c", formula="C", charge=0)
    convert = cobra.Reaction("convert", lower_bound=-1000, upper_bound=1000)
    convert.add_metabolites({a: -1, b: 1})
    uptake = cobra.Reaction("EX_a", lower_bound=-10, upper_bound=1000)
    uptake.add_metabolites({a: -1})
    export = cobra.Reaction("EX_b", lower_bound=0, upper_bound=1000)
    export.add_metabolites({b: -1})
    model.add_reactions([convert, uptake, export])
    model.objective = "EX_b"
    return model


def energy_model(*, cycle):
    """ATP hydrolysis; with ``cycle`` also a free ATP synthesis reaction.

    As in Human-GEM, hydroxide shares water's MetaNetX ID (MetaNetX merges
    protonation states), so MEMOTE's lookup finds two water candidates.
    """
    model = cobra.Model("energy")
    species = {
        "atp": ("MNXM3", "C10H12N5O13P3", -4),
        "adp": ("MNXM7", "C10H12N5O10P2", -3),
        "pi": ("MNXM9", "HO4P", -2),
        "h": ("MNXM1", "H", 1),
        "h2o": ("MNXM2", "H2O", 0),
    }
    mets = {
        name: cobra.Metabolite(
            f"{name}_c",
            name=name,
            formula=formula,
            charge=charge,
            compartment="c",
        )
        for name, (_, formula, charge) in species.items()
    }
    for name, (mnx, _, _) in species.items():
        mets[name].annotation = {"metanetx.chemical": mnx}
    mets["h2o"].annotation.update(
        {"kegg.compound": "C00001", "bigg.metabolite": "h2o", "chebi": "CHEBI:15377"}
    )
    hydroxide = cobra.Metabolite(
        "oh_c", name="hydroxide", formula="HO", charge=-1, compartment="c"
    )
    hydroxide.annotation = {"metanetx.chemical": "MNXM2", "kegg.compound": "C01328"}
    hydrolysis = cobra.Reaction("hydrolysis", lower_bound=0, upper_bound=1000)
    hydrolysis.add_metabolites(
        {mets["atp"]: -1, mets["h2o"]: -1, mets["adp"]: 1, mets["pi"]: 1, mets["h"]: 1}
    )
    neutralise = cobra.Reaction("neutralise", lower_bound=0, upper_bound=1000)
    neutralise.add_metabolites({hydroxide: -1, mets["h"]: -1, mets["h2o"]: 1})
    model.add_reactions([hydrolysis, neutralise])
    for name in ("atp", "adp", "pi", "h", "h2o"):
        exchange = cobra.Reaction(f"EX_{name}", lower_bound=-1000, upper_bound=1000)
        exchange.add_metabolites({mets[name]: -1})
        model.add_reactions([exchange])
    if cycle:
        synthase = cobra.Reaction("free_synthase", lower_bound=0, upper_bound=1000)
        synthase.add_metabolites(
            {
                mets["adp"]: -1,
                mets["pi"]: -1,
                mets["h"]: -1,
                mets["atp"]: 1,
                mets["h2o"]: 1,
            }
        )
        model.add_reactions([synthase])
    model.objective = "hydrolysis"
    return model


@pytest.mark.solver
def test_metabolite_leaks_name_metabolites_made_or_destroyed_without_boundaries():
    result = metabolite_leaks(leaky_model())
    assert result == {"produced": ["c_c"], "consumed": ["d_c"]}


@pytest.mark.solver
def test_metabolite_leaks_are_empty_for_a_conserved_network():
    assert metabolite_leaks(conserved_model()) == {"produced": [], "consumed": []}


@pytest.mark.solver
def test_metabolite_leaks_leave_the_model_unchanged():
    model = leaky_model()
    bounds = {reaction.id: reaction.bounds for reaction in model.reactions}
    variables = len(model.variables)
    metabolite_leaks(model)
    assert {reaction.id: reaction.bounds for reaction in model.reactions} == bounds
    assert len(model.variables) == variables


@pytest.mark.solver
@pytest.mark.memote
def test_energy_generating_cycle_names_the_reactions_charging_atp():
    pytest.importorskip("memote")
    result = energy_generating_cycles(energy_model(cycle=True))
    # The least-flux cycle: the free synthesis alone recharges dissipated ATP.
    assert result["cycles"] == {"atp_c": ["free_synthase"]}
    assert "atp_c" in result["tested"]


@pytest.mark.solver
@pytest.mark.memote
def test_energy_generating_cycles_pass_when_atp_cannot_be_charged_for_free():
    pytest.importorskip("memote")
    model = energy_model(cycle=False)
    bounds = {reaction.id: reaction.bounds for reaction in model.reactions}
    result = energy_generating_cycles(model)
    assert result["cycles"] == {}
    assert result["tested"] == ["atp_c"]
    assert {reaction.id: reaction.bounds for reaction in model.reactions} == bounds


@pytest.mark.solver
@pytest.mark.memote
def test_energy_generating_cycles_report_couples_missing_from_the_model():
    pytest.importorskip("memote")
    result = energy_generating_cycles(energy_model(cycle=False))
    assert "MNXM6" in result["not_found"]
    assert "MNXM3" not in result["not_found"]


@pytest.mark.solver
@pytest.mark.memote
def test_solver_profiles_report_leaks_and_energy_cycles_without_blocking():
    pytest.importorskip("memote")
    report = validate_model(energy_model(cycle=True), "beta1-standard")
    checks = {item["id"]: item for item in report["checks"]}
    cycles = checks["energy-generating-cycles"]
    assert cycles["status"] == "failed"
    assert cycles["release_blocking"] is False
    leaks = checks["metabolite-leaks"]
    assert leaks["release_blocking"] is False
    assert set(leaks["details"]["by_compartment"]) == {"produced", "consumed"}


def test_structural_profile_skips_leak_and_energy_checks():
    checks = {
        item["id"]
        for item in validate_model(conserved_model(), "structural-fast")["checks"]
    }
    assert not checks & {"metabolite-leaks", "energy-generating-cycles"}


@pytest.mark.solver
@pytest.mark.memote
@pytest.mark.parametrize("cycle", [False, True])
def test_release_energy_cycle_gate_uses_evaluated_result(cycle):
    report = validate_model(energy_model(cycle=cycle), "release-full")
    check = next(c for c in report["checks"] if c["id"] == "energy-generating-cycles")
    assert check["passed"] is (not cycle)
    assert check["release_blocking"] is True
    assert report["passed"] is (not cycle)
