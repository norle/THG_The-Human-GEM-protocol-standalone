# β2 compartment resolution: how it works, edge cases, and known gaps

*Notes from a code review on 2026-10-07, branch `refactoring-cleanup`. File references are relative to the repository root.*

β2 takes the validated β1 model and copies enzymatic reactions into every compartment where their enzymes are found. This document covers where the location data comes from, how a location becomes a model compartment, what happens in three edge cases, and two problems found with the UniProt input.

## Data sources

| Input | Source | What it gives | Notes |
|---|---|---|---|
| Gene locations (manual) | `gene_locations` in the β2 config | Locations written by hand | Override every other source |
| Gene locations | **GOA** (GO annotations for UniProt proteins) | GO term IDs directly, e.g. `GO:0005739` | Rated "strong" |
| Gene locations | **UniProt** REST API | Location text, e.g. "Mitochondrion matrix", plus a UniProt location ID (`SL-xxxx`) | Rated "supporting". The GO ID was always empty in live mode before the fix (see Known problems and Status) |
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
   - From the start term, walk up the GO tree through `is_a` and `part_of` links to the nearest configured compartment term (`src/thg_protocol/curation/go.py:168-198`).
   - Exception: if the start term is listed in `compartment_go_aliases` (currently only cytoplasm → `c`), it resolves straight to that compartment without walking the tree.
   - BioCyc's location ontology (CCO) is used instead only when no GO compartment terms are configured and the annotation has no GO ID (`_stages.py:1562-1576`; the CCO resolver itself is `resolve_compartment` at `src/thg_protocol/curation/beta2.py:42`).
3. **Combine per gene.** Each gene ends up with a set of compartments.
4. **Apply the GPR** (`infer-complex-and-isoenzyme-locations`, `resolve_gpr_locations` in `curation/beta2.py`).
   - **OR** (isoenzymes): union of the genes' compartments.
   - **AND** (complex subunits): intersection. Every subunit must be present in the compartment, otherwise that compartment is rejected (`required-subunit-location-intersection-is-empty`).
5. **Fill gaps from reaction evidence.** If step 4 gave no compartment, use the reaction's own resolved Reactome location (tagged `reaction-evidence-candidate`).
6. **Plan the expansion** (`generate-expansion-plan`). Each compartment found becomes a proposal to copy the reaction there with compartment-specific metabolites. The original reaction is always kept. If an equivalent reaction already exists in the target compartment, no copy is made.

## Edge cases

### 1. Two compartments the same distance away

- The location is **rejected**, never guessed. The record gets `status: "rejected"`, reason `ambiguous-compartment-resolution`, and the list of candidates (`curation/go.py:206-216`, `curation/beta2.py:127-138`).
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

- **A related case:** one gene has several annotations that each resolve cleanly, but to different compartments. *(Changed 2026-10-08, see Status.)* This used to mark the gene `status: "conflicting"` (reason `same-precedence-evidence-disagree`), and under the default `reject-conflicts` policy the gene then contributed **no compartments at all**. Now the gene keeps every compartment, because several compartments means the enzyme is in more than one place, which is what β2 expands into.

### 2. A reaction with no compartment evidence

- **No GPR:** the reaction isn't eligible for expansion. It's kept as-is with reason `no-gpr-or-ec-evidence` (`reaction_policy` in `curation/beta2.py`).
- **Genes with no known location:** the genes go on the unresolved list. If `fallback_location` is set in the config, they're assigned that location and the result is tagged `evidence_type: "fallback"`. If it isn't set, they contribute nothing.
- **No gene-derived compartment, but a Reactome location:** the Reactome location is used.
- **Nothing anywhere:** no expansion is planned. The reaction is kept in its original compartment (`action: "retain"`). It's never dropped.
- **Gene and reaction evidence disagree** (no overlap between them): a `gene-and-reaction-evidence-disagree` record is written. Nothing reads it, so it doesn't block anything. Gene evidence wins, and reaction evidence is only used when the gene route produced nothing.

### 3. A mismatch between UniProt and GO

- **Text vs GO ID within one annotation:** if a GO ID is present, it's used and the text is ignored (`curation/go.py:89-91`). Nothing checks that the two agree.
- **UniProt vs GOA for the same gene:** both are kept as locations for the gene. There is no precedence between them: the gene gets the union of their compartments (see Status for a GOA vs UniProt comparison).
- **Locations set by hand in the config:** these always win. GOA and UniProt annotations for those genes are stored under `supporting_evidence` for reference, but are never added to the gene's `locations` (`_stages.py:1068`). Snapshot records and the older UniProt lookup also skip those genes. Nothing flags a hand-set location that disagrees with the databases.

## Known problems with the UniProt input

Both were confirmed on 2026-10-07 by running the real `UniProtClient` against the live UniProt API for 50 human metabolic genes, with the configured GO release. The results are from that 50-gene sample, not a full β2 run. The existing `runs/thg-reference` has no gene location evidence recorded, so no real run output could be checked. `configs/beta2.json` does use `uniprot` as a location source in live mode, so both problems apply to real runs.

### Problem 1: UniProt locations never get a GO ID in live mode

- The code converts UniProt location IDs (`SL-xxxx`) to GO terms using a field called `sl_to_go`, which it reads from each API record (`src/thg_protocol/services/uniprot.py:176-181` before the fix).
- UniProt's API doesn't return that field. A real record gives only `{"value": "Mitochondrion matrix", "id": "SL-0170"}`. The only other readers of `sl_to_go` are the snapshot path (`StaticUniProtClient`, `uniprot.py:60`), which uses it only if a snapshot record happens to carry one, and a unit test that writes it into its own test data (`tests/unit/test_go_evidence.py:278`), which is why the tests passed.
- Result: **744 annotations, 0 with a GO ID.** Every UniProt location goes through the text-matching fallback:

| Outcome | Count | Examples |
|---|---|---|
| resolved | 311 | "Mitochondrion" → m, "Lysosome membrane" → l |
| `location-not-in-ontology` | 293 | "Cytoplasm, cytosol", "Cytoplasm, cytoskeleton" |
| `location-not-in-registry` | 140 | "Cytoplasm", "Membrane", "Chromosome" |

- UniProt's comma-separated names ("Cytoplasm, cytosol") are never GO names, so they always fail. Some simple names fail too: "Mitochondrion matrix" isn't a GO name (GO uses "mitochondrial matrix"). As a result, human citrate synthase (CS), the textbook mitochondrial enzyme, gets no UniProt location.

### Problem 2: the UniProt query includes every species and reads only one page

- The query is `gene:CS OR gene:ACO2 OR …` with no organism filter (`services/uniprot.py:123-134` before the fix). It requests one page of 500 records and ignores UniProt's next-page link.
- For the 50 genes, UniProt reported **60,904 matches**. The code kept 500, of which only **52 were human**.
- Any record whose primary gene name exactly matches (case-sensitive) is assigned to the human gene (`services/uniprot.py:169-171` before the fix). Mouse `Cs` therefore isn't picked up, but plant or bacterial records named `CS` are. This is how locations like "Periplasm", "Glyoxysome" and "Encapsulin nanocompartment" (bacteria and plants) end up on human genes.
- It changed the result for 5 of the 50 genes. Each had no human location that resolved and picked one up from another species:

| Gene | Human UniProt compartments | Compartments as coded |
|---|---|---|
| CS | none | nucleus |
| MDH2 | none | peroxisome (likely from a plant glyoxysome) |
| PGK1 | none | mitochondria |
| GOT1 | none | Golgi |
| ARG1 | none | ER |

- Those wrong compartments would become real reaction copies. If GOA gave the correct location for the same gene, the gene was marked conflicting and, under the default `reject-conflicts` policy, contributed nothing (that conflict rule was removed on 2026-10-08).
- All 50 human genes made it into the first page in this test, and in this sample reviewed human entries came first in UniProt's ranking (observed, not a documented guarantee). The code sends batches of 100 genes; whether human entries can fall off the page at that size wasn't tested.

## Suggested fixes

1. **Restrict and paginate the UniProt query:** add `AND organism_id:9606`, and either follow the next-page link or compare against the reported total so truncation can't happen silently.
2. **Use UniProt's official location-to-GO mapping:** load `subcell.txt` from a pinned UniProt release and use it to set `go_id`, instead of reading `sl_to_go` from the API response.
3. **Optional:** report genes whose hand-set config locations disagree with GOA or UniProt, and annotations whose text and GO ID point to different compartments.

## Status (2026-10-08)

Fixes 1 and 2 are implemented in `src/thg_protocol/services/uniprot.py`. Also added: a cytoplasm → cytosol alias, a fix so dual-located genes are no longer dropped as conflicting, an opt-in GOA evidence-code filter, and validation of `uncertainty_policy` (all below). Fix 3 (disagreement reports) is not done yet.

### What changed

- **Organism filter and exact gene match.** Each batch now queries `(gene_exact:CS OR … OR xref:ensembl-ENSG…) AND organism_id:9606` (`uniprot.py:159-171`). The parentheses make the organism filter apply to the whole OR group. `gene_exact:` stops synonym hits from using up page space.
- **Pagination.** The client follows the `Link: rel="next"` header until no next page is left (`uniprot.py:175-202`). It then compares the record count with `X-Total-Results` and raises `RuntimeError` if they differ, so a truncated result can no longer go through unnoticed.
- **SL→GO mapping from UniProt itself.** `UniProtClient._location_go_terms()` (`uniprot.py:110`) fetches UniProt's subcellular-location vocabulary once per client (`rest.uniprot.org/locations/stream`, fields `id,gene_ontologies`) and sets `go_id` from it. A mapping can also be passed in with `UniProtClient(sl_to_go=…)` for offline or pinned use. The old `record.get("sl_to_go")` lookup in the live parser is gone.
- **Provenance.** `metadata` now records the release the API actually served (`api_release`), the organism filter, and the URL, release and SHA-256 of the location mapping (`location_go_mapping`). `parser_version` went from `1` to `2`.
- **Tests** (`tests/unit/test_go_evidence.py`): the query-format assertions are updated, and three new tests cover GO IDs from a realistic SL-only record (`:322`), following next-page links (`:352`), and rejecting truncated results (`:380`). The full suite passes (2207 tests). The only failure is the docs build test, which fails because `mkdocs` isn't installed in the `thg_standalone` environment.

### Live re-check (same method as above, 50 human metabolic genes, GO 2026-06-19)

| | Before | After |
|---|---|---|
| Records kept | 500 of 60,904 (52 human) | all, human only |
| Annotations | 744 | 641 |
| With a GO ID | 0 | 628 |
| Resolved to a compartment | 311 | 498 |
| CS | nucleus (from another species) | `m` |
| MDH2 | peroxisome (from another species) | `m` |
| PGK1 | mitochondria (from another species) | `c`, `m` (human UniProt lists cytosol and mitochondrial matrix) |
| GOT1 | Golgi (from another species) | none (see below) |
| ARG1 | ER (from another species) | `c` |

No locations from other species remain (no Periplasm, Glyoxysome and so on). The 13 annotations still without a GO ID come from SL terms that UniProt doesn't map to GO, mostly "Microsome membrane".

### Cytoplasm → cytosol alias

- **The problem.** UniProt often gives only "Cytoplasm" (GO:0005737). In GO, cytoplasm sits *above* cytosol (GO:0005829, the `c` target), so walking up the tree never reaches a compartment and the annotation was rejected (`location-not-in-registry`). In the first re-check this caused 114 of the 143 rejections, and 11 of the 50 genes (including GOT1, GPI, TPI1 and LDHA) got no UniProt compartment.
- **Why an alias is right.** Strictly, GO's cytoplasm also includes the organelles, but a model lists organelles as their own compartments. What a model calls `c` (named "Cytosol" in Human-GEM and BiGG, sometimes "cytoplasm" elsewhere) is the cytosol. So for a metabolic enzyme, "Cytoplasm" with nothing more specific means `c`.
- **What changed.**
  - New config key `compartment_go_aliases`, set to `{"GO:0005737": "c"}` in `configs/beta2.json`.
  - `resolve_go_compartment` takes the aliases as a new argument (`curation/go.py:105`). An alias applies **only when the location starts at exactly that term** (`go.py:151`), whether it arrives as a GO ID or as the text "Cytoplasm". The walk up the tree never uses aliases, so descendants of cytoplasm such as "cytoplasmic granule" or "perinuclear region" still resolve, or are rejected, exactly as before. Results that resolved before the change are unaffected.
  - Records resolved this way are tagged `resolution_method: "configured-alias"`, and their `resolution_path` contains a `configured_alias` step, so the audit trail shows the choice.
  - Config validation (`workflow/config.py:842`): keys must be GO IDs, values must be compartments listed in `compartment_go_terms`, and an alias can't repeat a compartment's own GO term.
  - The aliases are passed through the compartment registry into resolution, the GO subgraph artifact and snapshot metadata (`_stages.py`).
- **Tests.** A resolver unit test (`tests/unit/test_go_evidence.py:65`), config validation (`tests/unit/test_config_api.py:135`), and an end-to-end β2 run where a cytoplasm annotation lands in `c` and a child term doesn't (`tests/integration/test_beta2_go_workflow.py:124`). Full suite: 2212 passed. The only failures are the two docs tests, which need `mkdocs`, and that isn't installed in `thg_standalone`.
- **Live 50-gene re-check with the alias:**

  | | UniProt fix only | + alias |
  |---|---|---|
  | Resolved annotations | 498 of 641 | 612 of 641 |
  | Rejected | 143 | 29 |
  | Genes with a UniProt compartment | 39 of 50 | 46 of 50 |
  | GOT1 | none | `c` |

  The 29 remaining rejections are specific terms that don't sit under a configured compartment ("Microsome membrane", "Membrane", "Secreted", sarcomere bands, "Chromosome"). ALDOA is left only with sarcomere-band terms, and TKT, ASL and FBP1 have no UniProt location at all. GOA should cover these.

### GOA vs UniProt, and the multi-compartment "conflict" bug

- **The two sources agree.** For the same 50 genes (current human GOA, all evidence codes):

  | UniProt compared with GOA | Genes |
  |---|---|
  | Same compartments | 11 |
  | UniProt's compartments all appear in GOA | 35 |
  | No UniProt compartment (ALDOA, TKT, ASL, FBP1; GOA covers all four) | 4 |
  | UniProt contradicts GOA | **0** |

  This is expected, because GOA already imports UniProt's location annotations as electronic (IEA) annotations. UniProt adds little that GOA doesn't already have.
- **Neither source wins.** Locations from both are pooled per gene. The "strong"/"supporting" label is set by whichever source creates the gene record first, and nothing reads it. Hand-set config locations still override both.
- **The bug.** `resolve-compartment-evidence` marked *every* gene with more than one compartment as `conflicting`, even when every source agreed. That was 44 of the 50 genes, including genuinely dual-located enzymes like GLS (`c,m`) and HMGCR (`r,x`). Both shipped configs set `uncertainty_policy: "report"`, which the code didn't recognize and treated as `reject-conflicts` without any error. So those genes contributed no compartments at all, and β2 would have expanded almost nothing.
- **Fixed:**
  1. A gene with several compartments now keeps all of them, and no conflict record is written (`_stages.py`, `resolve-compartment-evidence`). `uncertainty_policy` still applies to gene records that arrive already marked `conflicting` (for example from a snapshot).
  2. **New opt-in filter `goa_excluded_evidence_codes`** (a list of codes, empty by default). GOA annotations with these codes are skipped when evidence is collected. The shipped configs leave it empty, so high-throughput annotations (HDA, HTP and so on) are **kept**. For reference, across these 50 genes 84 of the 96 annotations that resolve to vesicle (`v`) are HDA, mostly "extracellular exosome" proteomics. CS, for example, gets `n` and `v` only from HDA. Setting `["HTP", "HDA", "HMP", "HGI", "HEP"]` would drop them.
  3. **`uncertainty_policy` is validated.** It must be `reject-conflicts` or `allow-conflicts`, and anything else is a config error. `configs/beta2.json` and `configs/reference.json` now say `reject-conflicts`, which is what `"report"` already behaved as.
- **Tests:** a β2 run where a gene annotated to cytosol and mitochondria keeps both, with an HDA-only nucleus annotation excluded by the filter (`tests/integration/test_beta2_go_workflow.py`); validation of both settings; and a check that both shipped configs pass validation (`tests/unit/test_config_api.py`). Full suite: 2217 passed. The only failures are the two docs tests, which need `mkdocs`.

### Still open

- **UniProt release pinning.** The REST API serves only the current release (2026_03 at the time of the check), while `configs/beta2.json` pins `2026_02`. The served release is now recorded in `api_release` but isn't enforced. For an exactly reproducible run, pass a pinned mapping via `sl_to_go` (for example from that release's `subcell.txt`) and use a UniProt snapshot.
- **A few unrequested records.** Two records that don't match any requested gene still come back ("ACLY variant protein", DDR2). The downstream `StaticUniProtClient` filter drops them, so they have no effect.
- **Fix 3** (reporting config vs database disagreements, and text vs GO ID mismatches) is still to do.
