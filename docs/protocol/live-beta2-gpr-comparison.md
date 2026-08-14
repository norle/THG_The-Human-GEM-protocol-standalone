# Archived β2 GPR comparison

Run date: 2026-08-14. The parser fixture and offline smoke checks pass. The
configured BioCyc credentials authenticate successfully, but the account
receives `Subscription Required` for HumanCyc and MetaCyc EC pages. No
archived fixture was changed. KEGG fallback values below are current observed
identifiers, not archived HumanCyc gene symbols.

| EC | Archived expected genes | HumanCyc | MetaCyc | KEGG fallback | Warning/status |
| --- | --- | --- | --- | --- | --- |
| `1.1.1.1` | `AA177072`, `FASN`, `OXSM` | subscription required* | subscription required* | `124,125,126,127,128,130,131` | explicit KEGG fallback; mismatch pending source access |
| `1.1.1.1` | `ADHFE1` | subscription required* | subscription required* | `124,125,126,127,128,130,131` | same EC result as above |
| `1.1.1.10` | `DCXR` | not collected | not collected | `51181` | per-EC BioCyc probe interrupted; fallback observed |
| `1.1.1.100` | `AA177072`, `OXSM`, `FASN` | not collected | not collected | none | unresolved until source access is available |
| `1.1.1.102` | `KDSR` | not collected | not collected | `102,2531` | per-EC BioCyc probe pending |
| `1.1.1.105` | `RDH5` | not collected | not collected | `105,195814,201140,8630` | per-EC BioCyc probe pending |
| `1.1.1.145` | `HSD3B1`, `HSD3B2` | not collected | not collected | `145,3283,3284` | per-EC BioCyc probe pending |
| `1.1.1.145` | `HSD3B1`, `HSD3B2` | not collected | not collected | `145,3283,3284` | duplicate archived case; same fallback |
| `1.1.1.146` | `HSD11B1` | not collected | not collected | `146,3290,374875` | per-EC BioCyc probe pending |
| `1.1.1.15` | `AA526438`, `H17063`, `MECR`, `PECR` | not collected | not collected | none | unresolved until source access is available |

`*` The authenticated `1.1.1.1` probe returned the account-level access page;
the other HumanCyc/MetaCyc cells are deliberately not presented as per-EC
proof because those requests were interrupted. Every recorded fallback uses
parser version `biocyc-gene-anchor-v1`; retrieval timestamps and warnings are
present in the JSON evidence records.

The remaining gate is to rerun all ten rows with an account entitled to the
HumanCyc/MetaCyc pages, then replace only the `not collected` cells with the
recorded source, warnings, parser version, and retrieval metadata.
