"""Basic structural statistics for one model. Usage: model_stats.py MODEL LABEL OUT.csv"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
import csv, hashlib, sys, warnings
import cobra

path, label, out = sys.argv[1:4]
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    m = cobra.io.load_json_model(path) if path.endswith(".json") else cobra.io.read_sbml_model(path)
subs = {r.subsystem for r in m.reactions if r.subsystem}
ann = lambda objs, keys: sum(1 for o in objs if any(k in o.annotation for k in keys)) / max(len(objs), 1)
row = {
    "model": label, "sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(),
    "reactions": len(m.reactions), "metabolites": len(m.metabolites), "genes": len(m.genes),
    "compartments": len(m.compartments), "subsystems": len(subs),
    "exchange_reactions": len(m.exchanges), "boundary_reactions": len(m.boundary),
    "met_xref_fraction": round(ann(m.metabolites, [k for k in {k for x in m.metabolites for k in x.annotation} if k not in ("sbo",)]), 4),
    "rxn_xref_fraction": round(ann(m.reactions, [k for k in {k for x in m.reactions for k in x.annotation} if k not in ("sbo",)]), 4),
    "gene_xref_fraction": round(ann(m.genes, [k for k in {k for x in m.genes for k in x.annotation} if k not in ("sbo",)]), 4),
    "sbml_warnings": len(w),
}
with open(out, "w", newline="") as fh:
    wr = csv.DictWriter(fh, fieldnames=list(row)); wr.writeheader(); wr.writerow(row)
print(row)
