Sphinx probs_rdf extension
==========================

This extension adds directives to Sphinx for adding Processes and Objects to a PRObs ontology system definition.

Standalone loader
------------------

If installed with the ``loader`` extra (``pip install sphinx_probs_rdf[loader]``), the system definitions can be parsed independently of the Sphinx build::

    from sphinx_probs_rdf import parse_system_definitions

    system = parse_system_definitions(["definitions.md"])
    print(system.objects, system.processes)

Identifiers are used exactly as written unless a prefix table is given. With one, they are
expanded as the Sphinx extension expands them (``""`` is the default namespace, the
counterpart of ``probs_rdf_system_prefix``)::

    system = parse_system_definitions(
        ["core.md", "casting_recipes.md", "casting_allocated.md"],
        prefixes={"": "https://example.org/steel/", "steel": "https://example.org/steel/",
                  "cast-r": "https://example.org/steel/casting/recipes/",
                  "cast-a": "https://example.org/steel/casting/allocated/"},
    )

A file can put its bare names in a namespace of its own with front matter::

    ---
    system_prefix: cast-a
    ---

Linking models
--------------

A parsed system can hold several alternative readings of part of a model, each in its own
namespace. ``link_model`` picks one model out of it and flattens it to local names, so a
consumer never sees prefixes or IRIs::

    from sphinx_probs_rdf import ProcessSelection, RecipeSubstitution, ObjectOverride, link_model

    model = link_model(system, [
        ProcessSelection("steel:"),
        ProcessSelection("cast-a:"),
        RecipeSubstitution(["steel:SheetSale"], {"_:HotBand": "cast-a:HotBandForSale"}),
        ObjectOverride("steel:PrimaryMillProduct", can_export=False),
    ])

``_:label`` is a placeholder: an object a process refers to without naming it, filled in
when a model is linked. A model contains exactly the objects its selected processes refer
to, with their declared parents. Namespace membership is the namespace each definition was
declared in (``rdfs:isDefinedBy`` in the RDF output), never inferred from the IRI.

License
-------

sphinx_probs_rdf is licensed with the `MIT license <LICENSE>`_.

Acknowledgements
----------------

Thanks to the `sphinxcontrib repositories`_ for inspiration on how to set up, package and test a Sphinx extension.

.. _sphinxcontrib repositories: https://github.com/sphinx-doc/sphinxcontrib-jsmath
