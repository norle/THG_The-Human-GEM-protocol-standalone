"""Canonical, source-independent stoichiometric GPR expressions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

COEFFICIENT_STATUSES = frozenset({"observed", "inferred", "defaulted", "unknown"})


@dataclass(frozen=True)
class GeneNode:
    gene: str
    coefficient: int | None = None
    coefficient_status: str = "unknown"
    source: str | None = None
    evidence: tuple[str, ...] = ()

    node_type: ClassVar[str] = "gene"

    @property
    def kind(self) -> str:
        return self.node_type

    def to_dict(self) -> dict[str, object]:
        return sgpr_to_dict(self)

    def __post_init__(self) -> None:
        object.__setattr__(self, "gene", str(self.gene).strip())
        object.__setattr__(self, "evidence", tuple(str(item) for item in self.evidence))


@dataclass(frozen=True)
class AndNode:
    children: tuple[SgprNode, ...]

    node_type: ClassVar[str] = "and"

    @property
    def kind(self) -> str:
        return self.node_type

    def to_dict(self) -> dict[str, object]:
        return sgpr_to_dict(self)

    def __post_init__(self) -> None:
        object.__setattr__(self, "children", tuple(self.children))


@dataclass(frozen=True)
class OrNode:
    children: tuple[SgprNode, ...]

    node_type: ClassVar[str] = "or"

    @property
    def kind(self) -> str:
        return self.node_type

    def to_dict(self) -> dict[str, object]:
        return sgpr_to_dict(self)

    def __post_init__(self) -> None:
        object.__setattr__(self, "children", tuple(self.children))


SgprNode = GeneNode | AndNode | OrNode


def validate_sgpr(node: SgprNode) -> None:
    """Raise ``ValueError`` when *node* is not a valid canonical expression."""
    if not isinstance(node, (GeneNode, AndNode, OrNode)):
        raise ValueError(f"unsupported sGPR node: {type(node).__name__}")
    if isinstance(node, GeneNode):
        if not node.gene:
            raise ValueError("gene nodes require a non-empty gene")
        if node.coefficient_status not in COEFFICIENT_STATUSES:
            raise ValueError(f"invalid coefficient status: {node.coefficient_status}")
        if node.coefficient is not None and (
            not isinstance(node.coefficient, int)
            or isinstance(node.coefficient, bool)
            or node.coefficient < 1
        ):
            raise ValueError("gene coefficients must be integers greater than zero")
        return
    if not node.children:
        raise ValueError("logical sGPR nodes require at least one child")
    for child in node.children:
        validate_sgpr(child)


def _semantic_key(node: SgprNode) -> tuple[object, ...]:
    if isinstance(node, GeneNode):
        return ("gene", node.gene, node.coefficient, node.coefficient_status)
    return (node.node_type, tuple(_semantic_key(child) for child in node.children))


def _ordering_key(node: SgprNode) -> tuple[object, ...]:
    """Order by genes first, so coefficient changes do not reshuffle branches."""
    if isinstance(node, GeneNode):
        return ((node.gene,), node.coefficient or 0, node.coefficient_status)
    return (genes_in_sgpr(node), _semantic_key(node))


def normalize_sgpr(node: SgprNode) -> SgprNode:
    """Flatten logical nodes and sort them deterministically.

    Repeated ``AND`` members are retained because they represent multiplicity;
    duplicate ``OR`` branches are removed.
    """
    validate_sgpr(node)
    if isinstance(node, GeneNode):
        return node
    children = tuple(normalize_sgpr(child) for child in node.children)
    flattened: list[SgprNode] = []
    for child in children:
        if isinstance(child, type(node)):
            flattened.extend(child.children)
        else:
            flattened.append(child)
    if isinstance(node, OrNode):
        unique: dict[tuple[object, ...], SgprNode] = {}
        for child in flattened:
            unique.setdefault(_semantic_key(child), child)
        flattened = list(unique.values())
    flattened.sort(key=_ordering_key)
    result = type(node)(tuple(flattened))
    validate_sgpr(result)
    return result


def _gene_text(
    node: GeneNode, *, stoich: bool, include_defaulted: bool, unknown_policy: str
) -> str:
    coefficient = node.coefficient
    if coefficient is None:
        if unknown_policy == "error":
            raise ValueError(f"unknown coefficient for {node.gene}")
        if unknown_policy == "default":
            coefficient = 1
        else:
            return node.gene
    if not stoich or (node.coefficient_status == "defaulted" and not include_defaulted):
        return node.gene
    return f"{node.gene}*{coefficient}"


def _render(
    node: SgprNode,
    *,
    stoich: bool,
    include_defaulted: bool,
    unknown_policy: str,
    legacy_gene_parens: bool = False,
) -> str:
    if isinstance(node, GeneNode):
        text = _gene_text(
            node,
            stoich=stoich,
            include_defaulted=include_defaulted,
            unknown_policy=unknown_policy,
        )
        return f"({text})" if legacy_gene_parens else text
    operator = " and " if isinstance(node, AndNode) else " or "
    parts = []
    for child in node.children:
        rendered = _render(
            child,
            stoich=stoich,
            include_defaulted=include_defaulted,
            unknown_policy=unknown_policy,
            legacy_gene_parens=legacy_gene_parens,
        )
        if isinstance(node, OrNode) and isinstance(child, AndNode):
            rendered = f"({rendered})"
        elif isinstance(node, AndNode) and isinstance(child, OrNode):
            rendered = f"({rendered})"
        parts.append(rendered)
    rendered = operator.join(parts)
    return (
        f"({rendered})"
        if isinstance(node, AndNode) and legacy_gene_parens and len(parts) > 1
        else rendered
    )


def to_gpr(node: SgprNode) -> str:
    """Serialize *node* as an ordinary Boolean GPR."""
    node = normalize_sgpr(node)
    return _render(node, stoich=False, include_defaulted=True, unknown_policy="omit")


def to_sgpr(
    node: SgprNode, *, include_defaulted: bool = True, unknown_policy: str = "omit"
) -> str:
    """Serialize *node* with coefficients when they are supported."""
    if unknown_policy not in {"omit", "default", "error"}:
        raise ValueError("unknown_policy must be 'omit', 'default', or 'error'")
    node = normalize_sgpr(node)
    return _render(
        node,
        stoich=True,
        include_defaulted=include_defaulted,
        unknown_policy=unknown_policy,
    )


def to_legacy_sgpr(node: SgprNode) -> str:
    """Serialize an sGPR using the historical ``*1`` compatibility default."""
    node = normalize_sgpr(node)

    def render(value: SgprNode) -> str:
        if isinstance(value, GeneNode):
            coefficient = value.coefficient if value.coefficient is not None else 1
            return f"({value.gene}*{coefficient})"
        operator = " and " if isinstance(value, AndNode) else " or "
        parts = [render(child) for child in value.children]
        if isinstance(value, AndNode):
            parts = [part[1:-1] if isinstance(child, GeneNode) else part
                     for child, part in zip(value.children, parts, strict=True)]
            return f"({operator.join(parts)})"
        return operator.join(parts)

    return render(node)


def default_sgpr_coefficients(node: SgprNode) -> SgprNode:
    """Materialize compatibility ``1`` values while marking them defaulted."""
    if isinstance(node, GeneNode):
        return (
            GeneNode(node.gene, 1, "defaulted", node.source, node.evidence)
            if node.coefficient is None
            else node
        )
    cls = AndNode if isinstance(node, AndNode) else OrNode
    return cls(tuple(default_sgpr_coefficients(child) for child in node.children))


def strip_stoichiometry(node: SgprNode) -> SgprNode:
    """Return the same logical expression without biological coefficients."""
    if isinstance(node, GeneNode):
        return GeneNode(node.gene, source=node.source, evidence=node.evidence)
    cls = AndNode if isinstance(node, AndNode) else OrNode
    return cls(tuple(strip_stoichiometry(child) for child in node.children))


def genes_in_sgpr(node: SgprNode) -> tuple[str, ...]:
    genes = (
        {node.gene}
        if isinstance(node, GeneNode)
        else {gene for child in node.children for gene in genes_in_sgpr(child)}
    )
    return tuple(sorted(genes))


def unambiguous_stoichiometry(node: SgprNode) -> dict[str, int] | None:
    """Derive the legacy flat mapping only for one enzyme branch."""
    node = normalize_sgpr(node)
    if isinstance(node, OrNode):
        return None
    leaves = (node,) if isinstance(node, GeneNode) else node.children
    result: dict[str, int] = {}
    for leaf in leaves:
        if (
            not isinstance(leaf, GeneNode)
            or leaf.gene in result
            or leaf.coefficient is None
        ):
            return None
        result[leaf.gene] = leaf.coefficient
    return result


def sgpr_to_dict(node: SgprNode) -> dict[str, object]:
    validate_sgpr(node)
    if isinstance(node, GeneNode):
        return {
            "type": "gene",
            "gene": node.gene,
            "coefficient": node.coefficient,
            "coefficient_status": node.coefficient_status,
            "source": node.source,
            "evidence": list(node.evidence),
        }
    return {
        "type": node.node_type,
        "children": [sgpr_to_dict(child) for child in node.children],
    }


def sgpr_from_dict(value: object) -> SgprNode:
    if not isinstance(value, dict):
        raise ValueError("sGPR structure must be an object")
    kind = str(value.get("type", value.get("kind", ""))).lower()
    if kind == "gene":
        coefficient = value.get("coefficient")
        if coefficient is not None:
            coefficient = int(coefficient)
        evidence = value.get("evidence", ())
        return GeneNode(
            str(value.get("gene", "")),
            coefficient,
            str(value.get("coefficient_status", "unknown")),
            value.get("source"),
            tuple(evidence) if isinstance(evidence, (list, tuple)) else (),
        )
    cls = {"and": AndNode, "or": OrNode}.get(kind)
    if cls is None or not isinstance(value.get("children"), list):
        raise ValueError("invalid sGPR structure")
    return cls(tuple(sgpr_from_dict(child) for child in value["children"]))


_TOKEN = re.compile(r"\s*(?:(and|or)\b|([A-Za-z0-9_.:-]+)|(\*)|([()])|([0-9]+))", re.I)


def parse_sgpr(expression: str) -> SgprNode:
    """Parse the small Boolean/coefficient syntax emitted by this module."""
    expression = str(expression).strip()
    tokens = []
    position = 0
    while position < len(expression):
        match = _TOKEN.match(expression, position)
        if not match:
            raise ValueError(f"invalid sGPR near {expression[position:]!r}")
        position = match.end()
        tokens.append(next(value for value in match.groups() if value is not None))
    index = 0

    def peek() -> str | None:
        return tokens[index] if index < len(tokens) else None

    def take(value: str | None = None) -> str:
        nonlocal index
        token = peek()
        if token is None or (value is not None and token.lower() != value.lower()):
            raise ValueError("invalid sGPR expression")
        index += 1
        return token

    def primary() -> SgprNode:
        if peek() == "(":
            take("(")
            result = disjunction()
            take(")")
        else:
            result = GeneNode(take())
        if peek() == "*":
            take("*")
            result = (
                GeneNode(result.gene, int(take()), "unknown")
                if isinstance(result, GeneNode)
                else result
            )
        return result

    def conjunction() -> SgprNode:
        values = [primary()]
        while peek() and peek().lower() == "and":
            take("and")
            values.append(primary())
        return values[0] if len(values) == 1 else AndNode(tuple(values))

    def disjunction() -> SgprNode:
        values = [conjunction()]
        while peek() and peek().lower() == "or":
            take("or")
            values.append(conjunction())
        return values[0] if len(values) == 1 else OrNode(tuple(values))

    result = disjunction()
    if index != len(tokens):
        raise ValueError("invalid trailing sGPR expression")
    return normalize_sgpr(result)


__all__ = [
    "AndNode",
    "COEFFICIENT_STATUSES",
    "default_sgpr_coefficients",
    "GeneNode",
    "OrNode",
    "SgprNode",
    "genes_in_sgpr",
    "normalize_sgpr",
    "parse_sgpr",
    "sgpr_from_dict",
    "sgpr_to_dict",
    "strip_stoichiometry",
    "to_gpr",
    "to_legacy_sgpr",
    "to_sgpr",
    "unambiguous_stoichiometry",
    "validate_sgpr",
]
