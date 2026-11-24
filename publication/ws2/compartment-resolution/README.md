# Frozen compartment-rule ablation

From the repository root in the publication environment:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python publication/scripts/measure_compartment_ablation.py
```

The script reruns location resolution, complex and isoenzyme inference, and expansion planning against the frozen build B dependencies. It loads the GO resolver immediately preceding `4e88dea` for the first two variants and reproduces the multi-location rejection policy from before `0188ac5` in the first variant. These are earlier standalone rules. The current variant's expansion-plan SHA-256 must match B before any result is saved.

The HPA column compares gene target sets to a fixed HPA mapping with uncertain records excluded. The common-gene comparison holds the denominator fixed. The separate final-model HPA analysis derives locations from placed reactions instead. Summary JSON records settings and source checksums. The CSV stores counts by compartment.
