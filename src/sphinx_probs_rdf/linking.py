"""Linking: from a library of system definitions to one concrete model.

A parsed system can hold more than one model's worth of definitions -- a shared core and
several alternative readings of some part of it, each in a namespace of its own. Linking
picks one model out of that library, wires it, and gives everything a short name::

    link_model(
        library,
        [
            ProcessSelection("us:", {"_:HotBand": "alloc:HotBandForSale"}),
            ProcessSelection("alloc:"),
        ],
        object_overrides={"us:HotBand": {"traded": (True, False)}},
    )

* Each :class:`ProcessSelection` selects processes, and can remap the objects their
  recipes refer to: "in these processes, where the recipe says X, use Y". This is how a
  placeholder (``_:label``) is filled, and how a reference is rewired without touching
  either definition. **Objects are not selected**: a model contains exactly the objects
  its processes refer to (recipe items and ``per`` objects), with their declared
  ancestors.
* ``object_overrides`` changes fields of an object (e.g. ``traded``) for this model.
* ``local_names`` names definitions in the linked model; the rest are named by the rule
  below.

The result is an ordinary :class:`~sphinx_probs_rdf.model.ParsedSystem`, so a consumer
that knows nothing of prefixes or IRIs can use it as it is.

Scopes
------

A selection's scope is ``ALL`` (every process), or a string or list of strings, each of
which is either

``"prefix:"``
    every process **declared in** that namespace (``ProcessDef.namespace``,
    ``rdfs:isDefinedBy`` in RDF), compared exactly. It is never inferred from the IRI,
    so namespaces may nest freely: a process declared in ``…/us/mill-feed/`` is not in
    ``…/us/``; or
``"prefix:Name"``, ``"Name"`` or ``"<iri>"``
    that one process.

A process in several selections takes the remapping of each, so a remapping can be
scoped to one process::

    [ProcessSelection("us:Sale", {...}), ProcessSelection("us:")]

Names in the linked model
-------------------------

A definition is called by its local name -- its identifier less the namespace it was
declared in -- unless another of its kind would be called the same, when it is called
by its prefixed name (``rec:HotStripMill``, or ``<iri>`` if no prefix fits). A parent
that is never declared is kept, and named the same way.

Errors
------

A scope that names nothing; a remapping that matches nothing in its scope, or maps one
reference in one process to two different objects; a placeholder left open; a reference
to an object never defined; an override or a local name for something not in the model;
two definitions given the same local name.
"""

from __future__ import annotations

import enum
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Union,
)

from .identifiers import Prefixes
from .model import ObjectDef, ParsedSystem, ProcessDef


class _All(enum.Enum):
    ALL = "ALL"

    def __repr__(self) -> str:
        return "ALL"


#: The scope of every process.
ALL = _All.ALL

Scope = Union[_All, str, Sequence[str]]


class LinkError(ValueError):
    """A model could not be linked as specified."""


@dataclass(frozen=True)
class ProcessSelection:
    """Include the processes in `scope` (see the module docstring), and in them replace
    each key of `remap` with its value wherever a recipe item or a ``per`` object refers
    to it.

    Keys are placeholders (``"_:HotBand"``) or ordinary identifiers; values are
    identifiers of objects the model will contain. A key must occur in at least one
    process in scope.
    """

    scope: Scope
    remap: Mapping[str, str] = field(default_factory=dict)


def link_model(
    parsed: ParsedSystem,
    selections: Iterable[ProcessSelection],
    *,
    object_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    local_names: Optional[Mapping[str, str]] = None,
) -> ParsedSystem:
    """Link one model from `parsed`: select and remap, override, then name.

    `object_overrides` maps an object to the :class:`~sphinx_probs_rdf.model.ObjectDef`
    fields to change, e.g. ``{"us:HotBand": {"traded": (True, False)}}``. `local_names`
    maps an object or process to its name in the linked model.

    Definition order is kept: processes and objects appear in the order they were
    parsed.
    """
    prefixes = Prefixes(parsed.prefixes)

    def expand(value: str) -> str:
        try:
            return prefixes.expand(value)
        except ValueError as err:
            raise LinkError(str(err)) from None

    remaps: Dict[str, Dict[str, str]] = {}
    for selection in selections:
        in_scope = _scope(selection.scope, parsed, prefixes, expand)
        for name in in_scope:
            remaps.setdefault(name, {})
        for raw_old, raw_new in selection.remap.items():
            old, new = expand(raw_old), expand(raw_new)
            hits = [n for n in in_scope if old in parsed.processes[n].references()]
            if not hits:
                raise LinkError(
                    f"ProcessSelection {selection.scope!r}: no process in scope "
                    f"refers to {raw_old!r}"
                )
            for name in hits:
                if remaps[name].get(old, new) != new:
                    raise LinkError(
                        f"{raw_old!r} in {prefixes.compact(name)} is remapped to both "
                        f"{prefixes.compact(remaps[name][old])} and "
                        f"{prefixes.compact(new)}"
                    )
                remaps[name][old] = new
    processes = {
        name: _rename(proc, remaps[name])
        for name, proc in parsed.processes.items()
        if name in remaps
    }

    still_open = [
        f"{prefixes.compact(name)}: {label}"
        for name, proc in processes.items()
        for label in proc.placeholders()
    ]
    if still_open:
        raise LinkError(
            "placeholders left open (fill each with a ProcessSelection remap): "
            + "; ".join(still_open)
        )

    objects = _objects_referred_to(processes, parsed, prefixes)
    for raw, fields in (object_overrides or {}).items():
        name = expand(raw)
        if name not in objects:
            raise LinkError(f"object_overrides: {raw!r} is not an object of this model")
        objects[name] = replace(objects[name], **fields)

    explicit = {expand(k): v for k, v in (local_names or {}).items()}
    object_names = _names(
        [*objects, *(o.parent for o in objects.values() if o.parent is not None)],
        parsed.objects,
        explicit,
        prefixes,
        "object",
    )
    process_names = _names(
        [*processes, *(p.parent for p in processes.values() if p.parent is not None)],
        parsed.processes,
        explicit,
        prefixes,
        "process",
    )
    unused = set(explicit) - set(object_names) - set(process_names)
    if unused:
        raise LinkError(
            "local_names: not in this model: "
            + ", ".join(sorted(prefixes.compact(n) for n in unused))
        )

    def parent(name: Optional[str], names: Dict[str, str]) -> Optional[str]:
        return names[name] if name is not None else None

    def in_model(
        members: List[str], names: Dict[str, str], model: Mapping
    ) -> List[str]:
        """The hierarchy links that stay inside the model, renamed."""
        return [names[n] for n in members if n in model]

    return ParsedSystem(
        objects={
            object_names[name]: replace(
                obj,
                name=object_names[name],
                parent=parent(obj.parent, object_names),
                composed_of=in_model(obj.composed_of, object_names, objects),
                composed_of_children_of=in_model(
                    obj.composed_of_children_of, object_names, objects
                ),
            )
            for name, obj in objects.items()
        },
        processes={
            process_names[name]: replace(
                _rename(proc, object_names),
                name=process_names[name],
                parent=parent(proc.parent, process_names),
                composed_of=in_model(proc.composed_of, process_names, processes),
                composed_of_children_of=in_model(
                    proc.composed_of_children_of, process_names, processes
                ),
            )
            for name, proc in processes.items()
        },
        parameters=dict(parsed.parameters),
        units=parsed.units,
        prefixes=None,
    )


def _scope(scope: Scope, parsed: ParsedSystem, prefixes: Prefixes, expand) -> Set[str]:
    """The processes `scope` names, as identifiers."""
    if scope is ALL:
        return set(parsed.processes)
    assert not isinstance(scope, _All)
    found: Set[str] = set()
    for entry in [scope] if isinstance(scope, str) else scope:
        if entry.endswith(":") and not entry.startswith("<"):
            try:
                namespace = prefixes.namespace(entry)
            except ValueError as err:
                raise LinkError(str(err)) from None
            members = {
                n for n, p in parsed.processes.items() if p.namespace == namespace
            }
            if not members:
                raise LinkError(
                    f"scope {entry!r}: no process is declared in namespace "
                    f"<{namespace}>"
                )
            found |= members
        else:
            identifier = expand(entry)
            if identifier not in parsed.processes:
                raise LinkError(f"scope: no process {entry!r} is defined")
            found.add(identifier)
    return found


def _rename(proc: ProcessDef, mapping: Mapping[str, str]) -> ProcessDef:
    """`proc` with each object it refers to (recipe items and ``per``) renamed by
    `mapping`; names not in `mapping` are kept."""
    if not mapping:
        return proc
    per = proc.per
    if isinstance(per, dict) and isinstance(per.get("object"), str):
        per = {**per, "object": mapping.get(per["object"], per["object"])}
    return replace(
        proc,
        consumes=[
            replace(i, object_name=mapping.get(i.object_name, i.object_name))
            for i in proc.consumes
        ],
        produces=[
            replace(i, object_name=mapping.get(i.object_name, i.object_name))
            for i in proc.produces
        ],
        per=per,
    )


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


def _names(
    identifiers: List[str],
    definitions: Mapping[str, Union[ObjectDef, ProcessDef]],
    explicit: Mapping[str, str],
    prefixes: Prefixes,
    kind: str,
) -> Dict[str, str]:
    """The name of each of `identifiers` in the linked model (see the module
    docstring)."""

    def local(identifier: str) -> str:
        definition = definitions.get(identifier)
        if definition is not None and definition.namespace is not None:
            return identifier[len(definition.namespace):]
        # Never declared, or declared as a full IRI: there is no recorded namespace,
        # so the name goes by its prefixed spelling.
        compact = prefixes.compact(identifier)
        _, colon, rest = compact.partition(":")
        return rest if colon and not compact.startswith("<") else compact

    identifiers = list(dict.fromkeys(identifiers))
    wanted = {i: explicit.get(i) or local(i) for i in identifiers}
    counts = Counter(wanted.values())
    names = {
        i: name if i in explicit or counts[name] == 1 else prefixes.compact(i)
        for i, name in wanted.items()
    }
    clashes = [
        name for name, count in Counter(names.values()).items() if count > 1
    ]
    if clashes:
        raise LinkError(
            f"two {kind}s would both be called {clashes[0]!r} in the linked model: "
            + ", ".join(prefixes.compact(i) for i in names if names[i] == clashes[0])
        )
    return names
