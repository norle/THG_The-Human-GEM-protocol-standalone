from thg_protocol.workflow.beta2 import BETA2_STAGE_IDS, BETA2_WORKFLOW
from thg_protocol.workflow.beta2._stages import beta2_stages


def test_beta2_workflow_contract_is_unchanged():
    stages = beta2_stages()
    assert BETA2_WORKFLOW.id == "beta2"
    assert tuple(stage.id for stage in stages) == BETA2_STAGE_IDS
    assert {stage.id: stage.dependencies for stage in stages} == {
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


def test_reference_beta2_declares_its_beta1_dependency():
    from thg_protocol.workflow.reference import REFERENCE_STAGES

    load = next(stage for stage in REFERENCE_STAGES if stage.id == "load-beta1")
    assert load.dependencies == ("export-beta1",)


def test_reference_fingerprint_tracks_artifacts_not_its_own_manifest(tmp_path):
    import json
    from types import SimpleNamespace

    from thg_protocol.runtime.hashing import artifact_record, sha256_json
    from thg_protocol.runtime.stage import StageContext
    from thg_protocol.workflow.beta2._stages import Beta2Stage

    source = tmp_path / "model.json"
    source.write_text("{}")
    manifest = {
        "steps": {
            "export-beta1": {
                "status": "completed",
                "outputs": [artifact_record("model", source, tmp_path)],
            }
        }
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    config = SimpleNamespace(
        workflow="reference",
        sections={"beta2": {}},
        source_path=tmp_path / "config.json",
    )
    context = StageContext(config, tmp_path, manifest)
    stage = Beta2Stage("load-beta1", ("export-beta1",))
    before = sha256_json(stage.fingerprint_data(context))
    external_config = SimpleNamespace(
        workflow="beta2",
        source_path=config.source_path,
        sections={
            "beta2": {
                "upstream": {
                    "run_dir": str(tmp_path),
                    "stage_id": "export-beta1",
                    "role": "model",
                }
            }
        },
    )
    external = StageContext(external_config, tmp_path, manifest)
    external_before = sha256_json(stage.fingerprint_data(external))
    manifest["updated_at"] = "downstream stage finished"
    path.write_text(json.dumps(manifest))
    assert sha256_json(stage.fingerprint_data(context)) == before
    assert sha256_json(stage.fingerprint_data(external)) != external_before
    source.write_text('{"changed": true}')
    manifest["steps"]["export-beta1"]["outputs"] = [
        artifact_record("model", source, tmp_path)
    ]
    path.write_text(json.dumps(manifest))
    assert sha256_json(stage.fingerprint_data(context)) != before
    source.write_text("tampered")
    assert "upstream_error" in stage.fingerprint_data(context)
