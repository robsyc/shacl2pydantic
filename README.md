# shacl2pydantic

Convert [SHACL 1.2 Core](https://www.w3.org/TR/shacl12-core/) shape definitions to [Pydantic v2](https://docs.pydantic.dev/) model classes.

## Quickstart

```bash
pip install -e .
```

Given a SHACL Turtle file `shapes.ttl`:

```turtle
@prefix ex:  <http://example.org/ns#> .
@prefix sh:  <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:PersonShape
    a sh:NodeShape ;
    rdfs:comment "A person." ;
    sh:property [
        sh:path ex:name ;
        sh:datatype xsd:string ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:minLength 1 ;
    ] ;
    sh:property [
        sh:path ex:age ;
        sh:datatype xsd:integer ;
        sh:maxCount 1 ;
        sh:minInclusive 0 ;
    ] ;
    sh:property [
        sh:path ex:email ;
        sh:datatype xsd:string ;
    ] .
```

Run the converter:

```bash
shacl2pydantic shapes.ttl -o models.py
```

Output:

```python
from typing import Annotated, Optional
from pydantic import BaseModel, Field


class PersonShape(BaseModel):
    """A person."""
    name: Annotated[str, Field(min_length=1)]
    age: Annotated[Optional[int], Field(ge=0, default=None)]
    email: Annotated[list[str], Field(default_factory=list)]
```

## CLI Usage

```
shacl2pydantic SHAPES.ttl              # print to stdout
shacl2pydantic SHAPES.ttl -o models.py # write to file
shacl2pydantic --version
```

Warnings (unknown datatypes, skipped paths) go to stderr.

## Supported SHACL Features

| SHACL Constraint | Pydantic Mapping |
|---|---|
| `sh:datatype` | Python type (`str`, `int`, `float`, `Decimal`, `bool`, `date`, `datetime`, …) |
| `sh:minCount` / `sh:maxCount` | Required/optional, scalar/list field |
| `sh:name` | `Field(title=…)` |
| `sh:description` | `Field(description=…)` |
| `sh:defaultValue` | `Field(default=…)` with type-aware coercion |
| `sh:in` | `Literal["v1", "v2", …]` |
| `sh:node` | Nested `BaseModel` reference |
| `sh:or` | `TypeA \| TypeB` union |
| `sh:minLength` / `sh:maxLength` | `Field(min_length=…, max_length=…)` |
| `sh:minInclusive` / `sh:maxInclusive` | `Field(ge=…, le=…)` |
| `sh:minExclusive` / `sh:maxExclusive` | `Field(gt=…, lt=…)` |
| `sh:pattern` | `Field(pattern=…)` |
| `sh:codeIdentifier` | Custom Python identifier (overrides URI local name) |
| `rdfs:label` / `rdfs:comment` | Class docstring |
| Circular `sh:node` refs | Forward-reference strings + `model_rebuild()` |

See [COMPLIANCE.md](COMPLIANCE.md) for full details including unsupported constraints.

## Example

See [`example.ttl`](example.ttl) for a comprehensive SHACL file exercising all supported features, including nested shapes, enums, unions, self-referential trees, validation constraints, and implicit shapes.

```bash
shacl2pydantic example.ttl
```
