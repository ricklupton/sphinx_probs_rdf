"""Structural checks on a `ParsedSystem`.

`sphinx_probs_rdf.loader.parse_system_definitions` runs `validate()` automatically
by default, logging any problem found as a warning.

Currently, not all properties with value mappings are checked further, e.g. a
process's ``per:`` may contain ``{object: X}``, a reference to another
definition -- but ``per`` is parsed as generic YAML and not validated further.

"""

from __future__ import annotations

from typing import List

from .model import ParsedSystem
from .units import UnitTable


def validate(system: ParsedSystem) -> List[str]:
    """Return a list of problems found in `system`."""
    units: UnitTable = system.units
    problems: List[str] = []

    for process in system.processes.values():
        for item in process.consumes + process.produces:
            if item.object_name not in system.objects:
                problems.append(
                    f"{process.source}: process {process.name!r} references object "
                    f"{item.object_name!r}, which is never declared"
                )
            elif item.unit is not None and not item.is_share:
                obj_basis = system.objects[item.object_name].basis
                if obj_basis is not None:
                    try:
                        item_basis = item.basis(units)
                    except ValueError:
                        item_basis = None  # unsupported unit -- not this check's job?
                    if item_basis is not None and item_basis != obj_basis:
                        problems.append(
                            f"{process.source}: process {process.name!r} item "
                            f"{item.object_name!r} = {item.amount} {item.unit} is in "
                            f"basis {item_basis!r}, but object {item.object_name!r} "
                            f"has basis {obj_basis!r}."
                        )

        sides = (("consumes", process.consumes), ("produces", process.produces))
        for side_name, items in sides:
            # A side is a simplex iff every item on it is written in `%`/`%layer` -- a
            # partial mix is ambiguous.
            amount_items = [i for i in items if i.amount is not None]
            share_items = [i for i in amount_items if i.is_share]
            if share_items and len(share_items) != len(amount_items):
                problems.append(
                    f"{process.source}: process {process.name!r} {side_name} mixes "
                    f"% and non-% items -- a side must be entirely shares or "
                    f"entirely intensities"
                )
            elif share_items:
                total = sum(i.amount for i in share_items if i.amount is not None)
                if abs(total - 100.0) > 0.5:
                    problems.append(
                        f"{process.source}: process {process.name!r} {side_name} "
                        f"shares sum to {total:g}%, not 100% (Sum)"
                    )

            # A bare `%` means "a fraction of this side's common basis", so it is
            # only meaningful if every object on the side sharing bare `%` shares one
            # basis. An explicit `%layer` names its own basis and carries no such
            # requirement -- e.g. `%mass` across objects with differing bases is
            # legitimate.
            bare_percent = [i for i in items if i.is_share and i.share_layer is None]
            bare_bases = {
                system.objects[i.object_name].basis
                for i in bare_percent
                if i.object_name in system.objects
                and system.objects[i.object_name].basis is not None
            }
            if len(bare_bases) > 1:
                problems.append(
                    f"{process.source}: process {process.name!r} {side_name} uses "
                    f"bare '%' shares across objects with different bases "
                    f"{sorted(bare_bases)} -- a bare '%' means a fraction of the "
                    f"side's common basis; use '%basis' to name an explicit one"
                )

        for child in process.composed_of:
            if child not in system.processes:
                problems.append(
                    f"{process.source}: process {process.name!r} is composed of "
                    f"{child!r}, which is never declared"
                )

    for obj in system.objects.values():
        for child in obj.composed_of:
            if child not in system.objects:
                problems.append(
                    f"{obj.source}: object {obj.name!r} is composed of {child!r}, "
                    f"which is never declared"
                )

    return problems
