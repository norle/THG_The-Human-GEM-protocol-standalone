"""Package-native model-file annotation and reconstruction workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ModelBuildReport:
    """Outcome of :func:`build_model`.

    Counts describe annotations applied to the model.  Errors are collected
    per service so a report can be written even when one optional lookup fails.
    """

    input_path: Path
    output_path: Path
    cache_dir: Path
    kegg_reactions: int = 0
    biocyc_ec_pages: int = 0
    ensembl_genes: int = 0
    errors: list[str] = field(default_factory=list)


def _identifiers(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = [value]
    result: list[str] = []
    for item in values:
        identifier = str(item).strip()
        if ":" in identifier:
            identifier = identifier.rsplit(":", 1)[-1]
        if identifier and identifier not in result:
            result.append(identifier)
    return result


def _load_json_cache(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _save_json_cache(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build_model(
    input_path: str | Path,
    output_path: str | Path,
    *,
    cache_dir: str | Path | None = None,
    errors_path: str | Path | None = None,
    biocyc_client: Any | None = None,
    kegg_client: Any | None = None,
    ensembl_client: Any | None = None,
) -> ModelBuildReport:
    """Annotate an existing COBRA model through injectable service clients.

    The workflow is deliberately explicit about all filesystem outputs.  It
    preserves the model's reactions and stoichiometry, enriching reaction
    annotations from KEGG/BioCyc and gene annotations from Ensembl.  Service
    clients are instantiated lazily only when a matching annotation exists,
    which keeps empty/toy models fully offline and testable.
    """
    from cobra import io

    source = Path(input_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    cache_root = (
        Path(cache_dir) if cache_dir is not None else destination.parent / "cache"
    )
    cache_root.mkdir(parents=True, exist_ok=True)
    error_file = Path(errors_path) if errors_path is not None else None
    if error_file is not None:
        error_file.parent.mkdir(parents=True, exist_ok=True)

    model = (
        io.read_sbml_model(str(source))
        if source.suffix.lower() != ".json"
        else io.load_json_model(str(source))
    )
    report = ModelBuildReport(source, destination, cache_root)

    kegg_cache_path = cache_root / "kegg_reaction_entries.json"
    kegg_cache = _load_json_cache(kegg_cache_path)
    kegg_ids = [
        identifier
        for reaction in model.reactions
        for identifier in _identifiers(reaction.annotation.get("kegg.reaction"))
    ]
    missing_kegg = [
        identifier
        for identifier in dict.fromkeys(kegg_ids)
        if identifier not in kegg_cache
    ]
    if missing_kegg:
        try:
            if kegg_client is None:
                from thg_protocol.services.kegg import KeggClient

                kegg_client = KeggClient()
            kegg_cache.update(kegg_client.get_reaction_entries(missing_kegg))
        except Exception as error:  # pragma: no cover - depends on live service
            report.errors.append(f"KEGG: {error}")
    for reaction in model.reactions:
        identifiers = _identifiers(reaction.annotation.get("kegg.reaction"))
        entries = {
            identifier: kegg_cache[identifier]
            for identifier in identifiers
            if identifier in kegg_cache
        }
        if entries:
            reaction.annotation["kegg.reaction.entry"] = json.dumps(
                entries, sort_keys=True
            )
            report.kegg_reactions += 1
    _save_json_cache(kegg_cache_path, kegg_cache)

    biocyc_cache_path = cache_root / "biocyc_ec_pages.json"
    biocyc_cache = _load_json_cache(biocyc_cache_path)
    ec_ids = [
        identifier
        for reaction in model.reactions
        for identifier in _identifiers(reaction.annotation.get("ec-code"))
    ]
    missing_ec = [
        identifier
        for identifier in dict.fromkeys(ec_ids)
        if identifier not in biocyc_cache
    ]
    if missing_ec:
        try:
            if biocyc_client is None:
                from thg_protocol.services.biocyc import BioCycClient

                biocyc_client = BioCycClient()
            for identifier in missing_ec:
                page = biocyc_client.get_ec_html(identifier)
                if page:
                    biocyc_cache[identifier] = page
        except Exception as error:  # pragma: no cover - depends on live service
            report.errors.append(f"BioCyc: {error}")
    for reaction in model.reactions:
        pages = {
            identifier: biocyc_cache[identifier]
            for identifier in _identifiers(reaction.annotation.get("ec-code"))
            if identifier in biocyc_cache
        }
        if pages:
            reaction.annotation["biocyc.ec.html"] = json.dumps(pages, sort_keys=True)
            report.biocyc_ec_pages += 1
    _save_json_cache(biocyc_cache_path, biocyc_cache)

    ensembl_cache_path = cache_root / "ensembl_annotations.json"
    ensembl_cache = _load_json_cache(ensembl_cache_path)
    gene_ids = [gene.id for gene in model.genes if gene.id]
    missing_genes = [
        identifier for identifier in gene_ids if identifier not in ensembl_cache
    ]
    if missing_genes:
        try:
            if ensembl_client is None:
                from thg_protocol.services.ensembl import EnsemblClient

                ensembl_client = EnsemblClient()
            annotations = ensembl_client.annotate(missing_genes)
            for identifier, annotation in annotations.items():
                ensembl_cache[identifier] = {
                    key: value
                    for key, value in annotation.as_dict().items()
                    if value is not None
                }
        except Exception as error:  # pragma: no cover - depends on live service
            report.errors.append(f"Ensembl: {error}")
    for gene in model.genes:
        annotation = ensembl_cache.get(gene.id)
        if annotation:
            gene.annotation.update(annotation)
            report.ensembl_genes += 1
    _save_json_cache(ensembl_cache_path, ensembl_cache)

    if destination.suffix.lower() == ".json":
        io.save_json_model(model, str(destination))
    else:
        io.write_sbml_model(model, str(destination))
    if error_file is not None:
        error_file.write_text(
            json.dumps(report.errors, indent=2) + "\n", encoding="utf-8"
        )
    return report


def __getattr__(name: str) -> Any:
    if name == "build_model_batch":
        from .batch import build_model_batch

        return build_model_batch
    raise AttributeError(name)


__all__ = ["ModelBuildReport", "build_model", "build_model_batch"]
