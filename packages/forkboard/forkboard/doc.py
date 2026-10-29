"""The review document (schema "bundle/1"): what a tool hands Forkboard to make a page of.

    {"schema": "bundle/1",
     "id": "csv",                      # names the page, its sections' eyebrow and its saved state
     "kind": "Brainstorm",             # what sort of review: the page title is "<kind>: <id>"
     "title": "Brainstorm: csv",       # the heading; empty means the page title
     "meta": {"picked by": "person"},  # shown under the heading
     "intro": "markdown",
     "sections": [{"title": "Options", "kind": "text|chosen|rejected|open|callout", "markdown": "...",
                   "items": [{"title": "A. Stream it", "label": "A", "chosen": false, "markdown": "..."}]}]}

The markdown is the restricted kind page.blocks() renders. Forkboard never reads or writes the tool's own files:
the tool turns them into this document, and writes back what people did itself.
"""

from . import SCHEMA

KINDS = ("text", "chosen", "rejected", "open", "callout")


def check(doc):
    """The document, or ValueError naming what is wrong with it."""
    if not isinstance(doc, dict):
        raise ValueError("a review document is a JSON object")
    schema = str(doc.get("schema") or "")
    if schema.split(".")[0] != SCHEMA.split(".")[0]:
        raise ValueError("this forkboard reads %s documents, not %s" % (SCHEMA, schema or "ones with no schema"))
    if not isinstance(doc.get("sections", []), list) or not isinstance(doc.get("meta", {}), dict):
        raise ValueError("sections must be a list and meta an object")
    for section in doc.get("sections") or []:
        if not isinstance(section, dict) or section.get("kind", "text") not in KINDS:
            raise ValueError("each section is an object whose kind is one of %s" % ", ".join(KINDS))
        if not isinstance(section.get("items", []), list) or not all(isinstance(i, dict) for i in section.get("items") or []):
            raise ValueError("a section's items must be a list of objects")
    return doc
