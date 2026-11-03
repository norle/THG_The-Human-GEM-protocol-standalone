# Functional and scientific repository review

Review date: 3 November 2026.

The review found **20 issues** across pathway construction, chemical annotation, gene rules, gap filling, validation, supplementary notebooks, and tests. Several can silently change model meaning. The existing test suite passed, but it did not detect these cases. The audit recorded the original defects; **all 20 findings have since been fixed**. See the [fix record](fixes.md) for changes, compatibility notes, and regression coverage.

The [detailed report](report.md) contains source locations, concrete examples, consequences, and proposed fixes. Finding numbers below match that report.

## What was done

1. Inventoried Python functions, methods, nested definitions, notebook functions, and handwritten JavaScript callbacks. Excluded generated `build/lib` copies and bundled third-party JavaScript in exported reports.
2. Used GPT-6 Luna subagents to review modeling algorithms; annotation, gene rules and external-service adapters; and workflow and validation code. Follow-up passes completed coverage gaps and reviewed the handwritten JavaScript.
3. Checked functional behavior and scientific meaning, tracing relevant callers, exports, configuration, and tests. Infrastructure and formatting helpers received scientific N/A assessments where appropriate. Preliminary findings were challenged to separate actual defects from documented limitations.
4. Read the test and fixture functions, ran the full test suite, and constructed small reproductions of the confirmed defects. Notebook reproductions extracted individual functions without executing whole notebooks.
5. Saved per-function assessments, source hashes, ranked findings, test output, and runnable reproductions in this directory.

The review baseline was commit `db455702352a34539ab09352ac975ded7934a413` plus the existing working-tree edits. No existing implementation, test, configuration, or model files were changed by the audit.

## Coverage

| Code reviewed | Function definitions or callbacks |
| --- | ---: |
| Package Python | 1,076 |
| Metabolic-task utility script | 2 |
| Supplementary notebooks | 28 |
| Python tests and fixtures | 743 |
| **Total Python definitions** | **1,849** |
| Handwritten JavaScript | 103 |

Python lambda bodies were reviewed with their surrounding code. The [Python ledger](functions.csv) and [JavaScript ledger](javascript-functions.csv) record the individual assessments. A function marked reviewed with no finding is not a guarantee of correctness or independent biological validation.

## What was found

### Must fix

| No. | Finding | Consequence |
| --- | --- | --- |
| 1 | Pathway parsing skips malformed or unresolved reaction participants. | An imported reaction can have different chemistry from its configuration. |
| 2 | Formula matching confuses selenium with sulfur and mishandles other elements. | Distinct compounds can receive each other's identifiers. |
| 3 | Reaction matching rounds coefficients and compares them separately from species. | Different equations can receive the same KEGG reaction annotation. |
| 4 | GPR reduction merges OR branches across an AND boundary. | Required enzyme components can become optional in the returned gene rule. |
| 5 | GPR deduplication ignores differences between AND and OR. | A valid alternative gene-supported branch can be deleted. |
| 6 | Subunit-rule curation passes existing annotation metadata as a GPR expression. | Annotated reactions can crash proposal generation. |
| 7 | Pathway construction repeats the global reaction list for each compartment. | ID-less reactions can be added multiple times. |
| 8 | Automatically generated reaction IDs can consume later explicit IDs. | A configured reaction can disappear depending on row order. |
| 9 | MILP gap filling accepts a negative minimum flux. | A blocked objective with zero flux can be reported as solved without additions. |
| 10 | Empty metabolite annotation results are parsed as a nonempty TSV. | An all-unresolved annotation pass crashes. |
| 11 | SBML reaction parsing assumes a nonempty reactant list. | A valid source-only boundary reaction can abort annotation of the file. |
| 12 | Expression threshold validation accepts non-finite numbers. | Finite measured activity can be classified as inactive and reactions removed. |

Findings 4 and 5 affect exported gene-rule helpers. The current validator discards the transformed output of `reduce_gpr`, and no production caller of `sanitize_gpr` was found. The review therefore did not establish that current workflows apply those corrupted rules to models.

### Should fix

| No. | Finding | Consequence |
| --- | --- | --- |
| 13 | CCO compartment resolution discards its containment preference during scoring. | A location with a preferred containment path remains unresolved. |
| 14 | Validation configuration accepts a missing input model. | The workflow fails later with an internal `KeyError`. |
| 15 | A public FVA helper calls large finite fluxes unbounded. | A conventional flux cap can be mistaken for mathematical unboundedness. |
| 16 | A supplementary notebook checks only the FVA maximum for blockage. | A reaction capable of reverse flux can be classified as blocked. |
| 17 | A supplementary notebook classifies dead ends without reaction bounds. | Reversible metabolites can be labeled final substrates or products. |
| 18 | Structured subunit counts are converted to integers before validation. | A count such as `2.7` is silently changed to `2`. |

### Lower priority

| No. | Finding | Consequence |
| --- | --- | --- |
| 19 | The legacy `nullity` helper can return a rank-deficient matrix completion. | External callers expecting an invertible completion can receive a singular matrix; clarify the contract before changing compatibility behavior. |
| 20 | A reverse-reaction test fixture's replacements restore its original input. | That particular test does not exercise reverse matching, although another characterization test does. |

## Checks performed

- **Full suite:** `python -m pytest -q` — 2,430 passed, 1,297 warnings, 52.45 seconds. See [pytest.log](pytest.log).
- **Defect reproductions:** Six saved scripts ran successfully and demonstrated the current wrong behavior. See the [reproduction instructions](reproductions/README.md) and [execution log](reproductions/reproduction-results.log). These assertions reproduce defects; they are not tests proving the code is fixed.
- **JavaScript syntax:** Five extracted scripts passed `node --check`. See [javascript-syntax-check.log](javascript-syntax-check.log). No browser interaction was exercised.
- **Audit artifacts:** Checked the function inventory for duplicate or missing entries, required assessment fields, links between findings and functions, and unchanged reviewed-source hashes.

The test environment used Python 3.12, COBRApy 0.29.1, NumPy 2.1.3, pandas 2.3.3, SciPy 1.15.2, MEMOTE 0.17.0, and swiglpk 5.0.12.

## Scientific interpretation and limits

The main scientific risks are altered reaction participants, incorrect chemical identities, changed Boolean gene requirements, and mistaken flux-direction conclusions. The fixes address the reported computational defects; see the [compatibility and verification record](fixes.md).

Mass balance, charge balance, stoichiometric consistency, flux feasibility, and physiological validity are different claims. Passing the existing tests or model checks does not independently establish biological correctness. The detailed report links the primary references used to assess these distinctions and records documented method limitations separately from defects.

Not checked: full published-model or phenotype reproduction, live credentialed services, every database record against its original paper, complete notebook execution, browser/DOM interactions, other Python or solver versions, and bundled third-party code.

## Saved material

- [Fix record and post-fix verification](fixes.md)
- [Detailed findings and proposed fixes](report.md)
- [Python function assessments](functions.csv)
- [JavaScript function assessments](javascript-functions.csv)
- [Reproduction instructions](reproductions/README.md)
- [Reviewed-source checksums](source-sha256.json)
- [Subagent review details](details/)
