"""Source-specific adapters that produce :class:`SgprEvidence`."""

from .biocyc import biocyc_sgpr_evidence
from .kegg import kegg_sgpr_evidence
from .reactome import reactome_sgpr_evidence
from .rhea import rhea_sgpr_evidence
from .uniprot import uniprot_sgpr_evidence

__all__ = [
    "biocyc_sgpr_evidence",
    "kegg_sgpr_evidence",
    "reactome_sgpr_evidence",
    "rhea_sgpr_evidence",
    "uniprot_sgpr_evidence",
]
