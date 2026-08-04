# Documentation UX Improvement Plan

## Review summary

The repository already has a substantial MkDocs site and generated API
reference. The main usability problem is that workflow documentation does not
link directly to the functions it describes.

The current site has these issues:

- API anchors exist, such as `thg_protocol.database.reconstruct_model`, but
  workflow pages display functions as plain inline code.
- Docstrings use `:func:` and `:mod:` syntax, which currently renders
  literally instead of becoming links.
- Generated API pages are large module dumps. The construction page renders
  42 generated sections and the workflows page renders 66.
- `show_source: true` and `inherited_members: true` contribute to API-page
  clutter in `mkdocs.yml`.
- The homepage, [`usage.md`](../usage.md), and
  [`workflow-overview.md`](../workflow-overview.md) provide overlapping task
  selection routes.
- The build identifies Markdown files outside the configured navigation,
  including the data/model reference, examples README, and implementation
  plans.
- The existing
  [`DOCUMENTATION_IMPLEMENTATION_PLAN.md`](DOCUMENTATION_IMPLEMENTATION_PLAN.md)
  claims that navigation is complete, although some pages are not included in
  the configured navigation.

The API reference does cover the maintained package modules, but the generated
symbols are not sufficiently connected to the user-facing guides.

## Goals

- Let readers click a documented function or class and jump directly to its
  API entry.
- Give users one clear route from the homepage to a workflow and then to its
  Python or CLI reference.
- Reduce duplication and visual noise in generated API pages.
- Make documentation coverage and link correctness testable in CI.

## Implementation plan

### 1. Establish a clearer information architecture

Organize the site around these audiences and tasks:

- **Start here:** installation, quickstart, and task chooser.
- **Concepts:** architecture, inputs, outputs, and model formats.
- **Workflows:** one page for each user-facing task.
- **API reference:** Python functions and classes.
- **CLI reference:** command usage and options.
- **Maintainer and archive material:** development, repository records, legacy
  documentation, and plans.

Make `usage.md` the canonical task chooser. The homepage and quickstart should
link to it for task selection. Keep `workflow-overview.md` as a conceptual
input-to-output map only; remove its competing task-selection call to action
and avoid repeating the task-guide table there.

### 2. Add clickable API references

Use MkDocstrings’ Autorefs support and standardize references in Markdown using
the fully qualified symbol as the target:

```markdown
[`reconstruct_model`][thg_protocol.database.reconstruct_model]
```

Update every workflow guide so its prose and its Python API section link
directly to the relevant functions or classes.

For example, the model reconstruction guide should link to:

- `reconstruct_model`
- `reconstruct_model_from_json`
- `reconstruct_model_from_pickle`
- `reconstruct_model_with_services`

Convert source docstrings from literal `:func:` and `:mod:` markup to the
supported Markdown cross-reference syntax. This includes references in
docstrings rendered by MkDocstrings, not only references written in workflow
Markdown.

### 3. Make the API reference easier to scan

Keep generated API documentation, but restructure it as follows:

- Add a short “Recommended entry points” section to every API page.
- Show each supported symbol in one canonical generated location. Its canonical
  owner is the module where it is defined; a package facade that re-exports it
  may link to that owner but must not render a second generated definition.
- Maintain an explicit API inventory with the canonical fully qualified symbol,
  owning API page, and whether it is a supported entry point or
  compatibility-only API. Generate `:::` member lists from that inventory (or
  keep equivalent, checked-in explicit member lists), rather than relying on
  each module's implicit member discovery.
- Avoid duplicate package and submodule listings, including lazy or explicit
  re-exports such as the mass-balance helpers available through
  `thg_protocol.model_build`.
- Disable inherited members unless they are explicitly part of the supported
  API.
- Consider disabling embedded source code by default to reduce page size.
- Keep full generated details below the curated entry-point sections.

### 4. Apply a consistent workflow-page template

Each workflow page should contain:

- What the workflow is for.
- When not to use it.
- Prerequisites and optional dependencies.
- Inputs.
- Outputs.
- A minimal Python example.
- A CLI example, where available.
- Clickable API links.
- Common errors.
- The next recommended workflow.

The existing pages have useful starting examples, but most are too short and
lack navigation between the guide and exact API symbols.

### 5. Make navigation coverage intentional

Publish `data-and-model-files.md` and `examples/README.md` in the appropriate
reference sections of `nav`. Treat all files below `docs/plans/` as internal
planning records: add `plans/**` to MkDocs `exclude_docs`, and remove or
replace links from published pages to those files. This policy includes this
plan and all implementation and refactoring plans.

The build should produce no unexplained navigation warnings.

### 6. Add documentation-specific validation

Create a checked-in workflow API inventory that maps every workflow Markdown
file to its primary fully qualified Python symbols and, where applicable, its
CLI command. Define the documented public API as the supported entries in the
canonical API inventory; module-level `__all__` values are input to that
inventory, not an implicit substitute for it. Compatibility-only exports must
be explicitly marked and excluded from the user-facing coverage requirement.

Extend `tests/docs` with checks that:

- Every API link named in the workflow API inventory resolves to its canonical
  generated HTML anchor.
- Every workflow page contains clickable references for all of its inventory
  symbols.
- Generated published HTML contains no unresolved `:func:` or `:mod:` markup.
- Internal links resolve.
- Every supported API-inventory entry is generated exactly once at its
  canonical location, and no compatibility-only entry is presented as a
  recommended entry point.

Run the link checks against a fresh temporary site built by
`mkdocs build --strict`; do not infer generated anchor names from source
Markdown. Keep `mkdocs build --strict` and the offline documentation examples
in CI.

### 7. Perform a UX review before publishing

Verify this path manually:

```text
Home -> Quickstart -> Workflow -> Function link -> API symbol
```

Check desktop and mobile navigation, API-page table of contents, search
results, and back-navigation from generated symbols.

## Recommended delivery order

The highest-value first implementation is:

1. Establish the navigation policy and canonical task chooser; publish the
   data/model and examples references, and exclude internal plans.
2. Create the canonical API and workflow API inventories.
3. Add Autorefs links to workflow pages and docstrings.
4. Reduce generated API clutter and add recommended entry points according to
   the canonical inventory.
5. Standardize workflow-page structure.
6. Add link and API-reference validation.
7. Perform the final site UX review.

This should solve the discoverability and structure problems without changing
the package’s public API.

## Acceptance criteria

- The workflow API inventory covers every workflow guide and identifies all of
  its primary functions and applicable CLI commands.
- A reader can click every primary function named in a workflow guide, and
  each click lands on that function's canonical generated API symbol.
- No published page contains unresolved `:func:` or `:mod:` markup.
- `data-and-model-files.md` and `examples/README.md` are navigable; all
  `docs/plans/**` files are explicitly excluded from publication.
- Every supported API-inventory entry is generated once at its canonical
  location; API pages have clear entry points and no avoidable duplicate
  listings.
- Documentation builds strictly and link validation passes in CI.
