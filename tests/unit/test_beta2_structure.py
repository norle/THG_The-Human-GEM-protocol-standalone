from thg_protocol.workflow.beta2 import BETA2_WORKFLOW, DETAILED_BETA2_STAGE_IDS
from thg_protocol.workflow.beta2._stages import detailed_beta2_stages


def test_beta2_workflow_contract_is_unchanged():
    stages = detailed_beta2_stages()
    assert BETA2_WORKFLOW.id == "beta2"
    assert tuple(stage.id for stage in stages) == DETAILED_BETA2_STAGE_IDS
    assert {
        stage.id: stage.dependencies
        for stage in stages
    } == {
        "load-beta1": (),
        "collect-catalysis-evidence": ("load-beta1",),
        "collect-gpr-evidence": ("collect-catalysis-evidence",),
        "resolve-gprs": ("collect-catalysis-evidence", "collect-gpr-evidence"),
        "normalize-compartments": ("resolve-gprs",),
        "collect-location-evidence": ("normalize-compartments",),
        "collect-reaction-location-evidence": ("collect-location-evidence",),
        "resolve-compartment-evidence": (
            "normalize-compartments",
            "collect-location-evidence",
            "collect-reaction-location-evidence",
        ),
        "infer-complex-and-isoenzyme-locations": (
            "resolve-compartment-evidence",
            "resolve-gprs",
        ),
        "generate-expansion-plan": ("infer-complex-and-isoenzyme-locations",),
        "apply-expansion-decisions": ("generate-expansion-plan",),
        "apply-expansion": ("apply-expansion-decisions",),
        "consolidate-expanded-model": ("apply-expansion",),
        "validate-beta2": ("consolidate-expanded-model",),
        "export-beta2": ("validate-beta2",),
    }
