# SHACL to Pydantic Compliance

**SHACL Version:** SHACL 1.2 Core
**Last Updated:** 2026-04-04

This document describes the compliance level of `shacl2pydantic` with the SHACL 1.2 Core specification.

`shacl2pydantic` converts SHACL NodeShapes to Pydantic v2 BaseModel classes. It supports the most commonly used SHACL Core constraint properties. Constraints that cannot be expressed as Pydantic field metadata are skipped with warnings.

## Supported Constraints

| SHACL Property | Pydantic Mapping | Notes |
|---------------|------------------|-------|
| `sh:datatype` | Python type (`str`, `int`, `float`, `Decimal`, `bool`, `date`, `datetime`, `time`, `timedelta`, `bytes`) | Maps ~40 XSD types to Python builtins and stdlib |
| `sh:minCount` ≥ 1 + `sh:maxCount` 1 | Required scalar field | No `Optional`, no default |
| `sh:minCount` absent/0 + `sh:maxCount` 1 | `Optional[Type] = None` | |
| `sh:minCount` ≥ 1 + `sh:maxCount` absent/> 1 | `list[Type]` (required) | |
| `sh:minCount` absent/0 + `sh:maxCount` absent/> 1 | `list[Type] = []` | `default_factory=list` |
| `sh:name` | `Field(title=...)` | On property shapes |
| `sh:description` | `Field(description=...)` | On property shapes |
| `sh:defaultValue` | `Field(default=...)` | Type-aware coercion for `str`, `int`, `float`, `bool`, `Decimal`, `date`, `datetime` |
| `sh:in` | `Literal["v1", "v2", ...]` | Values coerced by XSD type (string, integer, float, boolean) |
| `sh:node` | Nested `BaseModel` reference | Topological sort determines class ordering |
| `sh:node` (circular) | Forward-ref string + `model_rebuild()` | Handles both self-references and mutual cycles |
| `sh:or` (datatypes) | `TypeA \| TypeB` (pipe union) | Python 3.10+ syntax |
| `sh:or` (node shapes) | `TypeA \| TypeB` or `Union[...]` | Node shape refs resolved; `Union` used when forward refs are needed |
| `sh:or` (mixed) | `ModelType \| str` etc. | Supports mixing `sh:node` and `sh:datatype` members |
| `sh:minLength` | `Field(min_length=N)` | String type only; skipped with warning for other types |
| `sh:maxLength` | `Field(max_length=N)` | String type only; skipped with warning for other types |
| `sh:minInclusive` | `Field(ge=N)` | Numeric types only (`int`, `float`, `Decimal`) |
| `sh:maxInclusive` | `Field(le=N)` | Numeric types only |
| `sh:minExclusive` | `Field(gt=N)` | Numeric types only |
| `sh:maxExclusive` | `Field(lt=N)` | Numeric types only |
| `sh:pattern` | `Field(pattern="regex")` | String type only; skipped with warning for other types |
| `sh:codeIdentifier` | Python identifier (class/field name) | Priority: `codeIdentifier` > `sh:name`/`rdfs:label` > URI local name. Works on both NodeShapes and property shapes |
| `rdfs:label` | Class name (PascalCase) / docstring fallback | On NodeShape |
| `rdfs:comment` | Class docstring | On NodeShape (preferred over label) |

## Partially Supported Constraints

| SHACL Property | Notes |
|---------------|-------|
| `sh:flags` | Pattern flags (`i`, `s`, `m`, etc.) are detected and a warning is logged, but NOT applied. Pydantic's `Field(pattern=...)` does not accept regex flags. The pattern is emitted as-is. |

## Unsupported Constraints

| SHACL Property | Rationale |
|---------------|-----------|
| `sh:sparql` | Requires SPARQL engine; cannot be expressed as Pydantic validators |
| `sh:targetClass` / `sh:targetNode` / etc. | SHACL targets control validation scope; not applicable to model class generation |
| `sh:closed` / `sh:ignoredProperties` | Could map to `ConfigDict(extra='forbid')` but `sh:ignoredProperties` has no Pydantic equivalent; future enhancement |
| `sh:class` | RDF class type constraint; similar to `sh:node` but semantically different; future enhancement |
| `sh:hasValue` | Fixed-value constraints; would require `@model_validator` |
| `sh:nodeKind` | IRI vs Literal vs BlankNode distinction; no Pydantic equivalent |
| `sh:and` | Intersection types; complex to represent in Pydantic |
| `sh:not` | Exclusion patterns; would require custom validator |
| `sh:xone` | Exclusive-or union; would require custom validator |
| `sh:qualifiedValueShape` / `sh:qualifiedMinCount` / `sh:qualifiedMaxCount` | Complex cardinality on shape-constrained values |
| `sh:equals` / `sh:disjoint` / `sh:lessThan` / `sh:lessThanOrEquals` | Cross-field validation; would require `@model_validator` |
| `sh:group` / `sh:order` | Field grouping/ordering hints; no direct Pydantic equivalent |
| `sh:severity` | Violation severity level; not applicable to model generation |
| Property paths (sequence, inverse, alternative, `sh:zeroOrMorePath`, etc.) | Non-predicate paths are skipped with a warning |

## Known Limitations

- **Non-predicate paths**: Only simple predicate paths (`sh:path ex:somePredicate`) are supported. Complex property paths (sequence, inverse, alternative) are logged as warnings and skipped.
- **Field ordering**: Properties within a shape follow RDF graph iteration order, which matches document order for Turtle files but is not formally guaranteed.
- **Default value coercion**: `time`, `timedelta`, and `bytes` defaults are emitted as string literals rather than constructor calls.
- **Name collisions**: If multiple shapes resolve to the same Python class name after sanitization, duplicate classes will be emitted.
