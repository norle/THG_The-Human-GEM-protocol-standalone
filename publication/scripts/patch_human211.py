"""Write a patched copy of Human-GEM 2.1.1 with MAR20193 blocked.

Reason: with MAR20193 (succinate/H+ efflux) open, VerifyModel task 21 is feasible via the
unbalanced pool-composition reaction MAR00012. See publication/ws0/verifymodel_leaks.md.
Usage: patch_human211.py IN.xml OUT.xml
"""
import hashlib, sys
import cobra
src, dst = sys.argv[1:3]
m = cobra.io.read_sbml_model(src)
m.reactions.MAR20193.bounds = (0.0, 0.0)
m.reactions.MAR20193.notes["patch"] = "blocked: opens VerifyModel task 21 leak (publication/ws0/verifymodel_leaks.md)"
cobra.io.write_sbml_model(m, dst)
print(hashlib.sha256(open(dst, "rb").read()).hexdigest())
