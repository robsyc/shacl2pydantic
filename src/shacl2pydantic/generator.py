"""Pydantic v2 code generator: IR ShapeModel list → Python source code."""

from __future__ import annotations

import heapq
import logging
from collections import defaultdict

from .ir import FieldKind, PropertyField, ShapeModel

logger = logging.getLogger(__name__)

_NUMERIC = frozenset({"int", "float", "Decimal"})
_STDLIB = frozenset({"datetime", "decimal", "typing"})


# ── Public API ───────────────────────────────────────────────────────────────


def generate_code(shapes: list[ShapeModel]) -> str:
    """Generate Pydantic v2 source code from ShapeModels."""
    names = {s.name for s in shapes}
    deps = _dep_graph(shapes, names)
    ordered, cycles = _topo_sort(shapes, deps)
    fwd = _forward_refs(ordered, cycles, names)

    imports = _import_block(ordered, fwd)
    classes = [_fmt_class(s, fwd) for s in ordered]
    rebuilds = [f"{s.name}.model_rebuild()" for s in ordered if s.name in fwd]

    body = "\n\n\n".join(classes)
    suffix = "\n\n\n" + "\n".join(rebuilds) if rebuilds else ""
    return imports + "\n\n\n" + body + suffix + "\n" if classes else imports + "\n"


# ── Import collection ────────────────────────────────────────────────────────


def _import_block(shapes: list[ShapeModel], fwd: set[str]) -> str:
    needs_literal = any(f.enum_values for s in shapes for f in s.properties)
    needs_union = any(
        f.union_members and any(m in fwd for m in f.union_members)
        for s in shapes for f in s.properties
    )
    grouped: dict[str, set[str]] = defaultdict(set)
    grouped["typing"] = (
        {"Annotated", "Optional"}
        | ({"Literal"} if needs_literal else set())
        | ({"Union"} if needs_union else set())
    )
    grouped["pydantic"] = {"BaseModel", "Field"}

    for s in shapes:
        for f in s.properties:
            for imp in f.type_imports:
                if not imp.startswith("from "):
                    continue
                parts = imp[5:].split(" import ", 1)
                if len(parts) == 2:
                    for n in parts[1].split(","):
                        grouped[parts[0].strip()].add(n.strip())

    stdlib = sorted((m, sorted(ns)) for m, ns in grouped.items() if m in _STDLIB)
    other = sorted((m, sorted(ns)) for m, ns in grouped.items() if m not in _STDLIB)
    return "\n".join(f"from {m} import {', '.join(ns)}" for m, ns in stdlib + other)


# ── Dependency graph / topological sort ──────────────────────────────────────


def _dep_graph(shapes: list[ShapeModel], names: set[str]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {s.name: set() for s in shapes}
    for s in shapes:
        for f in s.properties:
            refs: set[str] = set()
            if f.node_shape_ref and f.node_shape_ref in names:
                refs.add(f.node_shape_ref)
            if f.union_members:
                refs.update(m for m in f.union_members if m in names)
            refs.discard(s.name)
            graph[s.name].update(refs)
    return graph


def _topo_sort(
    shapes: list[ShapeModel], deps: dict[str, set[str]]
) -> tuple[list[ShapeModel], set[str]]:
    by_name = {s.name: s for s in shapes}
    by_idx = {s.name: i for i, s in enumerate(shapes)}
    in_deg = {n: len(d) for n, d in deps.items()}
    rev: dict[str, set[str]] = {s.name: set() for s in shapes}
    for n, ds in deps.items():
        for d in ds:
            rev[d].add(n)

    queue = [by_idx[n] for n, d in in_deg.items() if d == 0]
    heapq.heapify(queue)
    result: list[str] = []
    while queue:
        name = shapes[heapq.heappop(queue)].name
        result.append(name)
        for dep in rev.get(name, set()):
            in_deg[dep] -= 1
            if in_deg[dep] == 0:
                heapq.heappush(queue, by_idx[dep])

    cycles = {s.name for s in shapes} - set(result)
    result.extend(s.name for s in shapes if s.name in cycles)
    return [by_name[n] for n in result], cycles


def _forward_refs(
    shapes: list[ShapeModel], cycles: set[str], names: set[str]
) -> set[str]:
    """Shapes needing model_rebuild(): self-references or mutual cycles."""
    refs: set[str] = set()
    for s in shapes:
        for f in s.properties:
            is_self = (f.node_shape_ref == s.name) or (
                f.union_members and s.name in f.union_members
            )
            has_ref = (f.node_shape_ref and f.node_shape_ref in names) or (
                f.union_members and any(m in names for m in f.union_members)
            )
            if is_self or (s.name in cycles and has_ref):
                refs.add(s.name)
                break
    return refs


# ── Code formatting ──────────────────────────────────────────────────────────


def _effective_type(f: PropertyField, fwd: set[str]) -> str:
    if f.enum_values:
        return f"Literal[{', '.join(f.enum_values)}]"
    if f.union_members:
        parts = [f'"{m}"' if m in fwd else m for m in f.union_members]
        if any(m in fwd for m in f.union_members):
            return f"Union[{', '.join(parts)}]"
        return " | ".join(parts)
    if f.node_shape_ref:
        return f'"{f.node_shape_ref}"' if f.node_shape_ref in fwd else f.node_shape_ref
    return f.python_type


def _wrap_type(ty: str, kind: FieldKind) -> str:
    if kind is FieldKind.REQUIRED_SCALAR:
        return ty
    if kind is FieldKind.OPTIONAL_SCALAR:
        return f"Optional[{ty}]"
    return f"list[{ty}]"


def _fmt_range(v: float) -> str:
    return str(int(v)) if v == int(v) else str(v)


def _field_params(f: PropertyField) -> str:
    parts: list[str] = []
    if f.title:
        parts.append(f"title={f.title!r}")
    if f.description:
        parts.append(f"description={f.description!r}")

    structural = f.enum_values or f.union_members or f.node_shape_ref
    if not structural:
        for attr, param in [("min_length", "min_length"), ("max_length", "max_length")]:
            val = getattr(f, attr)
            if val is not None:
                if f.python_type == "str":
                    parts.append(f"{param}={val}")
                else:
                    logger.warning("%s skipped for non-str type on '%s'", attr, f.name)
        for attr, param in [
            ("min_inclusive", "ge"), ("max_inclusive", "le"),
            ("min_exclusive", "gt"), ("max_exclusive", "lt"),
        ]:
            val = getattr(f, attr)
            if val is not None:
                if f.python_type in _NUMERIC:
                    parts.append(f"{param}={_fmt_range(val)}")
                else:
                    logger.warning("%s skipped for non-numeric type on '%s'", attr, f.name)
        if f.pattern is not None:
            if f.python_type == "str":
                if f.pattern_flags:
                    logger.warning("sh:flags '%s' ignored on '%s'", f.pattern_flags, f.name)
                parts.append(f"pattern={f.pattern!r}")
            else:
                logger.warning("pattern skipped for non-str type on '%s'", f.name)

    if f.default_value is not None:
        parts.append(f"default={_coerce_default(f.default_value, f.python_type)}")
    elif f.field_kind is FieldKind.OPTIONAL_SCALAR:
        parts.append("default=None")
    elif f.field_kind is FieldKind.OPTIONAL_LIST:
        parts.append("default_factory=list")

    return ", ".join(parts)


def _coerce_default(val: str, py_type: str) -> str:
    raw = val
    if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
        raw = raw[1:-1]
    match py_type:
        case "int":
            return str(int(raw))
        case "float":
            return str(float(raw))
        case "bool":
            return "True" if raw.lower() in ("true", "1") else "False"
        case "str":
            return val
        case "Decimal":
            return f"Decimal({val})"
        case "date":
            p = raw.split("-")
            return f"date({p[0]}, {int(p[1])}, {int(p[2])})"
        case "datetime":
            d, t = raw.split("T")
            dp, tp = d.split("-"), t.split(":")
            return f"datetime({dp[0]}, {int(dp[1])}, {int(dp[2])}, {int(tp[0])}, {int(tp[1])})"
        case _:
            return val


def _fmt_class(shape: ShapeModel, fwd: set[str]) -> str:
    lines = [f"class {shape.name}(BaseModel):"]
    if shape.docstring:
        escaped = shape.docstring.replace('"""', r'\"""')
        lines.append(f'    """{escaped}"""')
    if not shape.properties and not shape.docstring:
        lines.append("    pass")
    else:
        for f in shape.properties:
            ty = _wrap_type(_effective_type(f, fwd), f.field_kind)
            lines.append(f"    {f.name}: Annotated[{ty}, Field({_field_params(f)})]")
    return "\n".join(lines)
