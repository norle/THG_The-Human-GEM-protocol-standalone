# Published THG and updated reference workflow

The historical comparator is the final model from the [2023 THG paper](https://doi.org/10.3390/bioengineering10050576). The Europe PMC supplementary archive for PMC10215578 contains the publisher's supplemental bundle and its S2 model archive. The extracted S2 member `THG-2023-02-25.xml` matches the repository file byte for byte by SHA-256.

| Artifact | SHA-256 |
|---|---|
| S2 ZIP | `b9461dd1d1212ef7331fc10578463ba56ea440a58b26d2162f412ba78493d65b` |
| S2 THG model and `models/THG-2023-02-25.xml` | `72e90e562689eacd66fbfa1c20e2950826bd40fdea368ddf47aac1728dd014d1` |

```sh
curl -fL https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10215578/supplementaryFiles -o /tmp/thg-publication-2023-supplement.zip
unzip -p /tmp/thg-publication-2023-supplement.zip bioengineering-10-00576-s001.zip > /tmp/thg-publication-2023-s001.zip
unzip -p /tmp/thg-publication-2023-s001.zip 'Marin de Mas et al-Supplementary Material file S2.zip' > /tmp/thg-publication-2023-s2.zip
unzip -p /tmp/thg-publication-2023-s2.zip THG-2023-02-25.xml | sha256sum
sha256sum models/THG-2023-02-25.xml
```

## Workflow mapping

| 2023 workflow (Figure 1 and sections 3.5–3.9) | Updated workflow in B/C |
|---|---|
| Curate and balance a Human1 reference in β1 | Curate the patched Human-GEM 2.1.1 reference, run balance audit and consolidation, then validate and export β1 |
| Infer isoenzyme locations and create β2 | Resolve frozen GPR and location evidence through GO. Generate, apply and gate compartment-copy proposals |
| Reconstruct a separate Human Database and merge with β2 | Reconstruction and merge are implemented as optional stages. Both were disabled in B/C |
| Assess the merged model with MEMOTE, tasks and network consistency checks | Run putative transport gapfill on the β2 export, validate and export the reference, then run matched model assessment separately |

Current stage evidence is in [the fresh C stage table](../ws1/build-c/stages/stage_table.csv), [the run comparison](../ws1/replay-b-vs-c/comparison.json) and [the reference workflow documentation](../../docs/workflows/reference.md).

## Structural comparison

```sh
run_stats() {
  python -c 'import cobra,runpy,sys; cobra.Configuration().solver="glpk"; sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name="__main__")' publication/scripts/model_stats.py "$@"
}
run_stats models/THG-2023-02-25.xml thg-2023-repository publication/ws3/model_stats_thg-2023.csv
run_stats runs/thg-ws1-b/artifacts/export-reference/attempt-0002/thg-reference.xml thg-rebuilt-b publication/ws3/model_stats_rebuilt-b.csv
```

GLPK was selected for loading both models. Statistics do not involve optimization. The paper reports 20,677 reactions, 13,840 metabolites and 3,392 genes in THG. COBRApy reports 20,677 reactions, 14,058 metabolites and 3,394 genes from the exact S2 file. The manuscript should identify the source of each set of counts. Use the direct XML check below to distinguish declared species from reaction-linked species.

A direct XML count gives 14,058 declared species, of which 13,840 are referenced
by reactions. The latter matches the paper's metabolite count. The file contains
3,394 declared gene products. The difference from the paper's 3,392 remains
unexplained. The counts are saved in `sbml_counts.json`. Regenerate with:

```sh
python - models/THG-2023-02-25.xml <<'PY'
import json
import sys
from collections import Counter
from xml.etree.ElementTree import iterparse

counts = Counter()
used = set()
for _, element in iterparse(sys.argv[1], ("end",)):
    tag = element.tag.rsplit("}", 1)[-1]
    counts[tag] += 1
    if tag in ("speciesReference", "modifierSpeciesReference"):
        used.add(element.attrib["species"])
    element.clear()
print(json.dumps({
    **{tag: counts[tag] for tag in ("species", "reaction", "geneProduct", "compartment")},
    "reaction_linked_species": len(used),
}, indent=2))
PY
```


## Task-table provenance

S4's VerifyModel table is byte-identical to the current file. The Essential and
Full tables differ. The comparative task benchmark uses the current tables
and residual diagnostics on the patched baseline and rebuilt B. Published
task results retain their original method and denominator.

```sh
unzip -p /tmp/thg-publication-2023-s001.zip 'Marin de Mas et al-Supplementary Material file S4.zip' > /tmp/thg-publication-2023-s4.zip
for table in VerifyModel Essential Full; do
  unzip -p /tmp/thg-publication-2023-s4.zip "metabolic_tasks/metabolicTasks_${table}.txt" | sha256sum
  sha256sum "files/metabolic_tasks/metabolicTasks_${table}.txt"
done
```

Checksums are saved in `task_table_identity.csv`.
