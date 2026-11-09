# Draft figures

Figure 1: `figure1_workflow.svg` (vector), `.pdf` and `.png`. Regenerate with
`python publication/scripts/plot_workflow.py` from the repository root in
`thg_standalone` (`MPLCONFIGDIR=/tmp/thg-matplotlib` avoids a read-only cache warning).
Source table: `publication/ws1/figure1_workflow.csv`.

The figure shows the registered reference workflow, its scientific gates and
cross-stage provenance. Optional/disabled stages are included in the stage
counts. Publication VerifyModel/quality/task evaluation is shown separately
from construction. This diagram is not evidence of successful execution.

Figures 2 and 3 remain pending measured numerical reliability, the gated
candidate, matched quality/coverage and task evaluation. No candidate improvement
or independent replay result is illustrated yet.
