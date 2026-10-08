"""Linking: from a library of system definitions to one concrete model.

A parsed system can hold more than one model's worth of definitions -- a shared core and
several alternative readings of some part of it, each in a namespace of its own. Linking
picks one model out of that library, wires it, and flattens it to local names:

* :class:`ProcessSelection` -- which processes the model contains. **Objects are not
  selected**: a model contains exactly the objects its processes refer to (recipe items
  and ``per`` objects), with their declared parents.
* :class:`RecipeSubstitution` -- "in these processes, where the recipe says X, use Y".
  This is how a placeholder (``_:label``) is filled, and how a reference is rewired
  without touching either definition.
* :class:`ObjectOverride` -- an object's trade flags, changed for this model.

The result is an ordinary :class:`~sphinx_probs_rdf.model.ParsedSystem` whose
identifiers are the definitions' **local names**, so a consumer that knows nothing of
prefixes or IRIs can use it as it is.

Scopes
------

A selection or substitution applies to a *scope* of processes:

``ALL``
    every process (for a substitution: every selected process);
``"prefix:"`` or ``"<namespace iri>"`` -- a string
    every process **declared in** that namespace. Membership is the namespace each
    definition was declared with (``ProcessDef.namespace``, ``rdfs:isDefinedBy`` in
    RDF), compared exactly. It is never inferred from the IRI, so namespaces may nest
    freely: a process declared in ``…/us/mill-feed/`` is not in ``…/us/``;
``["prefix:Name", "<iri>", ...]`` -- a list
    exactly those processes.

A single string is always a namespace; name one process by passing a one-element list.

Everything ambiguous is an error rather than a rule to learn: a substitution that
matches nothing, two substitutions for one placeholder in one process, a placeholder
left open, an object referred to but never defined, two definitions with one local name.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

from .identifiers import Prefixes, is_placeholder
from .model import ObjectDef, ParsedSystem, ProcessDef, RecipeItem


class _All:
    """Every process."""

    _instance: Optional["_All"] = None

    def __new__(cls) -> "_All":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "ALL"


#: The scope of every process.
ALL = _All()

Scope = Union[_All, str, Sequence[str]]


class LinkError(ValueError):
    """A model could not be linked as specified."""


@dataclass(frozen=True)
class ProcessSelection:
    """Include the processes in `scope` (see the module docstring)."""

    scope: Scope


@dataclass(frozen=True)
class RecipeSubstitution:
    """In the selected processes in `scope`, replace each key of `replacements` with its
    value wherever a recipe item or a ``per`` object refers to it.

    Keys are placeholders (``"_:HotBand"``) or ordinary identifiers; values are
    identifiers of objects the model will contain. A key must occur in at least one
    process in scope.
    """

    scope: Scope
    replacements: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectOverride:
    """Change an object's trade flags for this model.

    ``None`` leaves a flag as declared.
    """

    object: str
    can_import: Optional[bool] = None
    can_export: Optional[bool] = None


Part = Union[ProcessSelection, RecipeSubstitution, ObjectOverride]


def link_model(parsed: ParsedSystem, parts: Iterable[Part]) -> ParsedSystem:
    """Link one model from `parsed`: select, substitute, override, then localise.

    `parts` is a flat sequence of :class:`ProcessSelection`, :class:`RecipeSubstitution`
    and :class:`ObjectOverride`, in any order -- typically a concatenation of lists, one
    per alternative a model uses, so that each alternative carries its own wiring.
    Definition order is kept: processes and objects appear in the order they were
    parsed.
    """
    prefixes = Prefixes(parsed.prefixes)
    parts = list(parts)
    selections = [p for p in parts if isinstance(p, ProcessSelection)]
    substitutions = [p for p in parts if isinstance(p, RecipeSubstitution)]
    overrides = [p for p in parts if isinstance(p, ObjectOverride)]
    for part in parts:
        if not isinstance(part, (ProcessSelection, RecipeSubstitution, ObjectOverride)):
            raise TypeError(f"not a part of a model: {part!r}")
    if not selections:
        raise LinkError("a model needs at least one ProcessSelection")

    selected: Set[str] = set()
    for selection in selections:
        selected |= _scope(selection.scope, parsed, prefixes, "ProcessSelection")
    processes = {
        name: proc for name, proc in parsed.processes.items() if name in selected
    }

    processes = _substitute(processes, substitutions, parsed, prefixes)

    still_open = [
        f"{prefixes.compact(name)}: {label}"
        for name, proc in processes.items()
        for label in proc.placeholders()
    ]
    if still_open:
        raise LinkError(
            "placeholders left open (fill each with a RecipeSubstitution): "
            + "; ".join(still_open)
        )

    objects = _objects_referred_to(processes, parsed, prefixes)
    objects = _override(objects, overrides, prefixes)
    return _localise(processes, objects, parsed, prefixes)


def _scope(
    scope: Scope, parsed: ParsedSystem, prefixes: Prefixes, what: str
) -> Set[str]:
    """The processes `scope` names, as identifiers."""
    if scope is ALL:
        return set(parsed.processes)
    if isinstance(scope, str):
        if not (scope.endswith(":") or (scope.startswith("<") and scope.endswith(">"))):
            raise LinkError(
                f"{what} scope {scope!r}: a string names a namespace, written "
                f"'prefix:' or '<iri>'; pass a list to name processes"
            )
        namespace = _namespace(scope, prefixes, what)
        found = {n for n, p in parsed.processes.items() if p.namespace == namespace}
        if not found:
            raise LinkError(
                f"{what} scope {scope!r}: no process is declared in namespace "
                f"<{namespace}>" + _near_miss(namespace, parsed)
            )
        return found
    names: Set[str] = set()
    assert not isinstance(scope, _All)
    for item in scope:
        identifier = _identifier(item, prefixes, what)
        if identifier not in parsed.processes:
            raise LinkError(f"{what} scope: no process {item!r} is defined")
        names.add(identifier)
    if not names:
        raise LinkError(f"{what} scope is empty")
    return names


def _namespace(spec: str, prefixes: Prefixes, what: str) -> str:
    try:
        return prefixes.namespace(spec, context=what)
    except ValueError as err:
        raise LinkError(str(err)) from None


def _identifier(value: str, prefixes: Prefixes, what: str) -> str:
    try:
        return prefixes.expand(value, context=what)
    except ValueError as err:
        raise LinkError(str(err)) from None


def _near_miss(namespace: str, parsed: ParsedSystem) -> str:
    """A hint when `namespace` differs from a real one only by its trailing
    separator."""
    stem = namespace.rstrip("/#")
    for ns in {p.namespace for p in parsed.processes.values() if p.namespace}:
        if ns != namespace and ns.rstrip("/#") == stem:
            return f"; did you mean <{ns}>?"
    return ""


def _substitute(
    processes: Dict[str, ProcessDef],
    substitutions: List[RecipeSubstitution],
    parsed: ParsedSystem,
    prefixes: Prefixes,
) -> Dict[str, ProcessDef]:
    """Apply every substitution, refusing overlaps and substitutions that match
    nothing."""
    plan: Dict[str, Dict[str, str]] = {name: {} for name in processes}
    origin: Dict[Tuple[str, str], int] = {}
    for index, sub in enumerate(substitutions):
        in_scope = _scope(sub.scope, parsed, prefixes, "RecipeSubstitution")
        outside = in_scope - set(processes)
        if outside and sub.scope is not ALL and not isinstance(sub.scope, str):
            raise LinkError(
                "RecipeSubstitution scope names processes the model does not select: "
                + ", ".join(sorted(prefixes.compact(n) for n in outside))
            )
        targets = [n for n in processes if n in in_scope]
        if not sub.replacements:
            raise LinkError(f"RecipeSubstitution {sub.scope!r} replaces nothing")
        for raw_from, raw_to in sub.replacements.items():
            old = _identifier(raw_from, prefixes, "RecipeSubstitution")
            new = _identifier(raw_to, prefixes, "RecipeSubstitution")
            if is_placeholder(new):
                raise LinkError(
                    f"RecipeSubstitution: {raw_from!r} cannot be replaced by another "
                    f"placeholder ({raw_to!r})"
                )
            hits = [n for n in targets if old in processes[n].references()]
            if not hits:
                raise LinkError(
                    f"RecipeSubstitution {sub.scope!r}: no selected process in scope "
                    f"refers to {raw_from!r}"
                )
            for name in hits:
                if (name, old) in origin:
                    raise LinkError(
                        f"two RecipeSubstitutions replace {raw_from!r} in "
                        f"{prefixes.compact(name)}: give their scopes no overlap"
                    )
                origin[(name, old)] = index
                plan[name][old] = new

    def apply(items: List[RecipeItem], mapping: Dict[str, str]) -> List[RecipeItem]:
        return [
            replace(i, object_name=mapping.get(i.object_name, i.object_name))
            for i in items
        ]

    result: Dict[str, ProcessDef] = {}
    for name, proc in processes.items():
        mapping = plan[name]
        if not mapping:
            result[name] = proc
            continue
        per = proc.per
        if isinstance(per, dict) and per.get("object") in mapping:
            per = {**per, "object": mapping[per["object"]]}
        result[name] = replace(
            proc,
            consumes=apply(proc.consumes, mapping),
            produces=apply(proc.produces, mapping),
            per=per,
        )
    return result


def _objects_referred_to(
    processes: Dict[str, ProcessDef], parsed: ParsedSystem, prefixes: Prefixes
) -> Dict[str, ObjectDef]:
    """The objects the processes refer to, and their declared ancestors, in parse
    order."""
    needed: Set[str] = set()
    missing: List[str] = []
    for name, proc in processes.items():
        for ref in proc.references():
            if ref in parsed.objects:
                needed.add(ref)
            else:
                missing.append(f"{prefixes.compact(name)} -> {prefixes.compact(ref)}")
    if missing:
        raise LinkError(
            "processes refer to objects that are never defined: " + "; ".join(missing)
        )
    frontier = list(needed)
    while frontier:
        parent = parsed.objects[frontier.pop()].parent
        if parent is not None and parent in parsed.objects and parent not in needed:
            needed.add(parent)
            frontier.append(parent)
    return {name: obj for name, obj in parsed.objects.items() if name in needed}


def _override(
    objects: Dict[str, ObjectDef], overrides: List[ObjectOverride], prefixes: Prefixes
) -> Dict[str, ObjectDef]:
    seen: Set[str] = set()
    for override in overrides:
        name = _identifier(override.object, prefixes, "ObjectOverride")
        if name not in objects:
            raise LinkError(
                f"ObjectOverride: {override.object!r} is not an object of this model"
            )
        if name in seen:
            raise LinkError(f"two ObjectOverrides for {override.object!r}")
        seen.add(name)
        can_import, can_export = objects[name].traded or (False, False)
        if override.can_import is not None:
            can_import = override.can_import
        if override.can_export is not None:
            can_export = override.can_export
        objects[name] = replace(objects[name], traded=(can_import, can_export))
    return objects


def _localise(
    processes: Dict[str, ProcessDef],
    objects: Dict[str, ObjectDef],
    parsed: ParsedSystem,
    prefixes: Prefixes,
) -> ParsedSystem:
    """Rename every identifier in the model to its local name."""
    local: Dict[str, str] = {}
    for kind, definitions in (("object", objects), ("process", processes)):
        owners: Dict[str, str] = {}
        for identifier, definition in definitions.items():
            name = definition.local_name
            if name is None:
                raise LinkError(
                    f"{kind} <{identifier}> was declared as a full IRI and has no "
                    "local name to link under; declare it with a prefix"
                )
            if name in owners:
                raise LinkError(
                    f"two {kind}s would both be called {name!r} in the linked "
                    f"model: {prefixes.compact(owners[name])} and "
                    f"{prefixes.compact(identifier)}"
                )
            owners[name] = identifier
            local[identifier] = name

    def rename(identifier: str) -> str:
        """A reference's local name: its definition's, else how it was written."""
        if identifier in local:
            return local[identifier]
        spellings = parsed.local_names.get(identifier, set())
        if len(spellings) == 1:
            return next(iter(spellings))
        if not spellings:
            return identifier
        raise LinkError(
            f"{prefixes.compact(identifier)} is written with different local names "
            f"({sorted(spellings)}) and is not defined in the model to settle it"
        )

    def rename_items(items: List[RecipeItem]) -> List[RecipeItem]:
        return [replace(i, object_name=rename(i.object_name)) for i in items]

    linked_objects: Dict[str, ObjectDef] = {}
    for identifier, obj in objects.items():
        linked_objects[local[identifier]] = replace(
            obj,
            name=local[identifier],
            parent=None if obj.parent is None else rename(obj.parent),
            composed_of=[rename(c) for c in obj.composed_of],
            composed_of_children_of=[rename(c) for c in obj.composed_of_children_of],
        )
    linked_processes: Dict[str, ProcessDef] = {}
    for identifier, proc in processes.items():
        per = proc.per
        if isinstance(per, dict) and isinstance(per.get("object"), str):
            per = {**per, "object": rename(per["object"])}
        linked_processes[local[identifier]] = replace(
            proc,
            name=local[identifier],
            parent=None if proc.parent is None else rename(proc.parent),
            composed_of=[rename(c) for c in proc.composed_of],
            composed_of_children_of=[rename(c) for c in proc.composed_of_children_of],
            consumes=rename_items(proc.consumes),
            produces=rename_items(proc.produces),
            per=per,
        )
    return ParsedSystem(
        objects=linked_objects,
        processes=linked_processes,
        parameters=dict(parsed.parameters),
        units=parsed.units,
        prefixes=None,
        local_names={name: {name} for name in [*linked_objects, *linked_processes]},
    )
