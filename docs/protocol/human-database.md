# Construct the Human Database

!!! warning "Scope and evidence"
    Deterministic reconstruction from normalized records is Implemented and
    tested at its package boundary. The 2023 protocol paper's complete live
    pathway-harvesting orchestration is Not implemented and has No replacement.

## What “Human Database” means in the 2023 protocol paper

The paper's Human Database is the complementary human metabolic network
assembled from a list of human metabolic pathways and information gathered from
online biological sources. It contains metabolites, reactions, genes, GPRs, and
compartments and is later combined with THGβ2. It is more than a generic local
database file.

## Inputs and information gathered in the paper

The paper's branch starts with human pathway records. For each pathway, the
construction gathers or normalizes metabolite identifiers and formulas,
reaction stoichiometry and identifiers, gene/protein relationships, GPRs, and
cellular compartments. Current package service clients cover selected KEGG,
BioCyc, Ensembl, PubChem, and location lookups, but they do not by themselves
constitute a complete pathway-list harvesting orchestrator.

## Current supported input forms

- normalized `MetaboliteRecord`, `ReactionRecord`, and optional `GeneRecord`
  objects;
- a JSON record bundle consumed by
  [`reconstruct_model_from_json`][thg_protocol.database.reconstruct_model_from_json];
- injected service clients consumed by
  [`reconstruct_model_with_services`][thg_protocol.database.reconstruct_model_with_services];
- historical pickle checkpoints through
  [`reconstruct_model_from_pickle`][thg_protocol.database.reconstruct_model_from_pickle]
  when the `database` extra is installed.

### JSON record schema

The supported JSON bundle has this shape. `metabolites` and `reactions` are
required; `genes`, `pathways`, and `model_name` are optional.

```json
{
  "model_id": "human-database-mini",
  "model_name": "Small normalized human network",
  "metabolites": [
    {"id": "a_c", "compartment": "c", "name": "A", "formula": "C1H2", "charge": 0, "annotation": {"chebi": "CHEBI:1"}}
  ],
  "reactions": [
    {"id": "R1", "stoichiometry": {"a_c": -1}, "name": "A use", "gene_reaction_rule": "GENE1", "annotation": {}}
  ],
  "genes": [{"id": "GENE1", "name": "Example gene", "annotation": {}}],
  "pathways": {"example": ["R1"]}
}
```

Every reaction stoichiometry key must name a metabolite in the same bundle;
duplicate IDs are rejected. A `.json` output uses COBRA JSON; another output
suffix uses SBML.

## Supported reconstruction example

```python
from pathlib import Path

from thg_protocol.database import reconstruct_model_from_json

records = Path("docs/examples/records.json")
output = Path("results/human-database/network.json")
model = reconstruct_model_from_json(records, output_path=output)
print(model.id, len(model.metabolites), len(model.reactions), output.exists())
```

This is a local reconstruction from already normalized records. It performs no
network access and does not mutate the records file. For service enrichment,
inject clients and retain their caches; do not claim that this function queries
KEGG, BioCyc, PubChem, or another service by itself.

## Current limitation

There is no supported current command that accepts only a pathway list and
recreates the paper's entire live information-gathering branch. Compose
the maintained record, parsing, service, and reconstruction APIs manually, or
use a separately maintained harvesting workflow and document its version and
inputs. Historical pickle adapters are compatibility input support, not proof of
a current live harvesting pipeline.

## Outputs and validation

Retain the normalized input bundle, reconstructed JSON/SBML model, pathway
membership, service caches, and a report of unresolved records. Run
[network analysis](../workflows/network-analysis.md), formula-balance checks,
and comparison before moving to [merge and validate](merge-and-validate.md).
