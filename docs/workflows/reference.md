# THG reference construction

Construct the reference model with one command:

```bash
thg-run reference configs/reference.json
```

The workflow runs THGβ1, THGβ2, an optional Human Database reconstruction and
merge, and required gapfill. It writes `thg-reference.json`, `thg-reference.xml`,
`reference-report.json`, `reference-report.md`, provenance, and checksums.

The `beta2` section must name an evidence source: `gene_locations`, an
`evidence_file`, or `live`/`snapshot` `location_sources`. It should carry the same
evidence settings as `configs/beta2.json`, and a test keeps the two shipped
configs in step. `gate-beta2` blocks the run when β2 exports no gene-location
evidence, because β2 would otherwise hand gapfill an unchanged β1 model.

Add `human_database` to the configuration to enable reconstruction and merge.
Its absence makes gapfill consume the immutable β2 export. When present, gapfill
consumes the integrated model. `reference.human_database_integration` accepts the
same merge policies as `final-thg`.

Construction is not validation. Validate any exported reference or cell-specific
model independently:

```bash
thg-run validate configs/reference-validation.json
thg-run validate configs/cell-validation.json
```

`final-thg` remains available as a compatibility workflow.
