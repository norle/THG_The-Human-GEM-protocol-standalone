# Annotation, GPR, service, database, and I/O audit

The package annotates metabolic models, adds gene–reaction rules, maps genes and metabolites to external databases, and curates reaction structure. I assumed one analyst running one model at a time; I checked correctness and data integrity rather than concurrent service load.

I read all 331 inventoried named functions in this audit slice and traced the relevant callers, exports, and tests. The ledger `/tmp/thg-audit-annotations-gpr-coverage.json` marks all 331 functional rows reviewed, with a concise functional rationale and scientific rationale; 258 are science-reviewed and 73 are N/A because they are transport or compatibility plumbing. This includes nested callback/lambda bodies within their containing functions. The parent ran the full suite (2,430 tests passed). I also ran the assertion-based reproductions in `/tmp/thg-audit-annotations-repro.py`; they pass by reproducing the failures and false matches.

## Must fix

1. **Formula matching confuses selenium with sulfur** (`src/thg_protocol/annotation/metabolites.py:424-480`)
   - **What this is:** PubChem candidates are accepted when their parsed formula similarity reaches a threshold.
   - **Problem:** `atom()` uses an incomplete element list and its sulfur regex also reads `Se` as `S`. `C3H7NO2Se` and `C3H7NO2S` both normalize to `C3H7O2N1S1`; the full `identify_metabolite` path accepts cysteine’s CID for selenocysteine. PubChem records list the distinct formulas for [selenocysteine](https://pubchem.ncbi.nlm.nih.gov/compound/25076) and [cysteine](https://pubchem.ncbi.nlm.nih.gov/compound/5862).
   - **Fix:** Compare complete element/count maps, with an explicit policy for charge or protonation differences.
   - **If we skip it:** A metabolite can receive another compound’s identifier.

2. **GPR reduction changes Boolean meaning** (`src/thg_protocol/gpr/ast_gpr.py:25-63, 73-94, 115-148, 151-207`)
   - **What this is:** The exported GPR helpers reduce and deduplicate AND/OR expressions.
   - **Problem:** `naive_reduce_or` flattens sibling ORs under an AND, so `(A or B) and (C or D)` becomes `A or B or C or D`. Separately, `compare_ast` ignores whether a node is AND or OR; `sanitize_gpr('(A and (B and C)) or (A and (B or C))')` drops the broader second branch and returns only `(A and (B and C))`. The resulting rules are logically different. SBML FBC defines these gene associations as Boolean logical expressions ([official FBC specification](https://sbml.org/specifications/sbml-level-3/version-1/fbc/sbml-fbc-version-2-release-1.pdf)).
   - **Fix:** Flatten only same-operator nodes, and require operator-aware structural comparison before removing an alternative.
   - **If we skip it:** Callers of these exported helpers can create false-positive or false-negative gene–reaction associations. In-repo `sanitize_gpr` has no production caller; the public helper still returns wrong rules.

3. **Reaction matching can assign a different chemical equation** (`src/thg_protocol/annotation/reactions.py:66-97, 104-145, 148-209`; caller `src/thg_protocol/annotation/metabolite_reactions.py:208-218`)
   - **What this is:** The annotation workflow maps model reactions to database reactions by metabolites and a post-match check.
   - **Problem:** `process_jaccard` does compare columns 8 and 21, which hold all coefficients; EC numbers are in columns 9 and 22. But those coefficient columns are separately rounded integers and are not paired with species. Full-pipeline reproductions show both failure modes: `1.4` versus `1.49` both round to `1` and get assigned; and database `A=1,B=2` versus model `B=1,A=2` gets assigned because species are matched as sets while the independent ordered coefficient lists are both `1,2`.
   - **Fix:** Match normalized `(species, coefficient)` pairs on each reaction side, and compare direction only when the reaction is reversible.
   - **If we skip it:** Different reactions can receive the same KEGG annotation.

4. **sGPR curation crashes when annotation metadata already exists** (`src/thg_protocol/curation/beta1.py:892`)
   - **What this is:** Curation attaches subunit counts to a reaction while preserving existing annotations.
   - **Problem:** The proposal passes the annotation dictionary to `serialize_s_gpr` as though it were the GPR expression. A COBRA reaction with GPR `G1 and G2`, annotation `{'source': ['existing']}`, and configured counts `{'G1': 2}` raises `AttributeError: 'dict' object has no attribute 'kind'`.
   - **Fix:** Pass the GPR rule to the serializer and keep the dictionary as annotation payload.
   - **If we skip it:** Proposal generation stops and the curation set is incomplete for annotated reactions.

5. **Explicit sGPR counts can be silently truncated** (`src/thg_protocol/gpr/stoichiometry.py:294-309`)
   - **What this is:** JSON-like sGPR records are converted into typed gene-count nodes.
   - **Problem:** `int(coefficient)` converts a numeric value such as `2.7` to `2` before validation, so validation cannot reject the non-integer count.
   - **Fix:** Reject non-integral numeric values before conversion; preserve the current accepted integer/string forms.
   - **If we skip it:** Malformed or fractional source data is reported as a different subunit count.

6. **Empty-sided reactions abort reaction parsing** (`src/thg_protocol/annotation/reactions.py:21-41, 148-200`)
   - **What this is:** `process_reac` parses every reaction in an SBML file before matching.
   - **Problem:** `identify_reaction` indexes the first `<listOfReactants>` match without checking whether the list has entries. A sink reaction with an empty reactant list raises `IndexError`, aborting the full annotation workflow.
   - **Fix:** Treat an empty or missing side as an empty species list, then let the matcher skip it if it cannot match.
   - **If we skip it:** One boundary reaction can prevent annotation of the whole model.

7. **An all-unannotated model crashes before reaction processing** (`src/thg_protocol/annotation/metabolites.py:392-403`)
   - **What this is:** The workflow reads the TSV produced by its PubChem pass.
   - **Problem:** If no metabolite is identified, the generated TSV is empty and `pandas.read_csv` raises `EmptyDataError` in `process_annotation`.
   - **Fix:** Return an empty mapping for an empty report.
   - **If we skip it:** A model with zero successful lookups aborts before reactions can be processed or results reported.

## Should fix

8. **Compartment resolution loses the containment preference** (`src/thg_protocol/curation/beta2.py:93-115`)
   - **What this is:** The offline CCO resolver follows `component_of` and `superclasses` edges to a configured compartment.
   - **Problem:** The queue records relation rank but the terminal candidate is always assigned rank zero. A graph with equal-length `component_of -> Cytosol` and `superclasses -> Mitochondria` paths is rejected as ambiguous despite the documented containment preference.
   - **Fix:** Carry the edge rank through the queue and use the path rank in candidate scoring.
   - **If we skip it:** An ontology location that has a preferred containment path remains unresolved.

## Scientific review

The GPR and sGPR code was checked for preserving AND/OR structure, branch multiplicity, and observed versus defaulted coefficients. The Boolean corruption above is confirmed against the SBML FBC specification. Reactome catalyst handling maps complexes to required members and entity sets to alternatives, consistent with [Reactome’s data model](https://reactome.org/documentation/data-model). GOA parsing selects cellular-component annotations and removes `NOT` rows according to the [official GAF schema](https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/). KEGG gene lists remain low-confidence alternatives, and ambiguous Rhea EC-to-reaction mappings remain unresolved. These checks validate the implementation’s interpretation of source structures; they do not validate each external biological record against primary literature.

No repository files were changed. The reproduction script uses assertions and runs the complete reaction parse → species match → postprocess pipeline for the two false-positive examples, plus the previously recorded failures.

**Verdict:** Fix the annotation identity and Boolean-rule defects first; they can silently assign incorrect model biology.

**Not checked:** Live remote database responses or every individual source record against its cited paper. No new full test-suite run was performed in this audit continuation.
