# Gap-filling with sink-MILP

*Technical note, 2026-10-12, branch `refactoring-cleanup` (head `41d28d2`).
Code: `src/thg_protocol/gapfill/ptr.py`. User docs: `docs/workflows/gapfill.md`.*

## The problem

After β2 has copied reactions into compartments, many reactions are
**blocked**: they cannot carry flux at steady state under the model's bounds.
Usually this is because a metabolite is made in one compartment and needed in
another, with no transport between them. Some parts of the network are not
connected to the main network at all.

`sink-milp` fixes this by adding **putative transport reactions (PTRs)**. A
PTR is a reversible reaction `X[c1] <=> X[c2]` (bounds ±1000) that moves the
same metabolite between two compartments. It tries to unblock as many
reactions as possible while adding as few PTRs as possible. It is the default
gap-filling method of the reference workflow (`configs/reference.json`).

## Before and after

The method comes from the legacy `gapfill/` scripts (strategy `sink_milp` in
`gapfill.py`, mainly `phase3_sink_milp_original.py`).

| | Legacy | Now |
| --- | --- | --- |
| Strategies | greedy, hybrid, tiered MILP, component MILP, sink MILP, chosen by CLI flag | `sink-milp` only for the putative-transport pipeline (`greedy` and `deadends` remain as simpler methods) |
| How it runs | Three scripts passing CSV/JSON files between them; components picked by hand (`--components 4,5,6,7`) | Four resumable stages in the reference workflow; every component of ≥ 4 nodes is processed |
| MILP | One per component, solved with PuLP or SciPy | One for the whole model, solved with the model's own solver (Gurobi/CPLEX/GLPK through optlang) and with a global budget |
| Blocked-reaction test | Two LPs per reaction, parallelised with a process pool | LPs over batches of reactions (FASTCC LP7 and a random-direction LP pair), single process |
| "Carries flux" threshold | `10 × solver tolerance` (≈ 1e-5 with Gurobi) | `1e-4` |
| Credit for the temporary sinks | Included in candidate coverage | Excluded (`sink_only`) |
| Caching | Pickle files keyed by a hash of the model file | Per-component JSONL lines in the run directory, reused when a retry has the same inputs |
| Checks | None | Rejects PTR IDs that clash with existing reactions; checks the result without sinks afterwards |

## How it works

### Stage 1 – candidates (`generate-gapfill-candidates`)

1. Build the undirected reaction–metabolite graph and number its connected
   components by size (1 = main component).
2. Group metabolites by **base ID**, i.e. the ID with its compartment suffix
   removed (`MAM01234c`, `MAM01234m` → `MAM01234`).
3. Within a group, every pair of metabolites in an **allowed compartment
   pair** is a possible PTR. The allowed pairs are the curated
   `allowed_connections` list in the config (21 pairs taken from legacy).
4. Each pair gets a type from the dead-end status of its two ends:
   - **A**: a dead-end product and a dead-end substrate (the best fit: one
     side makes what the other side needs);
   - **B**: two dead ends of the same kind;
   - **C**: anything else.
5. A pair is kept if its two ends are in **different components** (any type),
   or both are in the main component **and** it is type A or B.
6. Pairs that an existing transport already covers are kept for the record
   as `already-present` but are never added.

Output: `ptr-candidates.jsonl`, `ptr-components.json`.

### Stage 2 – connectors (`select-gapfill-connectors`)

Treat each component as a node and each candidate between two components as
an edge. Build a **minimum spanning tree** (Kruskal's algorithm) in which edges
are ranked by type (A < B < C) and then by base ID. This links every component
to the network with as few PTRs as possible. These PTRs are the
**connectors**. They are always proposed.

Output: `ptr-connectors.jsonl`.

### Stage 3 – coverage (`compute-gapfill-coverage`)

This is the expensive step. It runs on the model with the connectors added.

1. For each original component of at least `min_component_size` (4) nodes,
   the **targets** are its reactions that are still blocked.
2. Add a temporary **source** for every dead-end substrate and a temporary
   **sink** for every dead-end product. This simulates "the rest of the
   network can supply or remove this metabolite". Without it, a single PTR
   rarely unblocks anything on its own, because the pathway behind it is
   still a dead end.
3. Targets that the sinks/sources unblock without any PTR are recorded as
   `sink_only`. No candidate gets credit for them.
4. For each remaining candidate PTR that touches the component: add it, test
   which remaining targets are now unblocked, then remove it. This gives a
   coverage list `candidate → {targets it unblocks}`.

A reaction counts as unblocked if it can carry |v| ≥ 1e-4. The test does not
run two LPs per reaction:

- **Irreversible reactions** use FASTCC's LP7, which maximises the number of
  reactions that carry at least ε in one LP. Any reaction at ≥ ε in the
  solution is unblocked. If the optimum is below ε, none of the rest can be
  unblocked.
- **Reversible reactions** are pushed in both directions along one random
  weight vector `c` (max and min of `c·v`). If `c·v` cannot vary, none of
  them can carry flux.
- If neither LP gives a new answer, the remaining reactions are tested one at
  a time, so the result is the same as the per-reaction test (up to solver
  tolerance).

Each finished component is written as one line of `ptr-coverage.jsonl`. If
the stage fails or is interrupted, a retry with the same inputs reuses those
lines.

### Stage 4 – selection (`generate-gapfill-plan`)

One MILP over all components:

```
variables   y_p ∈ {0,1}    1 if candidate PTR p is selected
            z_r ∈ [0,1]    1 if target reaction r is covered

maximise    Σ_r z_r  −  λ · Σ_p y_p

subject to  z_r ≤ Σ_{p covers r} y_p     for every coverable target r
            Σ_p y_p ≤ max_additions − (number of connectors)
```

`λ` (`tradeoff_lambda`, default 0.01, must be between 0 and 1) is the cost of
one PTR relative to one unblocked reaction. Because λ < 1, a PTR is chosen
whenever it covers at least one target that is not covered yet. Among
solutions that cover the same number of targets, the one with the fewest PTRs
wins. The `z_r` do not need to be integer: at the optimum each one is pushed
to 0 or 1.

The result is a **plan**, not a changed model: connectors (`phase: 2`) and the
selected PTRs (`phase: 3`), with IDs `GAPFILL_PTR_<met1>_<met2>`. Status is:

- `solved`: everything coverable was covered;
- `partial`: the budget ran out while coverable targets remained;
- `failed`: the MILP did not reach an optimal solution.

Finally, `verify_selection` checks the model with the connectors and selected
PTRs but **without** the temporary sinks. It reports which targets really carry
flux (`verified_unblocked`) and which connectors carry none
(`inactive_connectors`). The report is for review only and changes nothing.

## Why the two legacy fixes matter

- **Credit for sink-only targets.** Legacy counted targets that the temporary
  sinks unblocked on their own as covered by whichever candidate was
  tested. The MILP then "paid" for PTRs that did nothing real.
- **Flux threshold.** Legacy used `10 × model.tolerance`. With Gurobi this
  equals the solver's feasibility tolerance, so forcing that much flux
  through a fully blocked reaction could still succeed numerically. Blocked
  reactions were reported as unblocked. 1e-4 is clearly above solver noise.

## A test run

One run on an older β2 candidate (12,877 reactions, with no location evidence)
with Gurobi:

| Step | Result | Time |
| --- | --- | --- |
| Candidates | 61 components (25 with ≥ 4 nodes); 240 candidates (97 A, 132 B, 11 C), 66 already present | 3.7 s |
| Connectors | 7 | – |
| Coverage | 1,195 blocked targets; 638 unblocked by the sinks alone; 39 coverable by a candidate | 174 s (170 s in the main component) |
| MILP | Optimal; 24 PTRs (7 A, 15 B, 2 C) cover all 39 | 0.06 s |
| Verification without sinks | 32 targets carry flux; 4 of the 7 connectors carry none | – |

Points to note from this run:

- Most of the time goes to the coverage step in the main component. The MILP
  itself is trivial.
- Only 39 of the 1,195 blocked reactions can be fixed by a single same-base
  transport. Most blocked reactions need something else, such as missing
  reactions or other metabolites, so this method can only ever be part of the
  answer.
- Verification found 32 of the 39 targets carrying flux without the sinks. The
  other 7 depended on a sink that the final model does not have.
- Connectors join components topologically, but 4 of the 7 carry no flux.
  They are still proposed. Whether to drop inactive connectors is an open
  decision.

## Open points

- The full reference run has not been repeated with `sink-milp` and the
  current β2 output (which now has location evidence). Numbers will change.
- `allowed_connections` contains no c–e (cytosol–extracellular) or m–i
  (mitochondria–inner mitochondrial membrane) pair. Those transports can never
  be proposed. Whether that is intended needs a decision.
- Inactive connectors and targets that fail verification are only reported.
  Nothing acts on them.
