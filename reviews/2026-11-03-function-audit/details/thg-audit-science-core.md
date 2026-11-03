What this repo does: This package builds and checks constraint-based human metabolic models, including pathway addition, gap filling, model merging, and task evaluation. I assumed one researcher or workflow process running analyses on genome-scale models, with solver-backed LP/FVA checks.

**Must fix**

1. **Pathway import can silently change reaction chemistry** (`src/thg_protocol/pathway/core.py:141-168`)
   - **What this is:** `parse_universal_reaction` resolves each parsed participant and builds the reaction stoichiometry from the ones it can resolve.
   - **Problem:** It skips any unresolved participant and returns the partial reaction if another term resolved. For `A[c] + MISSING[c] --> B[c]`, with A and B known but MISSING unknown, the public API returns `A_c --> B_c` as if it were the configured reaction. `create_compartment_reactions` then imports that altered reaction; the function is also exported as `thg_protocol.pathway.parse_universal_reaction`.
   - **Fix:** Reject the entire equation if any participant fails resolution, and surface the omitted term in the error/result.
   - **If we skip it:** Imported models can contain reactions with different chemistry from the supplied pathway config.

2. **Generated reaction IDs can silently discard configured reactions** (`src/thg_protocol/pathway/core.py:266-314`)
   - **What this is:** `create_compartment_reactions` assigns sequential `MAR#####` IDs to config rows without IDs and skips rows whose IDs already exist.
   - **Problem:** It processes rows in order. With an ID-less first row followed by an explicit `MAR00001` row, the first row consumes `MAR00001`; the explicit row is then skipped as a collision. I reproduced the public helper returning one addition and losing the second configured reaction.
   - **Fix:** Reserve all explicit IDs before assigning IDs to rows that need generated IDs, then report genuine duplicate explicit IDs instead of silently skipping them.
   - **If we skip it:** Valid reaction definitions can disappear based only on config ordering.

3. **Pathway workflow repeats ID-less reactions per compartment** (`src/thg_protocol/pathway/workflow.py:86-98`)
   - **What this is:** `implement_pathway` iterates over resolved compartments and calls `create_compartment_reactions` each time, while that helper ignores its compartment argument and consumes the full global reaction list.
   - **Problem:** A config with compartments `c` and `e` and one ID-less reaction `A[c] --> B[c]` adds the same stoichiometry twice under different IDs. The result passes duplicate-ID validation, so the accidental duplicate is not reported; the repeat is reached by the exported workflow API and its file/CLI wrapper.
   - **Fix:** Apply the reaction list once, or select reactions explicitly by target compartment before each call.
   - **If we skip it:** Pathway imports can inflate reaction counts and alter model behavior through duplicate reactions.

4. **Negative minimum flux can make failed gap fills appear solved** (`src/thg_protocol/gapfill/core.py:473-541, 750-837`)
   - **What this is:** `_resolved_parameters` validates the parameters passed by `gapfill_model`; `_run_milp` uses `minimum_flux` as the candidate lower bound and checks the final objective against that threshold.
   - **Problem:** `minimum_flux=-1` passes validation. I ran the public `gapfill_model` with a blocked biomass objective, a valid temporary universal model containing the needed precursor source, and that threshold: it returned `status='solved'`, selected no reactions, and still had objective flux 0. The final `abs(objective_flux) >= minimum_flux` check accepts zero, and the same negative value reaches COBRApy’s gap filler. The public API and CLI accept this parameter.
   - **Fix:** Require `minimum_flux` to be a finite positive number (and reject booleans/non-numbers), consistent with its meaning as a required flux threshold.
   - **If we skip it:** An infeasible objective with zero flux can be reported as solved when the caller supplies a negative threshold.

**Should fix**

5. **Finite flux bounds are reported as unbounded** (`src/thg_protocol/analysis/consistency.py:180-193`)
   - **What this is:** `unbounded_reactions` labels an FVA reaction unbounded when either endpoint has magnitude at least 999.
   - **Problem:** With `R: -> A` and `D: A ->`, both bounded `[0, 1000]`, and `D` as the objective, FVA returns 1000 and the function reports both as mathematically unbounded (fraction 1.0). I reproduced this with a small in-memory COBRA model. There are no production callers in the repository, but the helper is a documented public API.
   - **Fix:** Report this as a large-bound heuristic, or determine unboundedness from reaction bounds/solver status instead of a conventional cap.
   - **If we skip it:** Callers can mistake finite-cap reactions for structural unboundedness.


6. **Reverse-only reactions are treated as blocked during sink removal** (`supplementary_material/crucial_exchange_rs.ipynb`, cell 29, `test_and_remove_rxns`, lines 21-31)
   - **What this is:** The notebook removes sink/demand reactions one at a time and uses flux variability analysis (FVA) to check whether internal reactions remain usable.
   - **Problem:** It calls an internal reaction blocked whenever its FVA maximum is at most zero. An FVA interval of `[-10, 0]` permits reverse flux, but this code calls it blocked and restores the sink, leaving an unnecessary boundary reaction in the model. The extracted function reproducer confirms this behavior.
   - **Fix:** Call an interval blocked only when both minimum and maximum are approximately zero, using a solver tolerance.
   - **If we skip it:** The pruning step can keep sinks/demands that are not needed for internal reaction feasibility.

7. **Dead-end product/substrate labels ignore reaction bounds** (`supplementary_material/extra.ipynb`, cell 4, `classify_deadend_in_final_model`, lines 92-112)
   - **What this is:** The notebook labels a metabolite as a final substrate or product from the signs of its reaction stoichiometric coefficients.
   - **Problem:** It ignores whether the reaction can run forward or backward. In a reversible `A_c -> B_c` reaction with bounds `[-10, 10]`, it labels `A_c` a final substrate even though reverse flux can produce it; the extracted function reproducer confirms this.
   - **Fix:** Determine possible production and consumption from each reaction’s stoichiometry together with its flux bounds before assigning a label.
   - **If we skip it:** Notebook summary lists can report the wrong direction for a dead-end metabolite.

**Nice to have**

8. **`nullity` can return a rank-deficient completion** (`src/thg_protocol/model_build/mass_balance.py:262-284`)
   - **What this is:** `nullity` appends trailing unit rows until the output has one row per matrix column.
   - **Problem:** For `[[0, 1]]`, it appends `[0, 1]`, duplicating the independent row; the returned 2-by-2 matrix still has rank 1. `nullity` is listed in the public construction API, but repository search finds no production caller (only a shape-level unit test).
   - **Fix:** Choose completion rows independent of the retained rows, or rename/document the output if a square full-rank matrix is not promised.
   - **If we skip it:** External callers that rely on the completed matrix being full rank can get a singular matrix.

**Scientific review**

The remaining reviewed scientific checks use stoichiometric elemental totals for mass/charge diagnostics, reaction bounds for directional reachability, and boundary closure for cycle checks. These are useful model diagnostics, not proof of physiological feasibility or thermodynamic validity. The energy-cycle gate documents its limit: it examines one least-flux cycle per energy couple, so an existing cycle can hide a newly introduced alternative. This scope is consistent with the energy-generating-cycle work and COBRApy’s definition of FVA as reaction-wise minimum/maximum flux analysis ([Fritzemeier et al., 2017](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005494), [COBRApy FVA documentation](https://cobrapy.readthedocs.io/en/latest/autoapi/cobra/flux_analysis/variability/index.html)).

The per-function ledger is `/tmp/thg-audit-science-core-coverage.json` (410 entries, keyed by file/cell/line/name where relevant); it now records a short function-purpose rationale and identifies F1–F8. The supplementary notebook ledger covers 28 callable bodies. The boundary direction labels in `tr_row` are equation-forward hints and include bounds; they are not presented as feasible net directions.

Verdict: fix F2–F4 first because they can silently alter pathway imports; reject invalid `minimum_flux` values before running MILP gap filling.

Not checked: I did not rerun the full test suite or execute supplementary notebooks; notebook cells depend on local model files and some write generated workbooks. The six-case core reproducer passes; separate scripts reproduce the public negative-threshold gap-fill result and both notebook directionality findings. The full suite was reported by the parent agent as passing 2,430 tests.
