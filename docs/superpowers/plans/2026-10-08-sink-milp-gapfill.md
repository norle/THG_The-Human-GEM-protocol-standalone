# Sink-MILP Transport Gapfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the default reference gapfill the legacy three-phase putative-transport (PTR) pipeline: candidates → spanning-tree connector → sink MILP. Port it into the package as gapfill method `sink-milp`, with resumable workflow stages.

**Architecture:** A new module, `thg_protocol.gapfill.ptr`, holds four pure phase functions: candidates, connectors, coverage and MILP selection. It also holds a no-sink verification step and `run_sink_milp`, which composes them into the existing `GapfillResult`. `gapfill_model(method="sink-milp")` exposes it as a standalone API. The gapfill workflow gains three stages, enabled only for `sink-milp`: `generate-gapfill-candidates`, `select-gapfill-connectors` and `compute-gapfill-coverage`. `generate-gapfill-plan` turns their artifacts into the usual proposal plan, so apply/validate/gate/export are unchanged.

**Tech Stack:** Python 3.10–3.12, COBRApy 0.31, optlang (the model's solver interface: Gurobi locally, GLPK in CI), pytest. No networkx/PuLP/scipy MILP (see memory: reuse optlang/Gurobi).

**Spec:** Decisions agreed in the 2026-10-08 session (summarized under *Decisions* below). Legacy reference: `git show f3d0b0d:gapfill/phase1_connect_components.py`, `phase2_minimal_connector.py`, `phase3_sink_milp_original.py`.

## Decisions

1. Phases run in sequence: phase 1 candidates (no model change) → phase 2 minimum-spanning-tree connectors (added) → phase 3 sink MILP (added on top of phase 2).
2. **Candidates** pair metabolites with the same base ID (`re.sub(r"[a-z]+$", "", id)`) in two compartments listed in `allowed_connections` (unordered). A pair qualifies when:
   - its endpoints are in **different network components** (legacy, any type A/B/C), or
   - both endpoints are in the **main component** and at least one is a dead end (types A/B only; the extension the user chose).
3. Types follow the legacy rules, with sign-only dead ends: `product` = only produced, `substrate` = only consumed. **A** = one product and one substrate; **B** = both product or both substrate; **C** = otherwise.
4. Components follow legacy: connected components of the undirected reaction–metabolite graph after dropping metabolites in no reaction. They are numbered by node count, descending, with 1 = main. Ties are broken by the smallest node ID.
5. **Connectors** (phase 2): for each component pair, pick the representative candidate with the minimum `(type rank A<B<C, base, met1, met2)`. Then run Kruskal over the representatives sorted by `(type rank, base)`. Main-component-only candidates never act as connectors.
6. **Coverage** (phase 3a), computed on the phase-2 model:
   - Targets per component *k* = reactions originally in *k* that are blocked in the phase-2 model **without** sinks.
   - Components smaller than `min_component_size` (default 4, legacy) are skipped. The main component **is** processed.
   - Temporary sinks and sources follow legacy `get_deadend_info`, which accounts for bounds: a source for `substrate`, a sink for `product`, nothing for `isolated`.
   - **Deviation from legacy:** reactions unblocked by the temporary sinks alone are removed from every candidate's coverage, so the MILP is never credited for what the sinks did.
7. Unblocked-detection uses the FASTCC LP7-style loop (exact up to tolerance) instead of 2 LPs per reaction. Candidates are pre-filtered by graph reachability, which is exact as a necessary condition.
8. **MILP** (phase 3b), one global problem on the model's optlang interface:
   - Objective: maximize Σz − λΣy, with `tradeoff_lambda` default 0.01.
   - Constraints: z_r ≤ Σ y over the candidates covering r; Σy ≤ `max_additions` − (number of connectors).
   - Status is `partial` when the budget binds and some coverable target stays uncovered.
9. **Verification** runs without sinks on the final model:
   - `verified_unblocked` = targets that can now carry flux;
   - `inactive_connectors` = phase-2 reactions that carry no flux.
   Both are reported, not acted on.
10. Reaction IDs: `GAPFILL_PTR_<met1>_<met2>` with non-`[A-Za-z0-9_]` characters replaced by `_`. Reactions are reversible, ±1000.
11. `configs/reference.json` uses `method: "sink-milp"` and the curated `allowed_connections`: the 21 legacy pairs mapped onto the current compartments (Task 7 lists them). That list has **no c–e and no m–i pair**, but has g–i. Flag this to the user when reporting.

## Global Constraints

- Run tests with `conda run -n thg_standalone python -m pytest`; docs tests and `ruff` run in `base`.
- `ruff check src tests` and `ruff format --check src tests` must be clean.
- Gapfill never retains temporary sinks or sources in output models (decision in `aaf5500`).
- A disabled stage is recorded `skipped`; `_dependency_hashes` returns `[]` for it.
- Bump `implementation_version` on any stage whose output changes.
- Commit after each task. End commit messages with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- A model where no candidate exists (single compartment or empty `allowed_connections` intersection) should give status `solved` with 0 proposals. In the reference workflow the existing gate then blocks it (Task 5 test).
- A component whose only candidates are already-present transports: no proposal, coverage marked `already-present` (Task 1 test).
- An MILP that is infeasible or errors on the solver must give status `failed` with the solver status in `failure`, never a silent empty selection (Task 4 test).
- Resuming after an interrupted `compute-gapfill-coverage` must reuse completed component checkpoints (Task 6 test).
- Metabolite IDs with no compartment suffix: compartment comes from `metabolite.compartment`; the base keeps legacy regex behavior (Task 1 test).

---

### Task 0: Commit the guard fixes already in the working tree

- [ ] Run `git status`. Expect the earlier edits plus `tests/unit/test_gapfill_incremental.py` and this plan.
- [ ] Commit them as `make reference gapfill and β2 fail loudly on empty work`, describing:
  - β2 evidence settings in `reference.json`;
  - required evidence source;
  - non-empty `allowed_connections`;
  - the `gate-beta2` and `gate-gapfill` checks;
  - the incremental greedy search.

### Task 1: Components and candidates

**Files:** Create `src/thg_protocol/gapfill/ptr.py`; Test `tests/unit/test_gapfill_ptr.py`

**Interfaces — Produces:**
- `network_components(model: cobra.Model) -> Components`, where `Components` is a frozen dataclass with `of: dict[str, int]` (metabolite and reaction IDs → component) and `sizes: dict[int, int]`.
- `@dataclass(frozen=True) class PtrCandidate: met1: str; met2: str; base: str; compartments: tuple[str, str]; components: tuple[int, int]; type: str; reaction_id: str`, with `met1 < met2`. Add `to_dict()`/`from_dict()` for JSONL.
- `generate_ptr_candidates(model, allowed_connections: list[tuple[str, str]], candidate_types: list[str], components: Components) -> list[PtrCandidate]`, sorted by `reaction_id`. Pairs already covered by an existing transport (reuse `_TransportSearch.covers` from `core.py`) are excluded.

- [ ] **Write failing tests**:
  - `test_components_number_main_first`: a two-island model; the larger island is 1, and an unused metabolite has no entry.
  - `test_cross_component_pair_is_a_candidate_of_any_type`: `X_c` in the main island, `X_e` in a small island, both non-dead-end → one type-C candidate.
  - `test_main_component_pair_needs_a_dead_end`: two main-island pairs, one with a dead end → only that one, type A or B.
  - `test_pairs_outside_allowed_connections_are_dropped`.
  - `test_existing_transport_suppresses_candidate`.
  - `test_metabolite_without_suffix_uses_compartment_attribute`.
- [ ] Run them and see them fail (`ImportError`).
- [ ] Implement it. Use union-find over reactions; don't add a networkx dependency.
- [ ] Run the tests (pass), then ruff, then commit: `add PTR components and candidate generation`.

### Task 2: Spanning-tree connectors

**Files:** Modify `ptr.py`; Test `tests/unit/test_gapfill_ptr.py`

**Interfaces — Produces:** `select_connectors(candidates: list[PtrCandidate]) -> list[PtrCandidate]` (decision 5), ordered by selection.

- [ ] **Failing tests**:
  - `test_connectors_join_every_component_once`: 3 islands with 4 cross pairs → 2 connectors, no cycle.
  - `test_connector_prefers_type_a_then_base`.
  - `test_main_only_candidates_are_never_connectors`.
- [ ] Implement it, pass, commit: `add spanning-tree PTR connector selection`.

### Task 3: Coverage with temporary sinks

**Files:** Modify `ptr.py`; Test `tests/unit/test_gapfill_ptr.py`

**Interfaces — Produces:**
- `@dataclass class ComponentCoverage: component: int; targets: list[str]; sink_only: list[str]; coverage: dict[str, list[str]]` (candidate `reaction_id` → newly unblocked targets). Add `to_dict`/`from_dict`.
- `compute_coverage(model: cobra.Model, candidates: list[PtrCandidate], components: Components, *, min_component_size: int = 4, done: Mapping[int, ComponentCoverage] | None = None, on_component: Callable[[ComponentCoverage], None] | None = None) -> list[ComponentCoverage]`. `model` is the phase-2 model. Components already in `done` are not recomputed (resume). `on_component` is called after each component (checkpoint).
- Helper `unblockable(model, reaction_ids: set[str], epsilon: float) -> set[str]`: the LP7 loop (decision 7), forward and then reverse for reversible remainders, using `with model:` contexts.

Per component *k* (largest first): targets = blocked reactions originally in *k* (no sinks). Then add the temporary sinks, compute `sink_only = unblockable(targets)`, and for each candidate with an endpoint in *k* (and, for *k* = 1, the main-only candidates): add its PTR and record `unblockable(reachable targets − sink_only)`.

- [ ] **Failing tests** (small models solved with the default solver):
  - `test_unblockable_matches_per_reaction_fba`: random small models; compare against a 2-LP-per-reaction oracle written in the test.
  - `test_candidate_covers_reactions_it_unblocks`: an island `A_e → B_e → C_e` with a dead end, plus `A_c` in main; the PTR `A_c↔A_e` covers the island reactions.
  - `test_sink_only_unblocked_reactions_are_not_credited`.
  - `test_temporary_sinks_do_not_leak_into_model`: reaction IDs before == after.
  - `test_done_components_are_not_recomputed`: pass a `done` entry; `on_component` is not called for it.
  - `test_small_components_are_skipped`.
- [ ] Implement it, pass, commit: `add sink-based PTR coverage`.

### Task 4: MILP selection

**Files:** Modify `ptr.py`; Test `tests/unit/test_gapfill_ptr.py`

**Interfaces — Produces:** `select_unblockers(coverage: list[ComponentCoverage], *, tradeoff_lambda: float, budget: int, interface) -> Selection`. `interface` is an optlang interface module, e.g. `model.solver.interface`. `Selection` holds `selected: list[str]` (reaction IDs, sorted), `covered: list[str]`, `status: "solved" | "partial" | "failed"`, `failure: str | None` and `solver: dict`.

- [ ] **Failing tests**:
  - `test_milp_picks_fewest_candidates_for_full_coverage`: 3 candidates with overlapping coverage → the optimal 2.
  - `test_lambda_drops_candidates_worth_less_than_their_cost`: λ = 2 with a candidate covering 1 reaction → not selected.
  - `test_budget_binding_gives_partial`.
  - `test_solver_failure_is_reported`: monkeypatch `Model.optimize` to return `"infeasible"` → `failed`.
- [ ] Implement it (decision 8; binary variables via `interface.Variable(type="binary")`). Pass, commit: `add MILP selection of PTR unblockers`.

### Task 5: Verification and the `sink-milp` method

**Files:** Modify `ptr.py`, `src/thg_protocol/gapfill/core.py` (`_DEFAULTS`, `_resolved_parameters`, `gapfill_model`, `generate_gapfill_plan`); Test `tests/unit/test_gapfill_ptr.py`, `tests/unit/test_gapfill_api.py`

**Interfaces:**
- Produces `verify_selection(model, connectors: list[PtrCandidate], selected: list[PtrCandidate], targets: set[str]) -> dict`, with keys `verified_unblocked`, `inactive_connectors`.
- Produces `run_sink_milp(model, parameters, *, candidates=None, connectors=None, coverage=None) -> GapfillResult`. The precomputed phases come from workflow stages; the others are computed.
  - `candidate_coverage` maps every candidate to `connector`, `selected`, `already-present` or `available`.
  - Each selected candidate is annotated with `{"type", "base", "phase": 2|3}`.
  - `solver` holds the MILP metadata plus the verification dict.
- `_DEFAULTS["sink-milp"] = {"max_additions": 1000, "candidate_types": ["A", "B", "C"], "tradeoff_lambda": 0.01, "min_component_size": 4}`. `allowed_connections` is required and non-empty. `universal_model`/`objective`/`minimum_flux`/`penalties` are rejected.
- `generate_gapfill_plan(..., result: GapfillResult | None = None)` uses `result` instead of calling `gapfill_model`. `sink-milp` proposals carry the same `transport` block as the transport methods, plus `phase`.

- [ ] **Failing tests**:
  - `test_sink_milp_end_to_end_adds_connector_and_unblocker`: two islands → plan with one phase-2 and ≥1 phase-3 proposal; `apply_gapfill_plan` adds exactly them.
  - `test_verification_reports_inactive_connectors`.
  - `test_sink_milp_requires_allowed_connections`.
  - `test_generate_plan_accepts_precomputed_result`.
- [ ] Implement it, pass, run the full gapfill unit tests, commit: `add sink-milp gapfill method`.

### Task 6: Workflow stages and config

**Files:** Modify `src/thg_protocol/workflow/gapfill.py`, `src/thg_protocol/workflow/config.py`; Test `tests/integration/test_gapfill_registered_workflow.py`, `tests/unit/test_config_api.py`

**Interfaces:** New `GapfillStage` IDs, all enabled iff `section["method"] == "sink-milp"`:
- `generate-gapfill-candidates` (deps `load-gapfill-source`) → `ptr-candidates.jsonl`, `ptr-components.json`.
- `select-gapfill-connectors` (deps: the above) → `ptr-connectors.jsonl`.
- `compute-gapfill-coverage` (deps: both) → `ptr-coverage.jsonl`. Writes one line per component as it finishes. On a retry it reads the previous failed attempt's partial file from `failed/compute-gapfill-coverage/attempt-*/` into `done`.

`generate-gapfill-plan` adds the three as dependencies and, for `sink-milp`, calls `run_sink_milp` with the loaded artifacts. Its fingerprint gets `implementation_version` 2.

Config: `sink-milp` is accepted as a method. It requires non-empty `allowed_connections`, accepts `candidate_types`, `tradeoff_lambda` (0 < λ < 1) and `min_component_size` (int ≥ 1), and rejects the milp-only keys.

- [ ] **Failing tests**:
  - `test_sink_milp_workflow_runs_phase_stages`: standalone gapfill on a two-island fixture; all three stages completed; plan proposals carry phases 2 and 3.
  - `test_phase_stages_are_skipped_for_greedy`.
  - `test_coverage_resumes_from_partial_attempt`: make the second component raise once (monkeypatch); `resume`; the first component's line isn't recomputed.
  - Config tests for each accepted and rejected key.
- [ ] Implement it, pass, commit: `run sink-milp gapfill as resumable workflow stages`.

### Task 7: Reference default, docs, real-model run

**Files:** Modify `configs/reference.json`, `docs/workflows/gapfill.md`, `docs/tools/pathways-gapfill.md`, `CURRENT_STATE.md`

- [ ] Set `reference.json` gapfill to `method: "sink-milp"`, `max_additions: 1000` and `tradeoff_lambda: 0.01`. Set `allowed_connections` to:
  `[["a","c"],["a","ci"],["a","ck"],["a","e"],["a","r"],["a","v"],["c","ci"],["c","ck"],["c","g"],["c","l"],["c","m"],["c","n"],["c","r"],["c","v"],["c","x"],["ci","ck"],["ci","e"],["e","l"],["g","i"],["m","n"],["r","v"]]`.
- [ ] Docs: describe the three phases, the sinks-only deviation and the verification report.
- [ ] Time `run_sink_milp` on `runs/thg-reference/artifacts/export-beta2/attempt-0001/thg-beta2-candidate.json` with Gurobi, recording phase timings, the candidate and connector counts, the MILP selection, `verified_unblocked` and `inactive_connectors`. **If coverage takes over 2 h, stop and report to the user before going on.**
- [ ] Full suite (2266+ passing), docs tests in base, ruff. Commit: `make sink-milp the reference gapfill default`.
- [ ] Report to the user: timings, counts, the missing c–e and m–i pairs, and the reference rerun as the next step.
