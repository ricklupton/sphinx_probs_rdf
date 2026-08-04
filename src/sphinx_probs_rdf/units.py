"""A unit -> (scale, basis) table, shared by the Sphinx extension and the
standalone loader.

A ``basis`` is an opaque string naming what a recipe amount is measured *in* --
mass, area, energy, etc. It may be a plain label (``"mass"``) or a URI
(``"http://qudt.org/vocab/quantitykind/Mass"``).

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Unit:
    """A unit of measure: a multiplier into ``basis``'s canonical unit."""

    scale: float
    basis: str


@dataclass(frozen=True)
class UnitTable:
    """``unit -> Unit``."""

    units: Dict[str, Unit]

    def lookup(self, unit: str) -> Unit:
        """Look up `unit`. Raises ``ValueError`` for an unknown unit."""
        try:
            return self.units[unit]
        except KeyError:
            raise ValueError(f"unsupported unit {unit!r}") from None

    def is_share(self, unit: str) -> bool:
        """Whether `unit` (``"%"``, ``"%mass"``, ...) marks a fraction of a recipe
        side rather than a physical amount in one of this table's bases."""
        return unit.startswith("%")


#: kg/m2/m3/- with QUDT quantity kinds, matching
#: ``sphinx_probs_rdf.builder.DEFAULT_UNIT_METRICS``.
DEFAULT_UNITS = UnitTable(
    units={
        "kg": Unit(1.0, "http://qudt.org/vocab/quantitykind/Mass"),
        "m2": Unit(1.0, "http://qudt.org/vocab/quantitykind/Area"),
        "m3": Unit(1.0, "http://qudt.org/vocab/quantitykind/Volume"),
        "-": Unit(1.0, "http://qudt.org/vocab/quantitykind/Dimensionless"),
    },
)
