# β2 compartment resolution: how it works, edge cases, and known gaps

*Notes from a code review on 2026-10-07, branch `refactoring-cleanup`. File references are relative to the repository root.*

β2 takes the validated β1 model and copies enzymatic reactions into every compartment where their enzymes are found. This document covers where the location data comes from, how a location becomes a model compartment, what happens in three edge cases, and two problems found with the UniProt input.

## Data sources

| Input | Source | What it gives | Notes |
|---|---|---|---|
| Gene locations (manual) | `gene_locations` in the β2 config | Locations written by hand | Override every other source |
| Gene locations | **GOA** (GO annotations for UniProt proteins) | GO term IDs directly, e.g. `GO:0005739` | Rated "strong" |
| Gene locations | **UniProt** REST API | Location text, e.g. "Mitochondrion matrix", plus a UniProt location ID (`SL-xxxx`) | Rated "supporting". The GO ID is always empty in live mode (see Known problems) |
| Gene locations (last resort) | Older UniProt text lookup (`gpr/location.py`) | Location names | Live mode only, for genes with nothing from the sources above |
| Reaction locations | **Reactome** (and BioCyc if enabled) | A location for the reaction itself | `configs/beta2.json` doesn't list BioCyc in `reaction_sources`, so in practice this is Reactome only |
| Ontology | **GO** `go-basic.obo`, release 2026-06-19 (`go_ontology_url` in config) | The term tree used to map locations to compartments | |
| Target compartments | Config: `compartments` + `compartment_go_terms` | 13 compartments, each tied to one GO term (e.g. `m` = mitochondria = `GO:0005739`) | |

## Pipeline steps

Stage code is in `src/thg_protocol/workflow/beta2/_stages.py`.

1. **Collect evidence** (`collect-location-evidence`, `collect-reaction-location-evidence`). Gather per-gene locations from the config, GOA and UniProt, and per-reaction locations from Reactome.
2. **Map each location to a compartment** (`resolve-compartment-evidence`).
   - With a GO ID: start at that term.
   - Without one: match the text exactly against GO term names and synonyms. One match is used. Several give `ambiguous-go-term`, none gives `location-not-in-ontology`.
   - From the start term, walk up the GO tree through `is_a` and `part_of` links to the nearest configured compartment term (`src/thg_protocol/curation/go.py:105`).
   - BioCyc's location ontology (CCO) is used instead only when no GO compartment terms are configured (`src/thg_protocol/curation/beta2.py:42`).
3. **Combine per gene.** Each gene ends up with a set of compartments.
4. **Apply the GPR** (`infer-complex-and-isoenzyme-locations`, `resolve_gpr_locations` in `curation/beta2.py`).
   - **OR** (isoenzymes): union of the genes' compartments.
   - **AND** (complex subunits): intersection. Every subunit must be present in the compartment, otherwise that compartment is rejected (`required-subunit-location-intersection-is-empty`).
5. **Fill gaps from reaction evidence.** If step 4 gave no compartment, use the reaction's own resolved Reactome location (tagged `reaction-evidence-candidate`).
6. **Plan the expansion** (`generate-expansion-plan`). Each compartment found becomes a proposal to copy the reaction there with compartment-specific metabolites. The original reaction is always kept. If an equivalent reaction already exists in the target compartment, no copy is made.

## Edge cases

### 1. Two compartments the same distance away

- The location is **rejected**, never guessed. The record gets `status: "rejected"`, reason `ambiguous-compartment-resolution`, and the list of candidates (`curation/go.py:178-188`, `curation/beta2.py:127-138`).
- The GO resolver has no tie-break: `is_a` and `part_of` links count the same.
- The CCO resolver breaks one kind of tie first: a "contained in" link (`component_of`) beats an "is a kind of" link (`superclasses`). It rejects only if both the distance and the link type are tied.
- If two paths of equal length reach the **same** compartment, that isn't a conflict. The path that sorts first alphabetically is recorded; this only affects the audit trail.
- **How often it happens:** rarely. No saved run has any compartment-resolution records (the β2 run in `runs/thg-reference` produced an empty `beta2-compartment-resolution-evidence.json`), so there's no observed case. As an offline check on 2026-10-07, every cellular-component term in GO release 2026-06-19 was put through the resolver with the 13 compartments in `configs/beta2.json`:

  | Outcome | GO terms |
  |---|---|
  | resolved | 1,835 |
  | doesn't reach any configured compartment | 2,232 |
  | **tie between two compartments** | **8** |

  The 8 tied terms:

  | Tied compartments | GO terms |
  |---|---|
  | cilium (`ci`) + cytoskeleton (`ck`) | GO:0035253 ciliary rootlet; GO:0120260 ciliary microtubule quartet |
  | lysosome (`l`) + vesicle (`v`) | GO:0106174 phagolysosome vesicle lumen; GO:0106175 phagolysosome vesicle membrane |
  | inner mitochondria (`i`) + mitochondria (`m`) | GO:0001405 PAM complex, Tim23 associated import motor |
  | cytoskeleton (`ck`) + nucleus (`n`) | GO:0005638 lamin filament |
  | cell membrane (`a`) + ER (`r`) | GO:0009510 plasmodesmatal desmotubule (plant structure, irrelevant for human) |
  | cell membrane (`a`) + cilium (`ci`) | GO:0097538 ciliary necklace |

  None of these are typical locations for metabolic enzymes. When one occurs, only that annotation is rejected; the gene keeps its other locations. Whether any human gene actually carries one of these terms wasn't checked (that needs the human GOA annotation file). To find ties in a future run, search its output for the reason:

  ```bash
  grep -c ambiguous-compartment-resolution runs/<run>/artifacts/resolve-compartment-evidence/*/beta2-compartment-resolution-evidence.json
  ```

- **A related case:** one gene has several annotations that each resolve cleanly, but to different compartments. The gene is marked `status: "conflicting"` with reason `same-precedence-evidence-disagree`.
  - Under the default `uncertainty_policy: reject-conflicts`, the gene contributes **no compartments at all**.
  - Under `allow-conflicts`, it keeps all of them.

### 2. A reaction with no compartment evidence

- **No GPR:** the reaction isn't eligible for expansion. It's kept as-is with reason `no-gpr-or-ec-evidence` (`reaction_policy` in `curation/beta2.py`).
- **Genes with no known location:** the genes go on the unresolved list. If `fallback_location` is set in the config, they're assigned that location and the result is tagged `evidence_type: "fallback"`. If it isn't set, they contribute nothing.
- **No gene-derived compartment, but a Reactome location:** the Reactome location is used.
- **Nothing anywhere:** no expansion is planned. The reaction is kept in its original compartment (`action: "retain"`). It's never dropped.
- **Gene and reaction evidence disagree** (no overlap between them): a `gene-and-reaction-evidence-disagree` record is written. Nothing reads it, so it doesn't block anything. Gene evidence wins, and reaction evidence is only used when the gene route produced nothing.

### 3. A mismatch between UniProt and GO

- **Text vs GO ID within one annotation:** if a GO ID is present, it's used and the text is ignored (`curation/go.py:89-91`). Nothing checks that the two agree.
- **UniProt vs GOA for the same gene:** both are kept as locations for the gene. If they resolve to different compartments, it's the conflicting-gene case above, and under the default policy the gene contributes nothing.
- **Locations set by hand in the config:** these always win. GOA and UniProt annotations for those genes are stored under `supporting_evidence` for reference, but are never added to the gene's `locations` (`_stages.py:1068`). Snapshot records and the older UniProt lookup also skip those genes. Nothing flags a hand-set location that disagrees with the databases.

## Known problems with the UniProt input

Both were confirmed on 2026-10-07 by running the real `UniProtClient` against the live UniProt API for 50 human metabolic genes, with the configured GO release. The results are from that 50-gene sample, not a full β2 run. The existing `runs/thg-reference` has no gene location evidence recorded, so no real run output could be checked. `configs/beta2.json` does use `uniprot` as a location source in live mode, so both problems apply to real runs.

### Problem 1: UniProt locations never get a GO ID in live mode

- The code converts UniProt location IDs (`SL-xxxx`) to GO terms using a field called `sl_to_go`, which it reads from each API record (`src/thg_protocol/services/uniprot.py:176-181`).
- UniProt's API doesn't return that field. A real record gives only `{"value": "Mitochondrion matrix", "id": "SL-0170"}`, and nothing else in the repo supplies the mapping. The only other mention of `sl_to_go` is a unit test that writes it into its own test data (`tests/unit/test_go_evidence.py:272`), which is why the tests pass.
- Result: **744 annotations, 0 with a GO ID.** Every UniProt location goes through the text-matching fallback:

| Outcome | Count | Examples |
|---|---|---|
| resolved | 311 | "Mitochondrion" → m, "Lysosome membrane" → l |
| `location-not-in-ontology` | 293 | "Cytoplasm, cytosol", "Cytoplasm, cytoskeleton" |
| `location-not-in-registry` | 140 | "Cytoplasm", "Membrane", "Chromosome" |

- UniProt's comma-separated names ("Cytoplasm, cytosol") are never GO names, so they always fail. Some simple names fail too: "Mitochondrion matrix" isn't a GO name (GO uses "mitochondrial matrix"). As a result, human citrate synthase (CS), the textbook mitochondrial enzyme, gets no UniProt location.

### Problem 2: the UniProt query includes every species and reads only one page

- The query is `gene:CS OR gene:ACO2 OR …` with no organism filter (`services/uniprot.py:124-127`). It requests one page of 500 records and ignores UniProt's next-page link.
- For the 50 genes, UniProt reported **60,904 matches**. The code kept 500, of which only **52 were human**.
- Any record whose gene name matches is assigned to the human gene (`services/uniprot.py:166-168`). This is how locations like "Periplasm", "Glyoxysome" and "Encapsulin nanocompartment" (bacteria and plants) end up on human genes.
- It changed the result for 5 of the 50 genes. Each had no human location that resolved and picked one up from another species:

| Gene | Human UniProt compartments | Compartments as coded |
|---|---|---|
| CS | none | nucleus |
| MDH2 | none | peroxisome (likely from a plant glyoxysome) |
| PGK1 | none | mitochondria |
| GOT1 | none | Golgi |
| ARG1 | none | ER |

- Those wrong compartments would become real reaction copies. If GOA gives the correct location for the same gene, the two conflict, and under the default `reject-conflicts` policy the gene then contributes nothing.
- All 50 human genes made it into the first page in this test, because UniProt ranks reviewed human entries first. The code sends batches of 100 genes; whether human entries can fall off the page at that size wasn't tested.

## Suggested fixes

1. **Restrict and paginate the UniProt query:** add `AND organism_id:9606`, and either follow the next-page link or compare against the reported total so truncation can't happen silently.
2. **Use UniProt's official location-to-GO mapping:** load `subcell.txt` from a pinned UniProt release and use it to set `go_id`, instead of reading `sl_to_go` from the API response.
3. **Optional:** report genes whose hand-set config locations disagree with GOA or UniProt, and annotations whose text and GO ID point to different compartments.
