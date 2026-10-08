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
    The current namespace for bare names: the table's ``""`` entry, unless a
    ``system:prefix`` directive earlier in the document has set another.

With no prefix table the default namespace is ``""``, so a bare name is its own
identifier.

Namespaces are recorded, not inferred
-------------------------------------

RDF has no notion of which namespace an IRI belongs to: a prefix is an abbreviation, and
``<http://ex.org/a/b>`` is equally ``a:b`` and ``ab:`` + ``b`` under different bindings.
So the namespace of a *definition* is recorded when it is declared -- the namespace its
prefix expanded to (:meth:`Prefixes.split`) -- and never recovered from the IRI string
afterwards. A definition written as a full ``<iri>`` belongs to no namespace.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional, Tuple

#: The pseudo-prefix of a placeholder, as for a Turtle blank node. It cannot be
#: declared.
PLACEHOLDER_PREFIX = "_"


def is_placeholder(identifier: str) -> bool:
    """Whether `identifier` is a placeholder (``_:label``)."""
    return identifier.startswith(PLACEHOLDER_PREFIX + ":")


class Prefixes:
    """A prefix table: prefix names to namespace IRIs.

    Its ``""`` entry is the default namespace for bare names (``""`` if not given).
    """

    def __init__(self, table: Optional[Mapping[str, str]] = None) -> None:
        self._table: Dict[str, str] = dict(table or {})
        if PLACEHOLDER_PREFIX in self._table:
            raise ValueError(
                f"prefix {PLACEHOLDER_PREFIX!r} is reserved for placeholders "
                "(_:label) and cannot be declared"
            )
        self._table.setdefault("", "")

    @property
    def table(self) -> Dict[str, str]:
        """A copy of the prefix table."""
        return dict(self._table)

    @property
    def default(self) -> str:
        """The project-wide default namespace for bare names."""
        return self._table[""]

    def namespace(self, spec: str, *, context: str = "") -> str:
        """The namespace IRI that `spec` names.

        `spec` is a prefix name (``"usmf-a"``), the same with a trailing colon
        (``"usmf-a:"``), or a full ``"<iri>"``. ``":"`` is the default namespace.
        """
        if spec.startswith("<") and spec.endswith(">"):
            return spec[1:-1]
        name = spec[:-1] if spec.endswith(":") else spec
        if name not in self._table:
            where = f" in {context}" if context else ""
            raise ValueError(
                f"unknown prefix {name!r}{where}; declared prefixes are "
                f"{sorted(k for k in self._table if k)}"
            )
        return self._table[name]

    def split(
        self,
        value: str,
        *,
        default: Optional[str] = None,
        default_local: Optional[str] = None,
        context: str = "",
    ) -> Tuple[str, Optional[str]]:
        """`value`'s identifier, and the namespace it was written in.

        `default` is the namespace for bare names here (set by ``system:prefix``); it
        defaults to the table's ``""`` entry. `default_local` is the local name a
        ``prefix:`` with nothing after it stands for; without one, that is an error.

        The namespace is ``None`` for a full ``<iri>`` and for a placeholder, which is
        returned unchanged.
        """
        where = f" in {context}" if context else ""
        value = value.strip()
        if not value:
            raise ValueError(f"empty identifier{where}")
        if is_placeholder(value):
            if len(value) == len(PLACEHOLDER_PREFIX) + 1:
                raise ValueError(f"placeholder {value!r}{where} has no label")
            return value, None
        if value.startswith("<") and value.endswith(">"):
            return value[1:-1], None
        prefix, colon, local = value.partition(":")
        if not colon:
            prefix, local = "", value
        if prefix == "" and default is not None:
            namespace = default
        else:
            namespace = self.namespace(prefix, context=f"{value!r}{where}")
        if not local:
            if default_local is None:
                raise ValueError(f"identifier {value!r}{where} has no local name")
            local = default_local
        return namespace + local, namespace

    def expand(
        self,
        value: str,
        *,
        default: Optional[str] = None,
        default_local: Optional[str] = None,
        context: str = "",
    ) -> str:
        """`value`'s identifier. See :meth:`split`."""
        return self.split(
            value, default=default, default_local=default_local, context=context
        )[0]

    def compact(self, identifier: str) -> str:
        """`identifier` abbreviated with the longest matching prefix, preferring a
        named prefix to the default one."""
        if is_placeholder(identifier):
            return identifier
        best: Optional[Tuple[str, str]] = None
        for name, iri in self._table.items():
            if iri and identifier.startswith(iri) and len(identifier) > len(iri):
                if (
                    best is None
                    or len(iri) > len(best[1])
                    or (len(iri) == len(best[1]) and best[0] == "")
                ):
                    best = (name, iri)
        if best is not None:
            return f"{best[0]}:{identifier[len(best[1]):]}"
        if not self._table[""] and ":" not in identifier:
            return identifier
        return f"<{identifier}>"
