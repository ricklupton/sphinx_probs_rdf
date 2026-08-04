Sphinx probs_rdf extension
==========================

This extension adds directives to Sphinx for adding Processes and Objects to a PRObs ontology system definition.

Standalone loader
------------------

If installed with the ``loader`` extra (``pip install sphinx_probs_rdf[loader]``), the system definitions can be parsed independently of the Sphinx build::

    from sphinx_probs_rdf import parse_system_definitions

    system = parse_system_definitions(["definitions.md"])
    print(system.objects, system.processes)

License
-------

sphinx_probs_rdf is licensed with the `MIT license <LICENSE>`_.

Acknowledgements
----------------

Thanks to the `sphinxcontrib repositories`_ for inspiration on how to set up, package and test a Sphinx extension.

.. _sphinxcontrib repositories: https://github.com/sphinx-doc/sphinxcontrib-jsmath
