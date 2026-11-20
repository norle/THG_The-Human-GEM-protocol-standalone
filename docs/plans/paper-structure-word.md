Section	Content	Evidence from
Abstract	What THG adds to Human-GEM 2.1.1, how it is kept consistent, and verified quantitative findings	WS1, WS2, WS4, WS5
1. Introduction	Human GEM curation; limited subcellular resolution of Human-GEM; risk of breaking conservation when expanding a model	literature; citations still pending
2. Methods / Implementation	Workflow, compartment resolution through the GO hierarchy, provenance, scientific gates, numerical diagnostics, benchmark settings	WS0, WS1, WS7
3.1 Results: compartment resolution	Two rule changes (multi-compartment genes; one GO term to several compartments), ablation ladder, worked GO examples	WS2 (compartment-resolution/)
3.2 Results: safe expansion	Stage gates, leak mechanisms with origin of defects stated, 0 of 21 VerifyModel tasks feasible at every stage	WS1, WS2
3.3 Results: THG vs Human-GEM 2.1.1	Size, balance of additions, quality, task preservation, defects found in Human-GEM 2.1.1	WS4, WS5
3.4 Results: reproducibility	Independent replay and stage sizes/runtime	WS1
4. Discussion	Supported conclusions, connectivity of added reactions, numerical limits, missing validation and future work	all active WS
Data and code availability	Local artifacts and regeneration commands; public release pending	WS7
Supplementary	Full fix inventory with evidence strength, per-task results, manifests and validation detail	active WS

ID	Content	Produced by
Fig 1	Protocol stages, gates and provenance	WS1
Fig 2	Compartment resolution: GO-hierarchy mapping examples and ablation ladder (genes localised, reaction copies per compartment)	WS2
Fig 3	Safe expansion: VerifyModel per stage and the three leak mechanisms with measured effects	WS1, WS2
Fig 4	Human-GEM 2.1.1 vs. THG: quality, supported coverage, task preservation	WS4, WS5
Table 1	Model statistics and benchmark outcomes, including invalid/unresolved counts	WS0, WS4, WS5
Table S*	Fix inventory, per-task results, stage/replay evidence and validation details	active WS
