# Legacy parity fixtures

The first reaction-identification fixture is available, but its parity test is
opt-in because the legacy checkout is not vendored into this repository. The
test extracts the legacy module from the recorded commit rather than using a
dirty legacy working tree. Recorded service fixtures must be license-safe,
redacted, checksum-pinned, and offline by default; do not place credentials or
live responses in this directory. The metabolite-identification hit fixture
uses a synthetic normalized PubChem response and follows the same extraction
rule. The GPR page-parser fixture likewise compares a recorded static HTML
fragment and does not exercise live BioCyc or KEGG access.
