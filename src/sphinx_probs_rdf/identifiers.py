"""System identifiers: prefix expansion, placeholders and namespaces, as plain strings.

Shared by the standalone loader and the Sphinx/RDF path, so that one spelling always
means one identifier. Nothing here imports rdflib: an identifier stays a ``str`` until
the RDF writer turns it into a ``URIRef``.

How a reference is read
-----------------------

``<iri>``
    The IRI, as written.
``_:label``
    A **placeholder**: an object a process refers to without naming it, filled in when a
    model is linked (:func:`sphinx_probs_rdf.linking.link_model`). Like a blank node in
    Turtle, it has no IRI. Unlike one, its label is scoped to the *process* that uses
    it, not to the document.
``prefix:local``
    The namespace bound to ``prefix`` in the prefix table, followed by ``local``. Only
    the first colon separates the prefix, as in Turtle, so ``local`` may itself contain
    colons.
``:local`` or ``local``
    The default namespace for bare names in the current file: the table's ``""`` entry,
    unless the file's front matter sets ``system_prefix``.

**Opaque mode.** With no prefix table at all, nothing is expanded: every identifier is
used exactly as written, which is what a single-namespace user wants, and what the
loader always did before prefixes were supported. Only placeholders are recognised.

Namespaces are recorded, not inferred
-------------------------------------

RDF has no notion of which namespace an IRI belongs to: a prefix is an abbreviation, and
``<http://ex.org/a/b>`` is equally ``a:b`` and ``ab:`` + ``b`` under different bindings.
So the namespace of a *definition* is recorded when it is declared -- the namespace its
prefix expanded to -- together with its local name (:class:`Name`), and never recovered
from the IRI string afterwards. A definition written as a full ``<iri>`` belongs to no
namespace.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Mapping, Optional

log = logging.getLogger(__name__)

#: The pseudo-prefix of a placeholder, as for a Turtle blank node. It cannot be
#: declared.
PLACEHOLDER_PREFIX = "_"


def is_placeholder(identifier: str) -> bool:
    """Whether `identifier` is a placeholder (``_:label``)."""
    return identifier.startswith(PLACEHOLDER_PREFIX + ":")


@dataclass(frozen=True)
class Name:
    """An identifier as expanded, with the parts it was declared with.

    ``namespace`` and ``local`` are ``None`` for a full ``<iri>``, which names no
    namespace
    and has no reliable local part. In opaque mode the namespace is ``""`` and the local
    name is the identifier as written.
    """

    identifier: str
    namespace: Optional[str]
    local: Optional[str]


class Prefixes:
    """A prefix table, or none (opaque mode).

    ``table`` maps prefix names to namespace IRIs; its ``""`` entry is the default
    namespace
    for bare names. ``None`` means opaque mode: see the module docstring.
    """

    def __init__(self, table: Optional[Mapping[str, str]] = None) -> None:
        if table is None:
            self._table: Optional[Dict[str, str]] = None
            return
        table = dict(table)
        if PLACEHOLDER_PREFIX in table:
            raise ValueError(
                f"prefix {PLACEHOLDER_PREFIX!r} is reserved for placeholders "
                "(_:label) and cannot be declared"
            )
        for name, iri in table.items():
            if not isinstance(name, str) or not isinstance(iri, str):
                raise TypeError(
                    f"prefix table entries must be strings: {name!r}: {iri!r}"
                )
            if ":" in name:
                raise ValueError(f"prefix name {name!r} cannot contain ':'")
            if iri and iri[-1] not in "/#":
                log.warning(
                    "prefix %r is bound to %r, which ends in neither '/' nor '#': "
                    "%s:Foo would expand to %r",
                    name, iri, name or "", iri + "Foo",
                )
        table.setdefault("", "")
        self._table = table

    @property
    def opaque(self) -> bool:
        """Whether there is no prefix table, so identifiers are used as written."""
        return self._table is None

    @property
    def table(self) -> Optional[Dict[str, str]]:
        """A copy of the prefix table, or ``None`` in opaque mode."""
        return None if self._table is None else dict(self._table)

    @property
    def default(self) -> str:
        """The project-wide default namespace for bare names (``""`` in opaque mode)."""
        return "" if self._table is None else self._table[""]

    def namespace(self, spec: str, *, context: str = "") -> str:
        """The namespace IRI that `spec` names.

        `spec` is a prefix name (``"usmf-a"``), the same with a trailing colon
        (``"usmf-a:"``), or a full ``"<iri>"``. Used for a file's ``system_prefix`` and
        for a namespace selection when linking.
        """
        where = f" in {context}" if context else ""
        if spec.startswith("<") and spec.endswith(">"):
            return spec[1:-1]
        name = spec[:-1] if spec.endswith(":") else spec
        if self._table is None:
            if name == "":
                return ""
            raise ValueError(
                f"namespace {spec!r}{where} needs a prefix table, but none was given"
            )
        if name not in self._table:
            raise ValueError(
                f"unknown prefix {name!r}{where}; declared prefixes are "
                f"{sorted(k for k in self._table if k)}"
            )
        return self._table[name]

    def split(
        self, value: str, *, default: Optional[str] = None, context: str = ""
    ) -> Name:
        """Expand `value`, keeping the namespace and local name it was written with.

        `default` is the namespace for bare names here (a file's ``system_prefix``); it
        defaults to the table's ``""`` entry. Placeholders are returned unchanged, with
        no namespace.
        """
        where = f" in {context}" if context else ""
        value = value.strip()
        if not value:
            raise ValueError(f"empty identifier{where}")
        if is_placeholder(value):
            if len(value) == len(PLACEHOLDER_PREFIX) + 1:
                raise ValueError(f"placeholder {value!r}{where} has no label")
            return Name(value, None, None)
        if self._table is None:
            return Name(value, "", value)
        if value.startswith("<") and value.endswith(">"):
            return Name(value[1:-1], None, None)
        prefix, colon, local = value.partition(":")
        if not colon:
            prefix, local = "", value
        if not local:
            raise ValueError(f"identifier {value!r}{where} has no local name")
        if prefix == "":
            namespace = self._table[""] if default is None else default
        elif prefix in self._table:
            namespace = self._table[prefix]
        else:
            raise ValueError(
                f"unknown prefix {prefix!r} in {value!r}{where}; declared prefixes are "
                f"{sorted(k for k in self._table if k)}"
            )
        return Name(namespace + local, namespace, local)

    def expand(
        self, value: str, *, default: Optional[str] = None, context: str = ""
    ) -> str:
        """`value`'s expanded identifier. See :meth:`split`."""
        return self.split(value, default=default, context=context).identifier

    def compact(self, identifier: str) -> str:
        """`identifier` abbreviated with the longest matching prefix, for messages."""
        if self._table is None or is_placeholder(identifier):
            return identifier
        best: Optional[tuple] = None
        for name, iri in self._table.items():
            if iri and identifier.startswith(iri) and len(identifier) > len(iri):
                if best is None or len(iri) > len(best[1]):
                    best = (name, iri)
        if best is None:
            return identifier if not self._table[""] else f"<{identifier}>"
        return f"{best[0]}:{identifier[len(best[1]):]}"
