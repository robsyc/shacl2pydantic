"""Intermediate representation: FieldKind, PropertyField, ShapeModel."""

from __future__ import annotations

import dataclasses
import enum


class FieldKind(enum.Enum):
    """How SHACL cardinality maps to a Pydantic field pattern."""

    REQUIRED_SCALAR = "required_scalar"
    OPTIONAL_SCALAR = "optional_scalar"
    REQUIRED_LIST = "required_list"
    OPTIONAL_LIST = "optional_list"


def resolve_cardinality(min_count: int | None, max_count: int | None) -> FieldKind:
    """Map sh:minCount / sh:maxCount to a FieldKind.

    - absent/0 minCount → optional; >= 1 → required
    - maxCount 1 → scalar; absent or > 1 → list
    """
    required = max(0, min_count or 0) >= 1
    scalar = max_count == 1
    if scalar:
        return FieldKind.REQUIRED_SCALAR if required else FieldKind.OPTIONAL_SCALAR
    return FieldKind.REQUIRED_LIST if required else FieldKind.OPTIONAL_LIST


@dataclasses.dataclass
class PropertyField:
    """A SHACL property constraint mapped to a Pydantic field."""

    name: str
    python_type: str
    field_kind: FieldKind
    title: str | None = None
    description: str | None = None
    enum_values: list[str] | None = None
    node_shape_ref: str | None = None
    union_members: list[str] | None = None
    min_length: int | None = None
    max_length: int | None = None
    min_inclusive: float | None = None
    max_inclusive: float | None = None
    min_exclusive: float | None = None
    max_exclusive: float | None = None
    pattern: str | None = None
    pattern_flags: str | None = None
    default_value: str | None = None
    type_imports: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class ShapeModel:
    """A SHACL NodeShape mapped to a Pydantic BaseModel class."""

    name: str
    properties: list[PropertyField] = dataclasses.field(default_factory=list)
    docstring: str | None = None
