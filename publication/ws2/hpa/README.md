# HPA comparison of gene-to-compartment assignments

Approved by the user on 2026-11-20 (plan section 6, item 10). Preliminary:
first measurement on the rebuilt B; the ablation-ladder column is not done.

## Inputs (pinned)

| Input | File | SHA-256 |
|---|---|---|
| HPA subcellular locations | `source/subcellular_location.tsv.zip` (downloaded 2026-11-20 from `https://www.proteinatlas.org/download/tsv/subcellular_location.tsv.zip`; server `last-modified` 2026-11-10) | `f01de8b4…8d3d08` |
| GO release 2026-06-19 | `go/go-basic.obo` (same release and hash as the builds) | `c72fc198…0734c` |
| Patched Human-GEM 2.1.1 | `runs/human211-patched/Human_211_patched.xml` | in `results/summary.json` |
| Rebuilt B final | `runs/thg-ws1-b/artifacts/export-reference/attempt-0002/thg-reference.json` (commit `1805783`) | `fd7da017…636dda` |

## Command

```sh
python publication/scripts/measure_hpa_agreement.py \
  --model baseline=runs/human211-patched/Human_211_patched.xml \
  --model thg-b=runs/thg-ws1-b/artifacts/export-reference/attempt-0002/thg-reference.json
```

Outputs: `results/summary.json`, `results/gene_agreement_<model>.csv`.
Runtime: about 3 minutes. The script was untracked when run (the recorded
`code_commit` does not contain it; its SHA-256 is in the summary).

## Method

1. HPA records with reliability `Uncertain` are dropped (12,853 genes kept).
2. Each HPA GO term is resolved to THG compartments with the pipeline's own
   resolver `resolve_go_compartment` (upward walk through `is_a` and `part_of`,
   most specific compartments kept) and the compartment/GO table of the frozen
   registry. 12,121 genes have at least one mapped compartment.
3. A model's compartments for a gene are those of its **single-compartment
   (non-transport) reactions** that the gene catalyses.
4. Per gene present in both: exact set match, any overlap, model set contained in
   the HPA set, and Jaccard index. Only genes with a non-empty set on both sides
   count. The second row restricts both sides to the 9 compartments the two
   models share.

## Result (preliminary)

| Model | Genes compared | Exact match | Any overlap | Model ⊆ HPA | Mean Jaccard |
|---|---|---|---|---|---|
| Human-GEM 2.1.1 patched, all compartments | 1,494 | 244 | 975 | 614 | 0.365 |
| THG B, all compartments | 1,494 | 229 | 1,118 | 518 | 0.394 |
| Human-GEM 2.1.1 patched, 9 shared compartments | 1,415 | 313 | 975 | 614 | 0.427 |
| THG B, 9 shared compartments | 1,415 | 296 | 1,084 | 533 | 0.452 |

Reading: THG's gene sets overlap HPA's for more genes (1,118 vs 975, +143),
and the mean Jaccard is higher, but fewer THG sets are exact or contained in
HPA's (more locations per gene, not all in HPA). Both models cover the same
2,289 genes through single-compartment reactions. Nothing here shows THG
assignments are "more correct"; it shows how they relate to an independent
source.

## Limitations (do not drop from the paper)

- HPA labels with no mapped THG compartment are ignored, mainly `Vesicles`
  (2,277 gene-location records; HPA's GO term is not under THG's vesicle term),
  `Cell Junctions`, `Cytokinetic bridge`, `Focal adhesion sites`, `Lipid
  droplets`, `Midbody`. The comparison covers the organelles THG models, not the
  whole HPA vocabulary.
- A model's compartments for a gene come from reaction placement, not from a
  gene-location claim; a gene in several single-compartment reactions in
  several compartments gets all of them.
- HPA is itself immunofluorescence on a few cell lines, with isoform and
  cell-type limits. Agreement is a consistency check, not ground truth.
- The matching genes are the baseline's genes; the sets are not independent of
  the GO/UniProt evidence THG used, since HPA's GO terms also come from
  curated resources.
- Results use the rebuilt B only; they must be redone if B changes.
- Not yet done: HPA agreement as a column of the ablation ladder (needs the
  ladder, plan step 10).
