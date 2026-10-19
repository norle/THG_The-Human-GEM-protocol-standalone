# THG Protocol: what changed in the refactoring

*Status report, 2026-10-14, branch `refactoring-cleanup`. Covers the 33
commits from 2026-10-07 to 2026-10-09 (`e6b981b` to `41d28d2`) and the
uncommitted work of 2026-10-13/14.*

## Changes by workflow step

**β1: curate the reference model**
- Reactions in the objective are no longer merged as duplicates, so their
  separate fluxes and capacity survive cleanup. Duplicates are now removed
  with `remove_reactions`, which also drops their solver variables and
  metabolite back-references (`31952ec`).
- Stage classes lost their `Detailed` prefix (`Beta1Stage`, `beta1_stages`,
  `BETA1_STAGE_IDS`; the same for β2) (`ae83ef2`).
- Unchanged this week: β1 fixes an unbalanced reaction automatically only
  when adding water and protons balances it. The new `balance_equation` MILP
  (see Other) is not used by β1.

**β2: expand reactions into compartments**
- *UniProt locations* (`017796f`).
  - *Before:* the query had no organism filter and read only the first 500
    results. For 50 test genes it kept 500 of about 61,000 matches, and
    plant and bacterial locations ended up on human genes. It also read an
    `sl_to_go` field the API never returns, so no UniProt location had a GO ID.
  - *Now:* human entries only, all result pages, and a failure if records
    are missing. GO IDs come from UniProt's own location vocabulary. The
    served release is recorded.
- *Cytoplasm* (`cba7c08`). A bare "Cytoplasm" annotation sits above cytosol
  in GO and was rejected. A new `compartment_go_aliases` setting maps it to
  `c`, and applies only to annotations that name exactly that term.
- *Dual-located genes* (`0188ac5`).
  - *Before:* any gene with more than one compartment was marked
    conflicting and contributed no compartments. That was 44 of 50 sampled
    metabolic genes, including GLS (`c`, `m`) and HMGCR (`r`, `x`).
  - *Now:* a gene keeps every compartment. `uncertainty_policy` is
    validated (`reject-conflicts` or `allow-conflicts`). It now affects only
    records that arrive already marked conflicting, such as from a snapshot.
  - New opt-in `goa_excluded_evidence_codes` filter, empty by default.
- *One GO term, several compartments* (`4e88dea`).
  - *Before:* the resolver picked the compartment the fewest GO steps away.
    It narrowed 93 terms to an arbitrary single compartment and threw away 8
    ties.
  - *Now:* every configured compartment reached is kept, except one that
    contains another reached one. Examples: axonemal microtubule → cilium
    *and* cytoskeleton; mitochondrial inner membrane → `i` only.
- *GPR evidence* (`536f4cc`). Structured sGPR evidence follows the same
  acceptance rule as other database evidence. It supplies a GPR only when
  the model has none, and only at confidence `authoritative`, `strong` or
  `reaction-matched`. Rejected evidence is still reported.
- *Equivalent reactions* (`3e2acd5`). Two reactions count as equivalent only
  if their metabolites come from the same source metabolite and their
  bounds match. Isomers and differently bounded reactions are no longer
  treated as the same reaction.
- *Empty runs fail* (`cf0b827`). The reference workflow requires a β2
  location source, and `gate-beta2` blocks when β2 found no gene-location
  evidence.
- Details are in `beta2-compartment-resolution-notes.md`, and (uncommitted)
  in a new "Compartment expansion" section in `docs/workflows/beta2.md`.

**Gap-filling**
- New `sink-milp` method, the default in `configs/reference.json`
  (`8caf07e` to `81f8f7e`, reviewed in `f6ec4d6` and `abb8cf4`). It adds
  putative transport reactions: spanning-tree connectors between network
  components, then those a MILP selects to unblock the most reactions. It
  runs as four resumable stages. See `GAPFILL_SINK_MILP.md`.
- A gap-fill run fails when a selected reaction reuses an existing reaction
  ID. A run that fails partway returns the unmodified model (`421eb22`).
- Transport candidates pair β2 copies by source metabolite (`3e2acd5`).
- `gate-gapfill` blocks when no candidate exists while dead ends remain. The
  greedy search scores candidates incrementally instead of copying the
  model each time (`cf0b827`).
- The `thg-gapfill` CLI accepts `sink-milp` (`abb8cf4`).

**Validation**
- New checks (`99f669b`), both non-blocking:
  - metabolites that internal flux can create or destroy with every
    boundary closed;
  - MEMOTE-style energy-generating cycles.
- The unconserved-metabolites check is retired (`e6b981b`).
- The `release-full` profile now fails when mass or charge balance cannot
  be evaluated for a reaction (missing or unparsable formula, missing
  charge), and energy-generating cycles are blocking (`42cf051`).
- Validation stages rerun when the input model or an upstream result
  changes (`00e1a99`).
- Model compaction works on a GLPK copy, because copying a Gurobi problem
  takes minutes on a genome-scale model. Loop detection clears GPRs, which
  otherwise grow without limit as merged reactions concatenate them
  (`004169a`).
- *Uncommitted:* the report's balance suggestions now come from a MILP run
  in the model's own solver (Gurobi, CPLEX or GLPK through optlang). The
  previous SciPy/HiGHS version is kept as a legacy option and is used when
  the model's solver cannot solve MILPs. On all 268 unbalanced Human-GEM
  reactions, both give the same suggestions as before.

**Other**
- `balance_equation` balances a text equation by minimising integer
  coefficients with a MILP on the cobra solver. It used to return nothing
  when more than one solution existed (`357ed70`). It is a library helper;
  no workflow calls it.
- Human Database: a cached response from an earlier adapter release is no
  longer served when a refresh fails (`b1f007e`).
- Cell-specific: the expression file is hashed once per collection instead
  of once per row (`41d28d2`).
- Tidying:
  - test files named after what they test (`022ddae`);
  - Human Database and final-THG stages moved into their own workflow
    modules (`b0c1e64`);
  - a test that needs gitignored inputs is skipped when they are absent
    (`20bab56`).
