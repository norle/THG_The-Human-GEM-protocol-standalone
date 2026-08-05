"""Metabolite identification helpers."""

# The legacy annotation implementation is still being split into smaller
# helpers. Keep its historical lint exceptions localized until that move is
# complete; new service-boundary code is linted normally.
# ruff: noqa

from __future__ import annotations

import difflib
import hashlib
import json
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
    """Return the canonical snapshot path used by the annotation workflow.

    New callers should pass explicit paths to the annotation APIs.  This
    compatibility helper remains available for source-checkout consumers, but
    must point at the relocated artifact rather than the removed legacy tree.
    """
    return os.path.join(
        project_root,
        "supplementary_material",
        "metabolite_reaction",
        "met_annotation.tsv",
    )


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
    out: str | Path,
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
    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_path.with_name(
        f"{output_path.stem}.checkpoint.json"
    )
    failure_path = output_path.with_name(
        f"{output_path.stem}_failures{output_path.suffix}"
    )
    if delay_between_requests < 0:
        raise ValueError("delay_between_requests must be non-negative")
    if checkpoint_interval < 1:
        raise ValueError("checkpoint_interval must be at least 1")

    records = [list(record) for record in met_list]
    total = len(records)
    fingerprint = hashlib.sha256(
        json.dumps(
            records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()

    def initial_state() -> dict:
        return {
            "next_index": 0,
            "annotated": [],
            "unannotated": [],
            "failure_reasons": [],
            "api_failures": [],
            "annotation_lines": [],
        }

    def write_checkpoint(state: dict) -> None:
        payload = {
            "format_version": 1,
            "input_sha256": fingerprint,
            **state,
        }
        temporary = checkpoint_path.with_name(checkpoint_path.name + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, checkpoint_path)

    def read_checkpoint() -> dict:
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                f"annotation checkpoint is unreadable: {checkpoint_path}"
            ) from error
        if checkpoint.get("format_version") != 1:
            raise ValueError("unsupported annotation checkpoint format")
        if checkpoint.get("input_sha256") != fingerprint:
            raise ValueError(
                "annotation checkpoint input does not match met_list; "
                "use resume=False to start a new run"
            )
        next_index = checkpoint.get("next_index")
        if not isinstance(next_index, int) or not 0 <= next_index <= total:
            raise ValueError("annotation checkpoint has an invalid next_index")
        required = (
            "annotated",
            "unannotated",
            "failure_reasons",
            "api_failures",
            "annotation_lines",
        )
        if any(key not in checkpoint for key in required):
            raise ValueError("annotation checkpoint is missing progress fields")
        return {key: checkpoint[key] for key in ("next_index", *required)}

    def write_final(path: Path, content: str) -> None:
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)

    if resume and checkpoint_path.exists():
        state = read_checkpoint()
    else:
        if not resume and checkpoint_path.exists():
            checkpoint_path.unlink()
        state = initial_state()

    print(f"\n{'='*70}")
    print(f"Starting metabolite annotation for {total} metabolites")
    print(f"{'='*70}\n")

    for index in range(state["next_index"], total):
        name, formula, annotation, identifier = records[index]
        if (index + 1) % 100 == 0:
            print(
                f"[{index + 1}/{total}] "
                f"{((index + 1) / total) * 100:.1f}% | "
                f"Success: {len(state['annotated'])}, "
                f"Failed: {len(state['unannotated'])}, "
                f"API errors: {len(state['api_failures'])}"
            )

        try:
            result = identify_metabolite(
                name, formula, identifier, client=client
            )
            record = [name, formula, annotation, identifier]
            if result is None:
                state["unannotated"].append(record)
                state["failure_reasons"].append("not_found_or_api_error")
            else:
                state["annotation_lines"].append(str(result))
                state["annotated"].append(record)
        except Exception as error:
            error_str = str(error)
            record = [name, formula, annotation, identifier]
            state["unannotated"].append(record)
            if (
                "503" in error_str
                or "ServerBusy" in error_str
                or "HTTP Error" in error_str
            ):
                failure_reason = "api_error"
                state["api_failures"].append(record)
            elif "timeout" in error_str.lower():
                failure_reason = "timeout"
                state["api_failures"].append(record)
            else:
                failure_reason = f"exception: {error_str[:50]}"
            state["failure_reasons"].append(failure_reason)

        state["next_index"] = index + 1
        if (
            state["next_index"] % checkpoint_interval == 0
            or state["next_index"] == total
        ):
            write_checkpoint(state)
        if delay_between_requests and index + 1 < total:
            time.sleep(delay_between_requests)

    write_final(output_path, "".join(state["annotation_lines"]))
    failure_lines = [
        "name\tformula\tidentifier\tfailure_reason\n",
        *(
            f"{record[0]}\t{record[1]}\t{record[3]}\t{reason}\n"
            for record, reason in zip(
                state["unannotated"], state["failure_reasons"], strict=True
            )
        ),
    ]
    write_final(failure_path, "".join(failure_lines))
    checkpoint_path.unlink(missing_ok=True)

    annotated = state["annotated"]
    unnanotated = state["unannotated"]
    api_failures = state["api_failures"]
    
    print(f"\n{'='*70}")
    print(f"ANNOTATION COMPLETE")
    print(f"{'='*70}")
    print(f"Total metabolites:          {total}")
    def percentage(count: int) -> float:
        return (count / total) * 100 if total else 0.0
    print(f"Successfully annotated:     {len(annotated)} ({percentage(len(annotated)):.1f}%)")
    print(f"Failed (likely not in DB):  {len(unnanotated)-len(api_failures)} ({percentage(len(unnanotated)-len(api_failures)):.1f}%)")
    print(f"Failed (API/temp errors):   {len(api_failures)} ({percentage(len(api_failures)):.1f}%)")
    print(f"\nResults saved to:      {output_path}")
    print(f"Failures saved to:     {failure_path}")
    print(f"{'='*70}\n")
    
    return annotated, unnanotated


def remove_null_value(d):
    return {
        a: c
        for a, b in d.items()
        if (c := (b if not isinstance(b, dict) else remove_null_value(b)))
    }


def process_annotation(annotation_file: str | Path) -> Dict:
    """Generate metabolite annotation file.

    Parameters
    ----------
    annotation_file: str
        Tab-separated file, generated with `generate_met_annotation`
    """
    annotation_file = os.fspath(annotation_file)
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
