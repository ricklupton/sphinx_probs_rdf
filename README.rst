Sphinx probs_rdf extension
==========================

This extension adds directives to Sphinx for adding Processes and Objects to a PRObs ontology system definition.

Standalone loader
------------------

If installed with the ``loader`` extra (``pip install sphinx_probs_rdf[loader]``), the system definitions can be parsed independently of the Sphinx build::

    from sphinx_probs_rdf import parse_system_definitions

    system = parse_system_definitions(["definitions.md"])
    print(system.objects, system.processes)

By default, identifiers are parsed as if they were RDF with a blank default
prefix. A prefix table can also be given (``""`` is the default namespace, the
counterpart of ``probs_rdf_system_prefix``)::

    system = parse_system_definitions(
        ["core.md", "casting_recipes.md", "casting_allocated.md"],
        prefixes={"": "https://example.org/steel/", "steel": "https://example.org/steel/",
                  "cast-r": "https://example.org/steel/casting/recipes/",
                  "cast-a": "https://example.org/steel/casting/allocated/"},
    )

A ``system:prefix`` directive sets the default namespace, until the end of the
document or the next ``system:prefix`` (``:`` restores the default).

Linking models
--------------

A parsed system can hold several alternative components of a system, each in its own
namespace, of which only some are needed in a given model. ``link_model`` picks one model out of the parsed system and flattens it to use local names::

    from sphinx_probs_rdf import ProcessSelection, link_model

    model = link_model(
        system,
        [
            ProcessSelection("steel:", {"_:HotBand": "cast-a:HotBandForSale"}),
            ProcessSelection("cast-a:"),
        ],
        object_overrides={"steel:PrimaryMillProduct": {"traded": (True, False)}},
    )

A selection's scope is a namespace (``"prefix:"``), one process (``"prefix:Name"``), a
list of these, or ``ALL``. Optionally, object names can be remapped to fit into the wider system. An object name like ``_:label`` is a placeholder, to be filled in when a model is linked.

A model is defined based on the processes it includes; it automatically contains the objects its selected processes refer to, with their declared parents. In the linked model each definition is called by its local name, or by its prefixed name
(``cast-a:Cast``) where two would otherwise share one.

License
-------

sphinx_probs_rdf is licensed with the `MIT license <LICENSE>`_.

Acknowledgements
----------------

Thanks to the `sphinxcontrib repositories`_ for inspiration on how to set up, package and test a Sphinx extension.

.. _sphinxcontrib repositories: https://github.com/sphinx-doc/sphinxcontrib-jsmath
