from typing import cast
from docutils import nodes
from sphinx.transforms.post_transforms import SphinxPostTransform
from sphinx import addnodes

from rdflib import URIRef, namespace
from sphinx_probs_rdf.directives import SystemDomain, PROBS, PROBS_RECIPE, QUANTITYKIND, rdf_reference, probs_process_info, probs_object_info

class ProbsTransform(SphinxPostTransform):
    """Transform to fill in details of PRObs objects.
    """

    # Run early on, before references are resolved
    default_priority = 1

    def run(self, **kwargs):
        domain = cast(SystemDomain, self.env.get_domain("system"))
        g = domain.graph

        for node in self.document.findall(rdf_reference):
            ref = build_rdf_reference(g, node)
            node.replace_self([ref])

        for node in self.document.findall(probs_process_info):
            info = build_process_info(g, node)
            node.replace_self(info)

        for node in self.document.findall(probs_object_info):
            info = build_object_info(g, node)
            node.replace_self(info)

        # for node in self.document.findall(addnodes.desc):
        #     if node["domain"] != "system":
        #         continue
        #     # if node["objtype"] == "process":
        #     #     content = node.next_node(addnodes.desc_content)
        #     #     if content:
        #     #         for sig in node.findall(addnodes.desc_signature):
        #     #             transform_content_process(g, sig["uri"], content)
        #     #             sig.replace_self([nodes.title("", "", *sig.children)])
        #     #     content.replace_self(content.children)
        #     #     # new_node = nodes.admonition("", *node.children)
        #     #     # new_node["classes"] += ["toggle"]
        #     #     node["classes"] += ["toggle"]
        #     #     # node.replace_self([new_node])
        #     #     node.replace_self([nodes.admonition("", *node.children)])
        #     # elif node["objtype"] == "object":
        #     #     content = node.next_node(addnodes.desc_content)
        #     #     if content:
        #     #         for sig in node.findall(addnodes.desc_signature):
        #     #             transform_content_object(g, sig["uri"], content)
        #     #             sig.replace_self([nodes.title("", "", *sig.children)])
        #     #     content.replace_self(content.children)
        #     #     node["classes"] += ["toggle"]
        #     #     node.replace_self([nodes.admonition("", *node.children)])


def build_rdf_reference(g, node):
    uri = URIRef(node["target"])
    n3 = uri.n3(g.namespace_manager)
    contnodes = [
        addnodes.pending_xref_condition('', n3, condition='resolved'),
        addnodes.pending_xref_condition('', "[UNKNOWN!] " + n3, condition='*')
    ]
    result = nodes.inline("", "")
    newnode = addnodes.pending_xref(
        '',
        *contnodes,
        refdomain="system",
        reftarget=str(uri),
        reftype="ref",
        refwarn=True,
        refexplicit=True,  # use the label with prefix we provided
    )
    result += newnode

    def preferredLabel(
        subject,
        lang=None,
        default=None,
        labelProperties=(namespace.SKOS.prefLabel, namespace.RDFS.label),
    ):
        """
        Find the preferred label for subject.

        By default prefers skos:prefLabels over rdfs:labels. In case at least
        one prefLabel is found returns those, else returns labels. In case a
        language string (e.g., "en", "de" or even "" for no lang-tagged
        literals) is given, only such labels will be considered.

        Return a list of (labelProp, label) pairs, where labelProp is either
        skos:prefLabel or rdfs:label.

        """

        if default is None:
            default = []

        # setup the language filtering
        if lang is not None:
            if lang == "":  # we only want not language-tagged literals

                def langfilter(l_):
                    return l_.language is None

            else:

                def langfilter(l_):
                    return l_.language == lang

        else:  # we don't care about language tags

            def langfilter(l_):
                return True

        for labelProp in labelProperties:
            labels = list(filter(langfilter, g.objects(subject, labelProp)))
            if len(labels) == 0:
                continue
            else:
                return [(labelProp, l_) for l_ in labels]
        return default
    labels = preferredLabel(uri)
    if labels:
        result += nodes.Text(" (" + ", ".join(label for _, label in labels) + ")")

    return result


def build_process_info(g, info_node):
    uri = info_node["uri"]
    contentnode = nodes.container("")

    recipe = g.value(uri, PROBS_RECIPE.hasRecipe)
    if recipe:
        consumes_data = [
            {
                "object": g.value(item, PROBS_RECIPE.object),
                "amount": float(g.value(item, PROBS_RECIPE.quantity)),
                "metric": g.value(item, PROBS_RECIPE.metric),
            }
            for item in g[recipe:PROBS_RECIPE.consumes:]
        ]
        produces_data = [
            {
                "object": g.value(item, PROBS_RECIPE.object),
                "amount": float(g.value(item, PROBS_RECIPE.quantity)),
                "metric": g.value(item, PROBS_RECIPE.metric),
            }
            for item in g[recipe:PROBS_RECIPE.produces:]
        ]
        contentnode += nodes.paragraph("Consumes: ", "Consumes: ")
        contentnode += _recipe_table(g, consumes_data)
        contentnode += nodes.paragraph("Produces: ", "Produces: ")
        contentnode += _recipe_table(g, produces_data)
    else:
        # XXX TODO: show consumes and produces without recipe
        pass

    parents = list(g[:PROBS.processComposedOf:uri])
    if parents:
        p = nodes.paragraph("", "Parents:")
        for parent in parents:
            p += nodes.Text(" ")
            p += _system_id_link(g, parent)
        contentnode += p

    children = list(g[uri:PROBS.processComposedOf:])
    if children:
        p = nodes.paragraph("", "Children:")
        for child in children:
            p += nodes.Text(" ")
            p += _system_id_link(g, child)
        contentnode += p

    return contentnode


def build_object_info(g, info_node):
    uri = info_node["uri"]
    contentnode = nodes.container("")

    parents = list(g[:PROBS.objectComposedOf:uri])
    if parents:
        p = nodes.paragraph("", "Parents:")
        for parent in parents:
            p += nodes.Text(" ")
            p += _system_id_link(g, parent)
        contentnode += p

    children = list(g[uri:PROBS.objectComposedOf:])
    if children:
        p = nodes.paragraph("", "Children:")
        for child in children:
            p += nodes.Text(" ")
            p += _system_id_link(g, child)
        contentnode += p

    return contentnode


def _recipe_table(g, objects):
    header_rows = [[nodes.literal("", "Object"), nodes.literal("", "Amount")]]
    table_data = [
        [_system_id_link(g, obj["object"], nodes.paragraph),
         nodes.literal("", "%.1f %s" % (obj["amount"], obj["metric"]))
         if "amount" in obj else ""]
        for obj in objects
    ]
    return build_table_from_list(header_rows + table_data, header_rows=1)


def _system_id_link(g, sys_id, within=None):
    """Insert a cross reference to another object/process."""
    refnode = addnodes.pending_xref('', refdomain="system", refexplicit=False,
                                    reftype="ref", reftarget=sys_id)
    label = sys_id.n3(g.namespace_manager)
    refnode += nodes.inline(label, label)
    if within is not None:
        wrapper = within("", "")
        wrapper += refnode
        return wrapper
    return refnode


# Adapted from docutils ListTable directive
def build_table_from_list(table_data,
                          # col_widths,
                          header_rows, stub_columns=0, widths="auto"):
    """
    :param table_data: list of lists giving table data
    :param header_rows: list of header rows
    :param stub_columns: number of columns to mark as "stubs"
    """

    table = nodes.table()

    max_cols = len(table_data[0])
    col_widths = [100 // max_cols] * max_cols
    # if widths == 'auto':
    #     table['classes'] += ['colwidths-auto']
    # elif widths: # "grid" or list of integers
    #     table['classes'] += ['colwidths-given']
    table['classes'] += ['colwidths-auto']

    tgroup = nodes.tgroup(cols=max_cols)
    table += tgroup

    for col_width in col_widths:
        colspec = nodes.colspec()
        # if col_width is not None:
        #     colspec.attributes['colwidth'] = col_width
        if stub_columns:
            colspec.attributes['stub'] = 1
            stub_columns -= 1
        tgroup += colspec

    rows = []
    for row in table_data:
        row_node = nodes.row()
        for cell in row:
            entry = nodes.entry()
            entry += cell
            row_node += entry
        rows.append(row_node)

    if header_rows:
        thead = nodes.thead()
        thead.extend(rows[:header_rows])
        tgroup += thead

    tbody = nodes.tbody()
    tbody.extend(rows[header_rows:])
    tgroup += tbody

    return table
