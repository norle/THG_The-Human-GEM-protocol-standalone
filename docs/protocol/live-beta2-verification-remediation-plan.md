# Live β2 verification remediation plan

## Handoff objective

Make live β2 evidence collection scientifically trustworthy, then run a
separate live β2 workflow and verify that its snapshot can be replayed offline.

## Current evidence

- `.env` discovery works. The repository-root `.env` is found and both
  `BIOCYC_EMAIL` and `BIOCYC_PASSWORD` are present without printing values.
- The prior network-enabled handoff recorded **5 passed, 5 failed** for
  `tests/integration/test_legacy_gpr_online.py`. The current authenticated
  check reaches BioCyc, but the account receives `Subscription Required` for
  HumanCyc and MetaCyc EC pages.
- The archived mismatches therefore cannot yet be classified as biological
  source drift: current evidence uses the explicit KEGG fallback where
  available, and otherwise remains unresolved.
- The parser also captures enzyme-label snippets as genes. For EC `1.1.1.1`,
  the current result includes `ADH`, `ADH1B`, `ADH4`, and `ADH6`; `ADH` is an
  enzyme label, not a valid gene record from the page.
- The β1 input available at `runs/beta1` contains 12,877 reactions, 2,848
  genes, 5,125 reactions without GPRs, and 407 missing-GPR reactions with EC
  annotations. Do not launch a full live run until parser correctness is fixed.

## Local remediation evidence

- `tests/fixtures/biocyc/ec-enzyme-and-gene.html` records an enzyme tooltip and
  visible gene records; `parse_gene_pairs()` ignores the tooltip and preserves
  deterministic gene pairs.
- Live GPR candidates now record source, source version, retrieval time, parser
  version, identifiers, and warnings. Valid model GPRs are retained and live
  conflicts are recorded rather than selected.
- `tests/integration/test_beta2_live_snapshot_replay.py` is the bounded smoke
  gate. It verifies unique-EC lookup, separate gene/reaction evidence,
  explicit CCO edge traversal, complete snapshot export, zero-call snapshot
  replay, and matching semantic GPR/location/proposal/ID artifacts.
- The ten-case comparison is recorded in
  [`live-beta2-gpr-comparison.md`](live-beta2-gpr-comparison.md). Its live
  HumanCyc/MetaCyc cells remain account-access limited; the full β2 workflow
  must not run until the source-access gate is rerun with an entitled account.

## Progress status — 2026-08-14

Completed:

- BioCyc’s current `/ajax-login` flow is implemented and covered by a static
  client test. Credentials are never written to logs or artifacts.
- Authenticated BioCyc access was verified to reach the service; the account
  is accepted but is not entitled to the HumanCyc/MetaCyc EC pages.
- KEGG fallback results and access warnings are now recorded in each GPR
  candidate’s provenance.
- The bounded smoke/replay test passes, including one lookup per unique EC,
  model-GPR conflict preservation, explicit CCO edge traversal, rejected
  unsupported locations, zero-call snapshot replay, and matching semantic
  artifacts.

Pending:

- Rerun the ten archived EC cases with HumanCyc/MetaCyc access, then classify
  each mismatch as source drift or parser defect in the comparison report.
- Run the actual network-backed smoke workflow and only then the full β2 run
  in a fresh output directory. The current static-client smoke test is not
  evidence that those external-service gates have passed.

## Work sequence

### 1. Isolate and fix BioCyc GPR parsing

Inspect the current HTML structure in `src/thg_protocol/gpr/lookup.py` and
`src/thg_protocol/services/biocyc.py`.

Change parsing so it extracts only actual gene anchors/records, not
`data-tippy-content` from enzyme records. Preserve:

- gene symbol;
- BioCyc gene identifier;
- deterministic ordering;
- HumanCyc → MetaCyc → KEGG fallback behavior.

Add a recorded HTML fixture containing both enzyme and gene blocks. Assert that
enzyme labels are excluded and real gene anchors are retained.

### 2. Separate source drift from parser defects

Run the corrected parser against the ten archived EC cases and write a compact
comparison report containing:

- EC number;
- archived expected genes;
- current HumanCyc genes;
- current MetaCyc genes, if used;
- KEGG fallback status;
- parser warnings.

Do not silently rewrite the archived expected fixture. Decide per case whether
the difference is expected BioCyc data drift or a parser defect.

Acceptance gate: no false-positive enzyme labels; every remaining mismatch is
explained by recorded source/version evidence.

### 3. Define the live GPR policy for drift

Keep archived fixtures for regression history, but make live β2 provenance
explicit. Each candidate must record:

- source (`biocyc`, `metacyc`, or `kegg`);
- retrieval timestamp and service/version metadata when available;
- EC number;
- gene symbols and identifiers;
- fallback/warning state;
- parser version.

A live result that differs from the archived fixture may be accepted as current
evidence only when it is structurally valid and provenance-complete. An empty,
ambiguous, or malformed result remains unresolved and must not expand a
reaction.

### 4. Add a bounded live β2 smoke workflow

Do not begin with the 12,877-reaction model. Create a temporary or tracked
small β1 fixture containing:

- one valid model GPR;
- one missing GPR with a known EC;
- one gene-location lookup;
- one BioCyc CCO reaction-location record.

Run β2 with:

```json
{
  "evidence_mode": "live",
  "gpr_policy": "model-then-ec",
  "location_policy": "provided-then-evidence",
  "compartments": {"c": "cytosol", "m": "mitochondria"}
}
```

Use a fresh output directory. Never overwrite `runs/beta1` or an existing
release candidate.

Verify:

- valid model GPR wins over conflicting live evidence;
- missing GPR gets one candidate lookup per unique EC;
- gene and reaction location evidence remain separate;
- CCO child terms resolve only through explicit graph edges;
- unsupported or conflicting evidence produces unresolved/rejected records;
- the run exports all evidence artifacts and a complete snapshot.

### 5. Verify offline replay

Run the smoke workflow once in `live` mode, then configure a second fresh run
with `evidence_mode: "snapshot"` and the generated
`beta2-evidence-snapshot.jsonl`.

Acceptance gate: snapshot mode makes zero HTTP calls and produces semantically
identical:

- selected GPRs;
- compartment-resolution evidence;
- expansion proposals;
- deterministic IDs.

### 6. Run the full live workflow only after the smoke gate

Use a fresh run directory and preserve the generated evidence snapshot. Record
the exact configuration, software version, service metadata, and unresolved
report. Compare the live result with the β1 baseline before considering any
β2 expansion scientifically usable.

## Commands for the next agent

```bash
# Confirm dotenv discovery without printing secrets
python -c 'import os, thg_protocol; from thg_protocol.config import load_environment_files; print(load_environment_files()); print(bool(os.getenv("BIOCYC_EMAIL")), bool(os.getenv("BIOCYC_PASSWORD")))'

# Reproduce the current live regression state
pytest -q tests/integration/test_legacy_gpr_online.py

# Keep offline checks green while iterating
pytest -q tests/unit/test_gpr_lookup_api.py tests/unit/test_beta2_evidence.py
pytest -q tests/integration/test_beta2_live_snapshot_replay.py
ruff check src tests
```

## Do not do

- Do not update expected fixtures merely to make the online test green.
- Do not run the full live β2 workflow before parser and smoke-workflow gates
  pass.
- Do not print, commit, or include `.env` contents in artifacts.
- Do not treat BioCyc/KEGG/Ensembl/UniProt locations as legal compartments;
  `beta2.compartments` remains authoritative.
