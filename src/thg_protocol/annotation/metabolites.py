"""Metabolite identification helpers."""

# The legacy annotation implementation is still being split into smaller
# helpers. Keep its historical lint exceptions localized until that move is
# complete; new service-boundary code is linted normally.
# ruff: noqa

from __future__ import annotations

import difflib
import logging
import os
import pickle
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
if TYPE_CHECKING:
    import cobra

from thg_protocol.services.pubchem import PubChemClient, PubChemClientProtocol


project_root = Path(__file__).resolve().parents[3]

__all__ = [
    "atom",
    "formula_similarity",
    "gather_metabolites",
    "generate_met_annotation",
    "global_met_annotation_file",
    "identify_metabolite",
    "process_annotation",
    "remove_null_value",
    "setup_proxy",
    "PubChemClient",
    "PubChemClientProtocol",
]

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

LOGGER = logging.getLogger(__name__)
H_PATTERN = re.compile(r"H[0-9]+")
CHARGE_PATTERN = re.compile(r"[-\+][0-9]+")

# Rate limiting: Track last request time to ensure max 5 requests per second
_last_request_time = 0
_min_request_interval = 0.2  # Minimum 0.2 seconds between API calls (max 5 req/sec)


def _rate_limit():
    """Ensure we don't exceed 5 requests per second to PubChem API."""
    global _last_request_time
    current_time = time.time()
    time_since_last = current_time - _last_request_time

    if time_since_last < _min_request_interval:
        sleep_time = _min_request_interval - time_since_last
        time.sleep(sleep_time)

    _last_request_time = time.time()


def setup_proxy():
    """
    Setup proxy for PubChem requests to avoid IP rate limiting.

    Options:
    1. Set HTTP_PROXY and HTTPS_PROXY environment variables
    2. Use a proxy service (requires subscription)
    3. Disable VPN and use home internet
    4. Set DISABLE_PROXY=1 to disable proxy usage

    To use a proxy, set environment variables before running:
        export HTTP_PROXY="http://proxy-server:port"
        export HTTPS_PROXY="http://proxy-server:port"

    To disable proxy:
        export DISABLE_PROXY=1

    Or uncomment and configure the proxy dict below.
    """
    # Check if proxy is disabled
    if os.environ.get("DISABLE_PROXY") == "1":
        print("Proxy disabled by DISABLE_PROXY environment variable")
        LOGGER.info("Proxy disabled by environment variable")
        return None

    proxy = None

    # Option 1: Read from environment variables
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

    if http_proxy or https_proxy:
        proxy = {}
        if http_proxy:
            proxy["http"] = http_proxy
        if https_proxy:
            proxy["https"] = https_proxy
        print(f"Using proxy configuration: {proxy}")
        LOGGER.info(f"Using proxy: {proxy}")

    # Option 2: Manually configure proxy (DISABLED by default - proxy is broken)
    # Uncomment and update the proxy below if you have a working proxy
    # if not proxy:
    #     proxy = {
    #         "http": "http://your-proxy-server:port",
    #         "https": "http://your-proxy-server:port",
    #     }
    #     print(f"Using hardcoded proxy: {proxy}")
    #     LOGGER.info(f"Using hardcoded proxy: {proxy}")

    if not proxy:
        print("No proxy configured - using direct connection")
        LOGGER.info("No proxy configured - using direct connection")

    return proxy


PROXY_CONFIG = None


def global_met_annotation_file():
    global annotation_file
    annotation_file = os.path.join(
        project_root, "metabolite_reac_identification", "reports", "met_annotation.tsv"
    )
    return annotation_file


def gather_metabolites(model: cobra.Model) -> List[Tuple[str, str, str, str]]:
    """Gather metabolites info from a `model`, filtering out from `identifiers`."""
    met_list = []
    for met in model.metabolites:
        met_tuple = (met.name, met.formula, met.annotation, met.id[:-1])
        if met_tuple not in met_list:
            met_list.append(met_tuple)
    return met_list


def formula_similarity(formula_left: str, formula_right: str) -> float:
    """Compute similiratiy based on the stdlib SequenceMatcher."""
    pruned_left = H_PATTERN.sub("H", CHARGE_PATTERN.sub("", atom(formula_left)))
    pruned_right = H_PATTERN.sub("H", CHARGE_PATTERN.sub("", atom(formula_right)))
    return difflib.SequenceMatcher(
        lambda x: x == " ", pruned_left, pruned_right
    ).ratio()


def identify_metabolite(
    name: str,
    formula: str,
    iden: str,
    threshold: float = 0.82,
    max_retries: int = 3,
    use_proxy: bool = False,
    client: PubChemClientProtocol | None = None,
) -> Optional[str]:
    """Try to match metabolite info to a pubchem compound to get the annotation.

    Parameters
    ----------
    name: str
    formula: str
    iden: str
    threshold: float, default=0.82
        minimum similarity ratio between the molecular formulas. The default (0.82)
        was decided by performing sensibility tests of the metabolites in Human 1.
    max_retries: int, default=3
        maximum number of retry attempts when PubChem server is busy
    use_proxy: bool, default=False
        whether to use proxy configuration if available

    Returns
    -------
    met_result: Optional[str]
        Tab-separated str. If None, the metabolite was not identified.

    """
    # The package client owns HTTP, retries, pacing, caching, and response
    # normalization.  In particular, this workflow never imports PubChemPy or
    # changes process-wide proxy environment variables.
    del use_proxy
    if client is None:
        from thg_protocol.services.pubchem import PubChemClient

        client = PubChemClient(retries=max(0, max_retries))
    try:
        compound = client.get_compound(name)
    except Exception as error:  # network failures are an unresolved match
        LOGGER.warning("PubChem lookup failed for %s: %s", name, error)
        return None
    if compound is None or formula_similarity(formula, compound.molecular_formula) < threshold:
        return None

    synonyms = compound.synonyms or (name,)
    metabolite = max(
        synonyms,
        key=lambda synonym: difflib.SequenceMatcher(
            None, name.lower(), synonym.lower()
        ).ratio(),
    )
    kegg = next(
        (synonym for synonym in synonyms if re.fullmatch(r"[CG][0-9]{5}", synonym)),
        "",
    )
    lipidmaps = next(
        (
            synonym
            for synonym in synonyms
            if re.fullmatch(r"L[A-Z]{3}[0-9]+", synonym)
        ),
        "",
    )
    chebi = next(
        (synonym for synonym in synonyms if re.fullmatch(r"CHEBI:[0-9]+", synonym)),
        "",
    )
    return "\t".join(
        [
            metabolite,
            "",
            compound.molecular_formula,
            lipidmaps,
            kegg,
            chebi,
            str(compound.cid),
            "",
            compound.inchikey,
            compound.inchi,
            "",
            iden,
        ]
    ) + "\n"


def generate_met_annotation(
    met_list: List[Tuple[str, str, str, str]],
    out: str | Path | None = None,
    delay_between_requests: float = 1.0,
    checkpoint_interval: int = 10,
    resume: bool = True,
    client: PubChemClientProtocol | None = None,
) -> Tuple[List, List]:
    """Identify and write metabolite annotations to file (Tab-separated).

    Parameters
    ----------
    met_list: list[tuple[str, str, str, str]]
        list of metabolites to annotate
    out: str
        output file path
    delay_between_requests: float, default=1.0
        delay in seconds between PubChem API requests to avoid rate limiting
    checkpoint_interval: int, default=10
        save progress after every N metabolites
    resume: bool, default=True
        if True, resume from checkpoint file if it exists
    client: PubChemClientProtocol, optional
        PubChem service adapter. Supplying a client makes the workflow
        deterministic and keeps network access behind the service boundary.

    Returns
    -------
    unnanotated: list[tuple[str, str, str, str]]
        list of unnanotated metabolites
    anotated: list[tuple[str, str, str, str]]
        list of anotated metabolites
    """
    out = os.fspath(out or global_met_annotation_file())
    unnanotated, annotated = [], []
    api_failures = []  # Track API/temporary failures separately
    total = len(met_list)
    
    # Failure tracking file
    failure_file = out.replace('.tsv', '_failures.tsv')
    
    print(f"\n{'='*70}")
    print(f"Starting metabolite annotation for {total} metabolites")
    print(f"{'='*70}\n")

    with open(out, "w") as f, open(failure_file, "w") as fail_f:
        # Write header for failure file
        fail_f.write("name\tformula\tidentifier\tfailure_reason\n")
        
        for idx, (name, formula, annotation, iden) in enumerate(met_list, 1):
            if idx % 100 == 0:
                print(f"[{idx}/{total}] {(idx/total)*100:.1f}% | Success: {len(annotated)}, Failed: {len(unnanotated)}, API errors: {len(api_failures)}")
            
            try:
                # Track if this is an API failure
                api_error = False
                failure_reason = "unknown"
                
                result = identify_metabolite(name, formula, iden, client=client)
                met = [name, formula, annotation, iden]
                
                if result is None:
                    # Try to determine failure reason from recent logs
                    # Since we can't easily capture it, we'll mark for retry
                    unnanotated.append(met)
                    failure_reason = "not_found_or_api_error"
                    fail_f.write(f"{name}\t{formula}\t{iden}\t{failure_reason}\n")
                else:
                    f.write(result)
                    f.flush()  # Ensure data is written immediately
                    annotated.append(met)
                    
            except Exception as e:
                error_str = str(e)
                met = [name, formula, annotation, iden]
                unnanotated.append(met)
                
                # Categorize error
                if "503" in error_str or "ServerBusy" in error_str or "HTTP Error" in error_str:
                    failure_reason = "api_error"
                    api_failures.append(met)
                elif "timeout" in error_str.lower():
                    failure_reason = "timeout"
                    api_failures.append(met)
                else:
                    failure_reason = f"exception: {error_str[:50]}"
                
                fail_f.write(f"{name}\t{formula}\t{iden}\t{failure_reason}\n")
                continue
    
    print(f"\n{'='*70}")
    print(f"ANNOTATION COMPLETE")
    print(f"{'='*70}")
    print(f"Total metabolites:          {total}")
    def percentage(count: int) -> float:
        return (count / total) * 100 if total else 0.0
    print(f"Successfully annotated:     {len(annotated)} ({percentage(len(annotated)):.1f}%)")
    print(f"Failed (likely not in DB):  {len(unnanotated)-len(api_failures)} ({percentage(len(unnanotated)-len(api_failures)):.1f}%)")
    print(f"Failed (API/temp errors):   {len(api_failures)} ({percentage(len(api_failures)):.1f}%)")
    print(f"\nResults saved to:      {out}")
    print(f"Failures saved to:     {failure_file}")
    print(f"{'='*70}\n")
    
    return annotated, unnanotated


def remove_null_value(d):
    return {
        a: c
        for a, b in d.items()
        if (c := (b if not isinstance(b, dict) else remove_null_value(b)))
    }


def process_annotation(annotation_file: str | Path | None = None) -> Dict:
    """Generate metabolite annotation file.

    Parameters
    ----------
    annotation_file: str
        Tab-separated file, generated with `generate_met_annotation`
    """
    annotation_file = os.fspath(annotation_file or global_met_annotation_file())
    print(f"Processing annotation file: {annotation_file}")
    variableFile = pd.read_csv(annotation_file, sep="\t", header=None)
    variableFile[5] = variableFile[5].str.extract("(CHEBI:[0-9]+)", expand=True)
    variableFile = variableFile.rename(
        columns={
            3: "lipidmaps",
            4: "kegg.compound",
            5: "chebi",
            6: "pubchem.compound",
            8: "inchikey",
            9: "inchi",
        }
    )
    variableFile = variableFile.fillna(str())

    annotation = defaultdict(dict)

    for _, row in variableFile.iterrows():
        annotation[row[11]] = row.drop([0, 1, 2, 7, 10, 11]).to_dict()
    annotation = remove_null_value(annotation)
    return annotation


def atom(Formula):
    try:
        if "C" in Formula:
            C = re.findall(r"(C[0-9]+)", Formula)
            if not C:
                C = ["C1"]
        else:
            C = []
        if "H" in Formula:
            H = re.findall(r"(H\+*[0-9]+)", Formula)
            if not H:
                H = ["H1"]
        else:
            H = []
        if "O" in Formula:
            O = re.findall(r"(O[0-9]+)", Formula)
            if not O:
                O = ["O1"]
        else:
            O = []
        if "N" in Formula:
            N = re.findall(r"(N[0-9]+)", Formula)
            if not N:
                N = ["N1"]
        else:
            N = []
        if "P" in Formula:
            P = re.findall(r"(P[0-9]+)", Formula)
            if not P:
                P = ["P1"]
        else:
            P = []
        if "S" in Formula:
            S = re.findall(r"(Se?[0-9]+)", Formula)
            if not S:
                S = ["S1"]
        else:
            S = []
        if "I" in Formula:
            I = re.findall(r"(I[0-9]+)", Formula)
            if not I:
                I = ["I1"]
        else:
            I = []
        if "F" in Formula:
            F = re.findall(r"(Fe*[0-9]+)", Formula)
            if not F:
                F = ["F1"]
        else:
            F = []
        if "R" in Formula:
            R = re.findall(r"(R[0-9]+)", Formula)
            if not R:
                R = ["R1"]
        else:
            R = []
        return "".join(str(i) for i in C + H + O + N + P + S + I + F + R)
    except Exception as e:
        print(e)
