# Implementation Plan — End-to-End THG Reference Construction and Reporting

## 1. Goal

Make this the normal user-facing command:

```bash
thg-run reference configs/reference.json
```

It should perform the complete **construction** pipeline:

```text
Human reference GEM
        │
        ▼
      THGβ1
        │
        ▼
      THGβ2
        │
        ▼
Human Database reconstruction/integration
        │
        ▼
 required gapfill
        │
        ▼
 THG reference model
        │
        ├── JSON/SBML model
        ├── reference-report.json
        ├── reference-report.md
        ├── provenance
        └── detailed change ledgers/diffs
```

Human Database integration is optional/configurable, but when enabled it belongs inside `reference`.

Final/general validation remains separate:

```bash
thg-run validate configs/reference-validation.json
```

and the same command can later validate a cell-specific model:

```bash
thg-run validate configs/cell-validation.json
```

Stage-local sanity checks and gates inside β1, β2 and gapfill should remain. The change is specifically that the **general/final validation workflow is not embedded into `reference`**.

The existing `reference` workflow already composes β1 → β2 → required gapfill, so this is an extension of the current architecture rather than a replacement.

---

# 2. Desired reference DAG

Change `REFERENCE_STAGES` from approximately:

```text
β1
 ↓
β2
 ↓
β2 gate
 ↓
gapfill
```

to:

```text
β1
 ↓
β2
 ↓
β2 gate
 ↓
[Human Database reconstruction]   optional
 ↓
[Human Database integration]      optional
 ↓
gapfill
 ↓
reference construction report
 ↓
reference export
```

More explicitly:

```text
beta1-input
...
export-beta1
     │
     ▼
load-beta1
...
export-beta2
     │
     ▼
gate-beta2
     │
     ├──────────────────────────────┐
     │                              │
     │                       human-database
     │                              │
     │                              ▼
     │                    integrate-human-database
     │                              │
     └──────────────┬───────────────┘
                    ▼
             load-gapfill-source
                    │
                    ▼
              gapfill stages
                    │
                    ▼
          summarize-reference
                    │
                    ▼
            export-reference
```

If Human Database integration is not configured:

```text
gate-beta2 → gapfill
```

If it is configured:

```text
gate-beta2
   ↓
human-database
   ↓
integrate-human-database
   ↓
gapfill
```

The important invariant is:

> Gapfill always consumes the actual model produced by the immediately preceding construction stage.

---

# 3. Refactor Human Database integration into reusable stages

Currently the Human Database merge logic is tied conceptually to the `final-thg` compatibility workflow. The merge implementation itself is already reusable and returns useful counts such as added reactions, added metabolites, overlaps and removed isolated metabolites.

Refactor the workflow layer so that Human Database reconstruction and integration can be invoked from `reference` without invoking the legacy `final-thg` route.

Recommended code organization:

```text
src/thg_protocol/workflow/
    human_database.py
    human_database_integration.py   # new or extracted
    final_thg.py                    # compatibility adapter
    reference.py
```

The generic integration stage should own:

```text
generate integration/merge plan
apply merge
write merge report
write semantic diff
write provenance
export integrated model artifact
```

The existing `final-thg` workflow can then call the same underlying integration implementation.

That avoids having two implementations of Human Database merging.

Keep:

```text
workflow: final-thg
```

working for backward compatibility, but remove it from the primary documented construction path.

The existing workflow already writes `merge-report.json`, so this functionality should be reused rather than recreated.

---

# 4. Extend the `reference` configuration

Today `reference` requires exactly the construction sections:

```text
beta1
beta2
gapfill
```



Extend it to support an optional Human Database section plus orchestration-specific merge policy.

Recommended shape:

```json
{
  "workflow": "reference",

  "run": {
    "name": "thg-reference",
    "output_dir": "../runs/thg-reference"
  },

  "beta1": {
    "input_model": "../inputs/models/human-gem.xml",
    "...": "..."
  },

  "beta2": {
    "...": "..."
  },

  "human_database": {
    "records": "../inputs/human-database/records.json",
    "mode": "..."
  },

  "reference": {
    "human_database_integration": {
      "source_precedence": "base",
      "remove_isolated_metabolites": false,
      "direction": "strict",
      "proton_water": "strict",
      "formula_charge": "report",
      "bounds": "report",
      "gpr": "report"
    }
  },

  "gapfill": {
    "method": "...",
    "max_additions": 100,
    "validation_profile": "..."
  }
}
```

The `human_database` section should be optional.

Therefore:

```json
{
  "workflow": "reference",
  "beta1": {},
  "beta2": {},
  "gapfill": {}
}
```

remains valid.

Presence of:

```json
"human_database": {}
```

enables the Human Database branch.

Do not add:

```json
"enabled": true
```

unless there is a concrete need for it. Presence/absence of the section is simpler and avoids contradictory configs.

### Config parser changes

Update:

```text
src/thg_protocol/workflow/config.py
```

to add a `reference` orchestration section and permit:

```text
reference:
    beta1
    beta2
    human_database      optional
    reference           optional
    gapfill
```

Validation rules should include:

```text
beta1 + beta2 + gapfill are always required

human_database absent
    → integration settings must not be supplied

human_database present
    → Human Database reconstruction/integration is added to DAG

reference.human_database_integration
    → validate policies using the existing MergePolicy rules
```

Do not duplicate the merge-policy validation currently used by the merge implementation. Move/commonize that validation where appropriate.

---

# 5. Make gapfill consume the integrated model

This is one of the most important implementation changes.

Today the reference gapfill path consumes the checksum-verified β2 export.

Introduce a single logical concept such as:

```text
reference-construction-source
```

whose producer is:

```text
export-beta2
```

when Human Database integration is disabled, or:

```text
integrate-human-database
```

when it is enabled.

Avoid duplicating the whole gapfill workflow.

The gapfill implementation should still run exactly once.

Desired behavior:

```python
if human_database_enabled:
    gapfill_input = integrated_model
else:
    gapfill_input = beta2_model
```

The original β2 model must remain immutable and retained as an artifact.

Add an integration test explicitly checking:

```text
checksum(export-beta2 before integration)
==
checksum(export-beta2 after reference completes)
```

---

# 6. Add a canonical construction-report layer

This is the largest user-visible improvement.

Do **not** build the summary by manually interpreting every existing ledger independently.

Instead, use a consistent semantic model comparison at each major model boundary.

The project already has model comparison/diff infrastructure, and β2 already exports a semantic β1→β2 diff.

Generate these comparisons:

```text
input GEM
    → β1

β1
    → β2

β2
    → Human Database integrated model
        only when enabled

pre-gapfill
    → post-gapfill

input GEM
    → final THG reference model
```

This provides one consistent definition of:

```text
added
removed
changed
```

across the complete workflow.

Then augment those generic diffs with stage-specific information from the existing ledgers/reports.

---

# 7. Define a stable machine-readable report schema

Add a report structure such as:

```json
{
  "schema_version": 1,
  "workflow": "reference",
  "run": "thg-reference",

  "input": {
    "model_id": "...",
    "sha256": "...",
    "counts": {
      "reactions": 13417,
      "metabolites": 8362,
      "genes": 3625
    }
  },

  "stages": [
    {
      "id": "beta1",
      "input_sha256": "...",
      "output_sha256": "...",
      "counts_before": {},
      "counts_after": {},
      "changes": {}
    },

    {
      "id": "beta2",
      "changes": {}
    },

    {
      "id": "human-database",
      "enabled": true,
      "changes": {}
    },

    {
      "id": "gapfill",
      "changes": {}
    }
  ],

  "overall": {
    "counts_before": {},
    "counts_after": {},
    "changes": {}
  },

  "artifacts": {}
}
```

### Common change schema

Use the same keys wherever possible:

```json
{
  "reactions": {
    "added": 0,
    "removed": 0,
    "changed": 0
  },

  "metabolites": {
    "added": 0,
    "removed": 0,
    "changed": 0
  },

  "genes": {
    "added": 0,
    "removed": 0,
    "changed": 0
  }
}
```

Add detailed categories when available:

```text
reaction:
    added
    removed
    stoichiometry_changed
    bounds_changed
    gpr_changed
    annotation_changed
    renamed

metabolite:
    added
    removed
    formula_changed
    charge_changed
    annotation_changed
    renamed

gene:
    added
    removed
    mapping_changed
```

The JSON report should contain both counts and pointers to the detailed artifacts rather than embedding thousands of reaction records into the summary.

---

# 8. Add stage-specific metrics

Generic semantic comparison is not enough because each THG stage has scientific meaning.

## β1

Reuse the existing inventory/change-ledger information. β1 already exports inventory and ledger artifacts.

Expose counts such as:

```text
curation proposals generated
curation proposals applied
balance corrections
formula corrections
charge corrections
GPR corrections
duplicates consolidated
isolated metabolites removed
unresolved identities
unresolved balance cases
```

## β2

Reuse:

```text
beta2-change-ledger.jsonl
beta1-to-beta2-diff.json
beta2-summary.md
```



Expose:

```text
reactions added
compartment variants created
GPRs changed
location assignments
unresolved locations
reaction-location conflicts
```

The current summary already reports added reaction counts, so this can be moved into the common reporting API rather than parsed from Markdown.

## Human Database integration

Reuse `MergeReport`:

```text
added_metabolites
added_reactions
overlapping_metabolites
overlapping_reactions
removed_isolated_metabolites
```

and add:

```text
merge conflicts
resolved conflicts
unresolved conflicts
```

using the merge plan decisions.

## Gapfill

Reuse the gapfill ledger and semantic diff.

The current implementation already calculates `added_reactions` from the model diff.

Expose:

```text
candidate reactions considered
proposals generated
proposals accepted
reactions added
metabolites added
unresolved proposals
gapfill gate status
```

---

# 9. Create both JSON and Markdown construction reports

Add a final workflow stage:

```text
summarize-reference
```

It should write:

```text
reference-report.json
reference-report.md
```

The Markdown should be generated **from the JSON report**, not separately calculated.

That gives one source of truth.

Example:

```markdown
# THG Reference Model Construction Report

## Input

| Metric | Count |
|---|---:|
| Reactions | 13,417 |
| Metabolites | 8,362 |
| Genes | 3,625 |

## THGβ1

| Change | Count |
|---|---:|
| Reactions added | 3 |
| Reactions removed | 21 |
| Reactions modified | 147 |
| Balance corrections | 37 |

## THGβ2

| Change | Count |
|---|---:|
| Reactions added | 1,247 |
| GPRs changed | 103 |
| Unresolved locations | 28 |

## Human Database integration

| Change | Count |
|---|---:|
| New reactions | 491 |
| New metabolites | 113 |
| Overlapping reactions | 3,719 |
| Unresolved conflicts | 4 |

## Gapfill

| Change | Count |
|---|---:|
| Proposals | 137 |
| Reactions added | 42 |

## Overall

| Metric | Input | Final | Net |
|---|---:|---:|---:|
| Reactions | 13,417 | 15,179 | +1,762 |
| Metabolites | 8,362 | 9,223 | +861 |
```

The report must include artifact references for users needing exact details.

For example:

```text
Detailed reaction changes:
artifacts/.../beta1-change-ledger.jsonl

Semantic β1 → β2 changes:
artifacts/.../beta1-to-beta2-diff.json
```

---

# 10. Add a final `export-reference` stage

After reporting:

```text
summarize-reference
        ↓
export-reference
```

The export bundle should contain:

```text
thg-reference.json
thg-reference.xml

reference-report.json
reference-report.md

reference-provenance.json
reference-checksums.json
```

alongside references to the complete run artifacts.

The model should carry provenance identifying:

```text
original reference GEM
β1 artifact checksum
β2 artifact checksum
Human Database artifact checksum, if used
pre-gapfill checksum
post-gapfill checksum
configuration checksum
software/version information
```

### Validation status

Do not claim that construction implies validation.

The construction manifest/report should explicitly record:

```json
{
  "construction_status": "complete",
  "validation_status": "not-run"
}
```

or equivalent.

That allows:

```text
THG reference model
```

and:

```text
validated THG reference model
```

to remain distinct concepts.

Publication/release promotion can remain a separate concern if required.

---

# 11. Keep `validate` independent and reusable

Do not add final validation stages to the `reference` DAG.

The current validation configuration already supports an explicit input model/upstream handoff.

The desired workflow is:

```bash
thg-run reference configs/reference.json

thg-run validate configs/reference-validation.json
```

and later:

```bash
thg-run cell-specific configs/cell-specific.json

thg-run validate configs/cell-validation.json
```

Validation profiles can differ:

```text
reference-standard / final-standard
cell-specific-standard
```

while using the same validation engine.

Stage-local β1/β2/gapfill checks remain because they protect the integrity of the construction pipeline; they are not substitutes for the standalone quality report.

---

# 12. Preserve `final-thg` as compatibility only

Do not delete the existing workflow immediately.

Keep:

```text
workflow: final-thg
```

registered.

But implement it as a compatibility adapter around the reusable Human Database integration machinery.

Document it under something like:

```text
Compatibility / advanced workflows
```

rather than presenting it as the normal way to construct THG.

The existing documentation already says this route is a standalone compatibility path rather than the canonical post-gapfill reference workflow.

Do not rename existing stage IDs/artifacts unnecessarily if users may have existing runs depending on them.

---

# 13. Workflow-version / resume safety

Changing the `reference` DAG could affect resumable old runs.

Add an explicit workflow-definition version, for example:

```text
reference workflow version: 2
```

Include it in:

```text
manifest
workflow fingerprint
config snapshot/provenance
```

A run created by the older reference DAG should not silently resume into the new DAG.

Preferred behavior:

```text
old reference run + new workflow definition
    → clear incompatible-workflow-version error
    → user chooses a new output directory
```

This is much safer than attempting to splice Human Database stages into an old partial run.

---

# 14. Tests

Implement tests in four layers.

## Unit tests

Configuration:

```text
reference without Human Database → valid

reference with Human Database → valid

reference missing beta1 → invalid

reference missing beta2 → invalid

reference missing gapfill → invalid

integration config without human_database → invalid

invalid merge policy → invalid
```

Report summarization:

```text
semantic diff → correct counts

rename is not double-counted as add + remove

reaction modifications categorized correctly

overall net counts correct
```

## Workflow integration tests

No Human Database:

```text
input → β1 → β2 → gapfill → report → export
```

With Human Database:

```text
input → β1 → β2 → DB → integration → gapfill → report → export
```

Assert that:

```text
gapfill uses integrated model when enabled

gapfill uses β2 otherwise

β2 artifact remains unchanged

all major artifact checksums are recorded
```

## Construction-report tests

Use a tiny deterministic model where the expected result is known.

For example:

```text
β1 modifies one reaction
β2 adds two localized reactions
Human Database adds one reaction
gapfill adds one reaction
```

Expected report:

```text
β1:
changed reactions = 1

β2:
added reactions = 2

Human Database:
added reactions = 1

gapfill:
added reactions = 1

overall:
net reactions = +4
```

Test both the JSON data and important Markdown sections.

Avoid brittle full-file Markdown snapshots unless necessary.

## Validation interoperability tests

Run:

```text
reference
    ↓
validate
```

and:

```text
cell-specific
    ↓
validate
```

to prove that validation is genuinely independent of model construction.

---

# 15. Documentation changes

Add a dedicated:

```text
docs/workflows/reference.md
```

This should become the primary reference-construction documentation.

Update:

```text
docs/index.md
docs/workflows/index.md
docs/workflows/gapfill.md
docs/workflows/final-thg.md
docs/reference/cli.md
docs/reference/io-and-config.md
configs/README.md
README.md
```

The main docs should show:

```bash
# Construct reference model
thg-run reference configs/reference.json

# Validate reference model
thg-run validate configs/reference-validation.json

# Construct cell-specific model
thg-run cell-specific configs/cell-specific.json

# Validate cell-specific model
thg-run validate configs/cell-validation.json
```

The workflow diagram should become:

```text
Human reference GEM
      ↓
     β1
      ↓
     β2
      ↓
Human Database integration
      ↓
   Gapfill
      ↓
THG reference model
```

and separately:

```text
THG reference model ──→ validate

THG reference model
      ↓
cell-specific
      ↓
cell-specific model ──→ validate
```

That visually reinforces that **validation is reusable rather than part of construction**.

---

# 16. Suggested implementation sequence

### PR 1 — Extract Human Database integration

Refactor the existing merge/integration stages into reusable workflow code.

No user-facing behavior should change yet.

### PR 2 — Extend `reference`

Add optional Human Database reconstruction/integration to `reference` and redirect gapfill to the resulting model.

Add DAG/config integration tests.

### PR 3 — Common semantic change summarization

Add reusable utilities such as:

```python
summarize_model_diff(...)
summarize_model_counts(...)
summarize_merge_report(...)
```

Avoid workflow-specific formatting at this layer.

### PR 4 — Reference construction report

Add:

```text
summarize-reference
reference-report.json
reference-report.md
```

and aggregate β1, β2, Human Database and gapfill information.

### PR 5 — Reference export

Add a clear final construction artifact:

```text
thg-reference.json
thg-reference.xml
```

plus report, checksums and provenance.

### PR 6 — Docs and compatibility cleanup

Make `reference` the primary user-facing construction command.

Move `final-thg` documentation into the compatibility/advanced path.

Update examples, Quickstart and workflow diagrams.

---

# 17. Acceptance criteria

The implementation is complete when all of the following are true:

```text
✓ One command constructs the THG reference model:
  thg-run reference configs/reference.json

✓ β1 runs automatically.

✓ β2 consumes β1 automatically.

✓ Human Database reconstruction/integration can run automatically.

✓ Human Database integration can be omitted.

✓ Gapfill always runs after the last construction stage.

✓ Gapfill receives the Human-Database-integrated model when enabled.

✓ No upstream model is overwritten.

✓ A JSON reference construction report is produced.

✓ A human-readable Markdown construction report is produced.

✓ The report gives added/removed/changed reaction, metabolite and gene counts
  at every major boundary.

✓ Stage-specific metrics are included.

✓ Exact detailed changes remain available through the existing ledgers/diffs.

✓ Overall input→final changes are reported.

✓ Final model JSON and SBML are exported.

✓ Provenance and checksums connect every construction stage.

✓ `thg-run validate` is NOT part of the reference DAG.

✓ `thg-run validate` can validate the resulting reference model.

✓ The same validation workflow can validate a cell-specific model.

✓ Existing `final-thg` usage continues to work as a compatibility path.

✓ Old reference runs cannot silently resume under the changed DAG.

✓ CI, unit tests, integration tests, docs tests and `mkdocs build --strict`
  all pass.
```

## Final intended interface

The project should ultimately feel like this:

```bash
# Construct the general THG model
thg-run reference configs/reference.json

# Assess its quality
thg-run validate configs/reference-validation.json

# Derive a context-specific model
thg-run cell-specific configs/cell-specific.json

# Assess that model's quality
thg-run validate configs/cell-validation.json
```

That gives a clean separation of concerns:

```text
reference
    = how the model was constructed

reference-report
    = what changed during construction

validate
    = how good/valid the resulting model is

cell-specific
    = how a reference model was reduced/adapted
```

This fits the existing architecture well because β1, β2, gapfill, semantic diffs, change ledgers and Human Database merge reports already exist; the main implementation work is orchestration, common reporting, and clearer handoffs rather than rebuilding the scientific stages.