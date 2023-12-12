Changelog
=========

Unreleased
----------


v0.4.4 (2023-12-18)
-------------------

Bugfix release remaining on old PRObs prefix:

- Use rdflib version >= 6.2, <7.0 : This fixes turtle serialization errors for PNames that contain brackets, see [rdflib changelog](https://github.com/RDFLib/rdflib/blob/main/CHANGELOG.md#2022-07-16-release-620), pull request 1678).

- Include function preferredLabel within resolve.py : rdflib versions greater than 6.1.1 no longer have the preferredLabel method in the ConjunctiveGraph class.


v0.4.3 (2023-08-02)
-------------------

New features:
- "Market" processes corresponding to objects are now defined in the RDF output. These are intended to represent the part of a system where supply, imports, exports and consumption of that object type may be balanced.

Fixes:
- Fix logging exception when definitions are missing in index-building code


v0.4.2 (2023-05-10)
-------------------

Compatibility:
- Now compatible with myst-nb version 0.14 (used by jupyter-book version 0.15).

v0.4.1 (2023-05-04)
-------------------

Fixes:
- Config paths `probs_rdf_paths` are now relative to the configuration directory.

v0.4.0 (2023-04-20)
-------------------

Changes:
- Use full URIs as object/process identifiers, so that we can link to their definitions using intersphinx. This changes the HTML anchors within pages.

New features:
- External RDF data with definitions can be read, and used to make cross-references.
- New `object-equivalent-to` directive to declare `probs:objectEquivalentTo` relationships.

Fixes:
- Attempt to properly clear old data so that we can rebuild incrementally.


v0.3.0 (2022-10-27)
-------------------

Changes:
- Now depends on Sphinx version >= 4.0

v0.2.0 (2022-04-22)
-------------------

Changes:
- Recipes are now in namespace probs-recipe: not probs: prefix (the semantics are different so it should have been different)

v0.1.7 (2022-04-12)
-------------------

New:
- Recipes can be in several units other than "kg" ("m2" for area, "m3" for volume, and "-" for number). This list may be expanded in future.

v0.1.6 (2022-03-16)
-------------------

New:
- New config value `probs_rdf_extra_prefixes` is a dictionary of RDF prefixes which will be bound when parsing RDF values. Default prefixes include `sys:`, equal to the config value `probs_rdf_system_prefix`, `probs:` for the PRObs ontology, and `rec:` for recipes.
- `TTL` directive renders with syntax highlighting as a code block.
- `TTL` directive actually parses the turtle format RDF and checks it is valid.
- New `system:object` option `traded` to set `probs:objectIsTraded` (experimental).
- New `system:object` option `equivalent` to set `probs:objectEquivalentTo` (experimental).

v0.1.5 (2021-10-22)
-------------------

Fixes:
- Include static CSS files within the package distribution.

v0.1.4 (2021-10-22)
-------------------

Changes:
- The CSS for styling the object/process definition blocks is now included by the extension. The file `_static/system-definitions.css` no longer needs to be included in the documentation using the extension.

Fixes:
- Improve styling of "ending sub-objects" markers
- Fix object index when no processes are defined
- Fix cross-reference link to objects' parent

v0.1.3 (2021-10-01)
-------------------

- Objects are now also ReferenceObjects in RDF output

v0.1.2 (2021-07-29)
-------------------

- Added experimental RDF output of quantified recipes
- Improve HTML output of recipes and link to parent processes

v0.1.1 (2021-04-21)
-------------------

- Added objectName and processName to RDF output
