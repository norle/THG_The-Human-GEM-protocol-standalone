"""Package-owned reconstruction of normalized database records into COBRA."""

from __future__ import annotations

import json
import pickle
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BiocycCompartmentSummary:
    """Resolved compartment names derived from BioCyc location caches."""

    entry_count: int
    frameid_count: int
    resolved_count: int
    resolved: Mapping[str, str]
    unique_names: tuple[str, ...]
    sample: tuple[tuple[str, tuple[Mapping[str, Any], ...]], ...]


def summarize_biocyc_compartments(
    biocyc_locations: Mapping[str, Any],
    compartment_names: Mapping[str, Any],
    *,
    sample_size: int = 10,
) -> BiocycCompartmentSummary:
    """Resolve BioCyc frame IDs without reading files or printing output.

    ``biocyc_locations`` maps identifiers to lists of location dictionaries;
    each location may contain ``orgid`` and ``frameid``.  Missing names fall
    back to the frame ID, matching the historical report behavior.
    """
    if sample_size < 0:
        raise ValueError("sample_size must be non-negative")
    frameids: set[tuple[str, str]] = set()
    for locations in biocyc_locations.values():
        if not isinstance(locations, list):
            continue
        for location in locations:
            if not isinstance(location, Mapping):
                continue
            frameid = location.get("frameid")
            if frameid:
                frameids.add((str(location.get("orgid") or "HUMAN"), str(frameid)))

    resolved = {
        f"{org}:{frameid}": str(compartment_names.get(f"{org}:{frameid}") or frameid)
        for org, frameid in sorted(frameids)
    }
    samples: list[tuple[str, tuple[Mapping[str, Any], ...]]] = []
    if sample_size == 0:
        return BiocycCompartmentSummary(
            entry_count=len(biocyc_locations),
            frameid_count=len(frameids),
            resolved_count=len(set(resolved.values())),
            resolved=resolved,
            unique_names=tuple(sorted(set(resolved.values()))),
            sample=(),
        )
    for identifier, locations in sorted(biocyc_locations.items()):
        if not isinstance(locations, list) or not locations:
            continue
        valid = tuple(item for item in locations if isinstance(item, Mapping))
        if valid:
            samples.append((str(identifier), valid))
        if len(samples) >= sample_size:
            break
    return BiocycCompartmentSummary(
        entry_count=len(biocyc_locations),
        frameid_count=len(frameids),
        resolved_count=len(set(resolved.values())),
        resolved=resolved,
        unique_names=tuple(sorted(set(resolved.values()))),
        sample=tuple(samples),
    )


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

    # Historical database reconstruction represented pathways as COBRA groups.
    # Retain that structure for callers of the legacy-pickle compatibility API,
    # while also keeping the reaction-level annotation above useful to generic
    # model consumers.
    if pathways:
        from cobra.core import Group

        for pathway, reaction_ids in pathways.items():
            group = Group(str(pathway), name=str(pathway))
            model.add_groups([group])
            members = [
                model.reactions.get_by_id(reaction_id)
                for reaction_id in reaction_ids
                if model.reactions.has_id(reaction_id)
            ]
            group.add_members(members)

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


def _record_value(record: Any, name: str, default: Any = None) -> Any:
    """Read a field from either a mapping or a legacy record object."""
    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def _record_call(record: Any, name: str, default: Any = None) -> Any:
    value = _record_value(record, name, default)
    return value() if callable(value) else value


def _pickle_items(value: Any) -> list[tuple[Any, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return list(value.items())
    return list(enumerate(value))


def reconstruct_model_from_pickle(
    records_path: str | Path,
    *,
    output_path: str | Path | None = None,
) -> Any:
    """Reconstruct a model from the legacy database-generator pickle.

    The supported bundle is a mapping with ``name``/``id``, ``loc``,
    ``mets_cl`` (or ``mets``), ``reactions_cl`` (or ``reactions``), ``genes``,
    and ``pathways`` keys. Compound records use ``ID2``, ``Subcel``, ``Name``,
    ``Formula1``, and ``charge``. Reaction records use ``ID``, ``Name``,
    ``subs``/``prods`` (or callable ``Substrate``/``Product``), ``GPR``, and
    ``EC``. This adapter performs no network access; service enrichment remains
    available through :func:`reconstruct_model_with_services`.

    Standard pickle is attempted first. Pickles created with the historical
    ``dill`` workflow require ``dill`` to be installed and are loaded through
    it as a compatibility fallback.
    """
    path = Path(records_path)
    try:
        with path.open("rb") as handle:
            payload = pickle.load(handle)
    except Exception as pickle_error:
        try:
            import dill
        except ImportError as error:  # pragma: no cover - optional dependency
            raise ValueError(
                "could not load pickle; install dill for historical database "
                "pickles"
            ) from pickle_error
        try:
            with path.open("rb") as handle:
                payload = dill.load(handle)
        except Exception as error:
            raise ValueError(f"could not load database pickle: {path}") from error

    if not isinstance(payload, Mapping):
        raise ValueError("database pickle must contain a mapping")

    raw_model_id = str(payload.get("id") or payload.get("model_id") or "")
    model_name = str(payload.get("name") or payload.get("model_name") or "")
    if not raw_model_id:
        raise ValueError("database pickle requires a non-empty 'id' or 'model_id'")
    # The generator historically stored the output filename in ``id``. COBRA
    # model IDs must be stable identifiers, not absolute paths or XML names.
    model_id = (
        Path(raw_model_id).stem
        if "/" in raw_model_id or "\\" in raw_model_id
        else raw_model_id.removesuffix(".xml")
    )
    model_name = model_name or model_id

    locations = payload.get("loc") or payload.get("locations") or {}
    location_map = {str(key).lower(): str(value) for key, value in locations.items()}

    def compartment(value: Any) -> str:
        raw = str(value or "c")
        return location_map.get(raw.lower(), raw)

    def with_compartment(identifier: Any, value: Any) -> str:
        base = str(identifier)
        comp = compartment(value)
        return base if base.endswith(f"_{comp}") else f"{base}_{comp}"

    metabolite_records: list[MetaboliteRecord] = []
    metabolite_ids: dict[str, str] = {}
    source_mets = payload.get("mets_cl") or payload.get("metabolites") or payload.get(
        "mets", {}
    )
    for source_key, record in _pickle_items(source_mets):
        base_id = _record_value(record, "ID2") or _record_value(record, "id")
        base_id = base_id or source_key
        source_compartment = _record_value(record, "Subcel", "c")
        metabolite_id = with_compartment(base_id, source_compartment)
        annotation_names = {
            "pubchem.compound": "PubChem",
            "chebi.compound": "CheBI",
            "glycomedb": "GlyDB",
            "jcggdb": "JCGGDB",
            "inchi": "inchi",
            "inchikey": "inchikey",
            "lipidbank": "LipidBank",
            "lipidmaps": "LIPIDMAPS",
        }
        annotation = {
            target: value
            for target, source in annotation_names.items()
            if (value := _record_value(record, source)) not in (None, "", [])
        }
        metabolite_records.append(
            MetaboliteRecord(
                metabolite_id,
                compartment=compartment(source_compartment),
                name=str(_record_call(record, "Name", "") or ""),
                formula=_record_value(record, "Formula1"),
                charge=_record_value(record, "charge"),
                annotation=annotation,
            )
        )
        metabolite_ids[str(source_key)] = metabolite_id
        metabolite_ids[str(base_id)] = metabolite_id

    known_metabolite_ids = {record.id for record in metabolite_records}

    def compounds(record: Any, method: str, fallback: str) -> list[Any]:
        values = _record_call(record, method)
        if values is None:
            values = _record_value(record, fallback, [])
        return list(values or [])

    reaction_records: list[ReactionRecord] = []
    source_rxns = payload.get("reactions_cl") or payload.get("reactions") or {}
    for source_key, record in _pickle_items(source_rxns):
        source_id = _record_value(record, "ID", source_key)
        reaction_id = str(source_id)
        reaction_compartment = "c"
        if "_" in reaction_id:
            reaction_base, suffix = reaction_id.rsplit("_", 1)
            reaction_compartment = compartment(suffix)
            reaction_id = with_compartment(reaction_base, suffix)
        stoichiometry: dict[str, float] = {}
        for sign, values in (
            (-1.0, compounds(record, "Substrate", "subs")),
            (1.0, compounds(record, "Product", "prods")),
        ):
            for item in values:
                if not isinstance(item, (list, tuple)) or len(item) < 2:
                    raise ValueError(f"invalid compound entry in reaction {source_id}")
                coefficient = abs(float(item[0])) * sign
                source_metabolite = item[2] if len(item) > 2 else item[1]
                metabolite_id = metabolite_ids.get(str(source_metabolite))
                if metabolite_id is None:
                    metabolite_id = with_compartment(
                        source_metabolite, reaction_compartment
                    )
                if metabolite_id not in known_metabolite_ids:
                    # The historical reconstruction created a minimal
                    # metabolite when a reaction referenced a compound absent
                    # from the compartmentalized metabolite list. Preserve
                    # that compatibility behavior instead of rejecting an
                    # otherwise usable checkpoint.
                    metabolite_records.append(
                        MetaboliteRecord(
                            metabolite_id,
                            compartment=reaction_compartment,
                        )
                    )
                    known_metabolite_ids.add(metabolite_id)
                stoichiometry[metabolite_id] = (
                    stoichiometry.get(metabolite_id, 0.0) + coefficient
                )
        raw_gpr = _record_call(record, "GPR", ("", "")) or ("", "")
        if isinstance(raw_gpr, (list, tuple)):
            s_gpr = str(raw_gpr[0]) if raw_gpr else ""
            gene_rule = str(raw_gpr[1]) if len(raw_gpr) > 1 else ""
        else:
            s_gpr, gene_rule = "", str(raw_gpr)
        gene_rule = gene_rule.replace("[", "").replace("]", "")
        raw_ec = _record_call(record, "EC", []) or []
        ec = raw_ec[0] if isinstance(raw_ec, (list, tuple)) and raw_ec else raw_ec
        annotation = {"ec-code": ec} if ec else {}
        if s_gpr and s_gpr != "[]":
            annotation["sGPR"] = s_gpr
        reaction_records.append(
            ReactionRecord(
                reaction_id,
                stoichiometry,
                name=str(_record_call(record, "Name", "") or ""),
                lower_bound=0.0 if bool(_record_call(record, "Termodyn", False)) else -1000.0,
                gene_reaction_rule=gene_rule,
                annotation=annotation,
            )
        )

    gene_records = []
    for source_key, record in _pickle_items(payload.get("genes", {})):
        gene_id = str(source_key)
        gene_records.append(
            GeneRecord(
                gene_id,
                name=str(_record_call(record, "Name", "") or ""),
                annotation={
                    key: value
                    for key, source in (
                        ("ncbigene", "Entrez"),
                        ("uniprot", "Uniprot"),
                    )
                    if (value := _record_call(record, source)) not in (None, "", [])
                },
            )
        )

    reaction_ids = {record.id for record in reaction_records}
    pathways: dict[str, list[str]] = {}
    for pathway, members in (payload.get("pathways", {}) or {}).items():
        values = str(members).split() if isinstance(members, str) else list(members)
        normalized_members: list[str] = []
        for value in values:
            member = str(value)
            if member not in reaction_ids:
                candidates = [
                    reaction_id
                    for reaction_id in reaction_ids
                    if reaction_id == f"{member}_c"
                    or reaction_id.startswith(f"{member}_")
                ]
                member = candidates[0] if len(candidates) == 1 else member
            normalized_members.append(member)
        pathways[str(pathway)] = normalized_members

    return reconstruct_model(
        model_id,
        metabolite_records,
        reaction_records,
        gene_records,
        model_name=model_name,
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
    "BiocycCompartmentSummary",
    "GeneRecord",
    "MetaboliteRecord",
    "ReactionRecord",
    "reconstruct_model",
    "reconstruct_model_from_json",
    "reconstruct_model_from_pickle",
    "reconstruct_model_with_services",
    "summarize_biocyc_compartments",
]
