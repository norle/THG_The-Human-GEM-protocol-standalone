"""Reject gap-filled reactions that create energy-generating cycles.

A free transport can close a loop that charges ATP, NADH or another energy
carrier without any energy input (Fritzemeier et al. 2017). After gap-filling,
the model is checked with the same test MEMOTE uses
(:func:`thg_protocol.analysis.leakage.energy_generating_cycles`); any *added*
reaction that takes part in a reported cycle is removed, and the check repeats
until none does.

Limits: MEMOTE reports one least-flux cycle per energy metabolite. If the model
already had a cycle for a metabolite, an added reaction that opens a second one
can go unseen, so a model with existing cycles should be repaired first. The
check also needs MetaNetX cross-references (``metanetx.chemical``) on the
energy metabolites and an optional ``memote`` install; without them it reports
``skipped`` and changes nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def apply_energy_cycle_gate(model: Any, added: Sequence[str]) -> dict[str, Any]:
    """Remove ``added`` reactions found in energy-generating cycles.

    ``model`` is modified in place. Returns a JSON-serializable report with
    ``status`` (``checked`` or ``skipped``), ``reason`` when skipped,
    ``tested`` energy metabolites, ``rejected`` (reaction ID -> energy
    metabolites it helps charge) and the number of ``rounds`` that removed
    something.
    """
    report: dict[str, Any] = {
        "status": "skipped",
        "tested": [],
        "rejected": {},
        "rounds": 0,
    }
    if not added:
        report["reason"] = "no reactions were added"
        return report
    try:
        from thg_protocol.analysis.leakage import energy_generating_cycles

        energy_generating_cycles(model, couples=[])  # imports memote eagerly
    except ImportError:
        report["reason"] = "memote is not installed"
        return report
    except Exception as error:  # compartment lookup etc.: not checkable
        report["reason"] = f"{type(error).__name__}: {error}"
        return report

    kept = list(added)
    while kept:
        try:
            outcome = energy_generating_cycles(model)
        except Exception as error:
            if not report["rounds"]:
                report["reason"] = f"{type(error).__name__}: {error}"
                return report
            raise
        report["tested"] = list(outcome["tested"])
        if not outcome["tested"]:
            report["reason"] = "no energy metabolite could be identified"
            return report
        report["status"] = "checked"
        offenders: dict[str, list[str]] = {}
        for energy, reactions in outcome["cycles"].items():
            for reaction_id in reactions:
                if reaction_id in kept:
                    offenders.setdefault(reaction_id, []).append(energy)
        if not offenders:
            break
        model.remove_reactions(sorted(offenders))
        kept = [reaction_id for reaction_id in kept if reaction_id not in offenders]
        report["rejected"].update(
            {reaction_id: sorted(items) for reaction_id, items in offenders.items()}
        )
        report["rounds"] += 1
    return report


__all__ = ["apply_energy_cycle_gate"]
