from collections import defaultdict
from typing import Any, List, Dict, Iterator, Tuple, Optional, NamedTuple, cast
import re
import yaml

from docutils import nodes
from docutils.nodes import Node, Element
from docutils.parsers.rst import directives  # type: ignore
from rdflib import Graph, ConjunctiveGraph, URIRef, Literal, BNode, Namespace  # type: ignore
from rdflib.namespace import RDF, RDFS  # type: ignore
from sphinx import addnodes
from sphinx.addnodes import desc_signature, pending_xref
from sphinx.builders import Builder
from sphinx.locale import _, __
from sphinx.directives import ObjectDescription
from sphinx.directives.code import CodeBlock
from sphinx.domains import Domain, Index, ObjType
from sphinx.environment import BuildEnvironment
from sphinx.roles import XRefRole
from sphinx.util.docfields import DocFieldTransformer
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import make_refnode, find_pending_xref_condition, make_id
from sphinx.util import logging

logger = logging.getLogger(__name__)


def parse_composed_of(value):
    """Parse composed_of option."""
    if value is None:
        return []
    return [x.strip() for x in value.split()]


def parse_consumes_or_produces(value):
    """Parse consumes and products options."""
    if value is None:
        return []

    if "\n" in value or value.strip().startswith("{"):
        # Complex definitions, one per line -- or a single YAML-style definition
        items = [_parse_item(x.strip()) for x in value.strip().split("\n")]
    else:
        # A space-separated list of basic names
        items = [
            {"object": x.strip()}
            for x in value.split()
        ]

    return items


ITEM_STRING_REGEX = re.compile(r"""
    ^\s*
    ([^= \t]+)               # -> Object type
    \s*
    (?:                      # Optional amount section
        =
        \s*
        ([0-9.eE-]+)         # -> Amount
        (?:                  # Optional unit section
            \s*
            ([^{]+?)         # -> Unit
            \s*
        )?
    )?
    ({.+})?                  # Optional YAML section
    $
""", re.VERBOSE)


def _parse_item(item):
    if isinstance(item, str):
        match = ITEM_STRING_REGEX.match(item)
        if match:
            extra = {}
            if match.group(4):
                try:
                    extra = yaml.safe_load(match.group(4))
                except yaml.YAMLError:
                    pass
            return {
                "object": match.group(1),
                "amount": float(match.group(2)) if match.group(2) else None,
                "unit": match.group(3),
                **extra,
            }
        else:
            # Try parsing whole thing as yaml dict
            try:
                d = yaml.safe_load(item)
                if not isinstance(d, dict):
                    raise ValueError("YAML data should be dictionary")
                return d
            except yaml.YAMLError:
                pass

            return item
    elif isinstance(item, list):
        return {
            "object": item[0],
            "amount": item[1],
            "unit": item[2],
        }
    elif isinstance(item, dict):
        return item
    else:
        raise ValueError("cannot parse item: %r" % item)


def expand_consumes_produces_amounts(defs, *items):
    """Expand Python expressions in cleaned-up options."""
    defs_ns = {}
    exec(defs, defs_ns)

    # Expand amounts in produces/consumes lists using the defs
    result = [
        [eval_amount(x, defs_ns) for x in item_list]
        for item_list in items
    ]

    return result


def eval_amount(item, namespace):
    """Evaluate expressions within the "amount" field of the item.

    WARNING: not safe for use with untrusted input!
    """
    if isinstance(item, dict) and isinstance(item.get("amount"), str):
        amount = eval(item["amount"], {}, dict(namespace))
        return {**item, "amount": amount}
    return item


class TTL(CodeBlock):
    has_content = True

    def run(self):
        domain = cast(SystemDomain, self.env.get_domain("system"))
        g = domain.get_graph(self.env.docname)
        preamble = "\n".join('@prefix %s: <%s> .\n' % (prefix, uri)
                             for prefix, uri in g.namespaces())
        input_data = preamble + "\n" + "\n".join(self.content)
        try:
            g.parse(data=input_data, format="text/turtle")
        except SyntaxError as err:
            logger.warning("Cannot parse TTL block: %s", err,
                           location=(self.env.docname, self.lineno))

        # Force language
        self.arguments = ["turtle"]
        return super().run()


class StartSubProcessesDirective(SphinxDirective):
    required_arguments = 1

    def run(self):
        uri = parse_uri(self.config, self.arguments[0])
        self.env.ref_context["system:process"] = uri
        parents = self.env.ref_context.setdefault("system:processes", [])
        parents.append(uri)

        paragraph_node = nodes.literal_block(text=f'Starting sub processes of "{uri}"')
        return [paragraph_node]


class StartSubObjectsDirective(SphinxDirective):
    required_arguments = 1

    def run(self):
        uri = parse_uri(self.config, self.arguments[0])
        self.env.ref_context["system:object"] = uri
        parents = self.env.ref_context.setdefault("system:objects", [])
        parents.append(uri)

        paragraph_node = nodes.literal_block(text=f'Starting sub objects of "{uri}"')
        return [paragraph_node]


class EndSubProcessesDirective(SphinxDirective):
    def run(self):
        parents = self.env.ref_context.setdefault("system:processes", [])
        if parents:
            nesting_depth = len(parents)
            leaving = parents.pop()
            _, _, leaving_id = leaving.rpartition("/")
            paragraph_node = nodes.paragraph(
                text=f'Ending sub processes of "{leaving_id}"',
                classes=["system", "end-sub-processes", f"nested-{nesting_depth}"],
            )
        else:
            paragraph_node = nodes.literal_block(text="Nothing to end!")

        self.env.ref_context["system:process"] = (
            parents[-1] if parents else None
        )

        return [paragraph_node]


class EndSubObjectsDirective(SphinxDirective):
    def run(self):
        parents = self.env.ref_context.setdefault("system:objects", [])
        if parents:
            nesting_depth = len(parents)
            leaving = parents.pop()
            _, _, leaving_id = leaving.rpartition("/")
            paragraph_node = nodes.paragraph(
                text=f'Ending sub objects of "{leaving_id}"',
                classes=["system", "end-sub-objects", f"nested-{nesting_depth}"],
            )
        else:
            paragraph_node = nodes.literal_block(text="Nothing to end!")

        self.env.ref_context["system:object"] = (
            parents[-1] if parents else None
        )

        return [paragraph_node]


PROBS = Namespace("http://w3id.org/probs-lab/ontology#")
PROBS_RECIPE = Namespace("http://w3id.org/probs-lab/process-recipe#")
QUANTITYKIND = Namespace("http://qudt.org/vocab/quantitykind/")


class probs_info(nodes.Element, nodes.General):
    """Node for PRObs info.
    """


class rdf_reference(nodes.reference):
    """Reference to RDF object.
    """


class probs_process_info(probs_info):
    pass


class probs_object_info(probs_info):
    pass


class ObjectEquivalentTo(SphinxDirective):
    required_arguments = 2
    option_spec = {
        "confidence": directives.unchanged,
        'class': directives.class_option,
    }
    has_content = True

    def run(self):
        if not self.options.get('class'):
            self.options['class'] = ['admonition-object-equivalent-to']

        # self.assert_has_content()
        uri1 = parse_uri(self.config, self.arguments[0])
        uri2 = parse_uri(self.config, self.arguments[1])

        node = nodes.admonition()

        title = nodes.title("", "")
        title += [
            nodes.strong("Object equivalence: ", "Object equivalence: "),
            rdf_reference(uri1, target=uri1, include_label=True),
            nodes.Text(" ⇔ "),
            rdf_reference(uri2, target=uri2, include_label=True),
        ]

        self.indexnode = addnodes.index(entries=[])

        contentnode = nodes.paragraph()  # desc_content?
        node += [title, contentnode]
        self.state.nested_parse(self.content, self.content_offset, contentnode)

        g = self.env.get_domain("system").get_graph(self.env.docname)
        g.add((uri1, PROBS.objectEquivalentTo, uri2))

        return [self.indexnode, node]



class SystemObjectDescription(ObjectDescription):
    has_content = True
    required_arguments = 1

    def run(self) -> List[Node]:
        """Override to return admonitions rather than descs.

        This is a hacky way of getting a collapsible/togglable block, rather
        than inline descriptions.

        """
        nest_depth = "nested-%d" % self.get_nesting_depth()

        indexnode, node = super().run()

        # Replace `desc` with `admonition`
        new_node = nodes.admonition("", *node.children)
        new_node["classes"] = node["classes"] + ["toggle", nest_depth]

        # Replace desc_content with paragraph and desc_signature with title
        for sig in new_node.findall(addnodes.desc_signature):
            sig.replace_self([nodes.title("", "", *sig.children)])
        for content in new_node.findall(addnodes.desc_content):
            content.replace_self(content.children)

        return [indexnode, new_node]

    def get_signatures(self) -> List[str]:
        signatures = super().get_signatures()
        if len(signatures) > 1:
            logger.warning("Multiple signatures not supported")
        return signatures[:1]

    def handle_signature(self, sig: str, signode: desc_signature) -> str:
        """Transform a "signature" (i.e. name for this thing) into RST nodes.

        Return URI of the thing.
        """
        uri = parse_uri(self.config, sig)
        signode["uri"] = uri

        # XXX is there is a better desc_XXX node for this?
        signode += nodes.emphasis(self.signature_prefix, self.signature_prefix)
        signode += addnodes.desc_name(sig, sig)
        if "label" in self.options:
            signode += addnodes.desc_addname(
                self.options["label"], " / " + self.options["label"]
            )

        g = self.env.get_domain("system").get_graph(self.env.docname)
        self.define_graph(g, uri, sig)

        return uri


class Process(SystemObjectDescription):
    option_spec = {
        "label": directives.unchanged_required,
        "become_parent": directives.flag,
        "consumes": parse_consumes_or_produces,
        "produces": parse_consumes_or_produces,
        "composed_of": parse_composed_of,
        "defs": directives.unchanged,
    }
    signature_prefix = "Process: "

    def get_nesting_depth(self):
        return len(self.env.ref_context.get('system:processes', []))

    def add_target_and_index(self, uri, sig, signode):
        node_id = make_id(self.env, self.state.document, '', uri)
        signode["ids"].append(node_id)
        domain = cast(SystemDomain, self.env.get_domain("system"))
        # XXX maybe label should come from RDF later
        domain.note_thing(
            uri, "process", self.options.get("label", sig), node_id, location=signode
        )
        # XXX avoid parse_uri too many times?
        domain.note_process_recipe(
            uri,
            [parse_uri(self.config, obj["object"]) for obj in self.options.get("consumes", [])],
            [parse_uri(self.config, obj["object"]) for obj in self.options.get("produces", [])],
        )

    def before_content(self):
        """Handle object nesting before content."""
        if self.names:
            uri = self.names[-1]
            self.env.ref_context["system:process"] = uri
            parents = self.env.ref_context.setdefault("system:processes", [])
            parents.append(uri)

    def transform_content(self, contentnode):
        if self.names:
            uri = self.names[0]
            info = probs_process_info("", uri=uri)
            contentnode.insert(0, info)

    def after_content(self):
        """Handle object de-nesting after content."""
        parents = self.env.ref_context.setdefault("system:processes", [])
        if parents and "become_parent" not in self.options:
            parents.pop()
        self.env.ref_context["system:process"] = (
            parents[-1] if parents else None
        )

    def define_graph(self, g, uri, sig: str):
        label = self.options.get("label", sig)

        g.add((uri, RDF.type, PROBS.Process))
        g.add((uri, RDFS.label, Literal(label)))
        g.add((uri, PROBS.processName, Literal(label)))

        # ComposedOf relationships
        # determine parent
        if "parent" in self.options:
            parent = parse_uri(self.config, self.options["parent"])
        else:
            parent = self.env.ref_context.get("system:process")
        if parent:
            g.add((parent, PROBS.processComposedOf, uri))
        for child in self.options.get("composed_of", []):
            if child.startswith("*"):
                # include children of the named process -- this is expanded
                # later as a postprocessing step once all processes are defined.
                child_uri = parse_uri(self.config, child[1:])
                g.add((uri, PROBS.processComposedOfChildrenOf, child_uri))
            else:
                child_uri = parse_uri(self.config, child)
                g.add((uri, PROBS.processComposedOf, child_uri))

        # Recipes (inputs and outputs)
        # First expand any expressions
        defs = self.options.get("defs", "")
        consumes, produces = expand_consumes_produces_amounts(
            defs, self.options.get("consumes", []), self.options.get("produces", []))

        recipe_consumes, recipe_produces = [], []
        _process_inputs_outputs(g, self.config, uri, "consumes", consumes, recipe_consumes)
        _process_inputs_outputs(g, self.config, uri, "produces", produces, recipe_produces)
        if recipe_consumes or recipe_produces:
            recipe = BNode()
            g.add((uri, PROBS_RECIPE.hasRecipe, recipe))
            for item in recipe_consumes:
                g.add((recipe, PROBS_RECIPE.consumes, item))
            for item in recipe_produces:
                g.add((recipe, PROBS_RECIPE.produces, item))


def _process_inputs_outputs(g, config, uri, relation, objects, recipe_items):
    units = config.probs_rdf_units
    for obj in objects:
        obj_uri = parse_uri(config, obj["object"])
        g.add((uri, PROBS[relation], obj_uri))

        if "amount" in obj:
            # Have a recipe

            # XXX only support a few units for now, this could be more general.
            if "unit" in obj and obj["unit"] not in units:
                logger.error("Unsupported unit %r for object %r in recipe for %r -- treating as 'kg'",
                             obj["unit"], obj["object"], str(uri))
                scale, metric = units["kg"]
            else:
                scale, metric = units[obj["unit"]]

            item = BNode()
            g.add((item, PROBS_RECIPE.object, obj_uri))
            g.add((item, PROBS_RECIPE.quantity, Literal(scale * obj["amount"])))
            g.add((item, PROBS_RECIPE.metric, metric))
            recipe_items.append(item)


def parse_traded(value):
    """Check the value of the :traded: option is valid."""
    if value is None:
        return (False, False)
    value = value.lower()
    imp = value.startswith("import")
    exp = value.startswith("export")
    if (value in ("both", "yes", "true") or
        "import" in value and "export" in value):
        imp = exp = True
    return (imp, exp)


def parse_equivalent(value):
    """Convert list of uris."""
    if value is None:
        value = ""
    items = [x.strip() for x in value.split()]
    return items


def parse_uri(config, item, default=None):
    """Convert a string to a URIRef.

    A blank prefix or bare id refers to the namespace given by the
    `probs_rdf_system_prefix` config variable.

    A missing suffix means the same as the object currently being defined.

    """
    if item and item[0] == "<" and item[-1] == ">":
        return URIRef(item[1:-1])
    prefix, _, item_id = item.rpartition(":")
    if not prefix:
        ns = Namespace(config.probs_rdf_system_prefix)
    else:
        ns = Namespace(config.probs_rdf_extra_prefixes[prefix])
    if not item_id:
        item_id = default if default is not None else ""
    return getattr(ns, item_id)


class Object(SystemObjectDescription):
    has_content = True
    required_arguments = 1
    option_spec = {
        "label": directives.unchanged,
        "become_parent": directives.flag,
        "parent_object": directives.unchanged,
        "composed_of": parse_composed_of,
        "traded": parse_traded,
        "equivalent": parse_equivalent,
    }
    signature_prefix = "Object: "

    def get_nesting_depth(self):
        return len(self.env.ref_context.get("system:objects", []))

    def add_target_and_index(self, uri, sig, signode):
        node_id = make_id(self.env, self.state.document, '', uri)
        signode["ids"].append(node_id)
        domain = cast(SystemDomain, self.env.get_domain("system"))
        # XXX maybe label should come from RDF later
        domain.note_thing(
            uri, "object", self.options.get("label", sig), node_id, location=signode
        )

    def before_content(self):
        """Handle object nesting before content."""
        if self.names:
            uri = self.names[-1]
            self.env.ref_context["system:object"] = uri
            parents = self.env.ref_context.setdefault("system:objects", [])
            parents.append(uri)

    def transform_content(self, contentnode):
        if self.names:
            uri = self.names[0]
            info = probs_object_info("", uri=uri)
            contentnode.insert(0, info)

    def after_content(self):
        """Handle object de-nesting after content."""
        parents = self.env.ref_context.setdefault("system:objects", [])
        if parents and "become_parent" not in self.options:
            parents.pop()
        self.env.ref_context["system:object"] = (
            parents[-1] if parents else None
        )

    def define_graph(self, g, uri, sig: str):
        label = self.options.get("label", sig)

        g.add((uri, RDF.type, PROBS.Object))
        g.add((uri, RDF.type, PROBS.ReferenceObject))
        g.add((uri, RDFS.label, Literal(label)))
        g.add((uri, PROBS.objectName, Literal(label)))

        # ComposedOf relationships
        if "parent_object" in self.options:
            parent = parse_uri(self.config, self.options["parent_object"])
        else:
            parent = self.env.ref_context.get("system:object")
        if parent:
            g.add((parent, PROBS.objectComposedOf, uri))
        for child in self.options.get("composed_of", []):
            if child.startswith("*"):
                # include children of the named object -- this is expanded later
                # as a postprocessing step once all processes are defined.
                child_uri = parse_uri(self.config, child[1:])
                g.add((uri, PROBS.objectComposedOfChildrenOf, child_uri))
            else:
                child_uri = parse_uri(self.config, child)
                g.add((uri, PROBS.objectComposedOf, child_uri))

        if "traded" in self.options:
            imp, exp = self.options["traded"]
            if imp != exp:
                logger.error("Currently objects must be either fully traded"
                             "(imports and exports) or not at all")
            g.add((uri, PROBS.objectIsTraded, Literal(imp or exp)))

        if "equivalent" in self.options:
            for item in self.options["equivalent"]:
                item_uri = self.parse_uri(item)
                g.add((uri, PROBS.objectEquivalentTo, item_uri))

        # Define a process which represents the balancing market / control
        # volume for this object
        process_uri = URIRef(str(uri) + "_Market")
        g.add((process_uri, RDF.type, PROBS.Process))
        g.add((process_uri, PROBS.marketForObject, uri))
        g.add((process_uri, RDFS.label, Literal(label)))

    def parse_uri(self, item):
        """Convert a string to a URIRef.

        A blank prefix or bare id refers to the namespace given by the
        `probs_rdf_system_prefix` config variable.

        A missing suffix means the same as the object currently being defined.

        """
        signatures = self.get_signatures()
        assert len(signatures) == 1, "only assuming 1 signature can be given"
        default_item_id = signatures[0]
        return parse_uri(self.config, item, default_item_id)


class ObjectIndex(Index):
    """Index of objects."""

    name = "objectindex"
    localname = "Object Index"
    shortname = "objects"

    def generate(self, docnames=None):
        content = defaultdict(list)

        objects = {
            uri: thing
            for uri, thing in self.domain.things.items()
            if thing.thing_type == "object"
        }
        processes = {
            uri: thing
            for uri, thing in self.domain.things.items()
            if thing.thing_type == "process"
        }
        # processes = {
        #     name: (dispname, typ, docname, anchor)
        #     for name, dispname, typ, docname, anchor, _ in self.domain.data["processes"]
        # }
        process_recipe = self.domain.process_recipe
        object_processes = defaultdict(list)

        # Add the objects initially; this is necessary for any objects which are
        # NOT linked to processes to be included.
        for obj_uri in objects:
            object_processes[obj_uri] = []

        # Add in all the places that an object is consumed or produced by a
        # process
        for process_uri, objs in process_recipe.items():
            if process_uri not in processes:
                logger.warning(
                    "Process %s is not defined",
                    process_uri,
                    # location=(self.env.docname, self.lineno)
                )
                continue
            for obj_uri, direction in objs:
                if obj_uri not in objects:
                    logger.warning(
                        "Object %s %s by process %s is not defined",
                        obj_uri,
                        direction[:-1] + "d",
                        process_uri,
                        # location=(self.env.docname, self.lineno)
                    )
                    continue
                object_processes[obj_uri].append((process_uri, direction))

        # convert the mapping of objects to processes to produce the expected
        # output, shown below, using the object name as a key to group
        #
        # name, subtype, docname, anchor, extra, qualifier, description
        for obj_uri, process_uris in object_processes.items():
            obj = objects[obj_uri]
            k = obj.label.upper()[0]
            content[k].append((obj.label, 1, obj.docname, obj.node_id, obj.docname, "", obj.thing_type))

            for process_uri, direction in process_uris:
                if process_uri in processes:
                    p = processes[process_uri]
                    content[k].append((p.label, 2, p.docname, p.node_id, direction, "", p.thing_type))
                else:
                    logger.debug("Missing process in domain: %s", process_uri)

        # convert the dict to the sorted list of tuples expected
        content = sorted(content.items())

        return content, True


class ProcessIndex(Index):
    """Index of processes."""

    name = "processindex"
    localname = "Process Index"
    shortname = "processes"

    def generate(self, docnames=None):
        content = defaultdict(list)

        # sort the list of processes in alphabetical order
        processes = {
            uri: thing
            for uri, thing in self.domain.things.items()
            if thing.thing_type == "process"
        }

        # generate the expected output, shown below, from the above using the
        # first letter of the recipe as a key to group thing
        #
        # name, subtype, docname, anchor, extra, qualifier, description
        for process_uri, thing in processes.items():
            k = thing.label.upper()[0]
            content[k].append(
                (thing.label, 0, thing.docname, thing.node_id, thing.docname, "", thing.thing_type)
            )

        # convert the dict to the sorted list of tuples expected
        content = sorted(content.items())

        return content, True


class ThingEntry(NamedTuple):
    docname: str
    node_id: str
    thing_type: str
    label: str


class SystemDomain(Domain):

    name = "system"
    label = "System definition"

    # These are the different types of things that we can keep track of, and
    # which roles can cross-reference to them.
    object_types = {
        'process': ObjType(_('process'), 'ref'),
        'object':  ObjType(_('object'),  'ref'),
    }
    roles = {
        "ref": XRefRole()
    }
    directives = {
        "process": Process,
        "object": Object,
        "object-equivalent-to": ObjectEquivalentTo,
    }
    indices = [ProcessIndex, ObjectIndex]
    initial_data: dict = {
        "things": {},
        "process_recipe": {},
        "graph": None,
    }

    ### Keeping track of where things are defined

    @property
    def things(self) -> Dict[str, ThingEntry]:
        return self.data.setdefault('things', {})  # uri -> ThingEntry

    @property
    def graph(self) -> ConjunctiveGraph:
        if self.data.get("graph") is None:
            g = self.data["graph"] = ConjunctiveGraph()
            config = self.env.config
            g.bind("sys", Namespace(config.probs_rdf_system_prefix))
            g.bind("probs", PROBS)
            g.bind("rec", PROBS_RECIPE)
            for prefix, uri in config.probs_rdf_extra_prefixes.items():
                g.bind(prefix, uri)
        return self.data["graph"]

    @property
    def process_recipe(self) -> Dict[str, list]:
        return self.data.setdefault('process_recipe', {})  # uri -> list

    def get_graph(self, graph_id):
        return self.graph.get_context(graph_id)

    def note_thing(self, uri: str, thing_type: str, label: str, node_id: str, location: Any = None):
        """Note the definition of a thing (what Sphinx calls an "object")."""
        if uri in self.things:
            # duplicated
            other = self.things[uri]
            logger.warning(__('duplicate description of %s, '
                              'other instance in %s, use :noindex: for one of them'),
                           uri, other.docname, location=location)
        self.things[uri] = ThingEntry(self.env.docname, node_id, thing_type, label)

    def note_process_recipe(self, uri: str, consumes: list, produces: list):
        self.process_recipe[uri] = (
            [(k, "consumes") for k in consumes] +
            [(k, "produces") for k in produces]
        )

    def clear_doc(self, docname: str) -> None:
        for uri, thing in list(self.things.items()):
            if thing.docname == docname:
                del self.things[uri]

        g = self.get_graph(docname)
        g.remove((None, None, None))

    def merge_domaindata(self, docnames: List[str], otherdata: Dict) -> None:
        # XXX check duplicates?
        for uri, thing in otherdata['things'].items():
            if thing.docname in docnames:
                self.things[uri] = thing
        if "graph" in otherdata:
            self.graph += otherdata["graph"]

    def find_thing(
        self,
        name: str,
        base_uri: Optional[str] = None,
        current_thing: Optional[str] = None,
        thing_type: Optional[str] = None,
    ) -> List[Tuple[str, ThingEntry]]:
        """Find a thing definition for "name", perhaps using the configured
        prefixes. Returns a list of (uri, thing entry) tuples.
        """
        # XXX this could be more flexible, e.g. parsing prefixes, allowing
        # relative URIs or absolute URIs -- or looking first for names that
        # feature within the current process's inputs or outputs.

        if thing_type is None:
            thing_types = list(self.object_types)
        else:
            thing_types = self.objtypes_for_role(thing_type)

        matches = [
            (uri, thing)
            for uri, thing in self.things.items()
            if uri.endswith(name) and thing.thing_type in thing_types
        ]

        return matches

    def resolve_xref(
        self,
        env: BuildEnvironment,
        fromdocname: str,
        builder: Builder,
        thing_type: str,
        target: str,
        node: pending_xref,
        contnode: Element,
    ) -> Optional[Element]:

        matches = self.find_thing(target, thing_type=thing_type)

        if not matches:
            return None
        elif len(matches) > 1:
            logger.warning(__('more than one target found for cross-reference %r: %s'),
                           target, ', '.join(match[0] for match in matches),
                           type='ref', subtype='system', location=node)
        uri, thing = matches[0]

        # determine the content of the reference by conditions
        content = find_pending_xref_condition(node, 'resolved')
        if content:
            children = content.children
        else:
            # if not found, use contnode
            children = [contnode]

        return make_refnode(builder, fromdocname, thing.docname, thing.node_id, children, uri)

    # TODO: implement `resolve_any_xref`?

    def get_objects(self) -> Iterator[Tuple[str, str, str, str, str, int]]:
        # Returns:
        # - name: fully qualified name
        # - dispname: Name to display when searching/linking.
        # - type: Object type, a key in ``self.object_types``
        # - docname: The document where it is to be found.
        # - anchor: The anchor name for the object.
        # - priority: determines placement in search results:
        #   1 = default (before full-text matches)
        #   0 = important (before default-priority)
        #   2 = unimportant (after full-text matches)
        #   -1 = don't show in search at all

        for uri, thing in self.things.items():
            yield (uri, thing.label, thing.thing_type, thing.docname, thing.node_id, 1)

    def get_full_qualified_name(self, node):
        # XXX Fix me to return URI
        if node.get("refdomain") == "system":
            return "{}.{}".format("system", node.get("reftarget"))
        return None
