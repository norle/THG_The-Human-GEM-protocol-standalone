"""Metabolites that gap-filling must not move between compartments for free.

Energy and redox carriers (ATP/ADP, NAD(P)H/NAD(P)+, FADH2/FAD and relatives)
and the proton are moved across membranes by dedicated, energetically coupled
carriers. A free, reversible transport between compartments lets a model
charge them without any energy input, which creates the energy-generating
cycles MEMOTE checks for (Fritzemeier et al. 2017).

The default list holds MetaNetX identifiers: the energy couples from
``memote.support.consistency.ENERGY_COUPLES`` plus the cytosolic and external
proton. A test keeps it in step with the installed MEMOTE.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping

#: MetaNetX IDs of the energy couples (charged and discharged form) and H+.
DEFAULT_EXCLUDED_METABOLITES: tuple[str, ...] = tuple(
    sorted(
        {
            # ATP/ADP, CTP/CDP, GTP/GDP, UTP/UDP, ITP/IDP
            "MNXM3",
            "MNXM7",
            "MNXM63",
            "MNXM220",
            "MNXM51",
            "MNXM30",
            "MNXM121",
            "MNXM17",
            "MNXM423",
            "MNXM495",
            # NADPH/NADP+, NADH/NAD+
            "MNXM6",
            "MNXM5",
            "MNXM10",
            "MNXM8",
            # FADH2/FAD and the other redox partners
            "MNXM38",
            "MNXM33",
            "MNXM208",
            "MNXM119",
            "MNXM191",
            "MNXM232",
            "MNXM223",
            "MNXM509",
            "MNXM7517",
            "MNXM12235",
            "MNXM12233",
            "MNXM12236",
            "MNXM558",
            "MNXM2178",
            # acyl-CoA/CoA-type couple and the proton gradient couple
            "MNXM21",
            "MNXM12",
            "MNXM89557",
            "MNXM20",
            # H+ (cytosolic and external)
            "MNXM1",
            "MNXM15",
        }
    )
)


def _flatten(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _flatten(item)
    elif isinstance(value, Iterable):
        for item in value:
            yield from _flatten(item)


def is_excluded(
    metabolite_id: str,
    base_id: str,
    annotation: Mapping[str, object] | None,
    excluded: Collection[str],
) -> bool:
    """Whether a metabolite is on ``excluded``.

    It matches by exact metabolite ID, by compartment-free base ID, or by any
    cross-reference in ``annotation`` (also when given as a URL, by its last
    path component).
    """
    if not excluded:
        return False
    wanted = set(excluded)
    if metabolite_id in wanted or base_id in wanted:
        return True
    return any(
        reference in wanted or reference.rsplit("/", 1)[-1] in wanted
        for reference in _flatten(annotation or {})
    )


__all__ = ["DEFAULT_EXCLUDED_METABOLITES", "is_excluded"]
