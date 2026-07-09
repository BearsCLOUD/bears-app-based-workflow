# Code property graph

The code property graph records machine-extracted code facts for governed Bears files.

Fact rules:
- Python facts come from `ast` parsing.
- JSON facts come from parsed schema/catalog packets.
- Extracted facts start as `candidate` with `extraction_validated=true`.
- Stale source hashes invalidate stored derived facts.
- LLM output cannot create accepted CPG facts directly.

Commands:
- `python3 scripts/code_property_graph.py validate`
- `python3 scripts/code_property_graph.py extract --path scripts/code_property_graph.py --json`
- `python3 scripts/code_property_graph.py build --paths scripts/code_property_graph.py assets/catalog/code-property-graph.v1.json --json`
- `python3 scripts/code_property_graph.py query --selector scripts/code_property_graph.py --json`
- `python3 scripts/code_property_graph.py stale --json`
- `python3 scripts/code_property_graph.py doctor --json`

The workspace semantic graph consumes CPG nodes and edges as compact symbol context for context selection and workflow inference.
