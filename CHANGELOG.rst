Changelog
=========

v0.1.5 ()
-------------------

New:
- New config value `probs_rdf_extra_prefixes` is a dictionary of RDF prefixes which will be bound when parsing RDF values. Default prefixes include `sys:`, equal to the config value `probs_rdf_system_prefix`, `probs:` for the PRObs ontology, and `rec:` for recipes.
- `TTL` directive renders with syntax highlighting as a code block.
- `TTL` directive actually parses the turtle format RDF and checks it is valid.

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
