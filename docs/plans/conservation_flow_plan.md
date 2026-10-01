# Unconserved metabolites: detect, localize, propose, review, apply

Plan only; nothing is implemented. Written 2026-10-01. Related:
`metabolic_task_leaks_plan.md` (VerifyModel leaks in the endo models) and
`metabolic_task_decisions.md` (open decision 1).

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

### 2. Localize (one LP per unconserved metabolite or group)

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

- The `energy-generating-cycles` check in `validation.py` runs closed-medium
  FVA, so it reports internal loops, not energy-generating cycles. Rename
  (e.g. `internal-cycles`), and add a real Fritzemeier test separately if
  wanted.
- `minimal_inconsistent_sets` returns blocked-reaction singletons, not
  inconsistent sets; step 2 supersedes it.
- MEMOTE runs only with `run_memote: true`, and its results never affect
  `passed`. A full run takes hours at Human-GEM scale.
- `assemble-validation-report` hardcodes `tasks` as `not-requested`, so
  `thg-run validate` never runs a task suite (VerifyModel included).
