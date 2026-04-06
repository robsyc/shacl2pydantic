"""SHACL parser: Turtle file → IR ShapeModel list."""

from __future__ import annotations

import keyword
import logging
import re

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

from .ir import PropertyField, ShapeModel, resolve_cardinality
from .types import resolve_xsd_type

logger = logging.getLogger(__name__)

SH = Namespace("http://www.w3.org/ns/shacl#")
_XSD = "http://www.w3.org/2001/XMLSchema#"
_INT_LOCALS = frozenset({
    "integer", "int", "long", "short", "byte",
    "nonNegativeInteger", "positiveInteger", "nonPositiveInteger", "negativeInteger",
    "unsignedInt", "unsignedLong", "unsignedShort", "unsignedByte",
})


# ── Public API ───────────────────────────────────────────────────────────────


def parse_file(filepath: str) -> list[ShapeModel]:
    """Parse a SHACL Turtle file into ShapeModel instances."""
    g = Graph()
    g.parse(filepath, format="turtle")
    shapes: set[URIRef | BNode] = set()
    for s in g.subjects(RDF.type, SH.NodeShape):
        shapes.add(s)
    for s in g.subjects(SH.property, None):
        if (s, RDF.type, SH.NodeShape) not in g:
            shapes.add(s)
    return [_build_shape(g, s) for s in shapes]


# ── Name helpers ─────────────────────────────────────────────────────────────


def _to_snake(text: str) -> str:
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return re.sub(r"[\s\-]+", "_", s).lower()


def _to_pascal(text: str) -> str:
    return "".join(w[0].upper() + w[1:] for w in re.split(r"[_\s\-]+", text) if w)


def _sanitize(name: str) -> str:
    r = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    r = re.sub(r"^[0-9]+", "", r)
    r = re.sub(r"_+", "_", r).strip("_")
    if not r:
        return "unnamed"
    return f"{r}_" if keyword.iskeyword(r) else r


def _local_name(uri: str) -> str:
    if "#" in uri:
        return uri.rsplit("#", 1)[-1]
    if "/" in uri:
        return uri.rsplit("/", 1)[-1]
    return uri


def _class_name(code_id: str | None, label: str | None, uri_local: str | None) -> str:
    if code_id:
        return _sanitize(code_id)
    if label:
        return _sanitize(_to_pascal(label))
    if uri_local:
        return _sanitize(uri_local)
    return "UnnamedModel"


def _field_name(code_id: str | None, name_label: str | None, path_local: str | None) -> str:
    if code_id:
        return _sanitize(code_id)
    if name_label:
        return _sanitize(_to_snake(name_label))
    if path_local:
        return _sanitize(path_local)
    return "unnamed_field"


# ── RDF helpers ────────────────────────────────────────────────────────────


def _rdf_list(g: Graph, head: URIRef | BNode) -> list[object]:
    if head == RDF.nil:
        return []
    values: list[object] = []
    current: URIRef | BNode | None = head
    visited: set[URIRef | BNode] = set()
    while current is not None and current != RDF.nil and current not in visited:
        visited.add(current)
        first = g.value(current, RDF.first)
        if first is not None:
            values.append(first)
        current = g.value(current, RDF.rest)
    return values


def _classify_path(g: Graph, node: URIRef | BNode) -> tuple[str, URIRef | None]:
    if isinstance(node, URIRef):
        return ("predicate", node)
    if g.value(node, SH.inversePath) is not None:
        return ("inverse", None)
    if g.value(node, SH.alternativePath) is not None:
        return ("alternative", None)
    if (node, RDF.first, None) in g:
        return ("sequence", None)
    return ("unknown", None)


def _str(node: object) -> str | None:
    return str(node) if node is not None else None


def _int(node: object) -> int | None:
    return int(str(node)) if node is not None else None


def _float(node: object) -> float | None:
    return float(str(node)) if node is not None else None


# ── Shape / property extraction ──────────────────────────────────────────────


def _resolve_shape_class_name(g: Graph, shape_uri: URIRef) -> str:
    """Resolve a shape URI to the Python class name it will generate."""
    code_id = _str(g.value(shape_uri, SH.codeIdentifier))
    label = _str(g.value(shape_uri, RDFS.label))
    return _class_name(code_id, label, _local_name(str(shape_uri)))


def _build_shape(g: Graph, node: URIRef | BNode) -> ShapeModel:
    code_id = _str(g.value(node, SH.codeIdentifier))
    label = _str(g.value(node, RDFS.label))
    uri_local = _local_name(str(node)) if isinstance(node, URIRef) else None
    comment = _str(g.value(node, RDFS.comment))

    fields: list[PropertyField] = []
    for prop in g.objects(node, SH.property):
        f = _build_field(g, prop)
        if f:
            fields.append(f)

    return ShapeModel(
        name=_class_name(code_id, label, uri_local),
        properties=fields,
        docstring=comment or label,
    )


def _coerce_enum_val(node: object) -> str:
    """Coerce an RDF list value to a Python literal string for Literal[...]."""
    if isinstance(node, Literal):
        dt, val = node.datatype, str(node)
        if dt:
            local = str(dt).removeprefix(_XSD)
            if local == "boolean":
                return "True" if val.lower() in ("true", "1") else "False"
            if local in _INT_LOCALS:
                return str(int(val))
            if local in ("float", "double", "decimal"):
                return str(float(val))
        return f'"{val}"'
    return repr(str(node))


def _build_field(g: Graph, ps: URIRef | BNode) -> PropertyField | None:
    path_node = g.value(ps, SH.path)
    if path_node is None:
        return None
    ptype, pred = _classify_path(g, path_node)
    if ptype != "predicate":
        logger.warning("Skipping non-predicate path '%s'", ptype)
        return None

    code_id = _str(g.value(ps, SH.codeIdentifier))
    name_lbl = _str(g.value(ps, SH.name))
    fname = _field_name(code_id, name_lbl, _local_name(str(pred)))

    # ── Structural constraints ───────────────────────────────────────────
    enum_vals: list[str] | None = None
    enum_imps: list[str] = []
    sh_in = g.value(ps, SH["in"])
    if sh_in:
        raw = _rdf_list(g, sh_in)
        if raw:
            enum_vals = [_coerce_enum_val(v) for v in raw]
            enum_imps = ["from typing import Literal"]

    node_ref: str | None = None
    sh_node = g.value(ps, SH.node)
    if isinstance(sh_node, URIRef):
        node_ref = _resolve_shape_class_name(g, sh_node)

    union_members: list[str] | None = None
    union_imps: list[str] = []
    sh_or = g.value(ps, SH["or"])
    if sh_or:
        raw = _rdf_list(g, sh_or)
        if raw:
            members: list[str] = []
            for m in raw:
                if isinstance(m, URIRef):
                    members.append(_resolve_shape_class_name(g, m))
                elif isinstance(m, BNode):
                    dt = g.value(m, SH.datatype)
                    nd = g.value(m, SH.node)
                    if dt:
                        py, imp = resolve_xsd_type(str(dt))
                        members.append(py)
                        if imp:
                            union_imps.append(imp)
                    elif isinstance(nd, URIRef):
                        members.append(_resolve_shape_class_name(g, nd))
                    else:
                        members.append("Any")
                else:
                    members.append(str(m))
            union_members = members

    has_structural = node_ref is not None or union_members is not None

    # ── Datatype resolution ──────────────────────────────────────────────
    datatype = g.value(ps, SH.datatype)
    if datatype:
        py_type, imp = resolve_xsd_type(str(datatype))
        type_imports: list[str] = [imp] if imp else []
        if py_type == "Any":
            logger.warning("Unknown datatype %s for '%s'", datatype, fname)
    elif has_structural:
        py_type, type_imports = "Any", []
    else:
        py_type, type_imports = "Any", ["from typing import Any"]
        logger.warning("No sh:datatype on '%s', defaulting to Any", fname)

    type_imports.extend(enum_imps)
    type_imports.extend(union_imps)

    if union_members:
        py_type = union_members[0] if union_members else py_type
    elif node_ref:
        py_type = node_ref

    default_lit = g.value(ps, SH.defaultValue)

    return PropertyField(
        name=fname,
        python_type=py_type,
        field_kind=resolve_cardinality(
            _int(g.value(ps, SH.minCount)),
            _int(g.value(ps, SH.maxCount)),
        ),
        title=name_lbl,
        description=_str(g.value(ps, SH.description)),
        default_value=repr(str(default_lit)) if default_lit else None,
        type_imports=type_imports,
        enum_values=enum_vals,
        node_shape_ref=node_ref,
        union_members=union_members,
        min_length=_int(g.value(ps, SH.minLength)),
        max_length=_int(g.value(ps, SH.maxLength)),
        min_inclusive=_float(g.value(ps, SH.minInclusive)),
        max_inclusive=_float(g.value(ps, SH.maxInclusive)),
        min_exclusive=_float(g.value(ps, SH.minExclusive)),
        max_exclusive=_float(g.value(ps, SH.maxExclusive)),
        pattern=_str(g.value(ps, SH.pattern)),
        pattern_flags=_str(g.value(ps, SH.flags)),
    )
