# SBML and JSON consistency on rebuilt B

Both exports have the same reaction, metabolite and boundary reaction IDs, and exact reaction stoichiometry. Both fail the direct MEMOTE LP without the pipeline's curated exclusions.

The native curated JSON check passes with 66 exclusions. Native SBML fails with two. The 64 additional JSON exclusions are reactions in the Artificial reactions or Pool reactions subsystems. The B SBML export lacks those subsystem labels. Both curated checks pass when the same exclusions are applied. The configured candidate check in the matched validation supplies the 64 pseudo-subsystem IDs explicitly. MEMOTE benchmark output is reported separately under its own settings.

```sh
B=runs/thg-ws1-b/artifacts/export-reference/attempt-0002/thg-reference
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
python -c 'import gurobipy,runpy,sys; gurobipy.setParam("Threads",2); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name="__main__")' publication/scripts/check_sbml_json_consistency.py "$B.json" "$B.xml" publication/ws4/consistency/rebuilt-b-raw.json
python -c 'import runpy,sys; runpy.run_path("publication/ws1/run_build.py")["pin_solver"](); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name="__main__")' publication/scripts/check_conservation_exclusions.py "$B.json" "$B.xml" publication/ws4/consistency/rebuilt-b-exclusions.json
```
