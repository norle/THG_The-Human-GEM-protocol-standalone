# Native GIMME

GIMME is the recommended cell-specific reconstruction strategy. It maps each
sample's gene expression through GPR rules (`AND = min`, `OR = max`), then
minimizes the absolute flux through reactions below the expression threshold
while retaining each configured metabolic objective fraction.

Unknown genes and reactions without GPRs are unpenalized; known zero is not
unknown. A reaction is retained when it has expression support, lacks decisive
expression evidence, or carries flux in the GIMME solution. This deliberately
does not equate membership with one raw flux vector.

The implementation uses the COBRApy-attached optlang solver, so GLPK is the
default and Gurobi/CPLEX work through COBRApy without solver-specific code.
Unlike the legacy workflow, it has no Troppo/Cobamp dependency, does not mutate
the source model, and records failed samples rather than treating them as zero
activity.

```json
{
  "reduction_strategy": "gimme",
  "gpr": {"and_rule": "min", "or_rule": "max", "unknown_policy": "unpenalized"},
  "gimme": {
    "expression_threshold": 1.0,
    "flux_activity_tolerance": 1e-7,
    "objectives": [{"id": "biomass", "coefficients": {"MAR13082": 1.0}, "minimum_fraction_of_optimum": 0.2}],
    "minimum_successful_sample_fraction": 0.95
  },
  "consensus": {"presence_threshold": 0.0}
}
```

Expression units and threshold selection are scientific protocol choices; they
are intentionally not hidden defaults.
