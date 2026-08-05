# Contract: mass balance

- **Legacy:** historical equation and mass-balance routines under
  `build_model/`.
- **Maintained:** `thg_protocol.model_build.mass_balance.formula_atoms`,
  `reaction_compare`, and balancing helpers.
- **Inputs/defaults:** formulas and stoichiometric equations, including missing
  formulas and glycan branches; no solver or network access.
- **Result:** parsed atoms, imbalance/missing-atom reports, or a new balanced
  equation. Inputs are not mutated unless an API explicitly returns a revised
  object.
- **Comparison:** compare element totals, coefficient signs, normalization of
  formulas, exceptions, and the positive/negative balance decision.
- **Difference policy:** a changed scientific convention must be named in the
  contract before the differential test is enabled.
