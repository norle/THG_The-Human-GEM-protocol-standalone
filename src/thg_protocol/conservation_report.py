"""Dependency-free review pages for conservation fix proposals."""

# ruff: noqa: E501 - embedded HTML/CSS is clearer when kept intact.

from __future__ import annotations

from collections.abc import Iterable, Mapping
from html import escape

_COLUMNS = (
    "Proposal",
    "Object",
    "Rule",
    "Before",
    "After",
    "Elements before / after",
    "Charge before / after",
    "Input model",
    "Evidence",
    "Confidence",
)


def _elements(summary: Mapping[str, object] | None) -> str:
    if not summary:
        return "-"
    elements = summary.get("elements", {})
    if not isinstance(elements, Mapping):
        return "-"
    if elements.get("missing_formula"):
        return "no formula: " + ", ".join(map(str, elements["missing_formula"]))
    residual = elements.get("residual") or {}
    return (
        ", ".join(f"{key}: {value:+g}" for key, value in residual.items()) or "balanced"
    )


def _charge(summary: Mapping[str, object] | None) -> str:
    if not summary:
        return "-"
    charge = summary.get("charge", {})
    if not isinstance(charge, Mapping):
        return "-"
    if charge.get("missing_charge"):
        return "no charge: " + ", ".join(map(str, charge["missing_charge"]))
    residual = charge.get("residual") or 0
    return f"{residual:+g}" if residual else "balanced"


def _input(context: object) -> str:
    if not isinstance(context, Mapping) or not context.get("compared"):
        return "no input model"
    if not context.get("present"):
        return "not in input model"
    return f"in input model: {context.get('equation_ids', '')}"


def _rows(proposal: Mapping[str, object]) -> list[dict[str, str]]:
    """Flatten one proposal into one row per affected reaction."""
    metadata = proposal.get("metadata", {})
    metadata = metadata if isinstance(metadata, Mapping) else {}
    if "reactions" in metadata:
        details = [item for item in metadata["reactions"] if isinstance(item, Mapping)]
    else:
        reaction = metadata.get("reaction", {})
        reaction = reaction if isinstance(reaction, Mapping) else {}
        details = [
            {
                "id": proposal.get("object_id"),
                "before": reaction.get("before"),
                "after": reaction.get("after"),
                "input_model": metadata.get("input_model"),
            }
        ]
    flags = ", ".join(map(str, metadata.get("flags", [])))
    rule = str(proposal.get("policy", ""))
    if metadata.get("cofactor"):
        rule += f" ({metadata['cofactor']})"
    if proposal.get("status") == "unresolved":
        rule += " [unresolved]"
    obj = f"{proposal.get('object_type')} {proposal.get('object_id')}"
    if proposal.get("object_type") == "metabolite":
        obj += f": {proposal.get('before') or '(none)'} → {proposal.get('after')}"
    rows = []
    for item in details:
        before = item.get("before") or {}
        after = item.get("after")
        after_text = (
            "(removed)"
            if proposal.get("operation") == "remove-reaction"
            else "(excluded from conservation)"
            if proposal.get("operation") == "exclude-reaction"
            else f"{after.get('equation_ids')}\n{after.get('equation_names')}"
            if isinstance(after, Mapping)
            else "-"
        )
        rows.append(
            {
                "Proposal": str(proposal.get("proposal_id", "")),
                "Object": obj
                + (f" (reaction {item.get('id')})" if "reactions" in metadata else ""),
                "Rule": rule,
                "Before": f"{before.get('equation_ids', '')}\n{before.get('equation_names', '')}",
                "After": after_text,
                "Elements before / after": f"{_elements(before)} / {_elements(after)}",
                "Charge before / after": f"{_charge(before)} / {_charge(after)}",
                "Input model": _input(item.get("input_model")),
                "Evidence": "; ".join(map(str, proposal.get("evidence", [])))
                + (f"; flags: {flags}" if flags else ""),
                "Confidence": str(proposal.get("confidence", "")),
            }
        )
    return rows


_BLAMED_COLUMNS = (
    "Reaction",
    "Origin",
    "Imbalance",
    "Equation",
    "Elements",
    "Charge",
    "Flags",
)


def _blamed(localization: Mapping[str, object]) -> list[Mapping[str, object]]:
    rows = localization.get("blamed", [])
    return [row for row in rows if isinstance(row, Mapping)] if rows else []


def _blamed_groups(
    localization: Mapping[str, object],
) -> list[tuple[str, str, list[dict[str, str]]]]:
    """Blamed reactions split into flagged and unflagged, as display rows."""
    groups: dict[bool, list[dict[str, str]]] = {True: [], False: []}
    for row in _blamed(localization):
        fractional = row.get("fractional") or {}
        mismatched = row.get("formula_disagreement") or []
        flags = ", ".join(map(str, row.get("flags", [])))
        if fractional:
            flags += "\nnon-integer: " + ", ".join(
                f"{key} {value:g}" for key, value in fractional.items()
            )
        if mismatched:
            flags += "\nformula disagrees: " + ", ".join(map(str, mismatched))
        mislabelled = row.get("mislabelled") or []
        if mislabelled:
            flags += "\npossibly mislabelled: " + ", ".join(map(str, mislabelled))
        groups[bool(row.get("flags"))].append(
            {
                "Reaction": str(row.get("id", "")),
                "Origin": str(row.get("origin") or "-"),
                "Imbalance": f"{row.get('imbalance', 0):+g}",
                "Equation": f"{row.get('equation_ids', '')}\n{row.get('equation_names', '')}",
                "Elements": _elements(row),
                "Charge": _charge(row),
                "Flags": flags.strip() or "-",
            }
        )
    return [
        (
            "Blamed reactions with a chemical flag",
            "Element or charge imbalance, missing formula or charge, non-integer "
            "coefficients, or a metabolite whose formula disagrees or that may be "
            "mislabelled. Start here.",
            groups[True],
        ),
        (
            "Blamed reactions without a flag",
            "Balanced and integer. Often an innocent member of a loop the LP had "
            "to break somewhere; check whether a flagged reaction in the same "
            "pathway explains it.",
            groups[False],
        ),
    ]


def _summary_lines(localization: Mapping[str, object]) -> list[str]:
    blamed = _blamed(localization)
    flagged = sum(1 for row in blamed if row.get("flags"))
    return [
        f"Unconserved metabolites: {len(localization.get('unconserved', []))}",
        f"New in this step: {len(localization.get('new', []))}",
        f"Inherited from the input model: {len(localization.get('inherited', []))}",
        f"Blamed reactions: {len(blamed)} ({flagged} with a chemical flag, "
        f"{len(blamed) - flagged} without)",
    ]


def render_review_markdown(
    proposals: Iterable[Mapping[str, object]], localization: Mapping[str, object]
) -> str:
    """Render the proposals as a Markdown review table."""
    lines = ["# Conservation fix review", ""]
    lines.extend(f"- {line}" for line in _summary_lines(localization))
    lines.extend(
        [
            "",
            "Write one JSON line per proposal to the decisions file, e.g. "
            '`{"proposal_id": "...", "action": "approve"}` '
            "(actions: approve, reject, replace, defer).",
            "",
            "| " + " | ".join(_COLUMNS) + " |",
            "|" + "---|" * len(_COLUMNS),
        ]
    )
    for proposal in proposals:
        for row in _rows(proposal):
            cells = (
                row[column].replace("|", "\\|").replace("\n", "<br>")
                for column in _COLUMNS
            )
            lines.append("| " + " | ".join(cells) + " |")
    for title, note, rows in _blamed_groups(localization):
        lines.extend(["", f"## {title}", "", note, ""])
        if not rows:
            lines.append("None.")
            continue
        lines.append("| " + " | ".join(_BLAMED_COLUMNS) + " |")
        lines.append("|" + "---|" * len(_BLAMED_COLUMNS))
        for row in rows:
            cells = (
                row[column].replace("|", "\\|").replace("\n", "<br>")
                for column in _BLAMED_COLUMNS
            )
            lines.append("| " + " | ".join(cells) + " |")
    inherited = localization.get("inherited", [])
    if inherited:
        lines.extend(["", "## Inherited unconserved metabolites", ""])
        lines.extend(f"- {item}" for item in inherited)
    return "\n".join(lines) + "\n"


def render_review_html(
    proposals: Iterable[Mapping[str, object]], localization: Mapping[str, object]
) -> str:
    """Render the same content as a self-contained HTML page."""
    body = []
    for proposal in proposals:
        for row in _rows(proposal):
            body.append(
                "<tr>"
                + "".join(
                    f"<td>{escape(row[column]).replace(chr(10), '<br>')}</td>"
                    for column in _COLUMNS
                )
                + "</tr>"
            )
    summary = "".join(
        f"<li>{escape(line)}</li>" for line in _summary_lines(localization)
    )
    blamed_header = "".join(f"<th>{escape(column)}</th>" for column in _BLAMED_COLUMNS)
    blamed_html = "".join(
        f'<section><h2>{escape(title)}</h2><p class="lead">{escape(note)}</p>'
        + (
            f"<table><thead><tr>{blamed_header}</tr></thead><tbody>"
            + "".join(
                "<tr>"
                + "".join(
                    f"<td>{escape(row[column]).replace(chr(10), '<br>')}</td>"
                    for column in _BLAMED_COLUMNS
                )
                + "</tr>"
                for row in rows
            )
            + "</tbody></table>"
            if rows
            else "<p>None.</p>"
        )
        + "</section>"
        for title, note, rows in _blamed_groups(localization)
    )
    inherited = localization.get("inherited", [])
    inherited_html = (
        "<section><h2>Inherited unconserved metabolites</h2><ul>"
        + "".join(f"<li>{escape(str(item))}</li>" for item in inherited)
        + "</ul></section>"
        if inherited
        else ""
    )
    header = "".join(f"<th>{escape(column)}</th>" for column in _COLUMNS)
    rows = "".join(body) or f'<tr><td colspan="{len(_COLUMNS)}">No proposals</td></tr>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conservation fix review</title><style>
:root{{--line:#d8dee4;--muted:#59636e;--bg:#f6f8fa;--fg:#1f2328;--card:#fff}}@media(prefers-color-scheme:dark){{:root{{--line:#30363d;--muted:#8d96a0;--bg:#0d1117;--fg:#e6edf3;--card:#161b22}}}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif}}main{{max-width:1600px;margin:auto;padding:24px 16px}}section{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0;overflow:auto}}table{{border-collapse:collapse;min-width:1200px}}th,td{{padding:8px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}td{{font:12px ui-monospace,monospace}}.lead{{color:var(--muted)}}
</style></head><body><main><h1>Conservation fix review</h1>
<section><ul>{summary}</ul><p class="lead">Write one JSON line per proposal to the decisions file, e.g. <code>{{"proposal_id": "...", "action": "approve"}}</code> (actions: approve, reject, replace, defer).</p></section>
<section><h2>Fix proposals</h2><table><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table></section>
{blamed_html}
{inherited_html}
</main></body></html>
"""


__all__ = ["render_review_html", "render_review_markdown"]
