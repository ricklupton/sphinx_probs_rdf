Sphinx probs_rdf extension
==========================

This extension adds directives to Sphinx for adding Processes and Objects to a PRObs ontology system definition.

Standalone loader
------------------

If installed with the ``loader`` extra (``pip install sphinx_probs_rdf[loader]``), the system definitions can be parsed independently of the Sphinx build::

    from sphinx_probs_rdf import parse_system_definitions

    system = parse_system_definitions(["definitions.md"])
    print(system.objects, system.processes)

Without a prefix table, a bare name is its own identifier. With one, identifiers are
expanded as the Sphinx extension expands them (``""`` is the default namespace, the
counterpart of ``probs_rdf_system_prefix``)::

    system = parse_system_definitions(
        ["core.md", "casting_recipes.md", "casting_allocated.md"],
        prefixes={"": "https://example.org/steel/", "steel": "https://example.org/steel/",
                  "cast-r": "https://example.org/steel/casting/recipes/",
                  "cast-a": "https://example.org/steel/casting/allocated/"},
    )

A ``system:prefix`` directive puts the bare names that follow it in a namespace of their
own, until the end of the document or the next ``system:prefix`` (``:`` restores the
default)::

    ```{system:prefix} cast-a
    ```

On the Sphinx path, a file brought in with ``include`` that sets no prefix uses the one
in force where it is included; one that does set a prefix changes it for the rest of the
including document too.

Linking models
--------------

A parsed system can hold several alternative readings of part of a model, each in its own
namespace. ``link_model`` picks one model out of it and flattens it to local names, so a
consumer never sees prefixes or IRIs::

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
list of these, or ``ALL``. Its remapping (``{"_:HotBand": ...}``) applies to the
processes it selects, so ``[ProcessSelection("steel:SheetSale", {...}),
ProcessSelection("steel:")]`` remaps in ``SheetSale`` only.

``_:label`` is a placeholder: an object a process refers to without naming it, filled in
when a model is linked. A model contains exactly the objects its selected processes refer
to, with their declared parents. Namespace membership is the namespace each definition was
declared in (``rdfs:isDefinedBy`` in the RDF output), never inferred from the IRI.

In the linked model each definition is called by its local name, or by its prefixed name
(``cast-a:Cast``) where two would otherwise share one; ``local_names={...}`` chooses
names explicitly.

License
-------

sphinx_probs_rdf is licensed with the `MIT license <LICENSE>`_.

Acknowledgements
----------------

Thanks to the `sphinxcontrib repositories`_ for inspiration on how to set up, package and test a Sphinx extension.

.. _sphinxcontrib repositories: https://github.com/sphinx-doc/sphinxcontrib-jsmath
