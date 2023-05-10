from os import path
from sphinx.util.fileutil import copy_asset_file
from typing import Any, Dict, cast
from sphinx.application import Sphinx
from sphinx.config import Config

from .version import __version__
from .builder import ProbsSystemRDFBuilder
from .directives import (
    SystemDomain,
    StartSubProcessesDirective,
    StartSubObjectsDirective,
    EndSubProcessesDirective,
    EndSubObjectsDirective,
    TTL,
    ObjectEquivalentTo,
)
from .resolve import ProbsTransform


# Old version
NB_RENDER_PRIORITY = {
    "probs_rdf": (
        "application/vnd.jupyter.widget-view+json",
        "application/javascript",
        "text/html",
        "image/svg+xml",
        "image/png",
        "image/jpeg",
        "text/markdown",
        "text/latex",
        "text/plain",
    )
}

NB_RENDER_PRIORITY_NEW = [
    (k, v, (1 + i) * 10)
    for k, items in NB_RENDER_PRIORITY.items()
    for i, v in enumerate(items)
]



def copy_custom_files(app, exc):
    if app.builder.format == 'html' and not exc:
        staticdir = path.join(app.builder.outdir, '_static')
        here = path.dirname(__file__)
        copy_asset_file(path.join(here, '_static/system-definitions.css'), staticdir)


def save_graph(app, exc):
    if not exc:
        assert app.builder
        env = app.builder.env
        assert env is not None
        domain = cast(SystemDomain, env.get_domain("system"))
        import os.path
        from .postprocess import postprocess
        filename = os.path.join(app.builder.outdir, 'output.ttl')
        graph = domain.graph
        postprocess(graph)
        with open(filename, 'wb') as f:
            graph.serialize(f, format="turtle")


from rdflib import Namespace, URIRef  # type: ignore
QUANTITYKIND = Namespace("http://qudt.org/vocab/quantitykind/")
DEFAULT_UNIT_METRICS = {
    "kg": (1, QUANTITYKIND.Mass),
    "m2": (1, QUANTITYKIND.Area),
    "m3": (1, QUANTITYKIND.Volume),
    "-": (1, QUANTITYKIND.Dimensionless),
}


def parse_uri(config, value, default_ns):
    if value and value[0] == "<" and value[-1] == ">":
        return URIRef(value[1:-1])
    prefix, _, item_id = value.rpartition(":")
    if not prefix:
        ns = default_ns
    else:
        ns = Namespace(config.probs_rdf_extra_prefixes[prefix])
    if not item_id:
        raise ValueError("Missing suffix in %r" % value)
    return getattr(ns, item_id)


def merge_default_config(app: Sphinx, config: Config):
    d = config.probs_rdf_units
    for unit, value in d.items():
        if isinstance(value, str):
            scale = 1
            metric = value
        else:
            scale, metric = value
        metric = parse_uri(config, metric, QUANTITYKIND)
        d[unit] = (scale, metric)
    for unit, (scale, metric) in DEFAULT_UNIT_METRICS.items():
        if unit not in d:
            d[unit] = (scale, metric)


def read_external_graph(app: Sphinx, env):
    """Read in any data from external RDF files."""
    paths = env.config.probs_rdf_paths
    domain = cast(SystemDomain, env.get_domain("system"))
    g = domain.graph
    for p in paths:
        domain.graph.parse(location=path.join(app.confdir, p), format="ttl")

    # Check if the external graph has duplicated any of our own prefix
    # definitions
    seen = set()
    bound_namespaces = list(g.namespace_manager.namespaces())
    g.namespace_manager.reset()
    for prefix, ns in bound_namespaces:
        if ns in seen:
            g.bind(prefix, ns)
        seen.add(ns)


def setup(app: Sphinx) -> Dict[str, Any]:
    app.add_builder(ProbsSystemRDFBuilder)
    # Add config for jupyter-book / myst_nb.
    # See https://jupyterbook.org/advanced/advanced.html#enabling-a-custom-builder
    # -using-jupyter-book
    #
    # Older version -- kept for compatibility with myst-nb<0.14 for now
    if (
        "nb_render_priority" in app.config
        and app.config["nb_render_priority"] != "--unset--"
    ):
        app.config["nb_render_priority"]["probs_rdf"] = NB_RENDER_PRIORITY["probs_rdf"]
    elif "nb_mime_priority_overrides" in app.config:
        app.config["nb_mime_priority_overrides"] = NB_RENDER_PRIORITY_NEW
    else:
        app.add_config_value("nb_render_priority", NB_RENDER_PRIORITY, "probs_rdf")
        app.add_config_value("nb_mime_priority_overrides", NB_RENDER_PRIORITY_NEW, "env")

    app.add_domain(SystemDomain)

    app.add_directive("start-sub-processes", StartSubProcessesDirective)
    app.add_directive("start-sub-objects", StartSubObjectsDirective)
    app.add_directive("end-sub-processes", EndSubProcessesDirective)
    app.add_directive("end-sub-objects", EndSubObjectsDirective)
    app.add_directive("ttl", TTL)
    app.add_directive("object-equivalent-to", ObjectEquivalentTo)

    app.add_post_transform(ProbsTransform)

    # Since the graph is built when parsing, any change should trigger a rebuild
    app.add_config_value("probs_rdf_system_prefix", "", "env", [str])
    app.add_config_value("probs_rdf_extra_prefixes", {}, "env", [dict])
    app.add_config_value("probs_rdf_units", {}, "env", [dict])
    app.add_config_value("probs_rdf_paths", [], "env", [list])
    app.connect('config-inited', merge_default_config)

    app.connect("env-updated", read_external_graph)
    app.connect('build-finished', save_graph)

    # Add the custom CSS for the directives
    app.connect('build-finished', copy_custom_files)
    app.add_css_file('system-definitions.css')

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
