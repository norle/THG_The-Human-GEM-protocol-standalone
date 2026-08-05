# Legacy parity evidence

This directory defines the contracts and result format for comparing the
historical THG implementation with the maintained package. It is intentionally
separate from ordinary characterization tests: a maintained-only test is not
parity evidence.

## Current gate status

The maintained baseline is the current maintained repository commit. The committed legacy comparison
snapshot is `b474d80a34ef3bda9754bad3e24a21dc6cf3e57f`; it is available in an
adjacent checkout but is not vendored into this repository. That adjacent
working tree is dirty, so parity harnesses must extract files from the recorded
commit rather than import its working tree. A frozen published artifact is not
available. Four deterministic operation cases are available through the
separate pinned `legacy-parity` CI job; the ordinary package test command still
skips them when no legacy checkout is supplied. No capability is marked
`Parity-tested`.

When the legacy source is supplied, run each implementation in an isolated
subprocess or environment. Exchange only JSON, TSV, SBML, and normalized report
files. Do not import conflicting legacy and maintained modules into one Python
interpreter.

Set `THG_PARITY_RESULT_DIR` to retain the JSON result outside pytest's temporary
directory; otherwise the test still validates the result schema in its temporary
directory.

## Contract requirements

Every case must reference one file under [parity contracts](contracts/index.md), record its
fixture checksums and both source commits, and compare the declared result
fields. A case may record intentional differences, but an undocumented
difference is a failure.

Default parity fixtures must be offline and license-safe. Recorded service
responses must include their source, retrieval date, redaction status, and
SHA-256 checksum. Credentials and live network access are forbidden in the
default parity gate.

## Result schema

Each case writes JSON with these fields:

```json
{
  "contract_id": "reference.reaction-identification",
  "legacy_commit": "b474d80a34ef3bda9754bad3e24a21dc6cf3e57f",
  "maintained_commit": "<current maintained commit>",
  "fixture_checksums": {},
  "normalization_version": "reaction-row-v1",
  "matching_fields": [],
  "intentional_differences": [],
  "unexpected_differences": [],
  "pass": false
}
```

`pass` may be `true` only when the contract's pass/fail criteria are met on
both implementations. Model comparisons should use
[`model_signature`][thg_protocol.analysis.model_signature.model_signature] and
record serialized SBML checksums separately when byte stability matters.
