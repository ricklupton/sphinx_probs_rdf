"""Parse ``system:process`` / ``system:object`` / ``system:parameter`` MyST directive
fences directly into a :class:`sphinx_probs_rdf.model.ParsedSystem`.

Identifiers are plain strings, expanded with a prefix table the way the Sphinx/RDF path
expands them; without one, a bare name is its own identifier. A ``system:prefix``
directive sets the namespace of the bare names that follow it in the same file. See
:mod:`sphinx_probs_rdf.identifiers`.

Security
--------
``:defs:`` blocks and recipe ``amount`` expressions are executed with ``exec``/
``eval`` by ``grammar.expand_consumes_produces_amounts``. Only parse files you trust.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import (
    Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Set, Tuple, Union,
)

from docutils.parsers.rst import Directive
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from myst_parser.config.main import MdParserConfig
from myst_parser.parsers.directives import parse_directive_text
from myst_parser.parsers.mdit import create_md_parser

from . import grammar
from .identifiers import Prefixes, is_placeholder
from .model import (
    FactorSpec,
    ObjectDef,
    ParameterDef,
    ParsedSystem,
    ProcessDef,
    RecipeItem,
)
from .units import DEFAULT_UNITS, UnitTable
from .validate import validate as _validate_system

log = logging.getLogger(__name__)

#: Directive names this module understands. Other directives are silently ignored;
#: except for unknown ``system:*`` directives, which cause a warning.
PROCESS_DIRECTIVE = "system:process"
OBJECT_DIRECTIVE = "system:object"
PARAMETER_DIRECTIVE = "system:parameter"
PREFIX_DIRECTIVE = "system:prefix"
END_SUB_PROCESSES = "end-sub-processes"
END_SUB_OBJECTS = "end-sub-objects"

#: A MyST config that tokenises ``:::`` fences the same way ``colon_fence`` does --
DEFAULT_MD_CONFIG = MdParserConfig(enable_extensions={"colon_fence"})

#: Shim directives for parsing


class _ProcessShim(Directive):
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    has_content = True
    option_spec = grammar.PROCESS_OPTION_SPEC


class _ObjectShim(Directive):
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    has_content = True
    option_spec = grammar.OBJECT_OPTION_SPEC


class _ParameterShim(Directive):
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    has_content = True
    option_spec = grammar.CORE_PARAMETER_OPTIONS


# ----------------------------------------------------------------------------------
# Tokenising
# ----------------------------------------------------------------------------------


def _directive_fences(
    text: str, md_config: MdParserConfig
) -> Iterator[Tuple[str, str, Token]]:
    """Yield ``(directive_name, argument, token)`` for each directive fence in `text`.

    Tokenised by the MyST-configured markdown-it parser, so fences are recognised the
    same way the Sphinx build recognises them. Both plain ```` ``` ```` fences and
    ``:::`` colon fences are accepted.
    """
    md = create_md_parser(md_config, RendererHTML)
    for token in md.parse(text):
        if token.type not in ("fence", "colon_fence"):
            continue
        info = token.info.strip()
        if not (info.startswith("{") and "}" in info):
            continue
        name, _, argument = info[1:].partition("}")
        yield name.strip(), argument.strip(), token


def _recipe_items(
    raw_items: Iterable[Any],
    units: UnitTable,
    context: str,
    expand: Callable[[str], str] = lambda name: name,
) -> List[RecipeItem]:
    """Convert `grammar.parse_consumes_or_produces`-parsed items into `RecipeItem`s.

    `expand` turns each object reference into its identifier.
    """
    items = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValueError(f"could not parse recipe item {raw!r} in {context}")
        extra = {k: v for k, v in raw.items() if k not in ("object", "amount", "unit")}
        unit = raw.get("unit")
        unit = unit.strip() if isinstance(unit, str) else unit
        amount = raw.get("amount")
        if amount is not None and unit is None:
            # sphinx_probs_rdf defaults a missing unit to kg with a logged error; be
            # explicit here rather than silently assuming a unit.
            raise ValueError(
                f"recipe item {raw['object']!r} in {context} has an amount but no unit"
            )
        if unit is not None and not units.is_share(unit) and unit not in units.units:
            raise ValueError(
                f"unsupported unit {unit!r} for {raw['object']!r} in {context}"
            )
        items.append(
            RecipeItem(
                object_name=expand(str(raw["object"])),
                amount=float(amount) if amount is not None else None,
                unit=unit,
                extra=extra,
            )
        )
    return items


def _factor_specs(raw: Dict[str, Any], context: str) -> Dict[str, FactorSpec]:
    """Convert a parsed ``:factors:`` YAML mapping into ``{basis: FactorSpec}``."""
    specs = {}
    for basis, spec in raw.items():
        if not isinstance(spec, dict):
            raise ValueError(
                f"factor {basis!r} in {context} must be a YAML mapping, got {spec!r}"
            )
        range_ = spec.get("range")
        specs[basis] = FactorSpec(
            value=spec.get("value"),
            unit=spec.get("unit"),
            range=tuple(range_) if range_ is not None else None,
            source=spec.get("source"),
            derived=bool(spec.get("derived", False)),
        )
    return specs


_VALUE_UNIT_RE = re.compile(r"^\s*([0-9.eE+-]+)\s*(.*?)\s*$")


def _split_value_unit(raw: str, context: str) -> Tuple[float, Optional[str]]:
    """Split a `system:parameter`'s `:value:` (``"0.467 t/m3"``) into (number, unit)."""
    match = _VALUE_UNIT_RE.match(raw)
    if not match or not match.group(1):
        raise ValueError(
            f"could not parse value {raw!r} in {context} as 'NUMBER [unit]'"
        )
    return float(match.group(1)), (match.group(2) or None)


class _Parser:
    """Walks directive fences, maintaining the ``become_parent`` nesting stacks.

    The stacks mirror Sphinx's ``env.ref_context["system:processes"]`` /
    ``["system:objects"]``, and are updated in the same order the directive classes
    do it: a directive's parent is read *before* it pushes itself (matching
    ``handle_signature`` running before ``before_content``), its body is then parsed
    with itself on the stack, and it pops again afterwards unless it declared
    ``:become_parent:``.
    """

    def __init__(
        self, units: UnitTable, md_config: MdParserConfig, prefixes: Prefixes
    ) -> None:
        self.units = units
        self.md_config = md_config
        self.prefixes = prefixes
        self.system = ParsedSystem(
            objects={}, processes={}, parameters={}, units=units,
            prefixes=prefixes.table,
        )
        self.stacks: Dict[str, List[str]] = {
            PROCESS_DIRECTIVE: [], OBJECT_DIRECTIVE: []
        }
        #: The namespace of bare names in the file being parsed.
        self.default_ns = prefixes.default

    def parse_file(self, path: Path) -> None:
        self.parse_text(path.read_text(), origin=path.name)

    def parse_text(self, text: str, origin: str) -> None:
        # As Sphinx's ref_context, which holds the current prefix, is per document.
        self.default_ns = self.prefixes.default
        self._walk(text, origin=origin, line_offset=0)

    def _expand(
        self,
        value: str,
        where: str,
        *,
        placeholder_ok: bool = False,
        default_local: Optional[str] = None,
    ) -> str:
        """`value`'s identifier, read with the current namespace for bare names."""
        if is_placeholder(value.strip()) and not placeholder_ok:
            raise ValueError(
                f"{where}: placeholder {value!r} can only stand for an object a "
                "process consumes or produces"
            )
        return self.prefixes.expand(
            value, default=self.default_ns, default_local=default_local, context=where
        )

    def _walk(self, text: str, origin: str, line_offset: int) -> None:
        for name, argument, token in _directive_fences(text, self.md_config):
            line = line_offset + ((token.map[0] + 1) if token.map else 0)
            where = f"{origin}:{line}"

            if name in (END_SUB_PROCESSES, END_SUB_OBJECTS):
                kind = (
                    PROCESS_DIRECTIVE if name == END_SUB_PROCESSES else OBJECT_DIRECTIVE
                )
                if self.stacks[kind]:
                    self.stacks[kind].pop()
                else:
                    log.warning("%s: %s with nothing to end", where, name)
                continue

            if name == PREFIX_DIRECTIVE:
                self.default_ns = self.prefixes.namespace(argument, context=where)
                continue

            if name == PARAMETER_DIRECTIVE:
                self._parameter_directive(argument, token, where)
                continue

            if name in (PROCESS_DIRECTIVE, OBJECT_DIRECTIVE):
                self._directive(name, argument, token, where, origin, line)
                continue

            if name.startswith("system:"):
                log.warning("%s: unrecognised directive %r, not parsed", where, name)

    def _parameter_directive(self, argument: str, token: Token, where: str) -> None:
        """``system:parameter`` -- no nesting or body recursion."""
        parsed = parse_directive_text(
            _ParameterShim, argument, token.content, validate_options=True
        )
        for warning in parsed.warnings:
            log.warning("%s: %s", where, warning.msg)

        name = argument
        value, unit = (
            _split_value_unit(parsed.options["value"], where)
            if "value" in parsed.options
            else (None, None)
        )
        range_ = parsed.options.get("range")
        extra = {k: v for k, v in parsed.options.items()
                 if k not in ("label", "value", "range", "source")}
        definition = ParameterDef(
            name=name,
            label=parsed.options.get("label") or name,
            value=value,
            unit=unit,
            range=tuple(range_) if range_ is not None else None,
            source=parsed.options.get("source"),
            extra=extra,
        )
        if name in self.system.parameters:
            log.warning("%s: system:parameter %r redefined", where, name)
        self.system.parameters[name] = definition

    def _directive(
        self, name: str, argument: str, token: Token, where: str, origin: str, line: int
    ) -> None:
        is_process = name == PROCESS_DIRECTIVE
        shim = _ProcessShim if is_process else _ObjectShim
        parsed = parse_directive_text(
            shim, argument, token.content, validate_options=True
        )
        for warning in parsed.warnings:
            log.warning("%s: %s", where, warning.msg)

        if is_placeholder(argument):
            raise ValueError(f"{where}: a placeholder ({argument!r}) cannot be defined")
        key, namespace = self.prefixes.split(
            argument, default=self.default_ns, context=where
        )
        stack = self.stacks[name]
        parent_option = "parent" if is_process else "parent_object"
        parent_raw = parsed.options.get(parent_option)
        parent = (
            self._expand(parent_raw, where)
            if parent_raw
            else (stack[-1] if stack else None)
        )

        composed_of_raw = parsed.options.get("composed_of", [])
        composed_of = [
            self._expand(c, where) for c in composed_of_raw if not c.startswith("*")
        ]
        composed_of_children_of = [
            self._expand(c[1:], where) for c in composed_of_raw if c.startswith("*")
        ]
        label = parsed.options.get("label") or argument

        def expand_item(value: str) -> str:
            return self._expand(value, where, placeholder_ok=True)

        definition: Union[ObjectDef, ProcessDef]
        if is_process:
            consumes, produces = grammar.expand_consumes_produces_amounts(
                parsed.options.get("defs", ""),
                parsed.options.get("consumes", []),
                parsed.options.get("produces", []),
            )
            registry: Dict[str, Any] = self.system.processes
            definition = ProcessDef(
                name=key,
                label=label,
                parent=parent,
                composed_of=composed_of,
                composed_of_children_of=composed_of_children_of,
                source=where,
                consumes=_recipe_items(consumes, self.units, where, expand_item),
                produces=_recipe_items(produces, self.units, where, expand_item),
                per=self._per(parsed.options.get("per"), where),
                balance=parsed.options.get("balance"),
                extra=parsed.options.get("extra") or {},
                namespace=namespace,
            )
        else:
            registry = self.system.objects
            definition = ObjectDef(
                name=key,
                label=label,
                parent=parent,
                composed_of=composed_of,
                composed_of_children_of=composed_of_children_of,
                source=where,
                traded=parsed.options.get("traded"),
                # ``prefix:`` alone means this object's own name in that namespace.
                equivalent_to=[
                    self._expand(
                        e,
                        where,
                        default_local=(
                            key[len(namespace):] if namespace is not None else None
                        ),
                    )
                    for e in parsed.options.get("equivalent", [])
                ],
                basis=parsed.options.get("basis"),
                factors=_factor_specs(parsed.options.get("factors", {}), where),
                extra=parsed.options.get("extra") or {},
                namespace=namespace,
            )

        if key in registry:
            raise ValueError(
                f"{where}: {name} {self.prefixes.compact(key)!r} is already defined "
                f"at {registry[key].source}"
            )
        registry[key] = definition

        # Parse the body with this directive on the stack, so directives nested in it
        # take it as their parent -- and pop again unless it declared become_parent.
        stack.append(key)
        body = parsed.body
        if body:
            self._walk(
                "\n".join(body),
                origin=origin,
                line_offset=line + parsed.body_offset,
            )
        if "become_parent" not in parsed.options:
            stack.pop()

    def _per(self, per: Any, where: str) -> Any:
        """``per:`` with its object, if it names one, read as an identifier."""
        if isinstance(per, dict) and isinstance(per.get("object"), str):
            return {**per, "object": self._expand(per["object"], where,
                                                  placeholder_ok=True)}
        return per

    def finish(self) -> ParsedSystem:
        for kind, stack in self.stacks.items():
            if stack:
                log.warning("unclosed %s blocks at end of input: %s", kind, stack)
        return self.system


def _infer_object_bases(system: ParsedSystem) -> None:
    """Fill in ``ObjectDef.basis`` for every object that doesn't declare ``:basis:``
    explicitly, from its own (non-share) recipe items.

    An object with no ``:basis:`` and no recipe items to infer from at all has a
    basis of ``None``.
    """
    item_bases: Dict[str, Set[str]] = defaultdict(set)
    item_sources: Dict[str, Set[str]] = defaultdict(set)
    for process in system.processes.values():
        for item in process.consumes + process.produces:
            if (
                item.object_name not in system.objects
                or item.unit is None
                or item.is_share
            ):
                continue
            try:
                basis = item.basis(system.units)
            except ValueError:
                continue  # unsupported unit -- checked by validate pass
            if basis is not None:
                item_bases[item.object_name].add(basis)
                item_sources[item.object_name].add(process.source or "?")

    disagreements = []
    for name, obj in system.objects.items():
        if obj.basis is not None:
            continue
        bases = item_bases.get(name)
        if not bases:
            continue
        if len(bases) == 1:
            obj.basis = next(iter(bases))
        else:
            disagreements.append(
                f"{obj.source}: object {name!r} has no :basis: and its own recipe "
                f"items disagree on basis: {sorted(bases)} (seen in "
                f"{sorted(item_sources[name])})"
            )
    if disagreements:
        raise ValueError(
            f"{len(disagreements)} object(s) have recipe items that disagree on "
            "basis:\n" + "\n".join(disagreements)
        )


# ----------------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------------


def parse_system_definitions(
    paths: Iterable[Union[str, Path]],
    *,
    units: UnitTable = DEFAULT_UNITS,
    md_config: Optional[MdParserConfig] = None,
    validate: bool = True,
    prefixes: Optional[Mapping[str, str]] = None,
) -> ParsedSystem:
    """Parse `paths` (MyST markdown) into a `ParsedSystem`.

    Files are processed in the order given; the ``become_parent``/``end-sub-*``
    nesting stacks are shared across them, matching Sphinx's per-project
    ``ref_context``.

    `prefixes` is the prefix table (``{"": default namespace, name: namespace, ...}``),
    the counterpart of ``probs_rdf_system_prefix`` and ``probs_rdf_extra_prefixes`` on
    the Sphinx path. Without one, a bare name is its own identifier, and a prefixed one
    is an error. A ``system:prefix`` directive (``prefix``, ``prefix:`` or ``<iri>``)
    puts the bare names that follow it in its file in that namespace; ``:`` restores
    the default. The same identifier defined twice is an error.

    Every object's basis is resolved, raising a ValueError on inconsistencies.

    If `validate` (the default), structural problems found by
    :func:`sphinx_probs_rdf.validate.validate` are logged as warnings -- call
    ``validate()`` yourself for the list of problem strings.
    """
    parser = _Parser(units, md_config or DEFAULT_MD_CONFIG, Prefixes(prefixes))
    for path in paths:
        parser.parse_file(Path(path))
    system = parser.finish()
    _infer_object_bases(system)
    if validate:
        for problem in _validate_system(system):
            log.warning("%s", problem)
    return system


def parse_markdown(
    text: str,
    *,
    origin: str = "<string>",
    units: UnitTable = DEFAULT_UNITS,
    md_config: Optional[MdParserConfig] = None,
    prefixes: Optional[Mapping[str, str]] = None,
) -> ParsedSystem:
    """Parse MyST markdown `text` into a `ParsedSystem`.

    Unlike `parse_system_definitions`/`load_system`, does not automatically run
    `validate` -- call it yourself if required. `prefixes` is as for
    `parse_system_definitions`.
    """
    parser = _Parser(units, md_config or DEFAULT_MD_CONFIG, Prefixes(prefixes))
    parser.parse_text(text, origin=origin)
    system = parser.finish()
    _infer_object_bases(system)
    return system
