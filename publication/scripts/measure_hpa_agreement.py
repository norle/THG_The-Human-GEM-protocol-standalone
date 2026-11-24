"""Compare gene-to-compartment assignments in models with the Human Protein Atlas.

Usage (conda env thg_standalone):
    python publication/scripts/measure_hpa_agreement.py \
        --model baseline=runs/human211-patched/Human_211_patched.xml \
        --model thg-b=runs/thg-ws1-b/artifacts/export-reference/attempt-0002/thg-reference.json

HPA subcellular locations (``publication/ws2/hpa/source``) are mapped to the
THG compartments with the same GO resolver the pipeline uses
(``thg_protocol.curation.go.resolve_go_compartment``), the GO release pinned
in ``publication/ws1/frozen/sources/compartment-registry.json`` and the
compartment/GO tables of that registry. A model's compartments for a gene are
the compartments of its single-compartment (non-transport) reactions.
Reliability ``Uncertain`` HPA records are excluded unless --keep-uncertain.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import cobra

from thg_protocol.curation.go import load_obo, resolve_go_compartment

ROOT = Path(__file__).resolve().parents[2]
HPA_DIR = ROOT / "publication/ws2/hpa"
REGISTRY = ROOT / "publication/ws1/frozen/sources/compartment-registry.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hpa_locations(registry, graph, keep_uncertain):
    """Return {gene: set(compartment keys)}, plus mapping statistics."""
    terms = registry["compartment_go_terms"]
    aliases = registry.get("compartment_go_aliases", {})
    names = registry["compartments"]
    cache: dict[tuple[str, str], list[str]] = {}
    genes: dict[str, dict] = {}
    unmapped = Counter()
    mapped_terms = Counter()
    path = HPA_DIR / "source/subcellular_location.tsv"
    with path.open() as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            if row["Reliability"] == "Uncertain" and not keep_uncertain:
                continue
            found: set[str] = set()
            entries = [x for x in row["GO id"].split(";") if x.strip()]
            for entry in entries:
                label, _, go = entry.rpartition(" (")
                go = go.rstrip(")")
                key = (label, go)
                if key not in cache:
                    result = resolve_go_compartment(
                        label, go, graph, terms, names, aliases
                    )
                    ok = result.get("status") != "rejected"
                    cache[key] = (
                        list(result.get("target_compartment_ids", [])) if ok else []
                    )
                keys = cache[key]
                if keys:
                    found.update(keys)
                    mapped_terms[label] += 1
                else:
                    unmapped[label] += 1
            genes[row["Gene"]] = {
                "name": row["Gene name"],
                "reliability": row["Reliability"],
                "compartments": found,
                "n_locations": len(entries),
            }
    return genes, mapped_terms, unmapped, cache


def model_locations(model):
    """{gene: set(compartments)} from single-compartment reactions."""
    out: dict[str, set[str]] = {}
    for reaction in model.reactions:
        comps = {m.compartment for m in reaction.metabolites}
        if len(comps) != 1 or not reaction.genes:
            continue
        for gene in reaction.genes:
            out.setdefault(gene.id, set()).update(comps)
    return out


def compare(hpa, locations, only=None):
    rows = []
    for gene, comps in sorted(locations.items()):
        record = hpa.get(gene)
        if not record:
            continue
        h = record["compartments"] if only is None else (
            record["compartments"] & only)
        m = comps if only is None else (comps & only)
        if not h or not m:
            continue
        rows.append(
            {
                "gene": gene,
                "gene_name": record["name"],
                "hpa_reliability": record["reliability"],
                "hpa": ";".join(sorted(h)),
                "model": ";".join(sorted(m)),
                "exact": h == m,
                "any_overlap": bool(h & m),
                "model_subset_of_hpa": m <= h,
                "jaccard": round(len(h & m) / len(h | m), 4),
            }
        )
    return rows


def summarize(rows):
    n = len(rows)
    if not n:
        return {"genes": 0}
    return {
        "genes": n,
        "exact_match": sum(r["exact"] for r in rows),
        "any_overlap": sum(r["any_overlap"] for r in rows),
        "model_subset_of_hpa": sum(r["model_subset_of_hpa"] for r in rows),
        "mean_jaccard": round(sum(r["jaccard"] for r in rows) / n, 4),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", required=True,
                        help="LABEL=PATH (repeatable)")
    parser.add_argument("--keep-uncertain", action="store_true")
    parser.add_argument("--out", default=str(HPA_DIR / "results"))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    registry = json.loads(REGISTRY.read_text())
    graph = load_obo(HPA_DIR / "go/go-basic.obo")
    hpa, mapped, unmapped, _ = hpa_locations(registry, graph, args.keep_uncertain)

    summary = {
        "hpa_file": "publication/ws2/hpa/source/subcellular_location.tsv",
        "hpa_zip_sha256": sha256(HPA_DIR / "source/subcellular_location.tsv.zip"),
        "go_obo_sha256": sha256(HPA_DIR / "go/go-basic.obo"),
        "keep_uncertain": args.keep_uncertain,
        "hpa_genes_used": len(hpa),
        "hpa_genes_with_mapped_compartment": sum(
            bool(v["compartments"]) for v in hpa.values()),
        "hpa_terms_unmapped": unmapped.most_common(15),
        "hpa_terms_mapped": mapped.most_common(15),
        "code_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "script_sha256": sha256(Path(__file__)),
        "models": {},
    }
    loaded = {}
    for spec in args.model:
        label, _, path = spec.partition("=")
        model_path = ROOT / path
        model = (cobra.io.load_json_model(str(model_path))
                 if model_path.suffix == ".json"
                 else cobra.io.read_sbml_model(str(model_path)))
        loaded[label] = (model_path, model_locations(model), set(model.compartments))
    shared = set.intersection(*(c for _, _, c in loaded.values()))
    summary["shared_compartments"] = sorted(shared)
    for label, (model_path, locations, comps) in loaded.items():
        rows_all = compare(hpa, locations)
        rows_shared = compare(hpa, locations, shared)
        with (out / f"gene_agreement_{label}.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows_all[0]))
            writer.writeheader()
            writer.writerows(rows_all)
        summary["models"][label] = {
            "path": str(model_path.relative_to(ROOT)),
            "sha256": sha256(model_path),
            "compartments": sorted(comps),
            "genes_with_single_compartment_reactions": len(locations),
            "all_compartments": summarize(rows_all),
            "shared_compartments_only": summarize(rows_shared),
        }
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("hpa_terms_unmapped", "hpa_terms_mapped")},
                     indent=1))
    print("unmapped HPA terms:", summary["hpa_terms_unmapped"])


if __name__ == "__main__":
    main()
