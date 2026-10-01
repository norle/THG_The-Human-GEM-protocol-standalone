# Leaking reactions in the endo models

Hand-off for a new conversation. Context: `metabolic_task_decisions.md`
(open decision 1). Written 2026-10-01.

## Problem

`files/metabolic_tasks/metabolicTasks_VerifyModel.txt` holds 21 tasks that
**must be infeasible** (for example "oxygen from water", "ATP from nothing").
Run with the stored mapping, closed medium, biomass LB relaxed:

| Model | VerifyModel |
|---|---|
| Human-GEM | 21 of 21 correct (infeasible) |
| `endoA_251219_preprocessed_baseline.json` | 19 of 21 wrongly feasible |
| `endoC_final_7.xml` | 19 of 21 wrongly feasible |

So the endo models can make mass or energy from nothing. Every Essential/Full
"pass" on them is suspect until this is fixed.

Models are in `/home/reinism/pipeline/models/`. They use Human-GEM `MAR…`/`MAM…`
IDs, plus added reactions with other IDs (`R…_c`, `C…` metabolites, merged IDs
like `R08723_c@MARMAR40003@MAR01778`).

## What is known so far (endoC_final_7)

pFBA on "oxygen from water" uses:

- `R08758_c`: `3alpha,7alpha,26-trihydroxy-5beta-cholestane --> 3alpha,7alpha-dihydroxy-5beta-cholestan-26-al + 2 H+`.
  Unbalanced: the oxidant (NAD+/NADP+ → NAD(P)H) is missing, so it creates
  reducing equivalents/hydrogen from nothing.
- A cycle through `MAR07938` and `MAR01987`.
- Also active: `MAR13100`, `MAR01684`, `R08723_c@MARMAR40003@MAR01778`.

Not yet checked: which reactions drive the leaks on endoA, and whether the
other 18 tasks share the same culprits. The added non-`MAR` reactions are the
first suspects; `MAR…` reactions whose bounds or stoichiometry differ from
Human-GEM are the second.

## Plan

1. **Reproduce.** Run VerifyModel on endoA and endoC with the script below and
   confirm 19/21 feasible on each.
2. **Collect culprits per task.** For each feasible task, run pFBA and record
   the active reactions. Split them into:
   - reactions absent from Human-GEM (added in the pipeline),
   - `MAR…` reactions whose stoichiometry differs from Human-GEM,
   - `MAR…` reactions whose bounds/reversibility differ from Human-GEM.
3. **Check mass and charge balance** of every reaction in the first two groups
   (`cobra.manipulation.check_mass_balance`; formulas may be missing on added
   metabolites, so note those).
4. **Find a minimal set.** Iteratively block (bounds `(0, 0)`) the top
   suspect and rerun all VerifyModel tasks, until all 21 are infeasible. Then
   try unblocking each one again to make the set minimal. Do this inside
   `with model:` so nothing is saved.
5. **Decide each fix** with the user: correct the stoichiometry (for example
   add NAD+/NADH to `R08758_c`), make it irreversible, or remove it. Do not
   edit the model files in `pipeline/models/` without asking; propose fixes
   as a list or a patch script.
6. **Re-run** VerifyModel (expect 21 of 21 infeasible), then Essential and
   Full, and update the results table in `metabolic_task_decisions.md`. A
   task that only passed through a leak will now fail; list those.

## Scripts

Earlier scratchpad scripts are not kept between sessions. This is the core
loop (run from the THG repo root, GLPK):

```python
import sys
from cobra import Reaction
from cobra.flux_analysis import pfba
from cobra.io import load_json_model, read_sbml_model
from thg_protocol.raven_tasks import import_raven_tasks
from thg_protocol.tasks import run_task_suite

TASKS = "files/metabolic_tasks/metabolicTasks_VerifyModel.txt"
MAPPING = "files/metabolic_tasks/human_gem_names.json"

path = sys.argv[1]
m = load_json_model(path) if path.endswith(".json") else read_sbml_model(path)
m.solver = "glpk"

# Release forced internal fluxes (biomass LB > 0), else every task is infeasible.
for r in m.reactions:
    if not r.boundary and (r.lower_bound > 0 or r.upper_bound < 0):
        r.bounds = (min(r.lower_bound, 0), max(r.upper_bound, 0))

suite = import_raven_tasks(TASKS, m, mapping=MAPPING).suite
print(run_task_suite(m, suite)["counts"])

# pFBA per task to see which reactions carry the leak.
for task in suite.tasks:
    with m:
        for b in m.boundary:
            b.bounds = (0, 0)
        added = []
        for rid, (met, coef, _pair) in task.exchange_bounds().items():
            r = Reaction(rid)
            r.add_metabolites({m.metabolites.get_by_id(met): coef})
            added.append(r)
        m.add_reactions(added)
        for rid, (lb, ub) in task.reaction_bounds().items():
            if rid in m.reactions:
                m.reactions.get_by_id(rid).bounds = (lb, ub)
        print(f"\n[{task.id}] {task.description}")
        try:
            s = pfba(m)
        except Exception as e:  # infeasible: the correct outcome
            print("  infeasible", e)
            continue
        fl = s.fluxes[s.fluxes.abs() > 1e-7].sort_values(key=abs, ascending=False)
        for rid, v in fl.head(15).items():
            rxn = m.reactions.get_by_id(rid)
            print(f"  {v:9.3f} {rid} {rxn.build_reaction_string(True)[:110]}")
```

Human-GEM reference for comparisons: `pipeline/models/Human-GEM.xml`, or the
develop model at
`https://raw.githubusercontent.com/SysBioChalmers/Human-GEM/2f1d3e33ce591b357accc08d85aebc27bdcf4244/model/Human-GEM.yml`.

## Related

`conservation_flow_plan.md`: a general flow (unconserved metabolites →
responsible reactions → reviewed fixes) that would replace steps 2–5 here
for mass inconsistencies. It does not catch charge-only imbalances.

## Out of scope

- `EC_3006_1` (BiGG IDs; the tables do not resolve on it).
- Decisions 2–6 in `metabolic_task_decisions.md`.
