import importlib


def test_metabolite_reaction_workflow_import_is_safe_without_cobra():
    workflow = importlib.import_module(
        "thg_protocol.annotation.metabolite_reactions"
    )

    assert callable(workflow.run_metabolite_reaction_identification)


def test_legacy_annotation_wrapper_is_import_safe():
    legacy = importlib.import_module("functions.function_annotate_cobra_model")

    assert callable(legacy.annotate_cobra_model)
