from os import path
from sphinx.util.fileutil import copy_asset_file
from typing import Any, Dict
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
)


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



def copy_custom_files(app, exc):
    if app.builder.format == 'html' and not exc:
        staticdir = path.join(app.builder.outdir, '_static')
        here = path.dirname(__file__)
        copy_asset_file(path.join(here, '_static/system-definitions.css'), staticdir)


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


def setup(app: Sphinx) -> Dict[str, Any]:
    app.add_builder(ProbsSystemRDFBuilder)
    # Add config for jupyter-book / myst_nb.
    # See https://jupyterbook.org/advanced/advanced.html#enabling-a-custom-builder
    # -using-jupyter-book
    if "nb_render_priority" in app.config:
        app.config["nb_render_priority"]["probs_rdf"] = NB_RENDER_PRIORITY["probs_rdf"]
    else:
        app.add_config_value("nb_render_priority", NB_RENDER_PRIORITY, "probs_rdf")

    app.add_domain(SystemDomain)

    app.add_directive("start-sub-processes", StartSubProcessesDirective)
    app.add_directive("start-sub-objects", StartSubObjectsDirective)
    app.add_directive("end-sub-processes", EndSubProcessesDirective)
    app.add_directive("end-sub-objects", EndSubObjectsDirective)
    app.add_directive("ttl", TTL)

    # Since the graph is built when parsing, any change should trigger a rebuild
    app.add_config_value("probs_rdf_system_prefix", "", "env", [str])
    app.add_config_value("probs_rdf_extra_prefixes", {}, "env", [dict])
    app.add_config_value("probs_rdf_units", {}, "env", [dict])
    app.connect('config-inited', merge_default_config)

    # Add the custom CSS for the directives
    app.connect('build-finished', copy_custom_files)
    app.add_css_file('system-definitions.css')

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
