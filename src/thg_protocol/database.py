"""Package-owned reconstruction of normalized database records into COBRA."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MetaboliteRecord:
    """Normalized metabolite data consumed by :func:`reconstruct_model`."""

    id: str
    compartment: str = "c"
    name: str = ""
    formula: str | None = None
    charge: int | float | None = None
    annotation: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReactionRecord:
    """Normalized reaction data consumed by :func:`reconstruct_model`."""

    id: str
    stoichiometry: Mapping[str, float]
    name: str = ""
    lower_bound: float = -1000.0
    upper_bound: float = 1000.0
    gene_reaction_rule: str = ""
    annotation: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeneRecord:
    """Optional normalized gene annotation."""

    id: str
    name: str = ""
    annotation: Mapping[str, Any] = field(default_factory=dict)


def reconstruct_model(
    model_id: str,
    metabolites: Iterable[MetaboliteRecord],
    reactions: Iterable[ReactionRecord],
    genes: Iterable[GeneRecord] = (),
    *,
    model_name: str | None = None,
    pathways: Mapping[str, Iterable[str]] | None = None,
    output_path: str | Path | None = None,
) -> Any:
    """Build a COBRA model from explicit, normalized records.

    The function performs no network access and does not write a file unless
    ``output_path`` is supplied. A ``.json`` output uses COBRA JSON; all other
    suffixes use SBML. This is the reusable reconstruction core for the
    database/model-build workflows; service-backed record collection remains
    outside this function.
    """
    from cobra import Metabolite, Model, Reaction
    from cobra.io import save_json_model, write_sbml_model

    model = Model(model_id, model_name or model_id)
    metabolite_by_id: dict[str, Any] = {}
    for record in metabolites:
        if record.id in metabolite_by_id:
            raise ValueError(f"duplicate metabolite id: {record.id}")
        metabolite = Metabolite(
            record.id,
            name=record.name,
            formula=record.formula,
            charge=record.charge,
            compartment=record.compartment,
        )
        metabolite.annotation.update(dict(record.annotation))
        metabolite_by_id[record.id] = metabolite
    model.add_metabolites(list(metabolite_by_id.values()))

    for record in genes:
        if not record.id:
            raise ValueError("gene id must not be empty")
        gene = (
            model.genes.get_by_id(record.id)
            if model.genes.has_id(record.id)
            else None
        )
        if gene is None:
            from cobra.core import Gene

            gene = Gene(record.id, name=record.name)
            model.genes.append(gene)
        gene.name = record.name or gene.name
        gene.annotation.update(dict(record.annotation))

    pathways_by_reaction: dict[str, list[str]] = {}
    for pathway, reaction_ids in (pathways or {}).items():
        for reaction_id in reaction_ids:
            pathways_by_reaction.setdefault(reaction_id, []).append(pathway)

    for record in reactions:
        if record.id in model.reactions:
            raise ValueError(f"duplicate reaction id: {record.id}")
        reaction = Reaction(
            record.id,
            name=record.name,
            lower_bound=record.lower_bound,
            upper_bound=record.upper_bound,
        )
        missing = set(record.stoichiometry) - set(metabolite_by_id)
        if missing:
            raise KeyError(
                f"reaction {record.id} references unknown metabolites: "
                + ", ".join(sorted(missing))
            )
        reaction.add_metabolites(
            {
                metabolite_by_id[met_id]: coefficient
                for met_id, coefficient in record.stoichiometry.items()
            }
        )
        reaction.gene_reaction_rule = record.gene_reaction_rule
        reaction.annotation.update(dict(record.annotation))
        if record.id in pathways_by_reaction:
            reaction.annotation["pathway"] = pathways_by_reaction[record.id]
        model.add_reactions([reaction])

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".json":
            save_json_model(model, str(path))
        else:
            write_sbml_model(model, str(path))
    return model


def reconstruct_model_from_json(
    records_path: str | Path,
    *,
    output_path: str | Path | None = None,
) -> Any:
    """Reconstruct a model from one normalized JSON record bundle.

    The bundle has the following shape::

        {
          "model_id": "toy",
          "model_name": "Toy model",
          "metabolites": [{"id": "a_c", "compartment": "c"}],
          "reactions": [{"id": "R1", "stoichiometry": {"a_c": -1}}],
          "genes": [],
          "pathways": {"pathway-name": ["R1"]}
        }

    ``output_path`` is optional and, when supplied, overrides any output path
    in the bundle. Unknown top-level keys are ignored for forward-compatible
    record metadata.
    """
    path = Path(records_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("record bundle must be a JSON object")

    model_id = payload.get("model_id")
    if not isinstance(model_id, str) or not model_id:
        raise ValueError("record bundle requires a non-empty string 'model_id'")

    def records(name: str) -> list[Mapping[str, Any]]:
        value = payload.get(name, [])
        if not isinstance(value, list) or not all(
            isinstance(item, Mapping) for item in value
        ):
            raise ValueError(f"record bundle field '{name}' must be a list of objects")
        return value

    metabolites = [MetaboliteRecord(**dict(item)) for item in records("metabolites")]
    reactions = [ReactionRecord(**dict(item)) for item in records("reactions")]
    genes = [GeneRecord(**dict(item)) for item in records("genes")]
    pathways = payload.get("pathways", {})
    if not isinstance(pathways, Mapping):
        raise ValueError("record bundle field 'pathways' must be an object")

    return reconstruct_model(
        model_id,
        metabolites,
        reactions,
        genes,
        model_name=payload.get("model_name"),
        pathways=pathways,
        output_path=output_path,
    )


def reconstruct_model_with_services(
    model_id: str,
    metabolites: Iterable[MetaboliteRecord],
    reactions: Iterable[ReactionRecord],
    genes: Iterable[GeneRecord] = (),
    *,
    model_name: str | None = None,
    pathways: Mapping[str, Iterable[str]] | None = None,
    output_path: str | Path | None = None,
    biocyc_client: Any | None = None,
    kegg_client: Any | None = None,
    ensembl_client: Any | None = None,
) -> Any:
    """Collect optional service annotations before reconstructing a model.

    Records remain the workflow's explicit input boundary.  KEGG reaction
    entries are attached to reactions carrying ``kegg.reaction`` identifiers,
    BioCyc EC pages are attached to reactions carrying ``ec-code``, and
    Ensembl annotations are attached to supplied gene records.  Callers can
    inject static clients for offline execution; production clients are
    created lazily only when matching records require them.

    The deterministic model construction and output behavior are delegated to
    :func:`reconstruct_model`.
    """
    metabolite_records = list(metabolites)
    reaction_records = list(reactions)
    gene_records = list(genes)

    def values(annotation: Mapping[str, Any], key: str) -> list[str]:
        raw = annotation.get(key)
        if raw is None:
            return []
        if isinstance(raw, (list, tuple, set)):
            return [str(item).strip() for item in raw if str(item).strip()]
        value = str(raw).strip()
        return [value] if value else []

    reaction_kegg_ids = [
        identifier
        for record in reaction_records
        for identifier in values(record.annotation, "kegg.reaction")
    ]
    if reaction_kegg_ids:
        if kegg_client is None:
            from thg_protocol.services.kegg import KeggClient

            kegg_client = KeggClient()
        entries = kegg_client.get_reaction_entries(dict.fromkeys(reaction_kegg_ids))
        enriched_reactions: list[ReactionRecord] = []
        for record in reaction_records:
            annotation = dict(record.annotation)
            ids = values(annotation, "kegg.reaction")
            found = {
                identifier: entries[identifier]
                for identifier in ids
                if identifier in entries
            }
            if found:
                annotation["kegg.reaction.entry"] = json.dumps(
                    found, sort_keys=True
                )
            enriched_reactions.append(replace(record, annotation=annotation))
        reaction_records = enriched_reactions

    reaction_ec_ids = [
        identifier
        for record in reaction_records
        for identifier in values(record.annotation, "ec-code")
    ]
    if reaction_ec_ids:
        if biocyc_client is None:
            from thg_protocol.services.biocyc import BioCycClient

            biocyc_client = BioCycClient()
        enriched_reactions = []
        for record in reaction_records:
            annotation = dict(record.annotation)
            pages = {
                identifier: biocyc_client.get_ec_html(identifier)
                for identifier in values(annotation, "ec-code")
            }
            pages = {identifier: page for identifier, page in pages.items() if page}
            if pages:
                annotation["biocyc.ec.html"] = json.dumps(pages, sort_keys=True)
            enriched_reactions.append(replace(record, annotation=annotation))
        reaction_records = enriched_reactions

    gene_ids = [record.id for record in gene_records if record.id]
    if gene_ids:
        if ensembl_client is None:
            from thg_protocol.services.ensembl import EnsemblClient

            ensembl_client = EnsemblClient()
        annotations = ensembl_client.annotate(gene_ids)
        gene_records = [
            replace(
                record,
                annotation={
                    **dict(record.annotation),
                    **(
                        {
                            key: value
                            for key, value in annotations[record.id]
                            .as_dict()
                            .items()
                            if value is not None
                        }
                        if record.id in annotations
                        else {}
                    ),
                },
            )
            for record in gene_records
        ]

    return reconstruct_model(
        model_id,
        metabolite_records,
        reaction_records,
        gene_records,
        model_name=model_name,
        pathways=pathways,
        output_path=output_path,
    )


__all__ = [
    "GeneRecord",
    "MetaboliteRecord",
    "ReactionRecord",
    "reconstruct_model",
    "reconstruct_model_from_json",
    "reconstruct_model_with_services",
]
