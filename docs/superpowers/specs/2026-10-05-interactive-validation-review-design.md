# Interactive validation review

Date: 2026-10-05
Status: approved design, not yet implemented

## Goal

Make the validation HTML report the single place where a curator reviews model
problems and decides on fixes, and give that review a path back into the model.
Today the report is read-only, fix proposals exist only in a separate
conservation review page, and decisions are hand-written JSONL.

Success means: a curator opens `validation-report.html`, approves, rejects,
replaces or defers each proposed fix in the page, exports `decisions.jsonl`, runs
one command that applies the decisions and writes a fixed model plus a new report,
and repeats until the checks pass.

## Decisions taken

- Blocked reactions never fail validation.
- One review page: the validation report. The conservation workflow's separate
  review page is removed.
- Decisions are exported from the static page and applied by a new CLI
  subcommand (no local server).
- Fixes are offered only where an existing or newly specified rule produces one;
  other checks get navigation only.

## 1. Blocked reactions are warnings

`flux-consistency` is removed from the blocking set of the `post-gapfill`,
`final-standard` and `release-full` profiles in `src/thg_protocol/validation.py`.
The check keeps running and appears as a warning. The profile descriptions in
`PROFILES` of `src/thg_protocol/validation_report.py` no longer mention blocked
reactions as release-blocking.

## 2. Proposals in the validation result

`validate_model` adds a top-level `proposals` list to its result. Each entry is
`Proposal.to_dict()` (from `workflow/proposals.py`) plus a `checks` field listing
the check IDs that produced it. Proposal IDs are content hashes, so an identical
fix produced by two checks is stored once with both check IDs.

Proposals are generated only for checks that failed. The blame LP (`localize`)
runs only when stoichiometric consistency fails and identified unconserved
metabolites.

Per check:

| Check | Proposals |
|---|---|
| `stoichiometric-consistency` | `localize` then `propose_fixes` (existing rules: exclude pseudo-reaction, restore input/reference stoichiometry, integer rounding, cofactor pair, inferred formula, unresolved removal). The localization's blamed rows are also stored in the check details for display. |
| `formula-disagreement` | New rule. For each disagreeing metabolite group, alternatives: the reference model's formula and charge (when a reference is given), and the value held by the majority of compartments (when one exists). Emitted as `set-formula` and/or `set-charge` proposals for each metabolite whose value would change, grouped as alternatives. Each alternative's metadata records how many reactions of the affected metabolites are element- and charge-balanced before and after. |
| `fractional-coefficients` | `integer_candidates` per reaction, one `set-stoichiometry` alternative each. A reaction with no balanced candidate gets no proposal and is shown as "no automatic fix". |
| `mass-balance`, `charge-balance` | The per-reaction rules that need no LP (restore reference stoichiometry, integer rounding, cofactor pair) run on each unbalanced reaction. |
| `unusual-protons` | Restore reference stoichiometry when the reference reaction differs. The reference equation is stored in the details for display. |

The shared per-reaction rules are factored out of `propose_fixes` so they can be
called with a reaction instead of a localization row; `propose_fixes` keeps its
current behaviour.

The result also carries an `index` with only the reactions and metabolites any
check mentions: for reactions, the equation (IDs and names), subsystem and
bounds; for metabolites, name, formula, charge, compartment and reaction IDs.

No schema version bump: `proposals` and `index` are additive, and a report
without them renders as today.

## 3. New operation: `set-charge`

`apply_conservation_fixes` accepts `set-charge` on a metabolite; the value must be
an integer. Formula and charge fixes on one metabolite are different operations
but the same object; the one-fix-per-object rule is keyed by
`(object_type, object_id, field)` so a metabolite can receive one formula fix and
one charge fix from the same alternative.

## 4. The report page

Rendered by `validation_report.py`, still one self-contained file with inline CSS
and dependency-free inline JS.

- **Fix sections.** Under each failing check that has proposals, a list of
  proposal cards grouped by target object. Each card shows the rule, before and
  after (equation or formula/charge), element and charge residual before and
  after, evidence, confidence and the other checks it is listed under.
  Alternatives for one object are radio buttons across all checks, so only one
  can be approved. Actions: approve, reject, defer, replace. Replace opens an
  editable field pre-filled with the proposed value.
- **Stoichiometric consistency** also shows blamed reactions split into "with a
  chemical flag" and "without a flag", and unresolved reactions as "manual
  curation".
- **Navigation.** Metabolite and reaction IDs in any check link to an inline
  panel built from `index`: a metabolite's reactions with equations, a reaction's
  equation and subsystem. Mislabelled metabolites show both metabolites side by
  side. Blocked reactions can be filtered by subsystem.
- **Decision bar.** Sticky; counts approved, rejected, deferred, replaced and
  undecided; buttons to export `decisions.jsonl` (one `Decision.to_dict()` per
  decided proposal) and to import a decisions file.
- **Autosave.** Decisions are kept in `localStorage` under the model checksum.
  All storage access is wrapped in try/catch; the page works without it.

## 5. Applying decisions

New subcommand in `src/thg_protocol/workflow/cli.py`:

```
thg-run apply-decisions <validation-report.json> <decisions.jsonl> --model <path> -o <fixed.xml>
```

It is a sibling of `validate` because `validate` takes a positional model path.

1. Refuse when the model's sha256 differs from the report's `model_checksum`,
   printing both.
2. Read proposals from the report and decisions with `read_decisions`; apply with
   `apply_conservation_fixes`. Decisions referencing unknown proposals, invalid
   replacements or two fixes on one object are errors; nothing is written.
3. Append ledger entries with `ChangeLedger` next to the output model
   (`<fixed>.ledger.jsonl`).
4. Write the fixed model.
5. Re-run `validate_model` with the report's profile (and its reference model and
   exclusions when recorded), write `validation-report.json`/`.html` next to the
   fixed model, and print the checks whose status changed.

## 6. Conservation workflow

The `conservation-propose` stage stops writing `review.html` and `review.md`;
`src/thg_protocol/conservation_report.py` is deleted. Its apply and recheck stages
are unchanged and accept decisions exported from the validation report, since
proposal IDs match for the same model.

## 7. Testing

- Unit: formula-disagreement proposals (reference and majority alternatives,
  no proposal when neither exists); `set-charge` apply and its validation;
  per-reaction rules on unbalanced, fractional and proton reactions; proposal
  deduplication across checks.
- Unit: no profile fails on blocked reactions alone.
- Rendering: a report with proposals contains the radio groups, decision bar and
  cross-listings; a report without proposals renders the existing layout.
- End to end on a toy model: `apply-decisions` refuses a checksum mismatch,
  applies an approved fix, writes the ledger and a new report.
- Manual: open a generated report in a browser and check export, import and
  autosave.

## Out of scope

Automatic fixes for mislabelled metabolites; a live server; changes to how
reactions are blamed.
