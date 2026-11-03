> Remediation: all 20 findings below have been addressed. See [fixes.md](fixes.md). This report and its reproduction scripts describe the original audit baseline.

What this repo does: THG Protocol builds, annotates, expands, merges, and validates human genome-scale metabolic models. I assumed a researcher running local batch workflows with COBRApy and an optimization solver.

GPT-6 Luna subagents reviewed the functions in three areas: modeling algorithms; annotation, gene rules and services; workflows and validation. Follow-up Luna passes completed the initial coverage gaps and reviewed handwritten JavaScript. The coordinating review checked callers, challenged preliminary findings, read the test functions, and reran the saved reproductions. No existing source, tests, configuration, or model files were changed.

**Coverage and evidence**

| Scope | Function definitions reviewed |
| --- | ---: |
| Package Python, including methods and nested definitions | 1,076 |
| Metabolic-task utility script | 2 |
| Supplementary notebooks | 28 |
| Python tests and fixtures | 743 |
| Total Python definitions | 1,849 |
| Handwritten JavaScript functions and callbacks | 103 |

[functions.csv](functions.csv) gives each Python definition a functional assessment, a scientific assessment or N/A, its review notes, and applicable finding numbers. Notebook cell indexes are zero-based. [javascript-functions.csv](javascript-functions.csv) covers the JavaScript. Python lambda bodies were reviewed with their surrounding code. A reviewed function with no finding is not a guarantee of correctness or independent biological validation.

The baseline is commit `db455702352a34539ab09352ac975ded7934a413` plus the user's existing working-tree edits. The inventory predates these review artifacts. Generated `build/lib` copies and bundled third-party JavaScript in exported Plotly/MEMOTE reports were excluded; custom code in the archived D3 graph was included.

`python -m pytest -q` passed: **2,430 tests, 1,297 warnings, 52.45 seconds**, on Python 3.12 with COBRApy 0.29.1, NumPy 2.1.3, pandas 2.3.3, SciPy 1.15.2, MEMOTE 0.17.0, and swiglpk 5.0.12. See [pytest.log](pytest.log). Passing tests do not cover the defects below. The [reproductions](reproductions/) contain small assertions demonstrating the current wrong behavior; successful execution means the defect was reproduced, not fixed.

**Must fix**

1. **Pathway import silently drops reaction participants** ([core.py:119](../../src/thg_protocol/pathway/core.py#L119), [core.py:160](../../src/thg_protocol/pathway/core.py#L160)).
   - **What this is:** The equation parser and resolver build the stoichiometry imported by the pathway workflow.
   - **Problem:** Malformed terms are skipped, and unresolved metabolites are skipped again. `A[c] + MISSING[c] --> B[c]` becomes `A_c --> B_c` and can be imported as the configured reaction.
   - **Fix:** Reject the whole equation when any nonempty participant cannot be parsed or resolved, and identify the failed term. Keep model changes made during resolution out of the accepted result on failure.
   - **If we skip it:** A successful import can contain different chemistry from its configuration.

2. **Formula matching confuses selenium with sulfur** ([metabolites.py:75](../../src/thg_protocol/annotation/metabolites.py#L75), [metabolites.py:424](../../src/thg_protocol/annotation/metabolites.py#L424)).
   - **What this is:** PubChem candidate acceptance uses a formula similarity score.
   - **Problem:** `atom()` turns both `C3H7NO2Se` and `C3H7NO2S` into `C3H7O2N1S1`, giving similarity 1.0. An injected sulfur candidate is accepted for a selenium input and its identifier is written; other element symbols are also lost or misread.
   - **Fix:** Reuse the complete formula parser and compare element/count maps under an explicit protonation policy. Require incompatible non-hydrogen composition to reject the candidate.
   - **If we skip it:** Distinct chemical species can receive each other's identifiers and spread incorrect identity evidence downstream.

3. **Reaction matching can annotate a different chemical equation** ([reactions.py:66](../../src/thg_protocol/annotation/reactions.py#L66), [reactions.py:104](../../src/thg_protocol/annotation/reactions.py#L104), [reactions.py:203](../../src/thg_protocol/annotation/reactions.py#L203)).
   - **What this is:** The annotation workflow matches parsed SBML reactions to database reactions.
   - **Problem:** Coefficients are rounded to integers and then compared as a list separate from species. The complete pipeline accepts both `1.4 A + B -> C` versus `1.49 A + B -> C`, and `A + 2 B -> C` versus XML-ordered `B + 2 A -> C`.
   - **Fix:** Compare species-to-coefficient mappings with preserved numeric precision, using a consistent orientation/scale policy. Keep species sets as a candidate search only.
   - **If we skip it:** Chemically different equations can acquire the same KEGG reaction identifier. The postfilter does compare coefficient columns 8 and 21; the defect is their lossy, unpaired representation.

4. **GPR reduction turns required alternatives into optional alternatives** ([ast_gpr.py:73](../../src/thg_protocol/gpr/ast_gpr.py#L73)).
   - **What this is:** `reduce_gpr` calls `naive_reduce_or` to simplify Boolean gene–protein–reaction rules.
   - **Problem:** `(A or B) and (C or D)` becomes `A or B or C or D`. With only A present, the original rule is false and the reduced rule is true.
   - **Fix:** Flatten a child only when its Boolean operator matches its parent; preserve AND boundaries.
   - **If we skip it:** Public API users can create reactions that appear active without a required enzyme component. The current validator calls this helper for parsing but discards the transformed output, so that caller is not established to mutate model rules.

5. **GPR deduplication removes a logically different branch** ([ast_gpr.py:25](../../src/thg_protocol/gpr/ast_gpr.py#L25), [ast_gpr.py:46](../../src/thg_protocol/gpr/ast_gpr.py#L46)).
   - **What this is:** `sanitize_gpr` uses `compare_ast` to decide whether alternative branches are duplicates.
   - **Problem:** The comparison ignores AND versus OR. `(A and (B and C)) or (A and (B or C))` loses its second branch, changing the outcome when A and B are present but C is absent.
   - **Fix:** Require matching operators and correct structural equivalence before deleting a branch.
   - **If we skip it:** Public callers can lose a valid gene-supported alternative. No production caller of `sanitize_gpr` was found in this repository.

6. **Existing annotations crash subunit-rule curation** ([beta1.py:892](../../src/thg_protocol/curation/beta1.py#L892)).
   - **What this is:** `generate_curation_proposals` attaches stoichiometric GPR metadata while retaining reaction annotations.
   - **Problem:** For a reaction with GPR `G1 and G2`, nonempty annotations, and configured subunit counts, it passes the annotation dictionary as the GPR expression. The serializer raises `AttributeError: 'dict' object has no attribute 'kind'`.
   - **Fix:** Preserve the curated GPR string in a separate variable and pass that string to `serialize_s_gpr`.
   - **If we skip it:** A normal annotated reaction can stop proposal generation.

7. **Pathway imports duplicate ID-less reactions for each compartment** ([workflow.py:86](../../src/thg_protocol/pathway/workflow.py#L86), [core.py:274](../../src/thg_protocol/pathway/core.py#L274)).
   - **What this is:** `implement_pathway` creates components for each configured compartment.
   - **Problem:** Each iteration applies the entire global reaction list, while the reaction helper ignores the compartment argument. Two configured compartments and one ID-less `A[c] --> B[c]` produce two identical reactions with different IDs.
   - **Fix:** Apply the global reaction list once after creating the required metabolites.
   - **If we skip it:** Reaction counts and available pathway capacity can be inflated without a duplicate-ID error.

8. **Generated IDs consume IDs belonging to later explicit reactions** ([core.py:284](../../src/thg_protocol/pathway/core.py#L284)).
   - **What this is:** The pathway helper allocates `MAR#####` identifiers in configuration order.
   - **Problem:** An ID-less first row gets `MAR00001`; a later row explicitly using `MAR00001` is silently skipped, even when it describes a different reaction.
   - **Fix:** Reserve all explicit identifiers before allocating generated identifiers, and report conflicting explicit definitions.
   - **If we skip it:** Configuration ordering decides which reaction disappears.

9. **A negative flux requirement reports an unrepaired model as solved** ([core.py:473](../../src/thg_protocol/gapfill/core.py#L473), [core.py:809](../../src/thg_protocol/gapfill/core.py#L809)).
   - **What this is:** The public MILP gap-fill API accepts `minimum_flux` and uses it to require objective activity.
   - **Problem:** With a blocked biomass objective, a valid universal model, and `minimum_flux=-1`, `gapfill_model` returns `solved`, selects no reactions, and leaves objective flux at zero. The final absolute-flux comparison is trivially satisfied by a negative threshold.
   - **Fix:** Require a finite positive numeric threshold at the shared parameter boundary, rejecting booleans and malformed values.
   - **If we skip it:** An invalid parameter can turn a failed biological objective into a successful gap-fill result.

10. **Zero successful metabolite matches abort annotation** ([metabolites.py:392](../../src/thg_protocol/annotation/metabolites.py#L392)).
    - **What this is:** `process_annotation` reads the TSV generated by the PubChem pass.
    - **Problem:** When nothing matches, the generated file is empty and `pandas.read_csv` raises `EmptyDataError`. The calling workflow cannot report the unresolved model normally.
    - **Fix:** Return an empty annotation mapping for a valid empty result file.
    - **If we skip it:** A legitimate all-unresolved outcome becomes a workflow crash.

11. **An empty reactant side aborts SBML reaction parsing** ([reactions.py:169](../../src/thg_protocol/annotation/reactions.py#L169)).
    - **What this is:** `process_reac` sends every reaction to `identify_reaction`.
    - **Problem:** The parser indexes the first reactant-list regex match without checking it exists. A source-only boundary reaction with a missing or empty reactant list raises `IndexError` and stops the file's annotation.
    - **Fix:** Represent missing/empty sides as empty participant lists, then explicitly handle or skip boundary matching.
    - **If we skip it:** One valid boundary reaction can prevent annotation of the rest of the model.

12. **Non-finite expression thresholds silently deactivate genes** ([config.py:517](../../src/thg_protocol/workflow/config.py#L517), [cell_specific/__init__.py:37](../../src/thg_protocol/cell_specific/__init__.py#L37)).
    - **What this is:** The cell-specific workflow accepts a numeric activity threshold.
    - **Problem:** `1e309` becomes infinity and passes configuration validation. A finite gene activity then fails the threshold comparison; a NaN threshold similarly makes comparisons false.
    - **Fix:** Require `math.isfinite` at configuration and public evaluator boundaries before reduction.
    - **If we skip it:** Malformed settings can remove measured, active reactions as though the data supported their removal.

**Should fix**

13. **Compartment resolution loses its containment preference** ([beta2.py:94](../../src/thg_protocol/curation/beta2.py#L94)).
    - **What this is:** The CCO resolver ranks containment above generic superclass relationships.
    - **Problem:** Every terminal candidate receives rank zero. Equally near `component_of` and `superclasses` targets are rejected as ambiguous despite the stated preference.
    - **Fix:** Carry the relationship rank into candidate scoring, with an explicit policy for paths containing multiple edges.
    - **If we skip it:** A location with a preferred containment path remains unresolved. This is a mismatch with the implementation's policy, not evidence that every containment path is biologically preferable.

14. **Validation configuration accepts a missing input model** ([config.py:388](../../src/thg_protocol/workflow/config.py#L388), [validation.py:40](../../src/thg_protocol/workflow/validation.py#L40)).
    - **What this is:** The `validate` workflow fingerprints its input before its first stage runs.
    - **Problem:** A valid run block with `validation: {}` loads successfully, then fingerprinting raises `KeyError: 'input_model'`.
    - **Fix:** Require the currently supported input path during configuration validation, producing `ConfigError` before creating a run.
    - **If we skip it:** Incomplete configurations fail late with an internal-key error instead of an actionable input error.

15. **Finite capped flux is called unbounded** ([consistency.py:180](../../src/thg_protocol/analysis/consistency.py#L180)).
    - **What this is:** `unbounded_reactions` labels FVA endpoints with magnitude at least 999 as infinity.
    - **Problem:** A two-reaction source/drain network bounded at 1000 has a finite optimum of 1000, but both reactions are reported as unbounded and the reported fraction is 1.0.
    - **Fix:** Describe this as a large-bound heuristic, or obtain actual unboundedness from the solver rather than an arbitrary finite cutoff.
    - **If we skip it:** External users of this documented public helper can misinterpret a conventional flux cap. No internal production caller was found.

16. **A notebook mistakes reverse flux for blockage** ([crucial_exchange_rs.ipynb](../../supplementary_material/crucial_exchange_rs.ipynb), cell 29, function line 21).
    - **What this is:** `test_and_remove_rxns` removes boundary reactions when the remaining internal network stays active.
    - **Problem:** It declares a reaction blocked whenever its FVA maximum is at most zero. The feasible interval `[-10, 0]` carries reverse flux but is classified as blocked, so an unnecessary boundary reaction is restored.
    - **Fix:** Require both FVA endpoints to be near zero, using the solver's flux tolerance.
    - **If we skip it:** The archived notebook can retain boundaries for the wrong scientific reason. The package implementation was reviewed separately; this finding belongs to the notebook.

17. **A notebook ignores reversibility when classifying dead ends** ([extra.ipynb](../../supplementary_material/extra.ipynb), cell 4, function line 92).
    - **What this is:** `classify_deadend_in_final_model` labels final substrates and products for exported reports.
    - **Problem:** In `A <-> B` with bounds `[-10, 10]`, A can be both produced and consumed. The helper labels it a final substrate because it checks only the written coefficient sign.
    - **Fix:** Reuse the package's bound-aware directional-role logic when producing these labels.
    - **If we skip it:** Supplementary reports can present reversible metabolites as one-way dead ends.

18. **Structured subunit counts are silently truncated** ([stoichiometry.py:294](../../src/thg_protocol/gpr/stoichiometry.py#L294)).
    - **What this is:** `sgpr_from_dict` deserializes gene subunit counts.
    - **Problem:** A numeric count of `2.7` becomes `2` through `int(coefficient)` before validation. The original invalid value is lost.
    - **Fix:** Reject non-integral numeric counts before conversion; retain supported exact integer representations.
    - **If we skip it:** Malformed evidence is silently reported as a different subunit count.

**Nice to have**

19. **The legacy matrix-completion helper can return a singular matrix** ([mass_balance.py:262](../../src/thg_protocol/model_build/mass_balance.py#L262)).
    - **What this is:** `nullity` retains independent rows and appends unit rows to complete a square matrix.
    - **Problem:** Input `[[0, 1]]` returns two copies of `[0, 1]`, leaving rank 1. The existing test checks dimensions, not independence.
    - **Fix:** Choose linearly independent completion rows, or explicitly narrow the documented contract if full-rank completion is not intended.
    - **If we skip it:** External callers expecting an invertible completion receive a singular matrix. No package production caller was found, and the contract needs clarification before changing compatibility behavior.

20. **The reverse-reaction fixture never reverses its reaction** ([test_legacy_algorithm_apis.py:65](../../tests/integration/test_legacy_algorithm_apis.py#L65)).
    - **What this is:** The integration test claims to exercise opposite reaction orientations.
    - **Problem:** Its first replacement changes A to B; the second replacement changes that same occurrence back to A. `reverse_template == reaction_template` is true.
    - **Fix:** Swap the two IDs simultaneously or use a temporary placeholder, and assert that the resulting sides are reversed.
    - **If we skip it:** This particular test supplies no reverse-direction evidence. A separate characterization test does exercise reverse species-set matching.

**Scientific assessment and limits**

The highest-impact findings change encoded chemistry or Boolean gene requirements. Mass/charge balance, stoichiometric consistency, flux feasibility, and physiological validity are different claims; passing one does not establish the others. The reviewed conservation checks are computational diagnostics, and proposed chemistry repairs still require independent curation. The formal consistency distinction is described by [Gevorgyan, Poolman and Fell, 2008](https://pubmed.ncbi.nlm.nih.gov/18697772/).

The GIMME implementation was reviewed for required objective constraints, absolute reversible flux penalties, missing-expression handling, and sample consensus. Its results depend on chosen objectives, medium, expression preprocessing, and thresholds; the original method likewise requires presupposed metabolic functions. This audit did not reproduce experimental cell phenotypes. See [Becker and Palsson, 2008](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1000082).

The energy-cycle gate documents an important limitation: one least-flux cycle per energy couple can hide a newly introduced alternative when a cycle already exists. Missing cofactor annotations or optional dependencies can also make the check explicitly skipped. These are recorded limits, not newly claimed defects. Energy-generating cycles can distort model predictions; see [Fritzemeier et al., 2017](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005494).

GO traversal was checked against its distinction between `is_a` and `part_of`, with no inference from spatial-neighbor relationships. Such location evidence supports compartment assignment, rather than proving that a particular reaction occurs there. See the [Gene Ontology relationship definitions](https://geneontology.org/docs/ontology-relations/).

Handwritten report scripts passed five extracted-script `node --check` checks. The archived D3 graph uses equation-side arrows even for reversible edges; its arrows should be read as stoichiometric orientation, not feasible flux direction. Its tooltip interpolates the fixed embedded metadata into HTML; no malicious markup was found in that snapshot, and regenerated untrusted replacements were not tested. CDN library contents and browser interactions were not exercised.

**Verdict:** Fix silent chemistry/identity changes, Boolean-rule corruption, and false-success gap filling first. The test suite is healthy as an execution check, but it does not establish scientific correctness for the uncovered cases.

**Not checked:** Full published-model/phenotype reproduction, live credentialed service behavior, all database records against their original papers, full notebook execution, browser/DOM interactions, other Python/solver versions, and bundled third-party code. The remaining risk is untested behavior beyond this static review and the recorded small-model reproductions; no model is scientifically certified by this audit.
