from os import path
from sphinx.util.fileutil import copy_asset_file
from typing import Any, Dict
from sphinx.application import Sphinx

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

    # Add the custom CSS for the directives
    app.connect('build-finished', copy_custom_files)
    app.add_css_file('system-definitions.css')

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
