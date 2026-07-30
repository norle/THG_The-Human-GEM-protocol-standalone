"""Dependency-light transcriptomics and gene-annotation transformations.

These helpers operate on model-like objects and annotation XML only.  They do
not load COBRA, expression matrices, solvers, or repository-local files;
solver-backed transcriptomics workflows can compose them explicitly.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

RDF_NAMESPACE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


def extract_sgpr_rules(model: Any) -> list[str | None]:
    """Extract the final component of each reaction's ``sGPR`` annotation."""
    rules: list[str | None] = []
    for reaction in model.reactions:
        rule = None
        for key, resources in getattr(reaction, "annotation", {}).items():
            if "sGPR" not in key:
                continue
            if isinstance(resources, (list, tuple)):
                resources = resources[-1] if resources else ""
            rule = str(resources).rsplit("/", 1)[-1]
        rules.append(rule)
    return rules


def extract_ensembl_ids(model: Any) -> list[str]:
    """Extract ``ENSG`` identifiers from model genes in model order."""
    pattern = re.compile(r"ENSG\d+")
    return [
        match.group(0) if (match := pattern.search(gene.id)) else ""
        for gene in model.genes
    ]


def replace_index_tokens(model: Any, ensembl_ids: Sequence[str]) -> list[str]:
    """Replace ``x(index)`` GPR tokens with corresponding Ensembl IDs."""
    rules: list[str] = []
    for reaction in model.reactions:
        rule = reaction.gene_reaction_rule

        def replacement(match: re.Match[str]) -> str:
            index = int(match.group(1))
            identifier = ensembl_ids[index] if index < len(ensembl_ids) else ""
            return f"({identifier})"

        rules.append(re.sub(r"x\((\d+)\)", replacement, rule).strip())
    return rules


def extract_gene_annotation_pairs(model_path: str | Path) -> dict[str, str | list[str]]:
    """Read HGNC-symbol/Ensembl pairs from RDF annotation resources.

    Duplicate symbols retain all distinct Ensembl IDs in encounter order.
    Both historical ``hgnc.symbol`` and misspelled ``hgcn.symbol`` resources
    are accepted for compatibility.
    """
    root = ET.parse(model_path).getroot()
    resource_key = f"{{{RDF_NAMESPACE}}}resource"
    pairs: dict[str, str | list[str]] = {}
    for description in root.findall(f".//{{{RDF_NAMESPACE}}}Description"):
        symbol = ""
        ensembl = ""
        for item in description.findall(f".//{{{RDF_NAMESPACE}}}li"):
            resource = item.get(resource_key, "")
            if "hgnc.symbol/" in resource or "hgcn.symbol/" in resource:
                symbol = resource.rsplit("/", 1)[-1]
            elif "ensembl/ENSG" in resource:
                ensembl = resource.rsplit("/", 1)[-1]
        if not symbol or not ensembl:
            continue
        current = pairs.get(symbol)
        if current is None:
            pairs[symbol] = ensembl
        elif current == ensembl:
            continue
        elif isinstance(current, list):
            if ensembl not in current:
                current.append(ensembl)
        else:
            pairs[symbol] = [current, ensembl]
    return pairs


def replace_gene_symbols(
    model: Any, gene_mapping: Mapping[str, str | Sequence[str]]
) -> list[str]:
    """Replace gene symbols in model GPR rules with Ensembl identifiers."""
    values = {
        value
        for mapped in gene_mapping.values()
        for value in (mapped if isinstance(mapped, (list, tuple)) else [mapped])
    }
    output: list[str] = []
    for reaction in model.reactions:
        rule = reaction.gene_reaction_rule
        for gene in re.findall(r"\w+", rule):
            if gene in {"and", "or"} or gene.startswith("ENSG") or gene in values:
                continue
            mapped = gene_mapping.get(gene)
            replacement = mapped[0] if isinstance(mapped, (list, tuple)) else mapped
            rule = re.sub(rf"\b{re.escape(gene)}\b", replacement or "", rule)
        output.append(rule.strip())
    return output


__all__ = [
    "extract_ensembl_ids",
    "extract_gene_annotation_pairs",
    "extract_sgpr_rules",
    "replace_gene_symbols",
    "replace_index_tokens",
]
