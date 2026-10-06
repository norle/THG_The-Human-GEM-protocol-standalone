"""Dependency-free human-readable rendering of canonical validation JSON."""

# ruff: noqa: E501 - embedded HTML/CSS is clearer when kept intact.

from __future__ import annotations

import itertools
import json
import re
from collections import Counter
from collections.abc import Mapping
from html import escape

#: Each check's title and concise description.
CHECKS: dict[str, tuple[str, str]] = {
    "obligatory-loops": (
        "Obligatory infeasible loops",
        "Compacts linear pathways and proportional parallel reactions on a copy, "
        "excluding blocked, boundary and objective reactions. Lists original "
        "reactions in cycles that cancel completely. This does not find every "
        "possible loop and does not alter the model.",
    ),
    "reference-integrity": (
        "Reaction metabolites exist",
        "Checks that all reaction metabolites exist in the model.",
    ),
    "identifier-uniqueness": (
        "Unique identifiers",
        "Checks for duplicate reaction, metabolite or gene IDs.",
    ),
    "gpr": (
        "Gene rules are valid",
        "Checks that gene rules parse and reference only genes in the model.",
    ),
    "mass-balance": (
        "Mass balance",
        "Compares element counts across internal reactions. Pool, biomass and pseudo-reactions are reported separately without failing the check; boundary reactions and those missing formulas are skipped.",
    ),
    "charge-balance": (
        "Charge balance",
        "Compares total charge across internal reactions. Pool, biomass and pseudo-reactions are reported separately without failing the check; boundary reactions and those missing charges are skipped.",
    ),
    "fractional-coefficients": (
        "Fractional coefficients",
        "Lists non-integer coefficients in internal reactions, excluding biomass, pools and other pseudo-reactions.",
    ),
    "formula-disagreement": (
        "Formula disagreements",
        "Compares metabolite formulas and charges across compartments and against the reference model.",
    ),
    "annotation-conflict": (
        "Mislabelled metabolites",
        "Flags shared names with conflicting formulas (excluding hydrogen) or KEGG IDs, and reference metabolites renamed to another compound's name.",
    ),
    "unusual-protons": (
        "Unusual proton counts",
        "Flags proton coefficients above the limit, excluding those unchanged from the reference model.",
    ),
    "dead-end-topology": (
        "Dead-end metabolites",
        "Lists metabolites that are only produced or only consumed.",
    ),
    "unconserved-metabolites": (
        "Metabolites never produced or consumed",
        "Lists metabolites no reaction can produce, and metabolites no reaction can consume.",
    ),
    "stoichiometric-consistency": (
        "Stoichiometric consistency",
        "Uses MEMOTE to test whether all internal reactions conserve a shared set of positive metabolite masses, without formulas. Reports metabolites with no conserved mass assignment.",
    ),
    "workflow-specific-invariants": (
        "Workflow invariants",
        "Checks stage-specific invariants; not configured if none were supplied.",
    ),
    "ledger-to-diff-consistency": (
        "Ledger matches model changes",
        "Compares the decision ledger with actual model changes; not configured if no ledger was supplied.",
    ),
    "flux-consistency": (
        "Blocked reactions",
        "Uses flux variability analysis to find reactions unable to carry flux under current bounds.",
    ),
    "objective-feasibility": (
        "Objective is feasible",
        "Optimises the objective under current bounds and checks for an optimal solution.",
    ),
}

FAMILIES: dict[str, tuple[str, str]] = {
    "structural": ("Structure", "Is the model a well-formed object?"),
    "chemical": (
        "Chemistry",
        "Do formulas, charges and coefficients make chemical sense?",
    ),
    "topology": ("Network topology", "Can every metabolite be both made and used?"),
    "stoichiometry": ("Stoichiometry", "Does the network conserve mass as a whole?"),
    "workflow": ("Workflow", "Do the stage's own records agree with the model?"),
    "solver": ("Simulation", "Does the model behave under optimisation?"),
}

PROFILES: dict[str, str] = {
    "structural-fast": "Structural and diagnostic checks. Loop detection uses a solver by default. Only structural errors block the release.",
    "beta1-standard": "All checks with a solver. Structural errors and an infeasible objective block the release.",
    "beta2-standard": "All checks with a solver. Structural errors and an infeasible objective block the release.",
    "post-gapfill": "All checks with a solver, after gap-filling. Structural errors and an infeasible objective block the release.",
    "final-standard": "All checks with a solver, for the finished reference model. Structural errors and an infeasible objective block the release.",
    "cell-specific-standard": "All checks with a solver, for a context-specific model. Structural errors and an infeasible objective block the release.",
    "release-full": "All checks with a solver. Structural errors, mass or charge imbalance and an infeasible objective block the release.",
}

STATUS_LABELS = {
    "passed": "Passed",
    "failed": "Failed",
    "warning": "Warning",
    "not-evaluated": "Not evaluated",
    "infrastructure-error": "Error",
    "error": "Error",
}

METRICS = {
    "reactions": ("Reactions", ""),
    "metabolites": ("Metabolites", ""),
    "genes": ("Genes", ""),
    "compartments": ("Compartments", ""),
    "blocked_reactions": ("Blocked reactions", "cannot carry flux"),
    "dead_end_metabolites": ("Dead-end metabolites", "only made or only used"),
    "network_components": ("Network components", "disconnected subnetworks"),
    "largest_component_fraction": ("Largest component", "share of the network"),
}

#: Headings for detail keys whose generated label would be unclear.
KEY_LABELS = {
    "blamed_with_flag": "Blamed reactions with a chemical flag (start here)",
    "blamed_without_flag": "Blamed reactions without a flag (often an innocent member of a loop)",
}

#: Lists longer than this get a filter box.
_FILTER_AT = 12
#: Identifier-to-status maps longer than this are shown as counts only.
_STATUS_TABLE_LIMIT = 200


def _validation(report: Mapping[str, object]) -> Mapping[str, object]:
    after = report.get("after", {})
    value = report.get(
        "validation",
        after.get("validation", report) if isinstance(after, Mapping) else report,
    )
    return value if isinstance(value, Mapping) else {}


def _display(value: object) -> str:
    if isinstance(value, list):
        return f"{len(value):,} items"
    if isinstance(value, Mapping):
        return f"{len(value):,} entries"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _passed(report: Mapping[str, object]) -> bool:
    if report.get("status") in {"passed", "failed"}:
        return report["status"] == "passed"
    tasks = report.get("tasks", {})
    return _validation(report).get("passed") is True and not (
        isinstance(tasks, Mapping) and tasks.get("passed") is False
    )


def _status(check: Mapping[str, object]) -> str:
    status = str(check.get("status", "not-evaluated"))
    if status == "failed" and not check.get("release_blocking"):
        return "warning"
    return status


def _label(key: object) -> str:
    text = re.sub(r"[_-]+", " ", str(key)).strip()
    return text[:1].upper() + text[1:]


def _count(value: object) -> int | None:
    return len(value) if isinstance(value, (list, Mapping)) else None


def _anchor(text: object) -> str:
    return "check-" + re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


class _Ids:
    """Unique element IDs for filter boxes."""

    def __init__(self) -> None:
        self._next = itertools.count(1)

    def __call__(self) -> str:
        return f"list-{next(self._next)}"


def _filter(target: str, count: int, noun: str = "items") -> str:
    if count <= _FILTER_AT:
        return ""
    return (
        f'<input class="filter" type="search" data-target="{target}" '
        f'placeholder="Filter {count:,} {escape(noun)}" aria-label="Filter {escape(noun)}">'
    )


def _inline(value: object) -> str:
    """Compact rendering of a value inside a table cell."""
    if value is None:
        return '<span class="muted">none</span>'
    if isinstance(value, (bool, int, float)):
        return escape(_display(value))
    if isinstance(value, str):
        if " --> " in value or " <=> " in value or " <-- " in value:
            return f'<span class="equation">{escape(value)}</span>'
        return escape(value)
    if isinstance(value, list):
        if not value:
            return '<span class="muted">none</span>'
        return ", ".join(_inline(item) for item in value)
    if isinstance(value, Mapping):
        if not value:
            return '<span class="muted">none</span>'
        if all(isinstance(item, Mapping) for item in value.values()):
            return "".join(
                f'<span class="pair"><code>{escape(str(key))}</code> '
                + ", ".join(
                    f"{escape(_label(k))} {_inline(v)}" for k, v in item.items()
                )
                + "</span>"
                for key, item in value.items()
            )
        return " ".join(
            f'<span class="pair"><code>{escape(str(key))}</code> {_inline(item)}</span>'
            for key, item in value.items()
        )
    return escape(json.dumps(value, default=str))


def _id_list(values: list[object], ids: _Ids, noun: str = "identifiers") -> str:
    target = ids()
    items = "".join(f"<li>{escape(str(item))}</li>" for item in values)
    return f'{_filter(target, len(values), noun)}<ul class="ids" id="{target}">{items}</ul>'


def _table(
    header: list[str], rows: list[list[str]], ids: _Ids, noun: str = "rows"
) -> str:
    target = ids()
    head = "".join(f"<th>{escape(item)}</th>" for item in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    return (
        f"{_filter(target, len(rows), noun)}"
        f'<div class="table-wrap"><table id="{target}"><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def _value(value: object, ids: _Ids) -> str:
    """Render one evidence value as a list, table or definition list."""
    if isinstance(value, list):
        if not value:
            return '<p class="muted">None found.</p>'
        if all(isinstance(item, list) and len(item) == 1 for item in value):
            value = [item[0] for item in value]
        if all(not isinstance(item, (list, Mapping)) for item in value):
            return _id_list(value, ids)
        if all(isinstance(item, Mapping) for item in value):
            keys = list(dict.fromkeys(key for item in value for key in item))
            keys.sort(key=lambda key: (key not in {"id", "reaction", "name"}, 0))
            return _table(
                [_label(key) for key in keys],
                [[_inline(item.get(key)) for key in keys] for item in value],
                ids,
            )
        return f'<p class="cell">{_inline(value)}</p>'
    if isinstance(value, Mapping):
        if not value:
            return '<p class="muted">None found.</p>'
        if all(isinstance(item, str) for item in value.values()):
            counts = Counter(value.values())
            summary = _table(
                ["Status", "Count"],
                [
                    [escape(_label(key)), f"{count:,}"]
                    for key, count in counts.most_common()
                ],
                ids,
            )
            if len(value) > _STATUS_TABLE_LIMIT:
                return (
                    summary
                    + f'<p class="note">The {len(value):,} individual entries are in the JSON report.</p>'
                )
            return summary + (
                f"<details><summary>Show all {len(value):,}</summary>"
                + _table(
                    ["Identifier", "Status"],
                    [
                        [f"<code>{escape(str(k))}</code>", escape(_label(v))]
                        for k, v in value.items()
                    ],
                    ids,
                )
                + "</details>"
            )
        if all(isinstance(item, Mapping) for item in value.values()):
            keys = list(dict.fromkeys(key for item in value.values() for key in item))
            # Put long equations last so the short columns stay readable.
            keys.sort(key=lambda key: key == "equation")
            return _table(
                ["Identifier", *(_label(key) for key in keys)],
                [
                    [f"<code>{escape(str(name))}</code>"]
                    + [_inline(item.get(key)) for key in keys]
                    for name, item in value.items()
                ],
                ids,
            )
        return _fields(value, ids)
    return f"<p>{_inline(value)}</p>"


def _fields(details: Mapping[str, object], ids: _Ids) -> str:
    """Scalars as a definition list, then one block per collection."""
    scalars = {
        key: value
        for key, value in details.items()
        if not isinstance(value, (list, Mapping))
    }
    blocks = {key: value for key, value in details.items() if key not in scalars}
    html = ""
    if scalars:
        html += (
            '<dl class="fields">'
            + "".join(
                f"<dt>{escape(_label(key))}</dt><dd>{_inline(value)}</dd>"
                for key, value in scalars.items()
            )
            + "</dl>"
        )
    for key, value in blocks.items():
        count = _count(value)
        suffix = f' <span class="count">{count:,}</span>' if count else ""
        html += (
            f'<div class="block"><h4>{escape(KEY_LABELS.get(key, _label(key)))}{suffix}</h4>'
            f"{_value(value, ids)}</div>"
        )
    return html


#: Why a reaction is unbalanced by design, by ``conservation_exclusions`` rule.
PSEUDO_RULES = {
    "sbo-biomass": "Biomass reaction",
    "memote-biomass": "Biomass reaction",
    "pseudo-subsystem": "Pool or artificial reaction",
    "pseudo-name": "Pool or pseudo-reaction (by name)",
    "pool-metabolite": "Makes or uses a pool metabolite",
    "model-note": "Excluded by an accepted fix",
    "input-model": "Excluded in the reference model",
    "configuration": "Excluded in the configuration",
}
_ATOM = re.compile(r"([A-Z][a-z]*)(\d*)")


def _lookup(validation: Mapping[str, object], kind: str) -> Mapping[str, object]:
    """Reactions or metabolites from the report's index, by ID."""
    index = validation.get("index")
    value = index.get(kind) if isinstance(index, Mapping) else None
    return value if isinstance(value, Mapping) else {}


def _block(title: str, count: int | None, body: str, note: str = "") -> str:
    suffix = f' <span class="count">{count:,}</span>' if count is not None else ""
    note = f'<p class="muted">{note}</p>' if note else ""
    return f'<div class="block"><h4>{escape(title)}{suffix}</h4>{note}{body}</div>'


def _equation(reaction: object) -> str:
    if not isinstance(reaction, Mapping):
        return '<span class="muted">–</span>'
    return (
        f'<span class="equation clamp" title="{escape(str(reaction.get("equation", "")))}">'
        f"{escape(str(reaction.get('equation_names', '')))}</span>"
    )


def _imbalance(value: object) -> str:
    if isinstance(value, Mapping):
        return ", ".join(f"{key} {float(count):+g}" for key, count in value.items())
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):+g}"
    return "–"


def _balance_evidence(
    details: Mapping[str, object], ids: _Ids, validation: Mapping[str, object]
) -> str:
    """Real and by-design unbalanced reactions, then the status counts."""
    reactions = _lookup(validation, "reactions")
    imbalance = details.get("imbalance")
    imbalance = imbalance if isinstance(imbalance, Mapping) else {}
    real = details.get("unbalanced")
    real = [str(item) for item in real] if isinstance(real, list) else []
    design = details.get("unbalanced_by_design")
    design = design if isinstance(design, Mapping) else {}

    def subsystem(reaction_id: str) -> str:
        item = reactions.get(reaction_id)
        return (
            escape(str(item.get("subsystem") or ""))
            if isinstance(item, Mapping)
            else ""
        )

    html = _block(
        "Metabolic reactions",
        len(real),
        _table(
            ["Reaction", "Imbalance", "Subsystem", "Equation"],
            [
                [
                    f"<code>{escape(item)}</code>",
                    f'<span class="nowrap">{escape(_imbalance(imbalance.get(item)))}</span>',
                    subsystem(item),
                    _equation(reactions.get(item)),
                ]
                for item in real
            ],
            ids,
            "reactions",
        )
        if real
        else '<p class="muted">None found.</p>',
        "Ordinary reactions that should balance. These fail the check and need fixing. "
        "Imbalance is products minus reactants; long equations are cut short, select the reaction for the full one.",
    )
    if design:
        html += _block(
            "Pool and pseudo-reactions",
            len(design),
            _table(
                ["Reaction", "Kind", "Imbalance", "Equation"],
                [
                    [
                        f"<code>{escape(str(item))}</code>",
                        escape(PSEUDO_RULES.get(str(rule), _label(rule))),
                        f'<span class="nowrap">{escape(_imbalance(imbalance.get(item)))}</span>',
                        _equation(reactions.get(item)),
                    ]
                    for item, rule in design.items()
                ],
                ids,
                "reactions",
            ),
            "Biomass, pool and artificial reactions combine many compounds into one "
            "pseudo-metabolite, so they are not expected to balance. They are listed "
            "for reference and do not fail the check.",
        )
    rest = {
        key: value
        for key, value in details.items()
        if key not in {"unbalanced", "unbalanced_by_design", "imbalance"}
    }
    return html + (_fields(rest, ids) if rest else "")


def _atoms(formula: object) -> Counter:
    counts: Counter = Counter()
    for element, number in _ATOM.findall(str(formula or "")):
        counts[element] += int(number) if number else 1
    return counts


def _difference(value: object, base: object, field: str) -> str:
    """How ``value`` differs from ``base``: element counts or charge."""
    if field == "charge":
        try:
            return f"{int(value) - int(base):+d}"
        except (TypeError, ValueError):
            return "–"
    new, old = _atoms(value), _atoms(base)
    order = sorted(set(new) | set(old), key=lambda key: (key not in {"C", "H"}, key))
    return (
        ", ".join(
            f"{key} {new[key] - old[key]:+d}" for key in order if new[key] != old[key]
        )
        or "same elements"
    )


def _metabolite_ref(metabolite_id: str, text: str, metabolites: Mapping) -> str:
    """A metabolite shown as ``text`` that opens its details when indexed."""
    if metabolite_id in metabolites:
        return (
            f'<button type="button" class="xref" data-xref="{escape(metabolite_id)}" '
            f'title="{escape(metabolite_id)}">{escape(text)}</button>'
        )
    return f'<code title="{escape(metabolite_id)}">{escape(text)}</code>'


def _formula_evidence(
    details: Mapping[str, object], ids: _Ids, validation: Mapping[str, object]
) -> str:
    """One row per metabolite and field: each value, where it occurs, the change."""
    metabolites = _lookup(validation, "metabolites")
    names = validation.get("compartments")
    names = names.get("names", {}) if isinstance(names, Mapping) else {}

    def name(metabolite_id: str) -> str:
        item = metabolites.get(metabolite_id)
        return str(item.get("name") or "") if isinstance(item, Mapping) else ""

    def compartment(metabolite_id: str, base: str) -> str:
        item = metabolites.get(metabolite_id)
        if isinstance(item, Mapping) and item.get("compartment"):
            return str(item["compartment"])
        return metabolite_id.removeprefix(base).lstrip("_") or metabolite_id

    html = ""
    across = details.get("across_compartments")
    if isinstance(across, Mapping) and across:
        rows = []
        for base, group in across.items():
            if not isinstance(group, Mapping):
                continue
            members = group.get("metabolites")
            members = members if isinstance(members, Mapping) else {}
            for field in group.get("differs", []):
                values: dict[object, list[str]] = {}
                for member, item in members.items():
                    value = item.get(field) if isinstance(item, Mapping) else None
                    if value is not None and value != "":
                        key = (
                            tuple(sorted(_atoms(value).items()))
                            if field == "formula"
                            else value
                        )
                        values.setdefault(key, []).append(str(member))
                ranked = sorted(
                    values.values(),
                    key=lambda where: (-len(where), str(members[min(where)][field])),
                )
                common = members[min(ranked[0])][field] if ranked else ""
                cells = []
                for where in ranked:
                    value = members[min(where)][field]
                    places = " ".join(
                        _metabolite_ref(
                            member,
                            str(
                                names.get(
                                    compartment(member, str(base)),
                                    compartment(member, str(base)),
                                )
                            ),
                            metabolites,
                        )
                        for member in sorted(where)
                    )
                    change = (
                        ""
                        if value == common
                        else f' <span class="diff">{escape(_difference(value, common, field))}</span>'
                    )
                    cells.append(
                        f'<div class="variant"><code>{escape(str(value))}</code>{change}'
                        f'<span class="where">{places}</span></div>'
                    )
                first = next(iter(sorted(members)), str(base))
                rows.append(
                    [
                        f"<code>{escape(str(base))}</code>",
                        escape(name(first)),
                        escape(field.capitalize()),
                        "".join(cells),
                    ]
                )
        html += _block(
            "Across compartments",
            len(across),
            _table(
                ["Metabolite", "Name", "Field", "Values and compartments"],
                rows,
                ids,
                "metabolites",
            ),
            "Each value is followed by how it differs from the most common one and by "
            "the compartments that use it. Select a compartment to see that metabolite.",
        )
    against = details.get("against_reference")
    if isinstance(against, Mapping) and against:
        rows = []
        for metabolite_id, item in against.items():
            if not isinstance(item, Mapping):
                continue
            model = item.get("model") if isinstance(item.get("model"), Mapping) else {}
            reference = (
                item.get("reference")
                if isinstance(item.get("reference"), Mapping)
                else {}
            )
            for field in item.get("differs", []):
                rows.append(
                    [
                        f"<code>{escape(str(metabolite_id))}</code>",
                        escape(name(str(metabolite_id))),
                        escape(field.capitalize()),
                        f"<code>{escape(str(model.get(field)))}</code>",
                        f"<code>{escape(str(reference.get(field)))}</code>",
                        f'<span class="diff">{escape(_difference(model.get(field), reference.get(field), field))}</span>',
                    ]
                )
        html += _block(
            f"Against the reference model {details.get('reference') or ''}".strip(),
            len(against),
            _table(
                [
                    "Metabolite",
                    "Name",
                    "Field",
                    "This model",
                    "Reference",
                    "Difference",
                ],
                rows,
                ids,
                "metabolites",
            ),
        )
    return html or '<p class="muted">None found.</p>'


def _compartment_label(key: str, names: Mapping[str, object]) -> str:
    return " + ".join(str(names.get(part, part)) for part in key.split("+"))


def _compartment_split(
    groups: Mapping[str, object],
    totals: Mapping[str, object],
    names: Mapping[str, object],
    ids: _Ids,
    noun: str,
    kind: str,
) -> str:
    """Counts per compartment against its size, then the IDs per compartment."""
    groups = {
        str(key): [str(item) for item in value]
        for key, value in groups.items()
        if isinstance(value, list)
    }
    order = sorted(groups, key=lambda key: ("+" in key, -len(groups[key]), key))
    rows = []
    for key in order:
        total = totals.get(key)
        count = len(groups[key])
        rows.append(
            [
                f"{escape(_compartment_label(key, names))} <code>{escape(key)}</code>",
                f"{count:,}",
                f"{total:,}" if isinstance(total, int) else "–",
                f"{count / total:.0%}" if isinstance(total, int) and total else "–",
            ]
        )
    count = sum(len(value) for value in groups.values())
    total = sum(value for value in totals.values() if isinstance(value, int))
    rows.append(
        [
            "<strong>All compartments</strong>",
            f"<strong>{count:,}</strong>",
            f"{total:,}" if total else "–",
            f"{count / total:.0%}" if total else "–",
        ]
    )
    table = _table(
        ["Compartment", noun.capitalize(), f"All {kind} there", "Share"], rows, ids
    )
    lists = "".join(
        f"<details><summary>{escape(_compartment_label(key, names))} <code>{escape(key)}</code> "
        f'<span class="count">{len(groups[key]):,}</span></summary>'
        f"{_id_list(groups[key], ids, noun)}</details>"
        for key in order
    )
    return table + lists


def _compartment_evidence(
    details: Mapping[str, object], ids: _Ids, validation: Mapping[str, object]
) -> str:
    """Topology and blocked-reaction evidence split by compartment."""
    split = details.get("by_compartment")
    if not isinstance(split, Mapping):
        return _fields(details, ids)
    summary = validation.get("compartments")
    summary = summary if isinstance(summary, Mapping) else {}
    names = summary.get("names") if isinstance(summary.get("names"), Mapping) else {}
    reactions = "blocked" in details
    kind = "reactions" if reactions else "metabolites"
    totals = summary.get(kind) if isinstance(summary.get(kind), Mapping) else {}
    note = (
        "Reactions are grouped by the compartments of their metabolites; "
        "a reaction spanning several (a transport) is listed under all of them joined by +."
        if reactions
        else ""
    )
    if all(isinstance(value, list) for value in split.values()):
        noun = "blocked reactions" if reactions else "dead ends"
        return _block(
            "By compartment",
            None,
            _compartment_split(split, totals, names, ids, noun, kind),
            note,
        )
    return "".join(
        _block(
            _label(key),
            sum(len(item) for item in value.values() if isinstance(item, list)),
            _compartment_split(value, totals, names, ids, "metabolites", kind),
        )
        for key, value in split.items()
        if isinstance(value, Mapping)
    )


#: Checks with their own evidence layout.
EVIDENCE = {
    "mass-balance": _balance_evidence,
    "charge-balance": _balance_evidence,
    "formula-disagreement": _formula_evidence,
    "dead-end-topology": _compartment_evidence,
    "unconserved-metabolites": _compartment_evidence,
    "flux-consistency": _compartment_evidence,
}
#: Checks older reports hold that are no longer shown.
_RETIRED = {"blocked-reaction-singletons"}


def _headline(check: Mapping[str, object]) -> str:
    """One sentence summarising a check's result."""
    details = check.get("details", {})
    details = details if isinstance(details, Mapping) else {}
    check_id = check.get("id")
    status = str(check.get("status"))
    if status == "infrastructure-error":
        return f"Could not run: {details.get('message') or details.get('error') or 'unknown error'}"
    if status == "not-evaluated":
        return str(details.get("reason") or "Not evaluated in this run.")
    if details.get("status") == "not-configured":
        return "Not configured for this stage."
    if check_id in {"mass-balance", "charge-balance"}:
        statuses = details.get("statuses", {})
        statuses = statuses if isinstance(statuses, Mapping) else {}
        counts = Counter(statuses.values())
        evaluated = counts["balanced"] + counts["unbalanced"]
        unevaluable = sum(v for k, v in counts.items() if k.startswith("not-evaluable"))
        text = f"{counts['unbalanced']:,} of {evaluated:,} evaluated reactions are unbalanced"
        if counts["unbalanced-by-design"]:
            text += f"; {counts['unbalanced-by-design']:,} pool or pseudo-reactions are unbalanced by design"
        if unevaluable:
            text += f"; {unevaluable:,} could not be evaluated"
        return text + "."
    if check_id == "objective-feasibility":
        objective = details.get("objective")
        value = (
            f", objective value {objective:.6g}" if isinstance(objective, float) else ""
        )
        return f"Solver status {details.get('status', 'unknown')}{value}."
    if check_id == "stoichiometric-consistency":
        unconserved = _count(details.get("unconserved"))
        if details.get("consistent") is True:
            return "The network is stoichiometrically consistent."
        if unconserved:
            return f"{unconserved:,} metabolites cannot be assigned a conserved mass."
        return "The network is not stoichiometrically consistent."
    if check_id == "unconserved-metabolites":
        return (
            f"{_count(details.get('not-produced')) or 0:,} never produced, "
            f"{_count(details.get('not-consumed')) or 0:,} never consumed."
        )
    if check.get("passed") is True:
        return "No problems found."
    nouns = {
        "dangling_metabolites": "dangling metabolite references",
        "metabolites": "metabolites",
        "blocked": "blocked reactions",
        "sets": "blocked reactions",
        "reactions": "reactions",
        "across_compartments": "metabolites differ across compartments",
        "against_reference": "metabolites differ from the reference",
        "within_model": "names shared by different compounds",
        "renamed_from_reference": "renamed reference metabolites",
        "invalid": "invalid gene rules",
        "missing": "missing genes",
    }
    parts = [
        f"{_count(details[key]):,} {noun}"
        for key, noun in nouns.items()
        if _count(details.get(key))
    ]
    if isinstance(details.get("duplicates"), Mapping):
        parts += [
            f"{len(items):,} duplicate {kind} IDs"
            for kind, items in details["duplicates"].items()
            if items
        ]
    return (", ".join(parts) + ".") if parts else "Problems found; see evidence."


def _pill(status: str) -> str:
    return f'<span class="pill {escape(status)}">{escape(STATUS_LABELS.get(status, _label(status)))}</span>'


#: Plain-language names of the fix rules in ``analysis.conservation``.
RULES = {
    "exclude-pseudo-reaction": "Exclude from conservation checks (biomass, pool or lumped reaction)",
    "restore-input-stoichiometry": "Restore the reference model's stoichiometry",
    "integer-stoichiometry": "Solve coefficients to balance elements and charge with integer replacements",
    "stoichiometry-balance": "Solve the coefficients to balance elements and charge",
    "cofactor-pair": "Balance coefficients with missing small molecules or cofactors",
    "redox-cofactor": "Add the missing redox cofactor",
    "metabolite-charge": "Change this metabolite's charge by one",
    "infer-formula": "Set the one formula that balances all its reactions",
    "unresolved": "Remove the reaction (no rule fits; curate by hand)",
}


def _fix_target(proposal: Mapping[str, object]) -> str:
    """Radio-group key: one approved fix per reaction, or per metabolite field.

    Mirrors ``analysis.conservation.fix_target``, which enforces it on apply.
    """
    object_type = str(proposal.get("object_type"))
    operation = str(proposal.get("operation"))
    field = (
        operation.removeprefix("set-")
        if object_type == "metabolite" and operation in {"set-formula", "set-charge"}
        else ""
    )
    return f"{object_type}|{proposal.get('object_id')}|{field}"


def _proposals(validation: Mapping[str, object]) -> list[Mapping[str, object]]:
    value = validation.get("proposals")
    if not isinstance(value, list):
        return []
    return [
        item
        for item in value
        if isinstance(item, Mapping) and isinstance(item.get("proposal_id"), str)
    ]


def _residual(summary: object) -> str:
    """Element and charge balance of a reaction summary, in a few words."""
    if not isinstance(summary, Mapping):
        return ""
    parts = []
    elements = summary.get("elements")
    if isinstance(elements, Mapping):
        if elements.get("missing_formula"):
            parts.append(
                "no formula: " + ", ".join(map(str, elements["missing_formula"]))
            )
        elif elements.get("residual"):
            parts.append(
                ", ".join(f"{k} {v:+g}" for k, v in elements["residual"].items())
            )
        else:
            parts.append("elements balanced")
    charge = summary.get("charge")
    if isinstance(charge, Mapping):
        if charge.get("missing_charge"):
            parts.append("no charge: " + ", ".join(map(str, charge["missing_charge"])))
        elif charge.get("residual"):
            parts.append(f"charge {charge['residual']:+g}")
        else:
            parts.append("charge balanced")
    return "; ".join(parts)


def _rule(proposal: Mapping[str, object]) -> str:
    metadata = proposal.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    policy = str(proposal.get("policy", ""))
    if metadata.get("rule") == "formula-disagreement":
        field = str(metadata.get("field", "formula"))
        sources = metadata.get("sources") or []
        where = " and ".join(
            "the reference model" if item == "reference" else "most compartments"
            for item in sources
        )
        return f"Use the {field} {where or 'suggested'} {'has' if len(sources) < 2 else 'agree on'}"
    text = RULES.get(policy, _label(policy))
    if metadata.get("cofactor"):
        text += f": {metadata['cofactor']}"
    return text


def _alternative(proposal: Mapping[str, object], current_check: str) -> str:
    """The body of one radio option: what changes and what it does to balance."""
    metadata = proposal.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    operation = proposal.get("operation")
    lines = []
    if operation == "set-stoichiometry":
        reaction = metadata.get("reaction")
        reaction = reaction if isinstance(reaction, Mapping) else {}
        after = reaction.get("after")
        if isinstance(after, Mapping):
            lines.append(
                f'<span class="equation" title="{escape(str(after.get("equation_ids", "")))}">'
                f"{escape(str(after.get('equation_names', '')))}</span>"
            )
        before, after_text = _residual(reaction.get("before")), _residual(after)
        if before or after_text:
            lines.append(
                f'<span class="balance">{escape(before)} <span aria-hidden="true">→</span>'
                f'<span class="sr"> becomes </span> {escape(after_text)}</span>'
            )
    elif operation in {"set-formula", "set-charge"}:
        before = proposal.get("before")
        lines.append(
            f"<span><code>{escape(str(before if before not in (None, '') else '(none)'))}</code>"
            f' <span aria-hidden="true">→</span><span class="sr"> becomes </span> '
            f"<code>{escape(str(proposal.get('after')))}</code></span>"
        )
        balance = metadata.get("balance")
        if isinstance(balance, Mapping):
            old, new = balance.get("before", {}), balance.get("after", {})
            lines.append(
                f'<span class="balance">Balanced reactions of this metabolite: '
                f"{old.get('balanced', 0)} of {old.get('total', 0)} → "
                f"{new.get('balanced', 0)} of {new.get('total', 0)}</span>"
            )
        reactions = metadata.get("reactions")
        if isinstance(reactions, list) and reactions:
            clean = sum(
                1
                for item in reactions
                if isinstance(item, Mapping) and not item.get("flags")
            )
            lines.append(
                f'<span class="balance">Balances {clean} of {len(reactions)} reactions of this metabolite</span>'
            )
    others = [
        CHECKS.get(str(item), (_label(item),))[0]
        for item in proposal.get("checks", [])
        if item != current_check
    ]
    note = escape(str(proposal.get("reason", "")))
    if others:
        note += f" · also suggested by {escape(', '.join(others))}"
    lines.append(f'<span class="muted">{note}</span>')
    confidence = str(proposal.get("confidence", ""))
    return (
        f'<span class="alt-head"><span class="alt-rule">{escape(_rule(proposal))}</span>'
        f'<span class="conf {escape(confidence)}">{escape(confidence)} confidence</span></span>'
        + "".join(lines)
    )


def _fix_legend(proposal: Mapping[str, object]) -> str:
    object_type = str(proposal.get("object_type"))
    object_id = str(proposal.get("object_id"))
    metadata = proposal.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    detail = ""
    if object_type == "reaction":
        reaction = metadata.get("reaction")
        before = reaction.get("before") if isinstance(reaction, Mapping) else None
        if isinstance(before, Mapping):
            detail = (
                f'<span class="equation" title="{escape(str(before.get("equation_ids", "")))}">'
                f"{escape(str(before.get('equation_names', '')))}</span>"
            )
    else:
        described = metadata.get("metabolite")
        name = described.get("name") if isinstance(described, Mapping) else ""
        field = _fix_target(proposal).rsplit("|", 1)[1]
        detail = escape(" · ".join(item for item in (name, field) if item))
    return (
        f'<legend><span class="fix-kind">{escape(object_type.capitalize())}</span> '
        f"<code>{escape(object_id)}</code> {detail}</legend>"
    )


def _fixes(
    check_id: str,
    groups: Mapping[str, list[Mapping[str, object]]],
    ids: _Ids,
) -> str:
    """Decision controls for every fix target a check has proposals for."""
    mine = [
        key
        for key, items in groups.items()
        if any(check_id in item.get("checks", []) for item in items)
    ]
    if not mine:
        return ""
    target = ids()
    fieldsets = []
    for key in mine:
        items = groups[key]
        name = ids()
        options = "".join(
            f'<label class="alt"><input type="radio" name="{name}" value="{escape(str(item["proposal_id"]))}">'
            f'<span class="alt-body"><span class="alt-verb">Accept{" this option" if len(items) > 1 else ""}</span>{_alternative(item, check_id)}</span></label>'
            for item in items
        )
        fieldsets.append(
            f'<fieldset class="fix" data-group="{escape(key)}">{_fix_legend(items[0])}'
            f"{options}"
            f'<div class="fix-other">'
            f'<label><input type="radio" name="{name}" value="reject"> Reject{" all options" if len(items) > 1 else ""}</label>'
            f'<input type="radio" name="{name}" value="" checked hidden>'
            f'<button type="button" class="fix-clear" hidden>Clear choice</button></div>'
            f'<div class="fix-edit" hidden><label>Value to apply (JSON or plain text; change it to replace the suggestion)'
            f'<textarea rows="2" spellcheck="false"></textarea></label><p class="fix-error" role="alert"></p></div>'
            "</fieldset>"
        )
    count = len(mine)
    return (
        f'<div class="block fixes-block"><h4>Suggested fixes <span class="count">{count:,}</span></h4>'
        '<p class="muted">Accept one suggested fix per reaction or metabolite, or reject it; '
        "anything you leave alone stays unchanged. "
        "Your choices are kept in this browser; export them from the bar at the bottom and apply them with "
        "<code>thg-run apply-decisions</code>.</p>"
        f'{_filter(target, count, "fixes")}<div class="fixes" id="{target}">{"".join(fieldsets)}</div></div>'
    )


def _check_card(
    check: Mapping[str, object],
    ids: _Ids,
    groups: Mapping[str, list[Mapping[str, object]]] | None = None,
    validation: Mapping[str, object] | None = None,
) -> str:
    check_id = str(check.get("id", ""))
    title, what = CHECKS.get(check_id, (_label(check_id), ""))
    status = _status(check)
    blocking = bool(check.get("release_blocking"))
    details = check.get("details", {})
    details = details if isinstance(details, Mapping) else {"value": details}
    evidence = {key: value for key, value in details.items() if key != "passed"}
    fixes = _fixes(check_id, groups or {}, ids)
    is_open = (
        " open"
        if fixes or status in {"failed", "infrastructure-error", "error"}
        else ""
    )
    render = EVIDENCE.get(check_id)
    if not evidence:
        body = '<p class="muted">No evidence recorded.</p>'
    elif render and status not in {"not-evaluated", "infrastructure-error", "error"}:
        body = render(evidence, ids, validation or {})
    else:
        body = _fields(evidence, ids)
    explain = f'<p class="explain">{escape(what)}</p>' if what else ""
    return f"""<details class="check {escape(status)}" id="{_anchor(check_id)}"{is_open}>
<summary><span class="mark" aria-hidden="true"></span><span class="check-title">{escape(title)}</span>{_pill(status)}<span class="policy">{"Blocks release" if blocking else "Diagnostic"}</span><span class="headline">{escape(_headline(check))}</span></summary>
<div class="check-body">{explain}{fixes}<div class="evidence">{body}</div>
<p class="check-id">Check ID <code>{escape(check_id)}</code></p></div></details>"""


def _verdict(
    report: Mapping[str, object], checks: list[Mapping[str, object]]
) -> tuple[str, str]:
    passed = _passed(report)
    blocking = [item for item in checks if item.get("release_blocking")]
    failures = [item for item in blocking if item.get("passed") is not True]
    warnings = [item for item in checks if _status(item) == "warning"]

    def names(items: list[Mapping[str, object]]) -> str:
        return ", ".join(
            f'<a href="#{_anchor(item.get("id"))}">{escape(CHECKS.get(str(item.get("id")), (_label(item.get("id")),))[0])}</a>'
            for item in items
        )

    sentences = []
    if failures:
        sentences.append(
            f"{len(failures)} of {len(blocking)} release-blocking checks did not pass: {names(failures)}."
        )
    elif blocking:
        sentences.append(f"All {len(blocking)} release-blocking checks passed.")
    for key, label in (
        ("tasks", "Metabolic tasks"),
        ("gimme_objectives", "GIMME objectives"),
    ):
        value = report.get(key)
        if isinstance(value, Mapping) and value.get("passed") is False:
            sentences.append(
                f'<a href="#{key.replace("_", "-")}">{label}</a> did not pass.'
            )
    samples = report.get("gimme_samples")
    if isinstance(samples, Mapping) and samples.get("passed") is False:
        sentences.append('<a href="#gimme-samples">GIMME samples</a> did not pass.')
    elif isinstance(samples, list) and any(
        isinstance(item, Mapping) and item.get("status") != "passed" for item in samples
    ):
        sentences.append(
            'Some <a href="#gimme-samples">GIMME samples</a> did not pass.'
        )
    if warnings:
        sentences.append(
            f"{len(warnings)} diagnostic {'check raises a warning' if len(warnings) == 1 else 'checks raise warnings'}; "
            "these are reported for review and do not block the release."
        )
    if not sentences:
        sentences.append(
            "Passed." if passed else "Failed; see the sections below for the cause."
        )
    return ("PASSED" if passed else "FAILED"), " ".join(sentences)


def _metric_cards(report: Mapping[str, object]) -> str:
    after = report.get("after", {})
    after = after if isinstance(after, Mapping) else {}
    counts = after.get("counts")
    values = {**after, **(counts if isinstance(counts, Mapping) else {})}
    cards = []
    for key, (label, note) in METRICS.items():
        if key not in values:
            continue
        value = values[key]
        if key == "largest_component_fraction" and isinstance(value, float):
            shown = f"{value:.1%}"
        elif isinstance(value, (list, Mapping)):
            shown = f"{len(value):,}"
        else:
            shown = _display(value)
        cards.append(
            f'<div class="metric"><span class="metric-value">{escape(shown)}</span>'
            f'<span class="metric-label">{escape(label)}</span>'
            + (f'<span class="metric-note">{escape(note)}</span>' if note else "")
            + "</div>"
        )
    return f'<div class="metrics">{"".join(cards)}</div>' if cards else ""


def _reduction(report: Mapping[str, object], ids: _Ids) -> str:
    if "source_reaction_count" not in report:
        return ""
    fraction = report.get("fraction_retained")
    rows = [
        ["Reactions in source model", _display(report.get("source_reaction_count"))],
        ["Reactions retained", _display(report.get("retained_reaction_count"))],
        ["Reactions removed", _display(report.get("removed_reaction_count"))],
        [
            "Fraction retained",
            f"{fraction:.1%}" if isinstance(fraction, float) else _display(fraction),
        ],
    ]
    html = (
        '<section id="reduction"><h2>Context reduction</h2>'
        '<p class="lead-small">How much of the source model the context-specific model keeps.</p>'
        + _table(["Measure", "Value"], [[escape(a), escape(b)] for a, b in rows], ids)
    )
    for key, title, text in (
        (
            "unknown_genes",
            "Unknown genes",
            "Genes in the model with no expression data.",
        ),
        (
            "uncertain_reactions",
            "Uncertain reactions",
            "Reactions whose activity depends on unknown genes.",
        ),
    ):
        value = report.get(key)
        if isinstance(value, list):
            html += (
                f'<div class="block"><h4>{title} <span class="count">{len(value):,}</span></h4>'
                f'<p class="muted">{text}</p>{_value(value, ids)}</div>'
            )
    exchanges = report.get("exchange_configuration")
    if exchanges:
        html += f'<div class="block"><h4>Exchange configuration</h4>{_value(exchanges, ids)}</div>'
    return html + "</section>"


def _changes(report: Mapping[str, object], ids: _Ids) -> str:
    deltas = report.get("metric_deltas")
    if not isinstance(deltas, Mapping) or not deltas:
        return ""
    before = report.get("before", {})
    before = before if isinstance(before, Mapping) else {}
    after = report.get("after", {})
    after = after if isinstance(after, Mapping) else {}

    def amount(value: object) -> str:
        if isinstance(value, (list, Mapping)):
            return f"{len(value):,}"
        return _display(value) if value is not None else "–"

    rows = []
    for key, value in deltas.items():
        if isinstance(value, Mapping):
            old, new, delta = (
                value.get("before"),
                value.get("after"),
                value.get("delta"),
            )
        else:
            old, new, delta = before.get(key), after.get(key), value
        if isinstance(delta, (int, float)) and not isinstance(delta, bool):
            sign = "zero" if delta == 0 else ("up" if delta > 0 else "down")
            shown = "no change" if delta == 0 else f"{delta:+,.4g}"
        else:
            sign, shown = "zero", _display(delta)
        rows.append(
            [
                escape(METRICS.get(key, (_label(key),))[0]),
                escape(amount(old)),
                escape(amount(new)),
                f'<span class="delta {sign}">{escape(shown)}</span>',
            ]
        )
    return (
        '<section id="changes"><h2>Changes from the input model</h2>'
        '<p class="lead-small">Network size and quality before and after this stage. '
        "An increase in blocked reactions or dead-end metabolites is also listed under warnings.</p>"
        + _table(["Measure", "Before", "After", "Change"], rows, ids)
        + "</section>"
    )


def _tasks(report: Mapping[str, object], ids: _Ids) -> str:
    tasks = report.get("tasks")
    intro = (
        '<section id="tasks"><h2>Metabolic tasks</h2><p class="lead-small">'
        "Each task asks whether the model can (or must not be able to) perform a known metabolic function, "
        "such as making ATP from glucose.</p>"
    )
    if not isinstance(tasks, Mapping) or tasks.get("status") == "not-requested":
        return (
            intro
            + '<p class="muted">No task suite was requested for this run.</p></section>'
        )
    counts = tasks.get("counts")
    html = intro
    if isinstance(counts, Mapping):
        html += (
            '<p class="tally">'
            + " ".join(
                f'<span class="pill {"passed" if key == "passed" else "failed" if count else "not-evaluated"}">'
                f"{count:,} {escape(key)}</span>"
                for key, count in counts.items()
            )
            + "</p>"
        )
    rows = tasks.get("tasks")
    if isinstance(rows, list) and rows:
        html += _table(
            ["Task", "Group", "Expected", "Result", "Objective", "Diagnostics"],
            [
                [
                    f"<code>{escape(str(item.get('id')))}</code>",
                    _inline(item.get("group")),
                    _inline(item.get("expected_outcome")),
                    _pill(
                        "passed"
                        if item.get("passed")
                        else str(item.get("status", "failed"))
                    ),
                    _inline(item.get("objective_value")),
                    _inline(item.get("diagnostics") or None),
                ]
                for item in rows
                if isinstance(item, Mapping)
            ],
            ids,
            "tasks",
        )
    extra = {
        key: value
        for key, value in tasks.items()
        if key not in {"tasks", "counts", "passed", "status"}
    }
    if extra:
        html += _fields(extra, ids)
    return html + "</section>"


def _gimme(report: Mapping[str, object], ids: _Ids) -> str:
    html = ""
    samples = report.get("gimme_samples")
    if samples is not None and samples != []:
        html += (
            '<section id="gimme-samples"><h2>GIMME samples</h2>'
            '<p class="lead-small">The activity status GIMME assigned to each expression sample.</p>'
            + _value(samples, ids)
            + "</section>"
        )
    objectives = report.get("gimme_objectives")
    if isinstance(objectives, Mapping) and objectives.get("status") != "not-requested":
        html += (
            '<section id="gimme-objectives"><h2>GIMME objectives</h2>'
            '<p class="lead-small">Whether the reduced model still reaches each objective GIMME was required to keep.</p>'
            + _fields(objectives, ids)
            + "</section>"
        )
    return html


def _memote(report: Mapping[str, object], ids: _Ids) -> str:
    memote = report.get("memote")
    intro = (
        '<section id="memote"><h2>MEMOTE</h2><p class="lead-small">'
        "MEMOTE is the community test suite for genome-scale models; its own report is linked below when it was run.</p>"
    )
    if not isinstance(memote, Mapping) or memote.get("status") == "not-requested":
        return (
            intro + '<p class="muted">MEMOTE was not run for this report.</p></section>'
        )
    fields: dict[str, object] = {
        "Status": memote.get("status"),
        "Version": memote.get("version"),
    }
    result = memote.get("result")
    score = result.get("score") if isinstance(result, Mapping) else None
    if isinstance(score, Mapping):
        score = score.get("total_score")
    if isinstance(score, (int, float)):
        fields["Total score"] = f"{score:.1%}"
    if "threshold" in memote:
        fields["Threshold"] = memote.get("threshold")
        fields["Threshold met"] = memote.get("threshold_passed", "not available")
    html = intro + _fields(fields, ids)
    artifacts = memote.get("artifacts")
    if isinstance(artifacts, Mapping) and artifacts:
        html += _table(
            ["File", "Path", "Size"],
            [
                [
                    escape(str(name)),
                    f"<code>{escape(str(item.get('path', '')))}</code>",
                    escape(f"{item.get('size', 0):,} bytes"),
                ]
                for name, item in artifacts.items()
                if isinstance(item, Mapping)
            ],
            ids,
        )
    for key in ("stderr", "report_stderr"):
        if memote.get(key):
            html += (
                f"<details><summary>{escape(_label(key))}</summary>"
                f'<pre class="log">{escape(str(memote[key]))}</pre></details>'
            )
    return html + "</section>"


def _solver(report: Mapping[str, object], validation: Mapping[str, object]) -> str:
    solver = report.get("solver", validation.get("solver", {}))
    solver = solver if isinstance(solver, Mapping) else {}
    if not solver.get("requested"):
        body = '<p class="muted">This profile does not use a solver, so simulation checks were skipped.</p>'
    else:
        configuration = solver.get("configuration")
        configuration = configuration if isinstance(configuration, Mapping) else {}
        body = (
            '<dl class="fields">'
            + "".join(
                f"<dt>{escape(_label(key))}</dt><dd>{_inline(value)}</dd>"
                for key, value in configuration.items()
                if not str(value).startswith("<")
            )
            + "</dl>"
        )
    return f'<section id="solver"><h2>Solver</h2>{body}</section>'


def _provenance(report: Mapping[str, object]) -> str:
    rows = []
    for key, label in (
        ("model_id", "Model"),
        ("model_checksum", "Model SHA-256"),
        ("source_model_checksum", "Input model SHA-256"),
        ("result_model_checksum", "Result model SHA-256"),
        ("validation_profile", "Validation profile"),
        ("validation_profile_version", "Profile version"),
        ("schema", "Report schema"),
        ("schema_version", "Schema version"),
    ):
        if report.get(key) is not None:
            value = report[key]
            cell = (
                f"<code>{escape(str(value))}</code>"
                if "checksum" in key
                else _inline(value)
            )
            rows.append(f"<dt>{label}</dt><dd>{cell}</dd>")
    software = report.get("software")
    if isinstance(software, Mapping):
        rows.extend(
            f"<dt>{escape(str(name))}</dt><dd>{escape(str(version))}</dd>"
            for name, version in software.items()
        )
    return (
        '<section id="provenance"><h2>Provenance</h2>'
        '<p class="lead-small">What was validated and with which software. The complete results are in the JSON report next to this file.</p>'
        f'<dl class="fields">{"".join(rows)}</dl></section>'
    )


def _json_script(element_id: str, value: object) -> str:
    text = json.dumps(value, sort_keys=True, default=str).replace("<", "\\u003c")
    return f'<script type="application/json" id="{element_id}">{text}</script>'


def _review_data(
    report: Mapping[str, object],
    validation: Mapping[str, object],
    groups: Mapping[str, list[Mapping[str, object]]],
) -> str:
    """Embedded data, decision bar and lookup panel for the page's scripts."""
    html = ""
    index = validation.get("index")
    if isinstance(index, Mapping) and (
        index.get("reactions") or index.get("metabolites")
    ):
        html += _json_script("thg-index", index) + (
            '<aside id="xref-panel" class="xref-panel" hidden aria-label="Identifier details">'
            '<button type="button" class="xref-close" aria-label="Close">Close</button>'
            '<div id="xref-body"></div></aside>'
        )
    if groups:
        checksum = (
            report.get("model_checksum")
            or report.get("result_model_checksum")
            or report.get("model_id")
            or "unknown"
        )
        html += _json_script(
            "thg-review",
            {
                "key": f"thg-review:{checksum}",
                "groups": {
                    key: [
                        {"id": item["proposal_id"], "after": item.get("after")}
                        for item in items
                    ]
                    for key, items in groups.items()
                },
            },
        ) + (
            '<div class="decision-bar" role="region" aria-label="Fix decisions">'
            '<span id="decision-count" aria-live="polite"></span>'
            '<button type="button" id="decisions-export">Export decisions.jsonl</button>'
            '<label class="button">Import decisions<input type="file" id="decisions-import" accept=".jsonl,.json,.txt" hidden></label>'
            '<button type="button" id="decisions-clear">Clear</button>'
            '<span id="decision-message" class="muted" aria-live="polite"></span></div>'
        )
    return html


_FIX_CSS = """
.xref-id{cursor:pointer;border-bottom:1px dotted currentColor}
button.xref{all:unset;cursor:pointer;color:var(--link);border-bottom:1px dotted currentColor;font-family:var(--mono)}
button.xref:focus-visible,.xref-id:focus-visible{outline:2px solid var(--link);outline-offset:2px}
.xref-panel{position:fixed;top:0;right:0;bottom:0;width:min(460px,100vw);background:var(--paper);border-left:1px solid var(--line);box-shadow:-8px 0 24px rgba(0,0,0,.14);padding:18px 20px 90px;overflow:auto;z-index:30}
.xref-panel h3{font:600 1.1rem/1.3 var(--serif);margin:4px 0 2px;overflow-wrap:anywhere}.xref-panel .xref-close{float:right}
.xref-panel dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;margin:12px 0}.xref-panel dt{color:var(--muted)}.xref-panel dd{margin:0;overflow-wrap:anywhere}
.xref-panel ul{list-style:none;padding:0;margin:6px 0 0}.xref-panel li{padding:6px 0;border-top:1px solid var(--line);font-size:13px}
.fixes-block h4{color:var(--ink)}
.fixes{max-height:640px;overflow:auto;display:flex;flex-direction:column;gap:10px;padding:2px 4px 2px 0}
fieldset.fix{border:1px solid var(--line);border-left:4px solid var(--line);border-radius:8px;padding:8px 12px 10px;margin:0;background:var(--paper);min-width:0}
fieldset.fix.accepted{border-left-color:var(--ok)}fieldset.fix.rejected{border-left-color:var(--bad)}
fieldset.fix legend{padding:0 6px;font-size:13.5px;max-width:100%;overflow-wrap:anywhere}
.fix-kind{color:var(--muted);font-size:11.5px;text-transform:uppercase;letter-spacing:.05em}
label.alt{display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px;padding:7px 8px;border-radius:6px;cursor:pointer}
label.alt:hover{background:var(--soft)}label.alt:has(input:checked){background:var(--ok-bg)}
.alt-body{display:flex;flex-direction:column;gap:3px;font-size:13.5px;min-width:0}
.alt-head{display:flex;gap:8px;flex-wrap:wrap;align-items:baseline}.alt-rule{font-weight:600}
.alt-verb{font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--ok);font-weight:600}
.fix-clear{margin-left:auto;font-size:12.5px;padding:2px 8px}
.conf{font-size:11.5px;padding:0 7px;border-radius:999px;background:var(--na-bg);color:var(--na);white-space:nowrap}.conf.high{background:var(--ok-bg);color:var(--ok)}.conf.low{background:var(--warn-bg);color:var(--warn)}
.balance{font-size:12.5px;color:var(--muted);font-family:var(--mono)}
.fix-other{display:flex;gap:18px;flex-wrap:wrap;padding:6px 8px 0;margin-top:4px;border-top:1px dashed var(--line);font-size:13.5px}
.fix-other label{cursor:pointer}
.fix-edit label{display:block;font-size:12.5px;color:var(--muted);margin:8px 8px 0}
.fix-edit textarea{display:block;width:100%;font:12.5px/1.4 var(--mono);background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:6px 8px;margin-top:4px;resize:vertical}
.fix-error{margin:4px 8px 0;font-size:12.5px;color:var(--warn);min-height:0}
.decision-bar{position:fixed;left:0;right:0;bottom:0;display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:10px 24px;background:var(--paper);border-top:1px solid var(--line);box-shadow:0 -4px 16px rgba(0,0,0,.08);z-index:20;font-size:14px}
#decision-count{font-weight:600;margin-right:auto}
label.button{font-size:13px;background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:5px 10px;cursor:pointer}label.button:hover{background:var(--soft)}label.button:focus-within{outline:2px solid var(--link);outline-offset:2px}
button:disabled{opacity:.5;cursor:default}
body:has(.decision-bar) main{padding-bottom:110px}
@media print{.decision-bar,.xref-panel,.fix-other,.fix-edit{display:none}}
"""

_FIX_JS = r"""
(function(){
function data(id){var el=document.getElementById(id);if(!el)return null;try{return JSON.parse(el.textContent);}catch(e){return null;}}
function esc(t){return String(t==null?"":t).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
var index=data("thg-index");
if(index){
  var R=index.reactions||{},M=index.metabolites||{};
  var has=Object.prototype.hasOwnProperty;
  var kind=function(id){return has.call(R,id)?"reaction":has.call(M,id)?"metabolite":null;};
  var panel=document.getElementById("xref-panel"),body=document.getElementById("xref-body"),opener=null;
  var link=function(id){return '<button type="button" class="xref" data-xref="'+esc(id)+'">'+esc(id)+'</button>';};
  var linkTokens=function(text){return String(text||"").split(/(\s+)/).map(function(t){return kind(t)?link(t):esc(t);}).join("");};
  var show=function(id,from){
    var k=kind(id);if(!k)return;
    var html="";
    if(k==="reaction"){
      var r=R[id];
      html='<p class="fix-kind">Reaction</p><h3>'+esc(id)+'</h3><p class="muted">'+esc(r.name)+'</p><dl>'
        +'<dt>Equation</dt><dd class="equation">'+esc(r.equation_names)+'</dd>'
        +'<dt>IDs</dt><dd class="equation">'+linkTokens(r.equation)+'</dd>'
        +'<dt>Subsystem</dt><dd>'+esc(r.subsystem||"none")+'</dd>'
        +'<dt>Bounds</dt><dd>'+esc(r.bounds.join(" to "))+'</dd></dl>';
    }else{
      var m=M[id];
      html='<p class="fix-kind">Metabolite</p><h3>'+esc(id)+'</h3><p class="muted">'+esc(m.name)+'</p><dl>'
        +'<dt>Formula</dt><dd><code>'+esc(m.formula||"none")+'</code></dd>'
        +'<dt>Charge</dt><dd>'+esc(m.charge==null?"none":m.charge)+'</dd>'
        +'<dt>Compartment</dt><dd>'+esc(m.compartment||"none")+'</dd></dl>'
        +'<h4>Reactions <span class="count">'+m.reaction_count+'</span></h4>'
        +(m.reaction_count>m.reactions.length?'<p class="muted">Showing the first '+m.reactions.length+'.</p>':'')
        +'<ul>'+m.reactions.map(function(rid){var r=R[rid];return '<li>'+link(rid)+(r?'<div class="equation">'+esc(r.equation_names)+'</div>':'')+'</li>';}).join("")+'</ul>';
    }
    body.innerHTML=html;panel.hidden=false;panel.scrollTop=0;
    if(from&&!panel.contains(from))opener=from;
    panel.querySelector(".xref-close").focus();
  };
  var close=function(){panel.hidden=true;if(opener){opener.focus();opener=null;}};
  panel.querySelector(".xref-close").addEventListener("click",close);
  document.addEventListener("keydown",function(e){if(e.key==="Escape"&&!panel.hidden)close();});
  document.querySelectorAll(".check-body code, .check-body .ids li, .check-body td").forEach(function(el){
    if(el.children.length)return;
    var id=el.textContent.trim(),k=kind(id);if(!k)return;
    var item=k==="reaction"?R[id]:M[id];
    el.classList.add("xref-id");el.dataset.xref=id;el.tabIndex=0;el.setAttribute("role","button");
    el.dataset.search=[item.name,item.subsystem,item.formula].filter(Boolean).join(" ");
    el.title=(item.name||"")+(item.subsystem?" · "+item.subsystem:"");
  });
  document.addEventListener("click",function(e){
    var el=e.target.closest&&e.target.closest("[data-xref]");
    if(el){e.preventDefault();show(el.dataset.xref,el);}
  });
  document.addEventListener("keydown",function(e){
    var el=e.target;
    if((e.key==="Enter"||e.key===" ")&&el.classList&&el.classList.contains("xref-id")){e.preventDefault();show(el.dataset.xref,el);}
  });
}

var review=data("thg-review");
if(!review)return;
var groups=review.groups,state={};
var fmt=function(v){return typeof v==="string"?v:JSON.stringify(v);};
var parse=function(t){t=t.trim();try{return JSON.parse(t);}catch(e){return t;}};
var load=function(){try{var v=JSON.parse(localStorage.getItem(review.key)||"{}");if(v&&typeof v==="object")state=v;}catch(e){}
  Object.keys(state).forEach(function(g){var c=state[g]&&state[g].choice;if(c!=="reject"&&!item(g,c))delete state[g];});};
var save=function(){try{localStorage.setItem(review.key,JSON.stringify(state));}catch(e){}};
var item=function(g,id){return (groups[g]||[]).filter(function(x){return x.id===id;})[0];};
var fieldsets=document.querySelectorAll("fieldset.fix");
var message=document.getElementById("decision-message");
var say=function(t){message.textContent=t;};

function edited(g){
  var st=state[g];if(!st||st.text==null)return false;
  var chosen=item(g,st.choice);return chosen&&st.text.trim()!==fmt(chosen.after).trim();
}
function render(){
  fieldsets.forEach(function(fs){
    var g=fs.dataset.group,st=state[g]||{choice:""};
    fs.querySelectorAll('input[type="radio"]').forEach(function(r){r.checked=r.value===(st.choice||"");});
    var chosen=item(g,st.choice),edit=fs.querySelector(".fix-edit"),area=edit.querySelector("textarea");
    edit.hidden=!chosen;
    if(chosen&&document.activeElement!==area)area.value=st.text!=null?st.text:fmt(chosen.after);
    edit.querySelector(".fix-error").textContent=edited(g)?"Edited: this value replaces the suggestion when applied.":"";
    fs.classList.toggle("accepted",!!chosen);
    fs.classList.toggle("rejected",st.choice==="reject");
    fs.querySelector(".fix-clear").hidden=!st.choice;
  });
  var total=Object.keys(groups).length,n={accepted:0,rejected:0};
  Object.keys(state).forEach(function(g){
    if(!groups[g])return;var c=state[g].choice;
    if(c==="reject")n.rejected++;else if(item(g,c))n.accepted++;
  });
  var decided=n.accepted+n.rejected;
  document.getElementById("decision-count").textContent=decided+" of "+total+" fixes decided · "+n.accepted+" accepted · "+n.rejected+" rejected";
  document.getElementById("decisions-export").disabled=!decided;
}
fieldsets.forEach(function(fs){
  var g=fs.dataset.group;
  fs.addEventListener("change",function(e){
    if(e.target.type!=="radio")return;
    if(e.target.value)state[g]={choice:e.target.value,text:null};else delete state[g];
    save();render();
  });
  fs.querySelector(".fix-clear").addEventListener("click",function(){delete state[g];save();render();});
  fs.querySelector("textarea").addEventListener("input",function(e){
    if(!state[g])return;state[g].text=e.target.value;save();
    document.querySelectorAll('fieldset.fix').forEach(function(other){
      if(other!==fs&&other.dataset.group===g)other.querySelector("textarea").value=e.target.value;
    });
    render();
  });
});
function decisions(){
  var out=[];
  Object.keys(state).sort().forEach(function(g){
    var st=state[g],items=groups[g];if(!items)return;
    if(st.choice==="reject"){
      items.forEach(function(x){out.push({proposal_id:x.id,action:"reject",reason:""});});return;
    }
    if(!item(g,st.choice))return;
    items.forEach(function(x){
      if(x.id!==st.choice)out.push({proposal_id:x.id,action:"reject",reason:"another fix was chosen"});
      else if(edited(g))out.push({proposal_id:x.id,action:"replace",replacement:parse(st.text),reason:"edited in the validation report"});
      else out.push({proposal_id:x.id,action:"approve",reason:""});
    });
  });
  return out;
}
document.getElementById("decisions-export").addEventListener("click",function(){
  var list=decisions();
  var blob=new Blob([list.map(function(x){return JSON.stringify(x);}).join("\n")+"\n"],{type:"application/x-ndjson"});
  var a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="decisions.jsonl";
  document.body.appendChild(a);a.click();a.remove();
  setTimeout(function(){URL.revokeObjectURL(a.href);},1000);
  say("Exported "+list.length+" decisions.");
});
document.getElementById("decisions-import").addEventListener("change",function(e){
  var file=e.target.files[0];if(!file)return;
  file.text().then(function(text){
    var owner={};
    Object.keys(groups).forEach(function(g){groups[g].forEach(function(x){owner[x.id]=g;});});
    var byGroup={},count=0,unknown=0;
    text.split(/\r?\n/).forEach(function(line){
      if(!line.trim())return;
      var d;try{d=JSON.parse(line);}catch(err){unknown++;return;}
      var g=owner[d.proposal_id];if(!g){unknown++;return;}
      (byGroup[g]=byGroup[g]||[]).push(d);count++;
    });
    Object.keys(byGroup).forEach(function(g){
      var list=byGroup[g];
      var pick=list.filter(function(d){return d.action==="approve"||d.action==="replace";})[0];
      if(pick)state[g]={choice:pick.proposal_id,text:pick.action==="replace"?fmt(pick.replacement):null};
      else if(list.some(function(d){return d.action==="reject";}))state[g]={choice:"reject",text:null};
      else delete state[g];
    });
    save();render();
    say("Imported "+count+" decisions"+(unknown?"; "+unknown+" lines did not match a fix in this report":"")+".");
    e.target.value="";
  });
});
document.getElementById("decisions-clear").addEventListener("click",function(){
  if(!Object.keys(state).length||!confirm("Clear all decisions in this report?"))return;
  state={};save();render();say("Cleared.");
});
load();render();
})();
"""


def render_validation_html(report: Mapping[str, object]) -> str:
    """Render one self-contained, safe HTML file without recomputing results."""
    validation = _validation(report)
    checks = validation.get("checks", [])
    checks = (
        [
            item
            for item in checks
            if isinstance(item, Mapping) and item.get("id") not in _RETIRED
        ]
        if isinstance(checks, list)
        else []
    )
    ids = _Ids()
    passed = _passed(report)
    gate, verdict = _verdict(report, checks)
    profile = str(
        report.get("validation_profile", validation.get("profile", "unknown"))
    )
    model_id = report.get("model_id")

    groups: dict[str, list[Mapping[str, object]]] = {}
    for proposal in _proposals(validation):
        groups.setdefault(_fix_target(proposal), []).append(proposal)
    review = _review_data(report, validation, groups)

    families: dict[str, list[Mapping[str, object]]] = {}
    for item in checks:
        families.setdefault(str(item.get("family", "other")), []).append(item)

    strip = "".join(
        f'<a class="cell {escape(_status(item))}" href="#{_anchor(item.get("id"))}" '
        f'title="{escape(CHECKS.get(str(item.get("id")), (_label(item.get("id")),))[0])}: '
        f'{escape(STATUS_LABELS.get(_status(item), _status(item)))}">'
        f'<span class="sr">{escape(str(item.get("id")))}</span></a>'
        for item in checks
    )
    tally = Counter(_status(item) for item in checks)
    legend = " ".join(
        f'<span class="legend-item"><span class="swatch {key}"></span>{count} {escape(STATUS_LABELS[key].lower())}</span>'
        for key, count in (
            (key, tally[key])
            for key in (
                "passed",
                "failed",
                "warning",
                "not-evaluated",
                "infrastructure-error",
            )
        )
        if count
    )

    nav_checks = "".join(
        f'<li class="nav-family">{escape(FAMILIES.get(family, (_label(family),))[0])}<ul>'
        + "".join(
            f'<li><a href="#{_anchor(item.get("id"))}"><span class="dot {escape(_status(item))}"></span>'
            f"{escape(CHECKS.get(str(item.get('id')), (_label(item.get('id')),))[0])}</a></li>"
            for item in items
        )
        + "</ul></li>"
        for family, items in families.items()
    )
    sections = [
        ("reduction", "Context reduction", "source_reaction_count" in report),
        ("changes", "Changes from input", bool(report.get("metric_deltas"))),
        ("tasks", "Metabolic tasks", True),
        (
            "gimme-samples",
            "GIMME samples",
            report.get("gimme_samples") not in (None, []),
        ),
        (
            "gimme-objectives",
            "GIMME objectives",
            isinstance(report.get("gimme_objectives"), Mapping)
            and report["gimme_objectives"].get("status") != "not-requested",
        ),
        ("memote", "MEMOTE", True),
        ("solver", "Solver", True),
        ("provenance", "Provenance", True),
    ]
    nav_sections = "".join(
        f'<li><a href="#{anchor}">{title}</a></li>'
        for anchor, title, shown in sections
        if shown
    )

    check_sections = "".join(
        f'<section class="family" id="family-{escape(family)}">'
        f"<h3>{escape(FAMILIES.get(family, (_label(family), ''))[0])}"
        f'<span class="family-q">{escape(FAMILIES.get(family, ("", ""))[1])}</span></h3>'
        + "".join(_check_card(item, ids, groups, validation) for item in items)
        + "</section>"
        for family, items in families.items()
    )
    other_warnings = [
        str(item)
        for item in (report.get("warnings") or [])
        if str(item) not in {str(check.get("id")) for check in checks}
    ]
    if validation.get("proposal_error"):
        other_warnings.append(
            f"fix proposals could not be generated: {validation['proposal_error']}"
        )
    other = (
        '<p class="note">Other warnings: '
        + ", ".join(f"<code>{escape(_label(item))}</code>" for item in other_warnings)
        + ".</p>"
        if other_warnings
        else ""
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Validation report{escape(f" – {model_id}" if model_id else "")}</title><style>
:root{{--bg:#f3f5f6;--paper:#fff;--ink:#16202a;--muted:#5a6874;--line:#d9e0e5;--soft:#eef2f4;--link:#0d6577;
--ok:#1d7448;--ok-bg:#e1f2e8;--bad:#b3261e;--bad-bg:#fbe5e3;--warn:#8f5a00;--warn-bg:#fbefd6;--na:#76838f;--na-bg:#e8ecef;
--serif:Charter,"Bitstream Charter","Sitka Text",Cambria,Georgia,serif;--sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;--mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace}}
@media(prefers-color-scheme:dark){{:root{{--bg:#12181d;--paper:#1a2228;--ink:#e3e8ec;--muted:#98a6b1;--line:#2d3942;--soft:#222c33;--link:#6cc3d5;
--ok:#6fcf97;--ok-bg:#183326;--bad:#f2867d;--bad-bg:#3a1d1b;--warn:#e5b45a;--warn-bg:#352a14;--na:#8d9aa5;--na-bg:#262f36}}}}
*{{box-sizing:border-box}}html{{scroll-padding-top:16px}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 var(--sans)}}
a{{color:var(--link)}}a:focus-visible,summary:focus-visible,input:focus-visible,button:focus-visible{{outline:2px solid var(--link);outline-offset:2px}}
code,.ids,.equation,pre{{font-family:var(--mono);font-size:12.5px}}
.layout{{display:grid;grid-template-columns:250px minmax(0,1fr);max-width:1320px;margin:0 auto}}
nav{{position:sticky;top:0;align-self:start;max-height:100vh;overflow:auto;padding:28px 16px 28px 24px;font-size:13.5px}}
nav ul{{list-style:none;margin:0;padding:0}}nav a{{display:flex;align-items:center;gap:8px;padding:3px 6px;border-radius:5px;color:var(--ink);text-decoration:none}}nav a:hover{{background:var(--soft)}}
.nav-head{{margin:18px 0 6px;color:var(--muted);font-size:12.5px}}.nav-family{{margin:8px 0 2px;color:var(--muted);font-size:12.5px}}.nav-family ul{{margin-top:2px}}
.dot{{flex:none;width:9px;height:9px;border-radius:50%;background:var(--na)}}
.dot.passed{{background:var(--ok)}}.dot.failed,.dot.infrastructure-error,.dot.error{{background:var(--bad)}}.dot.warning{{background:var(--warn)}}
main{{padding:28px 32px 64px;min-width:0}}
header{{margin-bottom:28px}}h1{{font:600 2rem/1.15 var(--serif);margin:0 0 4px;letter-spacing:-.01em}}
.subtitle{{color:var(--muted);margin:0 0 22px}}
.verdict{{display:grid;grid-template-columns:auto 1fr;gap:18px;align-items:start;background:var(--paper);border:1px solid var(--line);border-left:6px solid {"var(--ok)" if passed else "var(--bad)"};border-radius:8px;padding:20px 22px}}
.gate{{margin:0;font:700 1.6rem/1 var(--serif);color:{"var(--ok)" if passed else "var(--bad)"}}}
.verdict-text{{margin:0;max-width:72ch}}.profile{{margin:8px 0 0;color:var(--muted);font-size:14px;max-width:72ch}}
.strip-wrap{{margin:22px 0 0}}.strip{{display:flex;flex-wrap:wrap;gap:4px}}
.strip .cell{{width:26px;height:26px;border-radius:4px;background:var(--na-bg);border:2px solid var(--na)}}
.strip .cell.passed{{background:var(--ok-bg);border-color:var(--ok)}}.strip .cell.failed,.strip .cell.infrastructure-error{{background:var(--bad);border-color:var(--bad)}}
.strip .cell.warning{{background:var(--warn-bg);border-color:var(--warn)}}.strip .cell:hover{{transform:translateY(-2px)}}
.legend{{margin:8px 0 0;color:var(--muted);font-size:13px;display:flex;flex-wrap:wrap;gap:14px}}.legend-item{{display:inline-flex;align-items:center;gap:6px}}
.swatch{{width:12px;height:12px;border-radius:3px;border:2px solid var(--na);background:var(--na-bg)}}.swatch.passed{{border-color:var(--ok);background:var(--ok-bg)}}.swatch.failed,.swatch.infrastructure-error{{border-color:var(--bad);background:var(--bad)}}.swatch.warning{{border-color:var(--warn);background:var(--warn-bg)}}
.sr{{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}}
h2{{font:600 1.35rem/1.25 var(--serif);margin:0 0 6px}}section{{margin:0 0 36px}}
.lead-small{{color:var(--muted);margin:0 0 14px;max-width:76ch}}
.guide{{background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:4px 18px;margin:0 0 32px}}
.guide summary{{cursor:pointer;padding:10px 0;font-weight:600}}.guide dl{{display:grid;grid-template-columns:max-content 1fr;gap:6px 16px;margin:4px 0 16px}}.guide dt{{white-space:nowrap}}.guide dd{{margin:0;max-width:70ch}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:8px;overflow:hidden;margin:0 0 36px}}
.metric{{background:var(--paper);padding:14px 16px;display:flex;flex-direction:column}}.metric-value{{font:600 1.45rem/1.2 var(--serif);font-variant-numeric:tabular-nums}}.metric-label{{font-size:13.5px}}.metric-note{{color:var(--muted);font-size:12.5px}}
.toolbar{{display:flex;justify-content:space-between;align-items:end;gap:12px;flex-wrap:wrap;margin-bottom:10px}}
button{{font:inherit;font-size:13px;background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:5px 10px;cursor:pointer}}button:hover{{background:var(--soft)}}
.family{{margin:0 0 26px}}.family h3{{font:600 1.05rem/1.3 var(--sans);margin:0 0 8px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}}.family-q{{font-weight:400;color:var(--muted);font-size:14px}}
.check{{background:var(--paper);border:1px solid var(--line);border-radius:8px;margin:0 0 8px}}
.check>summary{{list-style:none;cursor:pointer;display:grid;grid-template-columns:4px minmax(160px,240px) auto auto 1fr;gap:6px 14px;align-items:center;padding:12px 16px 12px 0}}
.check>summary::-webkit-details-marker{{display:none}}
.mark{{align-self:stretch;border-radius:0 3px 3px 0;background:var(--na)}}.check.passed .mark{{background:var(--ok)}}.check.failed .mark,.check.infrastructure-error .mark{{background:var(--bad)}}.check.warning .mark{{background:var(--warn)}}
.check-title{{font-weight:600}}.policy{{color:var(--muted);font-size:13px;white-space:nowrap}}.headline{{color:var(--muted);font-size:14px}}
.check[open]>summary{{border-bottom:1px solid var(--line)}}.check-body{{padding:14px 18px 16px 18px}}
.explain{{margin:0 0 6px;max-width:76ch;font:15.5px/1.6 var(--serif)}}
.evidence{{margin-top:14px}}.check-id{{margin:12px 0 0;color:var(--muted);font-size:12.5px}}
.pill{{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12.5px;font-weight:600;white-space:nowrap;background:var(--na-bg);color:var(--na)}}
.pill.passed{{background:var(--ok-bg);color:var(--ok)}}.pill.failed,.pill.infrastructure-error,.pill.error,.pill.invalid{{background:var(--bad-bg);color:var(--bad)}}.pill.warning{{background:var(--warn-bg);color:var(--warn)}}
.tally{{display:flex;gap:6px;flex-wrap:wrap}}
.block{{margin:14px 0 0}}.block h4{{margin:0 0 6px;font-size:14px}}.count{{display:inline-block;margin-left:4px;padding:0 7px;border-radius:999px;background:var(--soft);color:var(--muted);font-size:12px;font-weight:600}}
dl.fields{{display:grid;grid-template-columns:max-content 1fr;gap:4px 18px;margin:0}}dl.fields dt{{color:var(--muted)}}dl.fields dd{{margin:0;overflow-wrap:anywhere}}
.ids{{list-style:none;margin:0;padding:8px;display:flex;flex-wrap:wrap;gap:4px;max-height:220px;overflow:auto;background:var(--soft);border-radius:6px}}
.ids li{{padding:1px 6px;background:var(--paper);border:1px solid var(--line);border-radius:4px}}
.table-wrap{{max-height:420px;overflow:auto;border:1px solid var(--line);border-radius:6px}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}}th,td{{padding:7px 10px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}}
thead th{{position:sticky;top:0;background:var(--soft);font-weight:600;font-size:12.5px;color:var(--muted);z-index:1}}tbody tr:last-child td{{border-bottom:0}}
td{{overflow-wrap:break-word}}td code,.nowrap{{white-space:nowrap}}.equation{{display:block;min-width:28ch;line-height:1.45;overflow-wrap:anywhere}}
.equation.clamp{{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}}
.variant{{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline;padding:2px 0}}.variant+.variant{{border-top:1px dashed var(--line)}}
.where{{display:inline-flex;flex-wrap:wrap;gap:4px 8px;font-size:12.5px}}.diff{{font-family:var(--mono);font-size:12.5px;color:var(--warn);white-space:nowrap}}
.evidence details{{margin-top:6px}}.evidence details>summary{{font-size:13.5px}}
.pair{{display:inline-block;margin:0 10px 2px 0;overflow-wrap:normal;white-space:nowrap}}.muted{{color:var(--muted)}}.note{{color:var(--muted);font-size:13px;margin:8px 0 0}}
.filter{{display:block;width:min(320px,100%);margin:0 0 6px;padding:5px 9px;font:inherit;font-size:13px;background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:6px}}
.delta.up{{color:var(--warn);font-weight:600}}.delta.down{{color:var(--link);font-weight:600}}.delta.zero{{color:var(--muted)}}
details>summary{{cursor:pointer}}.block details,.check-body details{{margin-top:8px}}
pre.log{{max-height:320px;overflow:auto;white-space:pre-wrap;background:var(--soft);padding:10px;border-radius:6px}}
section>details,#memote .table-wrap{{margin-top:10px}}
@media(max-width:900px){{.layout{{display:block}}nav{{position:static;max-height:none;padding:16px 16px 0}}nav .nav-checks{{display:none}}main{{padding:16px 16px 48px}}
.check>summary{{grid-template-columns:4px 1fr auto;padding-right:12px}}.policy,.headline{{grid-column:2/4}}.verdict{{grid-template-columns:1fr}}}}
@media(prefers-reduced-motion:reduce){{.strip .cell:hover{{transform:none}}}}
@media print{{nav,.filter,.toolbar button{{display:none}}.layout{{display:block}}.table-wrap,.ids{{max-height:none}}}}
{_FIX_CSS}
</style></head><body><div class="layout">
<nav aria-label="Report sections"><a href="#top"><strong>Validation report</strong></a>
<p class="nav-head">Checks</p><ul class="nav-checks">{nav_checks}</ul>
<p class="nav-head">Other results</p><ul>{nav_sections}</ul></nav>
<main id="top">
<header><h1>Validation report{escape(f" for {model_id}" if model_id else "")}</h1>
<p class="subtitle">Profile <code>{escape(profile)}</code></p>
<div class="verdict"><p class="gate">{gate}</p><div><p class="verdict-text">{verdict}</p>
<p class="profile">{escape(PROFILES.get(profile, "Custom validation profile."))}</p></div></div>
{f'<div class="strip-wrap"><div class="strip" aria-label="Status of every check, in report order">{strip}</div><p class="legend">{legend}</p></div>' if checks else ""}
</header>
<details class="guide"><summary>How to read this report</summary><dl>
<dt>{_pill("passed")}</dt><dd>The check found no problems.</dd>
<dt>{_pill("failed")}</dt><dd>A release-blocking check found problems. The model does not pass validation until these are fixed.</dd>
<dt>{_pill("warning")}</dt><dd>A diagnostic check found problems. They are worth reviewing but do not block the release under this profile; many are inherited from the upstream model.</dd>
<dt>{_pill("not-evaluated")}</dt><dd>The check could not run, usually because an optional dependency is missing.</dd>
<dt>{_pill("infrastructure-error")}</dt><dd>The check itself crashed; its result is unknown.</dd>
<dt>Profile</dt><dd>Decides which checks run and which of them block the release. Each check shows whether it blocks release or is diagnostic.</dd>
<dt>Evidence</dt><dd>Open a check for its description and affected identifiers. Filter long lists by ID, name or subsystem. Full results are in the accompanying JSON report.</dd>
<dt>Identifiers</dt><dd>Underlined reaction and metabolite IDs open a panel with the equation, formula and connected reactions.</dd>
<dt>Suggested fixes</dt><dd>Where a rule can fix a problem, the check lists the fixes. Accept one per reaction or metabolite, or reject it; fixes you leave alone are not applied. Then export the decisions and run <code>thg-run apply-decisions</code> to get a fixed model and a new report.</dd>
</dl></details>
{_metric_cards(report)}
<section id="checks"><div class="toolbar"><div><h2>Checks</h2><p class="lead-small">Grouped by what they examine. Failed checks and checks with suggested fixes are open; select any check to see its evidence.</p></div>
<div><button type="button" data-toggle="open">Expand all</button> <button type="button" data-toggle="close">Collapse all</button></div></div>
{check_sections or '<p class="muted">No checks were recorded.</p>'}{other}</section>
{_reduction(report, ids)}{_changes(report, ids)}{_tasks(report, ids)}{_gimme(report, ids)}{_memote(report, ids)}{_solver(report, validation)}{_provenance(report)}
</main></div>
{review}
<script>
function searchText(el){{
  var text=el.textContent+" "+(el.dataset.search||"");
  el.querySelectorAll("[data-search]").forEach(function(x){{text+=" "+x.dataset.search;}});
  return text.toLowerCase();
}}
document.querySelectorAll("input.filter").forEach(function(input){{
  var target=document.getElementById(input.dataset.target);
  var items=target.tagName==="TABLE"?target.tBodies[0].rows:target.children;
  input.addEventListener("input",function(){{
    var q=input.value.trim().toLowerCase();
    for(var i=0;i<items.length;i++)items[i].hidden=q&&searchText(items[i]).indexOf(q)<0;
  }});
}});
document.querySelectorAll("[data-toggle]").forEach(function(button){{
  button.addEventListener("click",function(){{
    var open=button.dataset.toggle==="open";
    document.querySelectorAll("details.check").forEach(function(d){{d.open=open;}});
  }});
}});
document.querySelectorAll('a[href^="#check-"]').forEach(function(link){{
  link.addEventListener("click",function(){{
    var d=document.getElementById(link.getAttribute("href").slice(1));
    if(d)d.open=true;
  }});
}});
</script>
<script>{_FIX_JS}</script></body></html>\n"""


def render_validation_summary(report: Mapping[str, object]) -> str:
    validation = _validation(report)
    checks = validation.get("checks", [])
    failures = (
        [
            str(item.get("id"))
            for item in checks
            if isinstance(item, Mapping) and item.get("passed") is not True
        ]
        if isinstance(checks, list)
        else []
    )
    lines = [
        "# THG validation",
        "",
        f"- Overall: **{'PASSED' if _passed(report) else 'FAILED'}**",
        f"- Profile: {report.get('validation_profile', validation.get('profile', 'unknown'))}",
        f"- Findings: {', '.join(failures) if failures else 'none'}",
    ]
    deltas = report.get("metric_deltas", {})
    if isinstance(deltas, Mapping) and deltas:
        lines.extend(["", "## Changes from upstream", ""])
        lines.extend(
            f"- {key.replace('_', ' ')}: {_display(value)}"
            for key, value in deltas.items()
        )
    return "\n".join(lines) + "\n"


__all__ = ["render_validation_html", "render_validation_summary"]
