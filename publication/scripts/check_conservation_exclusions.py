"""Compare SBML and JSON conservation using native and shared exclusions."""

import hashlib
import json
import sys
from pathlib import Path

import cobra

from thg_protocol.analysis.conservation import (
    conservation_exclusions,
    find_unconserved_metabolites,
)


def main():
    json_path, sbml_path, output = map(Path, sys.argv[1:])
    models = {
        "json": cobra.io.load_json_model(str(json_path)),
        "sbml": cobra.io.read_sbml_model(str(sbml_path)),
    }

    def matrix(model):
        return {
            r.id: {m.id: x for m, x in r.metabolites.items()} for r in model.reactions
        }

    native = {label: conservation_exclusions(model) for label, model in models.items()}
    shared = native["json"] | native["sbml"]
    same_matrix = matrix(models["json"]) == matrix(models["sbml"])
    same_boundaries = {r.id for r in models["json"].boundary} == {
        r.id for r in models["sbml"].boundary
    }
    result = {
        "inputs": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (json_path, sbml_path)
        },
        "same_stoichiometry": same_matrix,
        "same_boundary_reaction_ids": same_boundaries,
        "native": {
            label: find_unconserved_metabolites(
                model, exclusions=native[label], identify=False
            )
            for label, model in models.items()
        },
        "shared_exclusions": {
            label: find_unconserved_metabolites(
                model, exclusions=shared, identify=False
            )
            for label, model in models.items()
        },
        "only_in_json": sorted(native["json"].keys() - native["sbml"].keys()),
        "only_in_sbml": sorted(native["sbml"].keys() - native["json"].keys()),
    }
    output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
