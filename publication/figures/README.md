# Draft publication figures

- **Figure 1.** [Reference workflow](figure1_workflow.svg), including the optional Human Database stages. The B/C benchmark ran with those stages disabled. Regenerate with `python publication/scripts/plot_workflow.py`. Source: `publication/ws1/figure1_workflow.csv`.
- **Figure 2.** [Compartment-rule ablation](figure2_compartment_ablation.svg). Source: [frozen-policy replay](../ws2/compartment-resolution/summary.json).
- **Figure 3.** [Stage VerifyModel and unresolved residuals](figure3_expansion_safeguards.svg). The plotting script checks each stage model's checksum against build B.
- **Figure 4.** [Flux-capability of additions](figure4_flux_coverage.svg). Source: [blocked reaction classification](../ws4/coverage-rebuilt-b/flux_coverage.json) from the post-gapfill model under its exchange bounds.

Regenerate Figures 2–4, their PDF versions and the draft Table 1 with
`python publication/scripts/plot_update_results.py` in `thg_standalone`.
