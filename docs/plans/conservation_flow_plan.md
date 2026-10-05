# Unconserved metabolites: detect, localize, propose, review, apply

Written 2026-10-01; implemented 2026-10-01/02 in `analysis/conservation.py`,
the `conservation` workflow and the validation checks; see
`docs/workflows/conservation.md` and `docs/workflows/validation.md`.
Detection reuses MEMOTE's `check_stoichiometric_consistency` /
`find_unconserved_metabolites` with the model's solver; localization is one
optlang LP built the same way. The sections from **Goal** on are the
original plan; where they differ from the implementation (step 2 in
particular), the next section is authoritative. Related:
`metabolic_task_leaks_plan.md` (VerifyModel leaks in the endo models) and
`metabolic_task_decisions.md` (open decision 1).

## What was implemented and why (2026-10-02)

All changes are uncommitted on `refactoring-cleanup`. Measurements are on
`models/THG-beta1.xml` against `models/Human-GEM_2022-06-21.xml`.

### 1. Localization: one LP instead of one LP per metabolite

**What.** `blame_reactions` in `analysis/conservation.py` solves

    min Σ_j w_j |s_j|   s.t.   Σ_i S_ij m_i = s_j,   m_i ≥ 1

over the non-excluded internal reactions. Every metabolite gets a positive
mass; `s_j` is the mass reaction `j` creates or destroys. Reactions with
`s_j ≠ 0` are **blamed**. `leakage_modes`, `rank_reactions` and the
`conservation.max_modes` key were removed.

**Why.**

- The per-metabolite leakage-mode LPs did not scale: β1 has 7,428
  unconserved metabolites, and GLPK found 20 modes in more than 25 minutes.
  Nearly the whole model being unconserved meant a few reactions were the
  cause, so the question is better asked of reactions than of metabolites.
- One LP of about the detection LP's size: 22 s with Gurobi, 311 s with
  GLPK. It needs no list of unconserved metabolites.
- Removing the blamed reactions always restores consistency, because `m`
  then conserves every remaining reaction. Verified on β1 with MEMOTE: 66
  reactions blamed, consistent after removal.
- It is the LP relaxation of the minimal-inconsistent-set MILP that did not
  finish at Human-GEM scale: small, not provably minimal.

**Tie-break.** A loop can be broken at several reactions at equal cost.
`chemically_suspect` reactions (element or charge imbalance, a metabolite
without formula or charge, a non-integer coefficient) cost 1, all others
1.001, so ties go to suspect reactions and the optimum moves by at most
0.1%. It uses the model alone.

**Rejected alternatives.**

- Origin weights (added 1, changed 2, unchanged 10 relative to the input
  model): blamed only β1-introduced reactions, but made the result depend
  on the input model.
- Reading leakage modes from the LP dual: the dual flux covered about
  11,000 reactions, too many to show a curator.
- A joint "reaction or formula" LP (`m` anchored to atom counts with weight
  λ, to blame wrong formulas): at λ = 0.1 it shifted about 10,700 formulas,
  at λ = 1-10 it blamed 157-228 reactions, and atom counts are no mass
  anchor with `R`/`X` pseudo-elements (ACP is `HOR`). It also could not have
  caught the EPA case below, where the formula is right and the identity is
  wrong.

### 2. Chemical flags on blamed reactions and new proposal rules

**What.** `localize` reports each blamed reaction with its imbalance,
origin, element and charge balance, non-integer coefficients
(`fractional-coefficients`), metabolites whose formula disagrees
(`formula-disagreement`) and possibly mislabelled metabolites
(`possibly-mislabelled`). Flagged reactions come first; the review page
shows flagged and unflagged blamed reactions in separate tables.
`propose_fixes` works per blamed reaction, with a new rule
`integer-stoichiometry`: each non-integer coefficient is rounded down or up
(never to zero) and the element-balanced results are proposed. The re-check
reruns the LP and reports a fix as ineffective when its reaction is still
blamed.

**Why.** The LP says which reactions break conservation, not what is wrong
with them. The flags say what, and separate real culprits from innocent
loop members. On β1 most culprits carry fitted coefficients
(`1.2 O2 -> 1.5 product`, `2.5 O2`, `1.3 …`), hence the integer rule.

### 3. Validation checks

**What** (`validation.py`, all diagnostic in every profile, no solver):

| Check | Flags | β1 vs Human-GEM |
| --- | --- | --- |
| `fractional-coefficients` | Internal reactions with non-integer coefficients (pseudo-reactions skipped by the conservation exclusion rules) | 202 |
| `formula-disagreement` | Formula or charge differing across compartments or from the reference (compared as element counts) | 0 |
| `annotation-conflict` | Names shared by different compounds (formula beyond H, or KEGG); metabolites renamed from the reference to another, conflicting compound's name | 19 names, 33 renamed |
| `unusual-protons` | More than 10 H+, new or changed relative to the reference | 22 |

`validation.reference_model` (optional) names the model the checked one
derives from; its conservation exclusions carry over and the checks above
compare against it. The closed-medium FVA `energy-generating-cycles` check
was removed. A β1 validation run with `beta1-standard` and solver checks
takes about 5 minutes with Gurobi.

**Why.**

- Fractional coefficients and wrong identities were the main causes found
  on β1; the checks find them without the LP.
- ChEBI is not compared because it gives an acid and its conjugate base
  different IDs (hundreds of false conflicts). The rename check requires the
  new name to belong to another, conflicting compound; any name change gave
  1,289 hits, mostly spelling ("eicosenoyl" -> "Icosenoyl").
- Proton limit 10: Human-GEM itself has 139 reactions above 4 and 63 above
  10 (mostly transport chains); compared with the reference, β1 has 22, all
  new or changed, including known culprits.
- The removed check reported internal loops, not energy-generating cycles,
  and a second full FVA was too slow at β1 scale.

### 4. The EPA case: wrong mappings in the legacy merge

**Finding.** `R08179_c` (`EPA-CoA + H2O -> 2 EPA + CoA + 14 H+`) is
element-balanced but wrong. Human Database has it right (`EPA-CoA + H2O ->
CoA + H+ + EPA`, KEGG `C06428`, `C20H29O2`). The legacy merge that built
THG-2023-02-25, and from it β1, mapped `C06428` onto Human-GEM's
`MAM00668c` (2-naphthol, `C10H8O`, KEGG `C11713`), renamed it to
icosapentaenoic acid, and fitted the coefficients to the wrong formula.
Human-GEM's real EPA is `MAM01784`, and Human-GEM itself is correctly named.
The same merge renamed about 30 other Human-GEM metabolites to other
compounds' names, for example succinylacetone -> arachidonyl-CoA, maltose ->
presqualene diphosphate, midazolam -> 2-oxoglutaramate, histidine ->
1-alkenyl-2-acylglycerol, sucrose -> 5-phosphoribosylamine, tyramine ->
2-hydroxyglutarate, valeric acid -> selenite.

**Prevention** (this repository; the legacy script is not part of it):

- `merge.generate_merge_plan` maps only on shared identifiers, never on
  names, and only when formula (hydrogen included) and charge are identical
  and KEGG compound IDs are not disjoint; see
  [final THG merge](../workflows/final-thg.md#merge-and-validation).
- β1 identity scoring (`score_metabolite_candidate`) no longer counts a name
  match whose formula conflicts beyond hydrogen; the β1 stage now passes
  InChI/InChIKey/SMILES annotations as structural identifiers.
- The β1 balance strategy was already safe: `proton-water` adds only H+/H2O
  and only when that removes both element and charge residuals, so it cannot
  fit `2 EPA + 14 H+`.
- Shared helper: `model_build.mass_balance.formulas_conflict` (formulas that
  differ only in H are protonation states, not a conflict).

**Detection.** The charge flag (+14), `annotation-conflict`,
`unusual-protons`, and the `possibly-mislabelled` flag on blamed reactions.

**Not done.** The wrong mappings already in β1 are not repaired; the
`annotation-conflict` details list them for curation.

### 5. Solver

cobrapy picks Gurobi, then CPLEX, then GLPK; `gurobipy` 12.0.1 is now
installed in `thg_standalone`, so Gurobi is the default there. Two fixes
followed:

- `leakage_modes` (since removed) read the solution after changing a bound;
  GLPK keeps the old solution, Gurobi discards it. The LP code now reads
  results before any model change.
- `thg-run validate MODEL --json` sends solver output to stderr, since
  Gurobi's licence banner on stdout broke the JSON. The GIMME test accepts
  the configured solver instead of GLPK.

### Tests

New or extended: `tests/unit/test_conservation.py`,
`test_phase3_validation.py`, `test_beta1_curation.py`, `test_merge_api.py`,
`test_workflow_structure.py`, `test_cell_specific_gimme.py`. 333 unit tests
pass with Gurobi; the conservation, validation, merge and β1 curation tests
also pass with GLPK. The strict docs build passes.

### Next

1. Curate the mislabelled metabolites in β1 (the `annotation-conflict`
   list) and remap affected reactions, for example `R08179_c` to `MAM01784`.
2. Run the `conservation` workflow on β1 against Human-GEM and review the
   proposals.
3. Review and commit.
4. Later: stage-level use after each pipeline step; the "found while
   planning" items below.

## Goal

A flow that finds metabolites a model cannot conserve, finds the reactions
responsible, proposes fixes where a rule supports one, and applies only the
fixes a curator has approved. Input models are never edited; fixes go to a
copy and to the change ledger.

## Why stoichiometric consistency, not a flux leak scan

- **Unconserved metabolites** (Gevorgyan et al. 2008, as in MEMOTE): there is

  no positive mass assignment under which every internal reaction conserves
  them. One LP. Uses stoichiometry only: directions and bounds are ignored, and
  creation and destruction of mass are both covered. No formulas needed.
- **Leaking metabolites** (closed medium, a sink on every metabolite): those
  the model can actually produce under its bounds and directions.
- Every leak implies an inconsistency, but not the reverse (an inconsistency
  may only run in a blocked direction). So leaking ⊆ unconserved, and the
  consistency check is the more conservative of the two. Chosen for that
  reason.
- **Not covered:** reactions whose atoms balance but charge or redox does not.
  A positive mass vector still exists, so they are not flagged. `R08758_c`
  (missing NAD(P)+ → NAD(P)H, releases 2 H+) is probably this kind
  (unverified). Charge is reported in the proposals (below) but is not used for
  detection yet. VerifyModel remains the backstop for these.

## Flow

### 1. Detect (one LP)

- Maximize the number of metabolites that can get a positive weight, subject
  to `Sᵀm = 0` over internal reactions and `0 ≤ z ≤ m`, `z ≤ 1`. Metabolites
  with `z = 0` are unconserved.
- Boundary reactions are excluded (as now). Biomass, pool and lumped
  pseudo-reactions are also excluded, since they are unbalanced by design and
  would otherwise dominate the result. A reaction is excluded when any of
  these holds (each excluded reaction is reported with the rule that caught
  it):
  1. SBO term `SBO:0000629` (biomass production);
  2. subsystem "Artificial reactions" or "Pool reactions" (Human-GEM's
     labels: 18 and 48 reactions);
  3. excluded in the input model (by ID), so the exclusion survives in
     derived models;
  4. listed in the configuration.

  Rule 3 matters because derived models lose subsystem names: endoC's 142
  groups are unnamed (`G_group1`, …) and endoA has no subsystems, while
  endoC keeps `SBO:0000629` on `MAR13082`. Only 13 of Human-GEM's 66
  artificial/pool reactions are in endoC.
- Output: consistent yes/no, the unconserved metabolites (ID, name,
  compartment), and the exclusion list used.
- This is the only step that runs inside `thg-run validate` (see open
  decision 1 for its policy). It replaces the pass/fail-only
  `stoichiometric_consistency` result with one that names the metabolites.

### 2. Localize (one LP per unconserved metabolite or group; superseded by one LP, see above)

- For an unconserved metabolite `i`, find the smallest combination of
  reactions (directions ignored, `min Σ|v|`) with `Sv ≥ 0` and `(Sv)ᵢ ≥ 1`,
  and the reverse for destruction. Each solution is a **leakage mode**: an
  explicit, small reaction set that creates or destroys `i`.
- Group metabolites that share a mode, so one LP is not repeated per
  metabolite.
- Rank reactions by the number of modes they appear in, then by origin
  relative to the **input model** (the model the step started from, not a
  fixed Human-GEM):
  1. added by the step (not in the input model),
  2. in the input model with changed stoichiometry,
  3. unchanged from the input model.
- Unconserved metabolites already present in the input model are reported
  separately as **inherited**: they were not caused by this step. Only new
  ones are attributed to it.
- Without an input model (a standalone check), there is no origin ranking
  and no restore rule; modes and formula-based rules still apply.
- Replaces the exact minimal-inconsistent-set MILP, which does not finish at
  Human-GEM scale. Expected cost seconds to minutes (unmeasured).

### 3. Propose fixes (only where a rule applies)

| Situation | Proposed fix |
|---|---|
| Reaction is in the input model with different stoichiometry | Restore the input model's stoichiometry |
| Element imbalance equals a known cofactor pair (2 H: NAD+/NADH or NADP+/NADPH; H2O, CO2, Pi, CoA) | Add the pair; list all fitting candidates when ambiguous |
| Added metabolite has no formula, and one formula balances all its reactions | Set that formula |
| Biomass, pool or lumped reaction | Add it to the exclusion list, not a stoichiometry change |
| No rule applies | `unresolved`, for manual curation; removal/blocking offered only as a last resort |

Proposals use the existing `workflow/proposals.py` `Proposal` record. Each
proposal states, for the reaction **before** and **after** the fix:

- the reaction equation, with IDs and with names,
- the element balance (per-element residual, e.g. `H: +2`), or which
  metabolites lack a formula,
- the charge balance (net charge residual), or which metabolites lack a charge,
- whether the reaction is in the input model, and its equation there,

plus the leakage modes and unconserved metabolites it explains, the rule that
produced it, and a confidence level. A fix whose "after" is still unbalanced
(in elements or charge) is flagged in the proposal rather than hidden.

### 4. Review (manual)

- Writes `proposals.jsonl` and a review page (HTML, with the same content as
  Markdown) with one row per proposal: reaction, before/after equation,
  element and charge residuals before/after, evidence, confidence.
- The curator writes `decisions.jsonl` with `approve`, `reject`, `replace`
  (own edited fix) or `defer` per proposal, the existing `Decision` record.

### 5. Apply and re-check

- Applies with `apply_proposals(..., mode="user-approved-only")`: only
  approved or replaced proposals change the model copy. Each change goes to the
  change ledger.
- Re-runs step 1 on the result and reports the unconserved set before and
  after. An approved fix that removed no unconserved metabolite is flagged.

## Where it lives

- `src/thg_protocol/analysis/conservation.py`: unconserved metabolites,
  leakage modes, element/charge residuals, proposal rules.
- `thg-run validate`: step 1 only.
- After each pipeline step (β1, β2, Human Database integration, gapfill,
  cell-specific reduction), with that step's input model as the comparison.
  Decided, low priority: after the standalone flow works.
- New registered workflow (name to decide, e.g. `conservation`) with resumable
  stages: detect → localize → propose → (decisions file) → apply → re-check.
  Run once to get proposals; add decisions; run again to apply.
- Tests: small models with a planted inconsistency of each kind (missing
  cofactor, changed stoichiometry, missing formula, pool reaction), checking
  detection, the leakage mode, and the proposed fix.
- Docs: `docs/workflows/validation.md` and a page for the new workflow.

## Decided (2026-10-01)

- **Comparison model:** the input model of the step being checked, not a
  fixed Human-GEM.
- **Exclusions:** SBO biomass term, Human-GEM's "Artificial reactions" and
  "Pool reactions" subsystems, inherited from the input model, plus a
  configured list (step 1).
- **Stage-level use:** run after each pipeline step; low priority.

## Open decisions

1. **Warning or blocking.** Whether the detect step in validation only warns
   (as `stoichiometric-consistency` does today in every profile) or blocks
   release in some profiles (`post-gapfill`, `final-standard`,
   `release-full`). Depends on what Human-GEM itself gives: if it has
   unconserved metabolites, blocking would need an accepted-exceptions list.
   With the input-model comparison, an option is to block only on **new**
   unconserved metabolites, not inherited ones.
2. **Charge-only imbalances** (the `R08758_c` kind): detect later through
   charge balance, or leave to VerifyModel. Deferred.

## Found while planning (not part of this flow)

- The `energy-generating-cycles` check (closed-medium FVA, so it reported
  internal loops, not energy-generating cycles) was removed from
  `validation.py` on 2026-10-02: a second full FVA was too slow at beta1
  scale. Add a real Fritzemeier test separately if wanted.
- `minimal_inconsistent_sets` returns blocked-reaction singletons, not
  inconsistent sets; step 2 supersedes it.
- MEMOTE runs only with `run_memote: true`, and its results never affect
  `passed`. A full run takes hours at Human-GEM scale.
- `assemble-validation-report` hardcodes `tasks` as `not-requested`, so
  `thg-run validate` never runs a task suite (VerifyModel included).
