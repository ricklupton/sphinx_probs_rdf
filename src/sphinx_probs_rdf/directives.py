from collections import defaultdict
from typing import Any, List

from docutils import nodes
from docutils.nodes import Node
from docutils.parsers.rst import directives
from rdflib import Graph, Literal, Namespace  # type: ignore
from rdflib.namespace import RDF, RDFS  # type: ignore
from sphinx import addnodes
from sphinx.directives import ObjectDescription
from sphinx.domains import Domain, Index
from sphinx.roles import XRefRole
from sphinx.util.docfields import DocFieldTransformer
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import make_refnode


class TTL(SphinxDirective):
    has_content = True

    def run(self):
        if not hasattr(self.env, "probs_all_ttl"):
            self.env.probs_all_ttl = []

        self.env.probs_all_ttl.append(
            {
                "docname": self.env.docname,
                "lineno": self.lineno,
                "content": self.content,
                # 'target': targetnode,
            }
        )
        # print(self.env.docname, self.lineno)
        # print(self.content)

        paragraph_node = nodes.literal_block(text="\n".join(self.content))
        return [paragraph_node]


class StartSubProcessesDirective(SphinxDirective):
    required_arguments = 1

    @property
    def SYS(self) -> Namespace:
        """Return the system namespace."""
        return Namespace(self.config.probs_rdf_system_prefix)

    def run(self):
        if not hasattr(self.env, "probs_parent"):
            self.env.probs_parent = []

        uri = getattr(self.SYS, self.arguments[0])
        self.env.probs_parent.append(uri)

        paragraph_node = nodes.literal_block(text=f'Starting sub processes of "{uri}"')
        return [paragraph_node]


class StartSubObjectsDirective(SphinxDirective):
    required_arguments = 1

    @property
    def SYS(self) -> Namespace:
        """Return the system namespace."""
        return Namespace(self.config.probs_rdf_system_prefix)

    def run(self):
        if not hasattr(self.env, "probs_parent_object"):
            self.env.probs_parent_object = []

        uri = getattr(self.SYS, self.arguments[0])
        self.env.probs_parent_object.append(uri)

        paragraph_node = nodes.literal_block(text=f'Starting sub objects of "{uri}"')
        return [paragraph_node]


class EndSubProcessesDirective(SphinxDirective):
    def run(self):
        if not hasattr(self.env, "probs_parent"):
            self.env.probs_parent = []
        if self.env.probs_parent:
            leaving = self.env.probs_parent.pop()
            paragraph_node = nodes.literal_block(
                text=f'Ending sub processes of "{leaving}"'
            )
        else:
            paragraph_node = nodes.literal_block(text="Nothing to end!")
        return [paragraph_node]


class EndSubObjectsDirective(SphinxDirective):
    def run(self):
        if not hasattr(self.env, "probs_parent_object"):
            self.env.probs_parent_object = []
        if self.env.probs_parent_object:
            leaving = self.env.probs_parent_object.pop()
            paragraph_node = nodes.literal_block(
                text=f'Ending sub objects of "{leaving}"'
            )
        else:
            paragraph_node = nodes.literal_block(text="Nothing to end!")
        return [paragraph_node]


PROBS = Namespace("https://ukfires.org/probs/ontology/")


def remove_ns(ns, uri):
    if uri[: len(ns)] == ns:
        return uri[len(ns) :]


class SystemObjectDescription(ObjectDescription):
    has_content = True
    required_arguments = 1
    # option_spec = {
    #     'label': directives.unchanged_required,
    #     'become_parent': directives.flag,
    #     'consumes': directives.unchanged,
    #     'produces': directives.unchanged,
    # }

    @property
    def SYS(self) -> Namespace:
        """Return the system namespace."""
        return Namespace(self.config.probs_rdf_system_prefix)

    def run(self) -> List[Node]:
        """
        Main directive entry function, called by docutils upon encountering the
        directive.

        This directive is meant to be quite easily subclassable, so it
        delegates to several additional methods.  What it does:

        * find out if called as a domain-specific directive, set self.domain
        * create a `desc` node to fit all description inside
        * parse standard options, currently `noindex`
        * create an index node if needed as self.indexnode
        * parse all given signatures (as returned by self.get_signatures())
          using self.handle_signature(), which should either return a name
          or raise ValueError
        * add index entries using self.add_target_and_index()
        * parse the content and handle doc fields in it

        """
        if ":" in self.name:
            self.domain, self.objtype = self.name.split(":", 1)
        else:
            self.domain, self.objtype = "", self.name
        self.indexnode = addnodes.index(entries=[])

        nest_depth = "nested-%d" % self.get_nesting_depth()
        node = nodes.admonition(classes=["toggle", self.objtype, nest_depth])
        node.document = self.state.document
        node["domain"] = self.domain
        # 'desctype' is a backwards compatible attribute
        node["objtype"] = node["desctype"] = self.objtype
        node["noindex"] = noindex = "noindex" in self.options
        if self.domain:
            node["classes"].append(self.domain)

        self.names = []  # type: List[Any]
        signatures = self.get_signatures()
        assert len(signatures) == 1, "only assuming 1 signature can be given"
        for i, sig in enumerate(signatures):
            # add a signature node for each signature in the current unit
            # and add a reference target for it
            signode = nodes.title(sig, "")
            self.set_source_info(signode)
            node.append(signode)
            try:
                # name can also be a tuple, e.g. (classname, objname);
                # this is strictly domain-specific (i.e. no assumptions may
                # be made in this base class)
                name = self.handle_signature(sig, signode)
            except ValueError:
                # signature parsing failed
                signode.clear()
                signode += addnodes.desc_name(sig, sig)
                continue  # we don't want an index entry here
            if name not in self.names:
                self.names.append(name)
                if not noindex:
                    # only add target and index entry if this is the first
                    # description of the object with this name in this desc
                    # block
                    self.add_target_and_index(name, sig, signode)

        contentnode = nodes.paragraph()
        node.append(contentnode)
        if self.names:
            # needed for association of version{added,changed} directives
            self.env.temp_data["object"] = self.names[0]
        self.before_content()
        self.state.nested_parse(self.content, self.content_offset, contentnode)
        self.transform_content(contentnode)
        self.env.app.emit(
            "object-description-transform", self.domain, self.objtype, contentnode
        )
        DocFieldTransformer(self).transform_all(contentnode)
        self.env.temp_data["object"] = None
        self.after_content()

        # Do this here so `become_parent` hasn't taken effect too early
        self.define_graph(signatures[0])

        return [self.indexnode, node]

    def handle_signature(self, sig, signode):
        signode += nodes.emphasis(self.signature_prefix, self.signature_prefix)
        signode += addnodes.desc_name(sig, sig)
        if "label" in self.options:
            signode += nodes.emphasis(
                self.options["label"], " / " + self.options["label"]
            )
        return sig


class Process(SystemObjectDescription):
    # has_content = True
    # required_arguments = 1
    option_spec = {
        "label": directives.unchanged_required,
        "become_parent": directives.flag,
        "consumes": directives.unchanged,
        "produces": directives.unchanged,
        "composed_of": directives.unchanged,
    }
    signature_prefix = "Process: "

    def transform_content(self, contentnode):
        if "consumes" in self.options:
            text = f"Consumes: {self.options['consumes']}"
            contentnode += nodes.paragraph(text, text)
        if "produces" in self.options:
            text = f"Produces: {self.options['produces']}"
            contentnode += nodes.paragraph(text, text)
        if hasattr(self.env, "probs_parent") and self.env.probs_parent:
            text = f"Parent: {self.env.probs_parent[-1]}"
            contentnode += nodes.paragraph(text, text)

    def get_nesting_depth(self):
        if hasattr(self.env, "probs_parent"):
            return len(self.env.probs_parent)
        return 0

    def add_target_and_index(self, name_cls, sig, signode):
        # print('add_target_and_index', name_cls, sig, signode)
        # print(self.options)
        signode["ids"].append("process" + "-" + sig)
        if "noindex" not in self.options:
            recipes = self.env.get_domain("system")
            recipes.add_process(
                sig,
                self.options.get("consumes", "").split(),
                self.options.get("produces", "").split(),
            )

    def define_graph(self, uri_str):
        if not hasattr(self.env, "probs_graph"):
            g = Graph()
            g.bind("sys", self.SYS)
            g.bind("probs", PROBS)
            self.env.probs_graph = g
        else:
            g = self.env.probs_graph

        if not hasattr(self.env, "probs_parent"):
            self.env.probs_parent = []

        uri = getattr(self.SYS, uri_str)

        g.add((uri, RDF.type, PROBS.Process))
        if "label" in self.options:
            g.add((uri, RDFS.label, Literal(self.options["label"])))
        else:
            g.add((uri, RDFS.label, Literal(uri_str)))

        # ComposedOf relationships
        if self.env.probs_parent:
            g.add((self.env.probs_parent[-1], PROBS.processComposedOf, uri))
        for child in self.options.get("composed_of", "").split():
            if child.startswith("*"):
                # include children of the named process -- this is expanded
                # later as a postprocessing step once all processes are defined.
                child_uri = self.SYS[child[1:]]
                g.add((uri, PROBS.processComposedOfChildrenOf, child_uri))
            else:
                child_uri = self.SYS[child]
                g.add((uri, PROBS.processComposedOf, child_uri))

        for obj in self.options.get("consumes", "").split():
            obj_uri = getattr(self.SYS, obj)
            g.add((uri, PROBS.consumes, obj_uri))

        for obj in self.options.get("produces", "").split():
            obj_uri = getattr(self.SYS, obj)
            g.add((uri, PROBS.produces, obj_uri))

        if "become_parent" in self.options:
            # print("xxx become parent")
            self.env.probs_parent.append(uri)


class Object(SystemObjectDescription):
    has_content = True
    required_arguments = 1
    option_spec = {
        "label": directives.unchanged,
        "become_parent": directives.flag,
        "parent_object": directives.unchanged,
    }
    signature_prefix = "Object: "

    # def handle_signature(self, sig, signode):
    #     signode += nodes.emphasis("Object: ", "Object: ")
    #     signode += addnodes.desc_name(sig, sig)
    #     if "label" in self.options:
    #         signode += addnodes.desc_addname(self.options["label"],
    #                                          self.options["label"])
    #     return sig

    def transform_content(self, contentnode):
        if hasattr(self.env, "probs_parent_object") and self.env.probs_parent_object:
            text = f"Parent: {remove_ns(self.SYS, self.env.probs_parent_object[-1])}"
            ref = nodes.reference()
            contentnode += nodes.paragraph(text, text)

    def get_nesting_depth(self):
        if hasattr(self.env, "probs_parent_object"):
            return len(self.env.probs_parent_object)
        return 0

    def add_target_and_index(self, name_cls, sig, signode):
        # print('add_target_and_index', name_cls, sig, signode)
        # print(self.options)
        signode["ids"].append("object" + "-" + sig)
        if "noindex" not in self.options:
            recipes = self.env.get_domain("system")
            recipes.add_object(sig, [])

    def define_graph(self, uri_str):
        if not hasattr(self.env, "probs_graph"):
            g = Graph()
            g.bind("sys", self.SYS)
            g.bind("probs", PROBS)
            self.env.probs_graph = g
        else:
            g = self.env.probs_graph

        if not hasattr(self.env, "probs_parent_object"):
            self.env.probs_parent_object = []

        uri = getattr(self.SYS, uri_str)

        g.add((uri, RDF.type, PROBS.Object))
        if "label" in self.options:
            g.add((uri, RDFS.label, Literal(self.options["label"])))
        else:
            g.add((uri, RDFS.label, Literal(uri_str)))

        if "parent_object" in self.options:
            parent_uri = getattr(self.SYS, self.options["parent_object"])
            g.add((parent_uri, PROBS.objectComposedOf, uri))
        elif self.env.probs_parent_object:
            g.add((self.env.probs_parent_object[-1], PROBS.objectComposedOf, uri))

        if "become_parent" in self.options:
            # print("xxx become parent object")
            self.env.probs_parent_object.append(uri)


class ObjectIndex(Index):
    """Index of objects."""

    name = "object"
    localname = "Object Index"
    shortname = "Object"

    def generate(self, docnames=None):
        content = defaultdict(list)

        objects = {
            name: (dispname, typ, docname, anchor)
            for name, dispname, typ, docname, anchor, _ in self.domain.data["objects"]
        }
        processes = {
            name: (dispname, typ, docname, anchor)
            for name, dispname, typ, docname, anchor, _ in self.domain.data["processes"]
        }
        process_consumes = self.domain.data["process_consumes"]
        process_produces = self.domain.data["process_produces"]
        object_processes = defaultdict(list)

        # flip from recipe_ingredients to ingredient_recipes
        for process_name, objs in process_consumes.items():
            for obj in objs:
                if ("object." + obj) not in objects:
                    msg = "WARNING: Object {} consumed by process {} is not defined"
                    print(msg.format(obj, process_name))
                    continue
                object_processes[obj].append((process_name, "consumed"))
        for process_name, objs in process_produces.items():
            for obj in objs:
                if ("object." + obj) not in objects:
                    msg = "WARNING: Object {} produced by process {} is not defined"
                    print(msg.format(obj, process_name))
                    continue
                object_processes[obj].append((process_name, "produced"))

        # convert the mapping of objects to processes to produce the expected
        # output, shown below, using the object name as a key to group
        #
        # name, subtype, docname, anchor, extra, qualifier, description
        for obj, process_names in object_processes.items():
            dispname, typ, docname, anchor = objects["object." + obj]
            k = dispname[0].lower()
            content[k].append((dispname, 1, docname, anchor, docname, "", typ))

            for process_name, direction in process_names:
                dispname, typ, docname, anchor = processes[process_name]
                content[k].append((dispname, 2, docname, anchor, direction, "", typ))

        # convert the dict to the sorted list of tuples expected
        content = sorted(content.items())

        return content, True


class ProcessIndex(Index):
    """Index of processes."""

    name = "process"
    localname = "Process Index"
    shortname = "Process"

    def generate(self, docnames=None):
        content = defaultdict(list)

        # sort the list of processes in alphabetical order
        processes = self.domain.data["processes"]
        processes = sorted(processes, key=lambda process: process[0])

        # generate the expected output, shown below, from the above using the
        # first letter of the recipe as a key to group thing
        #
        # name, subtype, docname, anchor, extra, qualifier, description
        for name, dispname, typ, docname, anchor, _ in processes:
            content[dispname[0].lower()].append(
                (dispname, 0, docname, anchor, docname, "", typ)
            )

        # convert the dict to the sorted list of tuples expected
        content = sorted(content.items())

        return content, True


class SystemDomain(Domain):

    name = "system"
    label = "System definition"
    roles = {"ref": XRefRole()}
    directives = {
        "process": Process,
        "object": Object,
        # 'startSubProcesses': StartSubProcessesDirective,
    }
    indices = [ProcessIndex, ObjectIndex]
    initial_data: dict = {
        "processes": [],  # object list
        "objects": [],  # object list
        "process_consumes": {},
        "process_produces": {},
    }

    def get_full_qualified_name(self, node):
        return "{}.{}".format("system", node.arguments[0])

    def get_objects(self):
        for obj in self.data["processes"]:
            yield (obj)
        for obj in self.data["objects"]:
            yield (obj)

    def resolve_xref(self, env, fromdocname, builder, typ, target, node, contnode):
        match = [
            (docname, anchor)
            for name, sig, typ, docname, anchor, prio in self.get_objects()
            if sig == target
        ]

        if len(match) > 0:
            todocname = match[0][0]
            targ = match[0][1]

            return make_refnode(builder, fromdocname, todocname, targ, contnode, targ)
        else:
            print("Awww, found nothing")
            return None

    def add_process(self, signature, consumes, produces):
        """Add a new process to the domain."""
        name = "{}.{}".format("process", signature)
        anchor = "process-{}".format(signature)

        # self.data['recipe_ingredients'][name] = ingredients
        # name, dispname, type, docname, anchor, priority
        self.data["processes"].append(
            (name, signature, "Process", self.env.docname, anchor, 0)
        )
        self.data["process_consumes"][name] = consumes
        self.data["process_produces"][name] = produces

    def add_object(self, signature, ingredients):
        """Add a new object to the domain."""
        name = "{}.{}".format("object", signature)
        anchor = "object-{}".format(signature)

        # self.data['recipe_ingredients'][name] = ingredients
        # name, dispname, type, docname, anchor, priority
        self.data["objects"].append(
            (name, signature, "Object", self.env.docname, anchor, 0)
        )
