"""Why does stoichiometric consistency differ between SBML and JSON?

Usage: check_sbml_json_consistency.py MODEL.json MODEL.xml OUT.json
Loads both, compares stoichiometry exactly, and runs MEMOTE's consistency LP
on each with the same solver (Gurobi).
"""
import json
import sys

import cobra

cobra.Configuration().solver = "gurobi"
from memote.support import consistency  # noqa: E402

from thg_protocol.analysis.conservation import conservation_exclusions  # noqa: E402,F401


def stoich(model):
    return {r.id: {m.id: c for m, c in r.metabolites.items()} for r in model.reactions}


def main(jpath, xpath, out):
    mj = cobra.io.load_json_model(jpath)
    mx = cobra.io.read_sbml_model(xpath)
    sj, sx = stoich(mj), stoich(mx)
    res = {"reactions_json": len(sj), "reactions_sbml": len(sx),
           "same_reaction_ids": set(sj) == set(sx)}
    diffs = []
    for rid in sorted(set(sj) & set(sx)):
        if sj[rid] != sx[rid]:
            diffs.append(rid)
    res["reactions_with_different_stoichiometry"] = len(diffs)
    res["first_differences"] = [
        {"id": r, "json": sj[r], "sbml": sx[r]} for r in diffs[:5]]
    res["metabolite_ids_equal"] = (
        {m.id for m in mj.metabolites} == {m.id for m in mx.metabolites})
    res["boundary_json"] = len(mj.boundary)
    res["boundary_sbml"] = len(mx.boundary)
    res["solver_json"] = type(mj.solver).__module__
    res["solver_sbml"] = type(mx.solver).__module__
    res["consistent_json"] = bool(consistency.check_stoichiometric_consistency(mj))
    res["consistent_sbml"] = bool(consistency.check_stoichiometric_consistency(mx))
    json.dump(res, open(out, "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main(*sys.argv[1:4])
