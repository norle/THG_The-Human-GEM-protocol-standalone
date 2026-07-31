# Legacy workflow status

The package APIs under `thg_protocol` are the supported interface. The files
listed here remain in the source checkout for historical reproducibility, but
are not included in wheels and are not part of the installed release contract.

## Replaced compatibility surfaces

- `functions/functions_mass_balance.py` delegates formula parsing and positive
  stoichiometric balancing to `thg_protocol.model_build.mass_balance`. It keeps
  the historical names and tuple shapes, but it does not infer new proton or
  water chemistry. Callers needing that chemistry must provide those compounds
  explicitly.
- `functions/functions_merge_metabolic_networks.py` delegates all merge
  variants to `thg_protocol.merge.merge_models`. The returned model is an
  independent copy; new code should use `MergeReport` rather than the legacy
  positional overlap lists.
- `functions/functions_network_consistency.py` delegates structural checks to
  `thg_protocol.analysis.consistency` and solver-backed checks to COBRA's
  optional flux-analysis functions. Network cleanup can write only to an
  explicitly supplied path.
- `network_analysis/find_components.py` retains its historical call shape,
  while `cleanup=True` and `visualize=True` now require explicit output paths
  and use package component reports.

## Archived source-checkout workflows

The following scripts are retained as historical, solver-heavy workflows and
are explicitly unsupported as installed commands:

- `cell_type_specific_model/ptr_one_round.py`
- `cell_type_specific_model/ptr_multi_round.py`
- `cell_type_specific_model/gimme_parallel.py`
- `cell_type_specific_model/transcriptomics.py`
- `implement_pathway/validate.py`
- `implement_pathway/visualize.py`

They may continue to use their historical model/data conventions when run from
the checkout. New automation should use the explicit package APIs, especially
`thg_protocol.cell_specific.reduce_model_by_activity`,
`thg_protocol.cell_specific.match_exchange_reactions`, and
`thg_protocol.pathway.implement_pathway_files`. The archived scripts are not
evidence for the installed package's import-safety or output-path guarantees.

## Historical test suites

Pytest owns the maintained suite under `tests/`. The large fixture-driven
directories under `test_algorithms/` and the additional MEMOTE checks remain
source-checkout archives: representative annotation and algorithm cases have
central tests, while full-model, solver, and online cases must be invoked
explicitly and marked before they can become release-gate tests. They are not
collected by the default `testpaths` configuration and are not evidence for the
offline wheel gate.
