Developing sphinx_probs_rdf
===========================

Tests
-----

Run tests with current python environment using ``pytest``, or for all supported environments with ``tox``.

Release
-------

Check tools are installed: ``pip install build twine``

1. Check tests pass
2. Check release version in ``src/sphinx_probs_rdf/version.py``
3. Update release date in ``CHANGELOG``
4. Build distribution files: ``python -m build``
5. Make a release: ``twine upload dist/<new-version-files>``
6. Tag git with version name. e.g.: ``git tag v1.1.0``
7. Bump version in ``src/sphinx_probs_rdf/version.py``
