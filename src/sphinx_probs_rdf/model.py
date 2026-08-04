"""The parsed-system intermediate representation (IR).

Plain dataclasses describing a system of objects and processes, independent of how
they were parsed (Sphinx/RDF, or the standalone :mod:`sphinx_probs_rdf.loader`).

Identifiers (``ObjectDef.name`` / ``ProcessDef.name`` / everywhere a name is
referenced, e.g. ``RecipeItem.object_name``) are opaque strings, exactly as written
in the source document.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from .units import UnitTable


@dataclass(frozen=True)
class RecipeItem:
    """One line of a ``:consumes:`` / ``:produces:`` block.

    ``amount`` is ``None`` for processes declaring inputs/outputs with no recipe
    values.

    ``extra`` holds any additional keys given in the item's trailing YAML
    mapping.

    """

    object_name: str
    amount: Optional[float] = None
    unit: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_share(self) -> bool:
        """Whether this item is written in ``%``/``%layer``."""
        return self.unit is not None and self.unit.startswith("%")

    @property
    def share_layer(self) -> Optional[str]:
        """The basis named after ``%`` (``"mass"`` in ``%mass``), or ``None`` for a
        bare ``%``. Only meaningful when ``is_share``."""
        if self.unit is None or not self.is_share:
            return None
        return self.unit[1:] or None

    def basis(self, units: UnitTable) -> Optional[str]:
        """The basis this item's amount is measured in, per `units`."""
        if self.unit is None or self.is_share:
            return None
        return units.lookup(self.unit).basis

    def quantity(self, units: UnitTable) -> Optional[float]:
        """The amount, scaled into the basis' base unit via `units`.

        For a share, this is the raw percentage number (``53 %`` -> ``53.0``, not
        ``0.53``).
        """
        if self.amount is None or self.unit is None:
            return None
        if self.is_share:
            return self.amount
        return units.lookup(self.unit).scale * self.amount


@dataclass
class FactorSpec:
    """One entry of an object's ``:factors:`` mapping: how to convert this object's
    amount into a different basis.

    ``value`` is a float (a point value) or a string expression referencing
    ``system:parameter`` names (e.g. ``"(1 - 0.09) / wood_dry_density"``).

    ``derived`` means "no independent information"; when set, ``value``/``range``
    are not used.
    """

    value: Union[float, str, None] = None
    unit: Optional[str] = None
    range: Optional[Tuple[float, float]] = None
    source: Optional[str] = None
    derived: bool = False


@dataclass
class ParameterDef:
    """A ``system:parameter`` -- a named scalar.
    """

    name: str
    label: str
    value: Optional[float] = None
    unit: Optional[str] = None
    range: Optional[Tuple[float, float]] = None
    source: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ObjectDef:
    name: str
    label: str
    parent: Optional[str] = None
    #: Explicit children, from this object's own ``:composed_of:`` (the plain-name
    #: entries only -- see ``composed_of_children_of``).
    composed_of: List[str] = field(default_factory=list)
    #: The ``*Name`` ("children of") form: this object's children are declared to be
    #: whatever `Name`'s children are, expanded later by
    #: ``sphinx_probs_rdf.postprocess`` (RDF path) or left to a consumer (loader
    #: path) -- recorded here, not expanded. The ``*`` sigil is stripped.
    composed_of_children_of: List[str] = field(default_factory=list)
    #: ``(can_import, can_export)``, or ``None`` when ``:traded:`` was not given.
    traded: Optional[Tuple[bool, bool]] = None
    equivalent_to: List[str] = field(default_factory=list)
    #: The basis this object's own recipes are written in -- a basis id from a
    #: ``UnitTable``'s vocabulary (see ``units.py``), not a unit of measure. Set from
    #: an explicit ``:basis:`` if given, else inferred by the loader from this
    #: object's own recipe items.
    basis: Optional[str] = None
    #: basis -> `FactorSpec`, the object's conversion factor into every other basis
    #: it participates in.
    factors: Dict[str, FactorSpec] = field(default_factory=dict)
    #: Provenance, e.g. ``"file.md:12"``.
    source: Optional[str] = None
    #: The ``:extra:`` YAML mapping. ``{}`` if ``:extra:`` wasn't given.
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessDef:
    name: str
    label: str
    parent: Optional[str] = None
    composed_of: List[str] = field(default_factory=list)
    composed_of_children_of: List[str] = field(default_factory=list)
    consumes: List[RecipeItem] = field(default_factory=list)
    produces: List[RecipeItem] = field(default_factory=list)
    #: The activity gauge -- ``{object, direction}`` or ``{throughput, side}`` -- or
    #: ``None`` for no gauge. Parsed as generic YAML; not interpreted here.
    per: Optional[Dict[str, Any]] = None
    #: The closure declaration: a bare list of bases or a mapping, or ``None`` for no
    #: closure equation. Parsed as generic YAML; not interpreted here.
    balance: Union[List[str], Dict[str, Any], None] = None
    source: Optional[str] = None
    #: The ``:extra:`` YAML mapping.
    #: ``{}`` if ``:extra:`` wasn't given.
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_recipe(self) -> bool:
        """Whether this process defines a recipe (amounts), not just connectivity.
        """
        return any(i.amount is not None for i in self.consumes + self.produces)


@dataclass
class ParsedSystem:
    objects: Dict[str, ObjectDef]
    processes: Dict[str, ProcessDef]
    parameters: Dict[str, ParameterDef]
    units: UnitTable

    def children_of_object(self, name: str) -> List[str]:
        return sorted(
            {c for c in self.objects[name].composed_of}
            | {o.name for o in self.objects.values() if o.parent == name}
        )

    def children_of_process(self, name: str) -> List[str]:
        return sorted(
            {c for c in self.processes[name].composed_of}
            | {p.name for p in self.processes.values() if p.parent == name}
        )

    def leaf_objects(self) -> List[str]:
        """Objects with no children."""
        return sorted(n for n in self.objects if not self.children_of_object(n))

    def processes_with_recipes(self) -> List[str]:
        """Processes that define a recipe. See `ProcessDef.has_recipe`."""
        return sorted(n for n, p in self.processes.items() if p.has_recipe)
