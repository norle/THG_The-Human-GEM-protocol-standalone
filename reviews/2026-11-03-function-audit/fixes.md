# Fix record — 3 November 2026

All 20 findings are addressed. The original report, ledgers, checksums, and defect reproductions remain evidence of the audit baseline; the reproductions assert the former wrong behavior and are not post-fix tests.

Regression coverage is in [test_function_audit_regressions.py](../../tests/unit/test_function_audit_regressions.py), with test names numbered after the findings. Finding 20 is covered by the corrected [integration test](../../tests/integration/test_legacy_algorithm_apis.py).

| Finding | Resolution |
| --- | --- |
| 1 | Malformed and unresolved participants raise `ValueError` identifying the term. Metabolite resolution is staged and committed only after every participant resolves. |
| 2 | Formula matching uses the shared complete element parser. Non-hydrogen element/count maps must match; hydrogen counts and a trailing charge may differ under the protonation policy. Invalid formulas cannot establish a match. `atom` retains all elements. |
| 3 | Decimal coefficients retain input precision. Candidate selection and postfiltering compare species/coefficient mappings on each side, allowing reversal but requiring the same scale. Incorrect early candidates no longer hide later valid matches. |
| 4 | Boolean flattening crosses only matching operators; AND boundaries remain intact. Truth-table tests cover every gene-presence combination for the reported expression. |
| 5 | AST comparison checks operators, child counts, and one-to-one structural matches before deduplication. Truth-table tests preserve the reported alternative branch. |
| 6 | Subunit metadata serialization receives the curated GPR string, while existing reaction annotations remain intact. A regression includes a gene rewrite and existing metadata. |
| 7 | The workflow applies global reactions once, after creating metabolites for all configured compartments. |
| 8 | Automatic IDs reserve every explicit configuration ID. Conflicting explicit definitions raise an identified error rather than silently disappearing. |
| 9 | The shared MILP parameter boundary rejects nonpositive, nonnumeric, Boolean, and non-finite minimum flux. Configuration also rejects non-finite flux. |
| 10 | An empty annotation TSV returns an empty mapping. Other file/read errors still propagate. |
| 11 | Missing or empty reaction sides are valid boundary cases, explicitly skipped for two-sided matching. An all-boundary input returns an empty table with the expected columns; following internal reactions still parse. |
| 12 | Configuration and the public activity evaluator reject non-finite and nonnumeric thresholds before classifying activity. |
| 13 | CCO scoring retains relationship rank across traversal. Shorter paths rank first; at equal distance, pure containment paths outrank any path containing a superclass edge. Ontology cycles terminate. |
| 14 | Validation configuration requires `validation.input_model` during loading, before a run is created. |
| 15 | Flux endpoints are optimized in both directions over the feasible model. Only an explicit solver `unbounded` status produces infinity; finite caps remain finite. The original objective is restored, and other solver failures propagate. |
| 16 | Both notebook FVA endpoints must be within the model's flux tolerance to count as blocked, including the notebook's final check. Reverse-only activity remains active. |
| 17 | Notebook dead-end labels reuse the package's bound-aware production/consumption helpers. Forward, reverse, reversible, and disabled reactions have regression cases. |
| 18 | Structured counts are validated before integer conversion. Fractions, booleans, non-finite values, and nonpositive counts are rejected; exact integer numbers and integer strings remain supported. |
| 19 | `nullity` is documented as returning a full-rank square completion plus the independent input rows. Unit rows are appended only when they increase rank. Inverse-based checks cover the reported singular completion and other rank-deficient inputs. |
| 20 | The fixture swaps species with a temporary placeholder, checks the changed XML, and verifies that both parsed sides are reversed. |

## Compatibility and limits

Invalid pathway participants and conflicting IDs now fail explicitly instead of being silently skipped. Formula compatibility is deliberately stricter for non-hydrogen atoms; `formula_similarity` returns 0 or 1, retaining the threshold argument for callers. Canonical `atom` output includes all elements in sorted order. Reaction matching retains the existing exclusions for configured proton/water species and permits reversal, but does not normalize reaction scale. Boundary reactions are excluded from two-sided annotation matching.

`unbounded_reactions` now measures the full feasible flux region rather than fixing the original objective at its optimum. It performs two serial optimizations per reaction and restores the original objective afterward. `nullity` retains its return order and shapes while correcting the completion's rank.

Notebook regression tests extract only the affected functions. Full notebook execution, live external services, and full published-model/phenotype reproduction were not performed. These changes correct the reported computational defects and do not independently establish biological validity.

## Verification

- Full suite: `python -m pytest -q` — **2,495 passed**, 1,297 warnings, 81.08 seconds. See [pytest-fixed.log](pytest-fixed.log).
- Regression tests: 65 cases covering findings 1–19; finding 20 is checked in the existing integration test.
- Ruff checks on all changed Python files and `git diff --check`.
