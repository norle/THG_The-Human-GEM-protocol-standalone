# Contract: mass balance

- **Legacy:** `functions/equations_bm_gdb.py:atom10` from the recorded legacy
  commit.
- **Maintained:** `thg_protocol.model_build.mass_balance.atom10`.
- **Inputs/defaults:** the four offline formulas in
  `tests/fixtures/legacy_parity/mass-balance-atom10.json`; no solver or
  network access.
- **Result:** the ordered twelve-element C/H/O/N/P/S/K/Ca/Na/Fe/X/R vector.
- **Comparison:** both implementations must return the fixture's exact vector
  for every formula, in isolated subprocesses.
- **Scope boundary:** this contract deliberately excludes the historical
  substring ambiguity for formulas such as `Ca`, and does not establish parity
  for equation balancing, missing-atom insertion, or other mass-balance
  routines.
