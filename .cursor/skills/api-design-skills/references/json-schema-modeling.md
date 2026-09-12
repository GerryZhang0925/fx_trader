# JSON Schema modeling

## Contents

1. Dialects
2. Object modeling
3. Composition
4. Evolution
5. Security and performance

## Dialects

Use JSON Schema 2020-12 for standalone schemas unless the target ecosystem requires another dialect. Declare `$schema` and stable `$id` values. In OpenAPI, follow the exact OAS schema dialect and tooling support.

## Object modeling

- Define required properties deliberately.
- Set `additionalProperties` explicitly.
- Bound strings, arrays, numbers, and nesting.
- Use `dependentRequired` and conditional schemas only when they improve clarity.
- Use `unevaluatedProperties` carefully with composition.
- Avoid using `format` as the only security validation.
- Include descriptions and examples without putting secrets or personal data in them.

## Composition

- `allOf` combines constraints; it is not class inheritance.
- `oneOf` requires exactly one match and can be expensive or ambiguous.
- `anyOf` permits multiple matches; use only when consumers can handle it.
- Discriminators are ecosystem-specific hints; schemas must remain logically valid without them.

## Evolution

Compatible changes commonly include adding optional properties and new enum values when clients tolerate unknown values. Breaking changes include removing/renaming fields, tightening constraints, changing types, adding required fields, or altering nullability.

Keep separate request and response schemas when write/read semantics diverge materially.

## Security and performance

Defend validators against deeply nested data, catastrophic regexes, remote reference fetching, oversized documents, and cyclic references. Pin trusted schema locations and disable arbitrary network resolution in build pipelines.
