# Authority Map

The authority map names the active source of truth for each major plugin topic.

## Authority

- `assets/catalog/authority-map.v1.json` maps each topic to one canonical source.
- `assets/schemas/authority-map.v1.schema.json` defines topic fields.
- `scripts/authority_map.py` validates canonical sources, validators, secondary docs, generated outputs, deprecated surfaces, and manifest claims.

## Topic fields

Each topic must include:

- `topic`
- `canonical_source`
- `validator`
- `owning_role`
- `secondary_docs`
- `generated_outputs`
- `deprecated_surfaces`
- `manifest_claims`

Deprecated surfaces must not be used as canonical sources, secondary docs, or generated outputs.
