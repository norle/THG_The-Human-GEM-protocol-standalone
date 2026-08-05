# Documentation Tone Review and Implementation Plan

## Review summary

The sales-oriented tone is concentrated in the documentation entry points. The
deeper protocol and API pages are already mostly formal and technical.

The main issues are:

- Direct-address headings such as “Choose your starting point”, “What you will
  produce”, and “Before you begin”.
- Conversational route labels such as “I have…”, “I want…”, “I need…”, and
  “Pick one”.
- Tutorial or promotional language such as “user journey” and “start here”.
- Repeated route-selection content across the homepage, README, workflow
  overview, and protocol overview.

Relevant files:

- [`docs/index.md`](../index.md)
- [`docs/workflow-overview.md`](../workflow-overview.md)
- [`docs/protocol/index.md`](../protocol/index.md)
- [`docs/usage.md`](../usage.md)
- [`README.md`](../../README.md)
- [`mkdocs.yml`](../../mkdocs.yml)

## Editorial direction

Use declarative, researcher-oriented wording that is formal and readable
without becoming obscure or excessively academic. Describe inputs, workflow
stages, outputs, requirements, and support boundaries directly. Retain direct
instructions inside executable procedures where they improve clarity, but avoid
framing the documentation as a sales funnel or personal journey.

Suggested terminology changes:

| Current wording | Suggested wording |
| --- | --- |
| Choose your starting point | Workflow entry points |
| What you will produce | Outputs |
| Before you begin | Requirements |
| I have an existing human GEM | Existing human GEM |
| I want to construct a network | Pathway/database records |
| I need only one operation | Individual operation |
| Pick one | Available workflows |
| User journey | Workflow example |
| Start here | Getting started |

## Implementation plan

### 1. Rewrite the public entry points

Update the homepage and README so they describe the package, workflow branches,
inputs, outputs, and support boundaries directly. Retain the route table, but
remove conversational framing and unnecessary recommendation-heavy language.

### 2. Rework the workflow overview

Make `workflow-overview.md` a neutral map from input types to workflow
branches. Replace “Choose your route” and “Pick one” with technical headings
such as “Workflow classification” and “Workflow branches”.

### 3. Align the protocol overview

Replace the question-based Mermaid label, “Where to start”, and similar wording
in `docs/protocol/index.md` with terminology based on inputs, stages, and
transitions. Preserve the distinction between the published scientific
protocol and the currently implemented package.

### 4. Normalize secondary wording

Review `docs/quickstart.md`, `docs/usage.md`, and the workflow pages for “you”,
“your”, “journey”, “recommended”, and similar phrasing. Retain direct
instructions inside executable procedures where useful, but use impersonal
language in explanatory sections.

### 5. Update navigation labels

Consider changing the following labels in `mkdocs.yml`:

- `Start here` → `Getting started`
- `Choose your route` → `Workflow overview`
- `Choose an operation` → `Operation reference`

### 6. Validate the rewrite

Run the strict documentation build and documentation tests:

```bash
mkdocs build --strict
pytest tests/docs
```

Then perform a final search for conversational or promotional phrases and
manually check the homepage-to-workflow navigation path.

## Acceptance criteria

- Entry-point pages use formal, declarative headings and descriptions.
- Route selection is described in terms of inputs and workflow branches.
- Technical distinctions and implementation-status claims remain unchanged.
- Internal links, navigation, Mermaid diagrams, and executable examples remain
  valid.
- `mkdocs build --strict` passes.
- `pytest tests/docs` passes.
