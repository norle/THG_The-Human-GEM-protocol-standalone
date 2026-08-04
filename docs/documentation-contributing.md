# Contributing documentation

Documentation is built with MkDocs Material and must pass:

```bash
python -m pip install -e ".[docs,dev]"
mkdocs build --strict
pytest tests/docs
```

Keep tutorials deterministic. Use explicit input and output paths, small
fixtures, static service clients, and marked optional sections for solvers,
MEMOTE, plotting, or live services. Every tutorial should state its purpose,
prerequisites, Python and/or CLI usage, expected outputs, and troubleshooting.

Mermaid diagrams use `pymdownx.superfences` during the build and a Mermaid
runtime script loaded from jsDelivr. The build has no network dependency; the
browser fetches Mermaid when a reader opens the site. Keep diagrams readable
without hover-only detail and verify the generated Mermaid container after
changing the configuration.

When a documentation change advances a phase, update the internal
documentation records in the same change: phase status, date, owner or PR,
checklist, evidence, and follow-up work. API changes require an API page update; workflow changes
require a tested example; new artifacts require an ownership and publication
decision.

The plan is the source of truth for documentation progress. Historical pages
may be reorganized for discoverability, but their status must remain clear and
they must not be presented as supported package interfaces.

## Enable GitHub Pages

After these changes are available on the default branch, a repository
administrator must select **Settings → Pages → Build and deployment → Source →
GitHub Actions**. The `Documentation` workflow in
`.github/workflows/docs.yml` then validates the site and deploys only when a push targets the repository's
default branch. It uses the `github-pages` environment and the Pages/OIDC
permissions required by `actions/deploy-pages`.

Verify the deployment URL shown by the workflow before marking Phase 7 complete;
do not mark the phase complete based only on a successful local build.
