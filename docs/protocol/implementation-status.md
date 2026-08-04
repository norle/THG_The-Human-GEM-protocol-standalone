# Published protocol coverage

!!! info "Status: Partial"
    This matrix distinguishes maintained package interfaces from the complete
    historical/published workflow. Status labels follow the repository policy:
    Supported, Partial, External, and Archived.

| Publication concept | Current entry point | Status | Evidence | Behavioral difference | Recommended path |
| --- | --- | --- | --- | --- | --- |
| Reference annotation and mass balancing → THGβ1 | `thg_protocol.annotation`, `thg_protocol.model_build`, formula and consistency helpers | **Partial** | [API contracts](../api-contracts.md), annotation/model-build tests, [legacy inventory](../legacy-api-inventory.md) | Building blocks do not provide one THGβ1 orchestrator or guarantee publication artifact naming | Compose inspection, injected annotation, explicit output, and balance checks; keep an intermediate model |
| Construct Human Database from live biological sources | `thg_protocol.database`, service clients, parsing/model-build helpers | **Partial** | Database API/tests and service-boundary audit | `reconstruct_model` consumes normalized records; it does not harvest KEGG/BioCyc/PubChem itself | Normalize records or compose clients manually; record source/cache dates |
| GPR/location curation and isoenzyme expansion → THGβ2 | `thg_protocol.gpr`, `thg_protocol.model_build`, pathway/model helpers | **Partial** | GPR/location tests, API contracts, legacy inventory | No maintained end-to-end THGβ2 expansion runbook or named artifact | Run only verified helper sequences and label the resulting state by its actual output |
| Similarity/identity-aware merge | `thg_protocol.merge.merge_models` | **Supported** with intentional differences | Merge tests and [API contracts](../api-contracts.md) | Retained base stoichiometry; merge report replaces historical positional overlap output | Preserve inputs, merge to explicit output, review `MergeReport`, and use comparison separately |
| Network and reaction checks | `thg_protocol.analysis` | **Supported** | Consistency and network-analysis tests | Structural checks are not a complete biological acceptance assessment; solver needs vary | Save connectivity, formula-balance, and consistency results |
| MEMOTE assessment | external `memote` command | **External** | [MEMOTE guide](../workflows/memote.md), `memote` optional dependency | Not a THG package API or default offline test | Install/pin MEMOTE separately and save its HTML report |
| Essential metabolic-task analysis | Historical MEMOTE task code | **Archived** | [legacy workflow status](../legacy-workflows.md), legacy inventory | No maintained replacement is installed or covered by the default suite | Record as Archived; do not infer task success from MEMOTE or structural checks |
| Iterative merge/consistency loop | `thg_protocol.workflow`, merge + consistency APIs | **Partial** | Resumable workflow tests and API contracts | Checkpointed engineering composition is available; scientific convergence decisions remain manual | Use `thg-run` for restartable checkpoints and review every result |
| Reproduce the final published THG artifact | complete staged workflow | **Partial** | This matrix, contracts, legacy inventory, and absence of an end-to-end run/test | Current package does not demonstrate exact publication regeneration | Treat current output as a documented composition, not exact artifact reproduction |

## How to read the statuses

**Supported** means a maintained API or installed CLI exists and current tests
cover it. **Partial** means maintained building blocks exist but the complete
published stage is not orchestrated. **External** means a separately installed
tool performs the step. **Archived** means the historical code or workflow is
recorded but is not a supported current interface.

The [API contracts](../api-contracts.md) are authoritative for mutation,
ownership, explicit output paths, injected service clients, and intentional
migration differences. The [legacy inventory](../legacy-api-inventory.md) is
authoritative for removed or compatibility-only workflows.
