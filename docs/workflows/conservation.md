# Conservation

The `conservation` workflow finds metabolites a model cannot conserve, finds
the reactions responsible, proposes fixes where a rule supports one, and
applies only the fixes a curator approves. The input model is never edited:
approved fixes go to a copy and to the change ledger.

It requires the optional `memote` extra (`pip install 'thg-protocol[memote]'`)
and uses the solver the model is configured with (Gurobi or CPLEX if
installed, otherwise GLPK).

## Run it

```json
{"workflow": "conservation",
 "run": {"name": "conservation", "output_dir": "../runs/conservation"},
 "conservation": {"input_model": "../inputs/models/beta1.xml",
                  "comparison_model": "../inputs/models/Human2.xml",
                  "decisions_file": "../inputs/conservation-decisions.jsonl",
                  "exclusions": []}}
```

```bash
thg-run conservation configs/conservation.json   # proposals and review page
# write the decisions file
thg-run conservation configs/conservation.json   # applies approved fixes, re-checks
```

The second run reuses detection, localization, and proposals; only the apply
and re-check stages rerun when the decisions file changes.

| Key | Meaning |
| --- | --- |
| `input_model` | Model to check (required) |
| `comparison_model` | The input model of the step being checked; enables origin labels, inherited/new attribution, the restore rule and formula comparison |
| `decisions_file` | JSONL curator decisions; may be absent on the first run |
| `exclusions` | Extra reaction IDs to leave out of the conservation analysis |

## Stages

1. **Detect** (`conservation-detect`). MEMOTE's
   `check_stoichiometric_consistency` (one LP) and, only if that fails,
   `find_unconserved_metabolites` (one MILP), after Gevorgyan et al. (2008).
   Stoichiometry only: directions, bounds and formulas are ignored. Boundary
   reactions are excluded, and so is each reaction caught by one of these
   rules (reported with the rule):
    - `sbo-biomass`: SBO term `SBO:0000629`;
    - `pseudo-subsystem`: subsystem "Artificial reactions" or "Pool reactions";
    - `model-note`: an approved exclusion recorded in the reaction notes;
    - `input-model`: excluded in the comparison model (by ID), so the
      exclusion survives in derived models that lost subsystem names;
    - `configuration`: listed in `exclusions`;
    - `memote-biomass`: any further reaction MEMOTE's biomass heuristic finds.
2. **Localize** (`conservation-localize`). One LP in the model's solver
   gives every metabolite a positive mass and minimizes the total mass the
   reactions create or destroy:
   `min Σ_j |s_j|` subject to `Σ_i S_ij m_i = s_j`, `m_i ≥ 1`. Reactions
   with `s_j ≠ 0` are **blamed**; removing them always leaves a consistent
   model, because `m` then conserves every remaining reaction. The set is
   small but not provably minimal, and it does not need the list of
   unconserved metabolites. On β1 (about 19,000 internal reactions) it takes
   about 20 s with Gurobi and 5 min with GLPK.

   A mass-creating loop can often be broken at several reactions at the same
   cost. Ties go to **chemically suspect** reactions (element or charge
   imbalance, a metabolite without formula or charge, non-integer
   coefficients): every other reaction costs 0.1% more. This uses the model
   alone, not the comparison model, and never changes the size of the set by
   more than that fraction.

   Each blamed reaction is reported with its imbalance, its origin relative
   to the comparison model (added, changed, unchanged), its element and
   charge balance, its non-integer coefficients, the metabolites whose
   formula or charge disagrees across compartments or with the comparison
   model, and possibly mislabelled metabolites (`possibly-mislabelled`: see
   `annotation-conflict` in [validation](validation.md)). Flagged reactions come first; a blamed reaction without any flag is
   often an innocent member of a loop that had to be broken somewhere.
   Metabolites already unconserved in the comparison model are reported as
   **inherited**.
3. **Propose** (`conservation-propose`). Writes `proposals.jsonl`. The
   [validation report](validation.md#suggested-fixes) shows the same
   proposals (their IDs match for the same model) with decision controls,
   next to fixes for other checks. Decisions exported there are applied with
   `thg-run apply-decisions`, not with this workflow: the `decisions_file`
   here may only reference proposals in `proposals.jsonl`, and any other
   decision stops the apply stage.
4. **Apply** (`conservation-apply`). Applies only `approve` and `replace`
   decisions (`mode="user-approved-only"`), writes `model-fixed.*` and
   `change-ledger.jsonl`.
5. **Re-check** (`conservation-recheck`). Detects again on the fixed copy and
   reports the unconserved set before and after. If the copy is still
   inconsistent, the localization LP runs again, and an applied fix whose
   reaction is still blamed is reported as ineffective.

## Proposal rules

| Situation | Proposal | Policy |
| --- | --- | --- |
| Reaction is in the comparison model with different stoichiometry | Restore that stoichiometry | `restore-input-stoichiometry` |
| Reaction has non-integer coefficients (such as fitted `1.2 O2 -> 1.5 product`) | Round each one down or up (never to zero) and keep the integer stoichiometries that balance the elements; several are listed as low-confidence alternatives | `integer-stoichiometry` |
| Element residual equals a cofactor addition: NAD+/NADH + H+, NADP+/NADPH + H+, H2O, CO2, Pi, CoA (either direction) | Add it; every fitting candidate is listed, as low-confidence alternatives | `cofactor-pair` |
| Added metabolite has no formula and one formula balances all its reactions | Set that formula | `infer-formula` |
| Reaction ID or name looks like a biomass, pool, pseudo, lumped or artificial reaction | Exclude it from the analysis (recorded in its notes) | `exclude-pseudo-reaction` |
| A blamed reaction no rule covers | `unresolved` removal, for manual curation only | `unresolved` |

Each proposal records, for the reaction before and after the fix, the
equation with IDs and with names, the element residual (or the metabolites
lacking a formula), the charge residual (or those lacking a charge), and the
reaction in the comparison model. Its evidence is the blamed reaction and its
imbalance, and it lists the reactions it targets and a confidence level. A fix that is
still unbalanced afterwards carries `after-unbalanced-elements`,
`after-unbalanced-charge` or a missing-formula/charge flag.

The review page lists the proposals, then the blamed reactions in two tables:
those with a chemical flag, and those without.

## Decisions

One JSON object per line:

```json
{"proposal_id": "prop-…", "action": "approve"}
{"proposal_id": "prop-…", "action": "reject", "reason": "wrong cofactor"}
{"proposal_id": "prop-…", "action": "replace", "replacement": {"MAM02039c": 1, "MAM02040c": -1}}
{"proposal_id": "prop-…", "action": "defer"}
```

A `replace` uses the same shape as the proposal's `after`: a stoichiometry
object for reactions, a formula string for metabolites. Approving two fixes
for the same reaction (for example both NAD and NADP alternatives) is an
error.

## Not covered

Reactions whose atoms balance but whose charge or redox does not still admit a
positive mass vector and are not detected; charge is reported in proposals
and flags only. A reaction that balances against a metabolite with the wrong
identity (for example a name-based match to a different compound) shows up
only through its flags, typically a charge imbalance or unusual coefficients. Metabolic tasks (for example VerifyModel) remain the backstop for these.

Canonical APIs:
[`find_unconserved_metabolites`][thg_protocol.analysis.conservation.find_unconserved_metabolites],
[`localize`][thg_protocol.analysis.conservation.localize],
[`propose_fixes`][thg_protocol.analysis.conservation.propose_fixes], and
[`apply_conservation_fixes`][thg_protocol.analysis.conservation.apply_conservation_fixes].
