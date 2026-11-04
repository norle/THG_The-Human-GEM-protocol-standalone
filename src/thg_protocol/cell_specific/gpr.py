"""Safe GPR expression scoring with explicit missing-data evidence."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ReactionExpressionEvidence:
    reaction_id: str
    score: float | None
    status: Literal["measured", "partial", "unknown", "no-gpr"]
    genes_used: tuple[str, ...]
    missing_genes: tuple[str, ...]
    #: Whether the expression data fixes ``score``. A partially observed OR
    #: only bounds it from below. ``None`` (evidence serialized before this
    #: field existed) means exact only when the status is ``measured``.
    exact: bool | None = None

    @property
    def is_exact(self) -> bool:
        if self.exact is None:
            return self.status == "measured"
        return self.exact and self.score is not None


_TOKEN = re.compile(r"\s*(\(|\)|\band\b|\bor\b|[^\s()]+)", re.I)


def _tokens(rule: str) -> list[str]:
    tokens = [match.group(1) for match in _TOKEN.finditer(rule)]
    if "".join(tokens).lower() != re.sub(r"\s+", "", rule).lower():
        raise ValueError(f"invalid GPR rule: {rule!r}")
    return tokens


def _parse(rule: str):
    tokens, position = _tokens(rule), 0

    def primary():
        nonlocal position
        if position >= len(tokens):
            raise ValueError("unexpected end of GPR rule")
        token = tokens[position]
        position += 1
        if token == "(":
            value = disjunction()
            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError("unclosed GPR parenthesis")
            position += 1
            return value
        if token in {")", "and", "or"}:
            raise ValueError(f"unexpected GPR token: {token}")
        return ("gene", token)

    def conjunction():
        nonlocal position
        value = primary()
        while position < len(tokens) and tokens[position].lower() == "and":
            position += 1
            value = ("and", value, primary())
        return value

    def disjunction():
        nonlocal position
        value = conjunction()
        while position < len(tokens) and tokens[position].lower() == "or":
            position += 1
            value = ("or", value, conjunction())
        return value

    result = disjunction()
    if position != len(tokens):
        raise ValueError(f"unexpected GPR token: {tokens[position]}")
    return result


def _evaluate(node, expression: Mapping[str, float | None]):
    """Return ``(score, genes, missing, complete, exact)`` for a GPR node."""
    kind = node[0]
    if kind == "gene":
        gene = node[1]
        value = expression.get(gene)
        if value is None:
            return None, (), (gene,), False, False
        return float(value), (gene,), (), True, True
    left = _evaluate(node[1], expression)
    right = _evaluate(node[2], expression)
    scores = [value for value in (left[0], right[0]) if value is not None]
    genes = tuple(sorted(set(left[1] + right[1])))
    missing = tuple(sorted(set(left[2] + right[2])))
    complete = left[3] and right[3]
    if kind == "or":
        # An unobserved isozyme can only raise the maximum: unless every
        # branch is exact, the score is a lower bound.
        exact = left[4] and right[4]
        return (max(scores) if scores else None), genes, missing, complete, exact
    # An observed zero subunit proves an AND complex has zero support.  Other
    # partially observed complexes remain unknown rather than inventing a score.
    if complete:
        return min(scores), genes, missing, True, True
    if any(child[0] == 0 and child[4] for child in (left, right)):
        return 0.0, genes, missing, False, True
    return None, genes, missing, False, False


def reaction_expression_evidence(
    reaction_id: str, rule: str, expression: Mapping[str, float | None]
) -> ReactionExpressionEvidence:
    """Score one GPR using AND=min and OR=max without executing the rule."""
    if not rule.strip():
        return ReactionExpressionEvidence(reaction_id, None, "no-gpr", (), ())
    score, used, missing, complete, exact = _evaluate(_parse(rule), expression)
    return ReactionExpressionEvidence(
        reaction_id,
        score,
        "measured" if complete else "partial" if score is not None else "unknown",
        used,
        missing,
        exact and score is not None,
    )


def reaction_expression_for_model(model, expression: Mapping[str, float | None]):
    """Return deterministic reaction evidence in model reaction order."""
    return tuple(
        reaction_expression_evidence(
            reaction.id, str(reaction.gene_reaction_rule or ""), expression
        )
        for reaction in model.reactions
    )


__all__ = [
    "ReactionExpressionEvidence",
    "reaction_expression_evidence",
    "reaction_expression_for_model",
]
